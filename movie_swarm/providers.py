"""Live provider calls for text, picture, and sound.

A picture or audio call is sent only when every one of these is true:

- the command passed ``live=True`` (the ``--live`` flag)
- the generation gate is approved
- the stage split is locked and the estimate fits that line and the film cap
- the provider key is in the environment
- the rate card has a price, or Ron has approved a one-call price override

A text call does not use the generation gate. Offline is still the default.
``--live`` with no writing approval prints a quote and sends nothing. A
recorded writing approval for the run, a price on the rate card, and a worst
case that fits that ceiling, the stage line, and the film cap are what send it.

The same request hash is not sent twice, so a re-run does not pay twice.
Keys are read from the environment and stripped from anything this module
saves or returns.

The engine does not name a film. Model names, endpoints, and prices come
from ``config/model-routing.json`` and ``config/generation-rates.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from movie_swarm.assets import ASSET_ROOT_ENV, load_asset_config, resolve_asset
from movie_swarm.duration import clip_lengths, request_value, seconds_text
from movie_swarm.paths import config_dir
from movie_swarm.http_retry import (
    HttpConnectionError,
    HttpResult,
    HttpStatusError,
    HttpTimeout,
    UrllibTransport,
    send_with_retry,
)
from movie_swarm.line_producer import LineProducer, record_path, writing_booked
from movie_swarm.models import resolve_model
from movie_swarm.money import as_money, money_number
from movie_swarm.rates import generator_rate, load_rate_card, token_dollars, token_prices
from movie_swarm.redact import redact
from movie_swarm.roles import (
    COLOR_MIX_BILLING,
    DAILIES_BILLING,
    DELIVERY_BILLING,
    PHASE2_BILLING,
    SOUND_BILLING,
    TRAILER_BILLING,
)

FAL_QUEUE = "https://queue.fal.run"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ELEVEN_TTS = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVEN_SFX = "https://api.elevenlabs.io/v1/sound-generation"
ELEVEN_MUSIC = "https://api.elevenlabs.io/v1/music"

KEY_FOR = {
    "anthropic": "ANTHROPIC_API_KEY",
    "fal.ai": "FAL_KEY",
    "fal": "FAL_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
}

PRICE_MARK = "price-override:"
ALLOWANCE_MARK = "live-allowance:"


class ProviderFailure(Exception):
    """The provider accepted a request and then failed it."""


class ProviderRejected(ProviderFailure):
    """The provider refused the call and produced nothing."""


_CLIENT_REJECTED = {400, 401, 403, 404, 405, 422}


@dataclass
class CallSettings:
    """Knobs for one live attempt. Tests pass a fake transport and a sleeper.

    ``poll_interval`` is the first pause between fal status checks. ``None``
    reads ``config/providers.json``. ``0`` does not pause, and the loop stops
    after ``max_polls`` checks. That is how the tests stay off the clock.
    ``wait_seconds`` is the total pause budget. ``None`` reads the same file.
    """

    transport: object | None = None
    sleeper: object = time.sleep
    attempts: int = 3
    timeout: float = 60
    poll_interval: float | None = None
    poll_interval_max: float | None = None
    wait_seconds: float | None = None
    progress_every: float | None = None
    max_polls: int | None = None
    progress: object | None = None
    rates_path: str | Path | None = None
    price_override: float | None = None
    providers_path: str | Path | None = None


_POLL_DEFAULTS = {
    "wait_seconds": 600.0,
    "backoff_start_seconds": 5.0,
    "backoff_step_seconds": 5.0,
    "backoff_max_seconds": 15.0,
    "progress_every_seconds": 30.0,
}


def load_provider_config(path: str | Path | None = None) -> dict:
    """Provider timing. A missing or unreadable file uses the coded defaults."""
    file = Path(path) if path else config_dir() / "providers.json"
    if not file.is_file():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def poll_window(settings: CallSettings) -> dict:
    """The fal wait: total seconds, the first pause, the step, and the cap."""
    fal = load_provider_config(settings.providers_path).get("fal") or {}
    if not isinstance(fal, dict):
        fal = {}
    start = _poll_number(settings.poll_interval, fal, "backoff_start_seconds")
    maximum = _poll_number(settings.poll_interval_max, fal, "backoff_max_seconds")
    if maximum < start:
        maximum = start
    step = _poll_number(None, fal, "backoff_step_seconds")
    wait = _poll_number(settings.wait_seconds, fal, "wait_seconds")
    every = _poll_number(settings.progress_every, fal, "progress_every_seconds")
    if settings.max_polls is not None:
        cap = settings.max_polls
    elif start <= 0:
        cap = 40
    else:
        cap = 10000
    return {
        "start": start,
        "maximum": maximum,
        "step": step,
        "wait": wait,
        "every": every,
        "max_polls": cap,
    }


def _poll_number(override, fal: dict, key: str) -> float:
    if override is not None:
        try:
            return float(override)
        except (TypeError, ValueError):
            return _POLL_DEFAULTS[key]
    try:
        number = float(fal.get(key, _POLL_DEFAULTS[key]))
    except (TypeError, ValueError):
        return _POLL_DEFAULTS[key]
    if number <= 0:
        return _POLL_DEFAULTS[key]
    return number


def billing_stage(role: str) -> str:
    """The locked line a role spends against. No new line is added."""
    return (
        PHASE2_BILLING.get(role)
        or DAILIES_BILLING.get(role)
        or SOUND_BILLING.get(role)
        or COLOR_MIX_BILLING.get(role)
        or DELIVERY_BILLING.get(role)
        or TRAILER_BILLING.get(role)
        or role
    )


def run_test_shot(
    producer: LineProducer,
    shot_id: str,
    *,
    live: bool = False,
    settings: CallSettings | None = None,
    routing_path: str | Path | None = None,
    model: str | None = None,
    tier: str | None = None,
    announce=print,
) -> dict:
    """Prepare exactly one picture call for one shot, and send it only when allowed.

    The result is also written to ``runs/<run-id>/test-shot.json``. That file
    has no key in it. A dry run includes the quote. A live call prints that
    same quote before anything is sent.
    """
    settings = settings or CallSettings()
    folder = producer.production_dir
    from movie_swarm.continuity import enforce_prompt, load_prop_lock
    from movie_swarm.generation import load_shots
    from movie_swarm.shot_model import format_shot_quote, resolve_shot_model, unwired_note

    if model or tier:
        resolve_shot_model(
            folder,
            model=model,
            tier=tier,
            routing_path=routing_path,
            rates_path=settings.rates_path,
        )
    shots, _source = load_shots(folder)
    match = [shot for shot in shots if shot.get("shot_id") == shot_id]
    if len(match) != 1:
        result = _stopped(
            "refused",
            f"Shot {shot_id} was not found. Nothing was sent.",
            shot_id=shot_id,
        )
        _write_test_record(producer, result)
        return result
    shot = match[0]
    lock = load_prop_lock(folder)
    enforced = enforce_prompt(shot.get("prompt") or "", shot.get("props") or [], lock)
    if enforced.blocked:
        joined = "; ".join(enforced.blocked)
        result = _stopped(
            "refused",
            f"This prompt would not be sent. It contains a forbidden phrase: {joined}. Nothing was sent.",
            shot_id=shot_id,
        )
        _write_test_record(producer, result)
        return result
    choice = resolve_shot_model(
        folder,
        model=model,
        tier=tier,
        shot_id=shot_id,
        scene=shot.get("scene_id") or None,
        routing_path=routing_path,
        rates_path=settings.rates_path,
    )
    quote = redact(format_shot_quote(producer, shot, choice, settings.rates_path))
    if live and announce is not None:
        announce(quote)
    result = run_provider_call(
        producer,
        live=live,
        kind="video",
        stage="production",
        provider=choice["provider"],
        model=choice["model"],
        prompt=enforced.prompt,
        duration_seconds=shot.get("duration_seconds"),
        shot_id=shot_id,
        aspect_ratio=_aspect_ratio(folder),
        settings=settings,
        label=shot_id,
    )
    if not live:
        extra = ""
        if not choice["wired"]:
            extra = "\n" + unwired_note(choice["model"], settings.rates_path, routing_path)
        result["message"] = redact(result["message"].rstrip() + "\n" + quote + extra)
    result["quote"] = quote
    result["model"] = choice["model"]
    result["tier"] = choice["tier"]
    _write_test_record(producer, result)
    return result


def run_provider_call(
    producer: LineProducer,
    *,
    live: bool,
    kind: str,
    stage: str,
    provider: str,
    model: str,
    prompt: str,
    settings: CallSettings,
    duration_seconds: float | None = None,
    shot_id: str | None = None,
    cue_id: str | None = None,
    voice_id: str | None = None,
    role: str | None = None,
    purpose: str | None = None,
    system: str | None = None,
    max_tokens: int | None = None,
    aspect_ratio: str | None = None,
    label: str = "",
) -> dict:
    """The shared gate. Returns a result dict. Does not raise for a refusal."""
    label = label or shot_id or cue_id or f"{role or kind}/{purpose or kind}"
    if not live:
        return _stopped(
            "offline",
            "Offline is the default. Pass --live to send this call. Nothing was sent.",
            shot_id=shot_id,
            cue_id=cue_id,
        )
    text_estimate = None
    if kind == "text":
        max_tokens = int(max_tokens or 4000)
        stopped, text_estimate = _writing_preflight(
            producer,
            stage=stage,
            model=model,
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            role=role,
            purpose=purpose,
            label=label,
            rates_path=settings.rates_path,
            shot_id=shot_id,
            cue_id=cue_id,
        )
        if stopped is not None:
            return stopped
    else:
        gate = producer.paid_generation_block()
        if gate is not None:
            return _stopped("refused", gate.message, shot_id=shot_id, cue_id=cue_id)

        allocations = producer.record["stage_allocations"]
        if allocations.get("status") != "approved":
            return _stopped(
                "refused",
                "The stage split is not locked, so this call has no stage line to check. Nothing was sent.",
                shot_id=shot_id,
                cue_id=cue_id,
            )
        if stage not in (allocations.get("split") or {}):
            return _stopped(
                "refused",
                f"The locked split has no {stage} line. Nothing was sent.",
                shot_id=shot_id,
                cue_id=cue_id,
            )

    provider_name = _provider_name(kind, provider, model, settings.rates_path)
    key_var = KEY_FOR.get(provider_name)
    if not key_var:
        return _stopped(
            "refused",
            f"No key is configured for provider {provider_name or '(unset)'}. Nothing was sent.",
            shot_id=shot_id,
            cue_id=cue_id,
        )
    key = os.environ.get(key_var, "").strip()
    if not key:
        return _stopped(
            "refused",
            f"{key_var} is not set. Nothing was sent.",
            shot_id=shot_id,
            cue_id=cue_id,
        )

    row = generator_rate(load_rate_card(settings.rates_path), model) if model else None
    endpoint = _endpoint(kind, model, row, voice_id)
    if endpoint is None:
        if kind == "video":
            from movie_swarm.shot_model import unwired_note

            message = unwired_note(model or "", settings.rates_path)
        else:
            message = f"No provider endpoint is configured for {model or '(unset)'}. Nothing was sent."
        return _stopped(
            "refused",
            message,
            shot_id=shot_id,
            cue_id=cue_id,
        )
    if _needs_voice(kind, purpose) and not (voice_id or "").strip():
        return _stopped(
            "refused",
            "This dialogue cue has no voice id. Add voice_id on the sound prompt. Nothing was sent.",
            shot_id=shot_id,
            cue_id=cue_id,
        )

    if kind == "text":
        estimate, billed, price_note = text_estimate, None, ""
    else:
        estimate, billed, price_note = _estimate(model, duration_seconds, settings.rates_path)
    if kind == "video" and row is not None:
        refusal = _video_request_refusal(model, row, duration_seconds)
        if refusal is not None:
            return _stopped("refused", refusal, shot_id=shot_id, cue_id=cue_id)
    request_hash = _request_hash(
        {
            "kind": kind,
            "stage": stage,
            "provider": provider_name,
            "model": model,
            "endpoint": endpoint,
            "prompt": prompt,
            "system": system or "",
            "billed_seconds": None if billed is None else str(billed),
            "duration_seconds": None if duration_seconds is None else str(as_money(duration_seconds)),
            "shot_id": shot_id or "",
            "cue_id": cue_id or "",
            "voice_id": voice_id or "",
            "role": role or "",
            "purpose": purpose or "",
            "max_tokens": max_tokens or 0,
            "aspect_ratio": aspect_ratio or "",
        }
    )

    cache = _load_cache(producer)
    cached = (cache.get("calls") or {}).get(request_hash) or {}
    status = cached.get("status")
    if status in {"settled", "replayed"}:
        return _replay(producer, stage, request_hash, cached, shot_id, cue_id, estimate)
    if status == "failed":
        message = (
            f"This request already failed at the provider ({request_hash[:12]}). "
            "It was not sent again. The estimate stays booked. The pipeline is still at this stage."
        )
        producer.hold_for_review(message)
        return _stopped(
            "failed", message, shot_id=shot_id, cue_id=cue_id, request_hash=request_hash,
            estimate_usd=cached.get("estimate_usd", estimate),
        )
    if status in {"unknown", "sending"}:
        message = (
            f"This request may already have been sent ({request_hash[:12]}). "
            "It was not sent again, so it cannot be charged twice. "
            "The estimate stays booked. The pipeline is still at this stage."
        )
        producer.hold_for_review(message)
        return _stopped(
            "failed", message, shot_id=shot_id, cue_id=cue_id, request_hash=request_hash,
            estimate_usd=cached.get("estimate_usd", estimate),
        )

    override_id = None
    continuing = status in {"reserved", "submitted"}
    if estimate is None and not continuing:
        priced, override_id, refusal = _resolve_override(
            producer,
            stage,
            request_hash,
            model,
            settings.price_override,
            price_note,
            shot_id=shot_id,
            cue_id=cue_id,
        )
        if refusal is not None:
            return refusal
        estimate = priced
    if estimate is None:
        estimate = as_money(cached.get("estimate_usd") or 0)

    allowance = None
    if not continuing:
        allowance = _find_mark(producer, f"{ALLOWANCE_MARK}{request_hash}", approved_only=True)
        if allowance is not None and as_money(allowance["amount_usd"]) != as_money(estimate):
            allowance = None
        if allowance is None:
            block = producer._block_reason(
                stage,
                estimate,
                books_money=False,
                description=f"{ALLOWANCE_MARK}{request_hash} {model}",
                crew_gates=False,
            )
            if block is not None:
                return _stopped("refused", block.message, shot_id=shot_id, cue_id=cue_id, request_hash=request_hash)

    entry_id = cached.get("entry_id") if continuing else None
    if entry_id is None:
        description = (
            f"Reserved estimate ${money_number(estimate):.2f} for {label}. "
            f"Waiting on the provider. Request {request_hash[:12]}."
        )
        producer._book(stage, estimate, "generation", description, override_id)
        entry_id = producer.record["ledger"][-1]["entry_id"]
        reserved = {
            "estimate_usd": money_number(estimate),
            "actual_usd": None,
            "actual_source": "estimate",
            "request_hash": request_hash,
            "call_phase": "reserved",
        }
        if kind == "text":
            reserved["writing"] = True
        producer.annotate_ledger(entry_id, **reserved)
        cached = {
            "request_hash": request_hash,
            "status": "reserved",
            "entry_id": entry_id,
            "estimate_usd": money_number(estimate),
            "actual_usd": None,
            "model": model,
            "shot_id": shot_id,
            "cue_id": cue_id,
            "output": None,
            "text": None,
            "provider_request_id": None,
            "endpoint": endpoint,
            "purpose": purpose or "",
            "max_tokens": int(max_tokens or 0),
        }
        cache.setdefault("calls", {})[request_hash] = cached
        _save_cache(producer, cache)

    provider_request_id = cached.get("provider_request_id")
    if status != "submitted":
        cached["status"] = "sending"
        cache["calls"][request_hash] = cached
        _save_cache(producer, cache)
        try:
            provider_request_id, early, queue_urls = _submit(
                kind,
                endpoint,
                key,
                provider_name,
                model,
                prompt,
                billed if billed is not None else duration_seconds,
                voice_id,
                system,
                max_tokens,
                aspect_ratio,
                row,
                purpose,
                settings,
            )
        except HttpTimeout as exc:
            return _keep(
                producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, "unknown",
                f"The provider did not answer before the timeout. {exc} "
                "The estimate stays booked because the request may have been accepted. "
                "It was not sent again. The pipeline is still at this stage.",
            )
        except HttpConnectionError as exc:
            return _release(
                producer, cache, cached, entry_id, request_hash, shot_id, cue_id,
                f"The provider could not be reached. {exc} Nothing was booked. "
                "The booked estimate was released. The original entry stays on the ledger. "
                "The pipeline is still at this stage.",
            )
        except HttpStatusError as exc:
            if exc.status in _CLIENT_REJECTED:
                return _release(
                    producer, cache, cached, entry_id, request_hash, shot_id, cue_id,
                    f"The provider rejected the request. {exc} "
                    "The booked estimate was released. Nothing was produced. The pipeline is still at this stage.",
                )
            return _keep(
                producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, "unknown",
                f"{exc} The estimate stays booked because the provider may have accepted the call. "
                "It was not sent again. The pipeline is still at this stage.",
            )
        except ProviderRejected as exc:
            return _release(
                producer, cache, cached, entry_id, request_hash, shot_id, cue_id,
                f"{exc} The booked estimate was released. The pipeline is still at this stage.",
            )
        except ProviderFailure as exc:
            return _keep(
                producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, "unknown",
                f"{exc} The estimate stays booked. It was not sent again. The pipeline is still at this stage.",
            )
        if queue_urls.get("status_url"):
            cached["status_url"] = queue_urls["status_url"]
        if queue_urls.get("response_url"):
            cached["response_url"] = queue_urls["response_url"]
        if provider_request_id:
            cached["provider_request_id"] = provider_request_id
            cached["status"] = "submitted"
            cache["calls"][request_hash] = cached
            _save_cache(producer, cache)
        if early is not None:
            return _finish(
                producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id,
                label, kind, early, override_id, allowance, settings, model,
            )
    try:
        payload = (
            _poll_fal(
                endpoint,
                key,
                provider_request_id,
                settings,
                status_url=cached.get("status_url"),
                response_url=cached.get("response_url"),
            )
            if kind == "video"
            else None
        )
    except HttpTimeout as exc:
        cached["status"] = "submitted"
        cache["calls"][request_hash] = cached
        _save_cache(producer, cache)
        message = (
            f"The provider is still working ({request_hash[:12]}). {exc} "
            "The estimate stays booked. A re-run checks the same request and does not send a new one. "
            "The pipeline is still at this stage."
        )
        producer.hold_for_review(message)
        return _stopped(
            "failed", message, shot_id=shot_id, cue_id=cue_id,
            request_hash=request_hash, estimate_usd=estimate,
        )
    except ProviderRejected as exc:
        return _release(
            producer, cache, cached, entry_id, request_hash, shot_id, cue_id,
            f"The provider did not finish the request. {exc} "
            "The booked estimate was released. The pipeline is still at this stage.",
        )
    except HttpStatusError as exc:
        if exc.status in {400, 422}:
            return _release(
                producer, cache, cached, entry_id, request_hash, shot_id, cue_id,
                f"The provider rejected the request. {exc} "
                "The booked estimate was released. Nothing was produced. The pipeline is still at this stage.",
            )
        return _keep(
            producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, "failed",
            f"The provider did not finish the request. {exc} "
            "The estimate stays booked. It was not sent again. The pipeline is still at this stage.",
        )
    except (HttpConnectionError, ProviderFailure) as exc:
        return _keep(
            producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, "failed",
            f"The provider did not finish the request. {exc} "
            "The estimate stays booked. It was not sent again. The pipeline is still at this stage.",
        )
    return _finish(
        producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id,
        label, kind, payload, override_id, allowance, settings, model,
    )


class LiveGenerationClient:
    """Picture client. ``generate`` matches the offline client. It sends only when ``live`` is set."""

    def __init__(self, producer: LineProducer, *, live: bool = True, settings: CallSettings | None = None):
        self.producer = producer
        self.live = live
        self.settings = settings or CallSettings()

    def generate(self, request: dict) -> dict:
        result = run_provider_call(
            self.producer,
            live=self.live,
            kind="video",
            stage="production",
            provider="fal.ai",
            model=str(request.get("model") or ""),
            prompt=str(request.get("prompt") or ""),
            duration_seconds=request.get("duration_seconds"),
            shot_id=request.get("shot_id"),
            aspect_ratio=_aspect_ratio(self.producer.production_dir),
            settings=self.settings,
            label=str(request.get("shot_id") or "shot"),
        )
        return _as_generate_response(result)


class LiveSoundClient:
    """Sound client. Same ``generate`` shape as the offline sound client."""

    def __init__(self, producer: LineProducer, *, live: bool = True, settings: CallSettings | None = None):
        self.producer = producer
        self.live = live
        self.settings = settings or CallSettings()

    def generate(self, request: dict) -> dict:
        cue_type = str(request.get("type") or "sfx")
        result = run_provider_call(
            self.producer,
            live=self.live,
            kind="audio",
            stage="sound-designer",
            provider="elevenlabs",
            model=str(request.get("model") or ""),
            prompt=str(request.get("prompt") or ""),
            duration_seconds=request.get("duration_seconds"),
            cue_id=request.get("cue_id"),
            voice_id=request.get("voice_id"),
            purpose=cue_type,
            settings=self.settings,
            label=str(request.get("cue_id") or cue_type),
        )
        return _as_generate_response(result)


class GuardedLLM:
    """Anthropic text calls through the same gate. Used only when ``--live`` is set."""

    def __init__(
        self,
        production_dir: str | Path,
        run_id: str,
        *,
        price_override: float | None = None,
        settings: CallSettings | None = None,
    ):
        self.production_dir = Path(production_dir)
        self.run_id = run_id
        self.settings = settings or CallSettings(price_override=price_override)
        if price_override is not None:
            self.settings.price_override = price_override

    def complete(self, *, role: str, purpose: str, system: str, user: str, max_tokens: int = 4000) -> str:
        """Send one text call. The quote counts this system string and this user string.

        Do not pass a shortened copy. The ceiling check uses that same worst case.
        """
        from movie_swarm.llm import LLMError, WritingQuote

        try:
            producer = LineProducer.open(self.production_dir, self.run_id)
        except Exception as exc:
            raise LLMError(redact(str(exc))) from exc
        chosen = resolve_model(role, purpose=purpose)
        result = run_provider_call(
            producer,
            live=True,
            kind="text",
            stage=billing_stage(role),
            provider="anthropic",
            model=str(chosen.get("model") or ""),
            prompt=user,
            system=system,
            role=role,
            purpose=purpose,
            max_tokens=max_tokens,
            settings=self.settings,
            label=f"{role}/{purpose}",
        )
        if result["status"] == "quoted":
            raise WritingQuote(result["message"])
        if result["status"] != "generated" and result["status"] != "replayed":
            raise LLMError(result["message"])
        from movie_swarm.llm import ModelReply

        output_tokens = result.get("output_tokens")
        max_tokens_sent = result.get("max_tokens")
        return ModelReply(
            result.get("text") or "",
            stop_reason=result.get("stop_reason"),
            output_tokens=None if output_tokens is None else int(output_tokens),
            max_tokens=None if not max_tokens_sent else int(max_tokens_sent),
        )


def llm_for_command(
    production: str | Path,
    run_id: str,
    *,
    live: bool,
    offline: bool,
    price_override: float | None = None,
):
    """The model client for a command. Offline unless ``--live`` is set."""
    if offline or not live:
        return None
    try:
        LineProducer.open(production, run_id)
    except Exception:
        LineProducer.start(production, run_id=run_id)
    return GuardedLLM(production, run_id, price_override=price_override)


def _submit(
    kind, endpoint, key, provider_name, model, prompt, duration, voice_id,
    system, max_tokens, aspect_ratio, row, purpose, settings: CallSettings,
):
    """Send the request.

    Returns ``(provider_request_id or None, finished payload or None, queue urls)``.
    A fal picture call sends the input fields at the top of the JSON body.
    """
    transport = settings.transport or UrllibTransport()
    if kind == "video":
        allowed = row.get("allowed_resolutions") if row else None
        resolution = row.get("resolution") if row else None
        if allowed and resolution and resolution not in allowed:
            names = ", ".join(str(item) for item in allowed)
            raise ProviderRejected(
                f"{model} does not accept {resolution}. Allowed resolutions: {names}. Nothing was produced."
            )
        payload = {"prompt": prompt}
        if duration is not None and row is not None:
            lengths, _notes = clip_lengths(duration, row)
            if len(lengths) == 1:
                payload["duration"] = request_value(lengths[0], row)
            else:
                payload["duration"] = request_value(duration, row)
        elif duration is not None:
            payload["duration"] = _seconds_text(duration)
        if resolution:
            payload["resolution"] = resolution
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if row and row.get("with_audio") is True:
            payload["generate_audio"] = True
        response = send_with_retry(
            transport,
            method="POST",
            url=f"{FAL_QUEUE}/{endpoint}",
            headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
            body=payload,
            timeout=settings.timeout,
            attempts=settings.attempts,
            sleeper=settings.sleeper,
            retry_timeout=False,
        )
        data = _json_object(response.body)
        request_id = str(data.get("request_id") or "")
        if not request_id:
            raise ProviderRejected("The provider did not return a request id. Nothing was produced.")
        return request_id, None, {
            "status_url": _fal_queue_url(data.get("status_url")),
            "response_url": _fal_queue_url(data.get("response_url")),
        }
    if kind == "audio":
        audio_kind = purpose if purpose in {"dialogue", "music", "sfx", "foley", "ambience"} else "sfx"
        if audio_kind == "dialogue":
            url = f"{ELEVEN_TTS}/{voice_id}"
            body = {"text": prompt, "model_id": model}
        elif audio_kind == "music":
            url = ELEVEN_MUSIC
            body = {"prompt": prompt}
            if duration is not None:
                body["music_length_ms"] = int(as_money(duration) * 1000)
        else:
            url = ELEVEN_SFX
            body = {"text": prompt, "model_id": model}
            if duration is not None:
                body["duration_seconds"] = float(as_money(duration))
        response = send_with_retry(
            transport,
            method="POST",
            url=url,
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            body=body,
            timeout=settings.timeout,
            attempts=settings.attempts,
            sleeper=settings.sleeper,
            retry_timeout=False,
        )
        return None, {"audio": response.body, "cost_usd": None}, {}
    response = send_with_retry(
        transport,
        method="POST",
        url=ANTHROPIC_URL,
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        body={
            "model": model,
            "max_tokens": max_tokens or 4000,
            "system": system or "",
            "messages": [{"role": "user", "content": prompt or ""}],
        },
        timeout=max(settings.timeout, 120),
        attempts=settings.attempts,
        sleeper=settings.sleeper,
        retry_timeout=False,
    )
    return None, _json_object(response.body), {}


def _poll_fal(
    endpoint,
    key,
    request_id,
    settings: CallSettings,
    status_url=None,
    response_url=None,
) -> dict:
    if not request_id:
        raise ProviderRejected("The picture call has no provider request id to check. Nothing was produced.")
    transport = settings.transport or UrllibTransport()
    headers = {"Authorization": f"Key {key}"}
    status_url = _fal_queue_url(status_url) or _fal_status_url(endpoint, request_id)
    result_url = _fal_queue_url(response_url) or _fal_result_url(endpoint, request_id)
    window = poll_window(settings)
    waited = 0.0
    interval = window["start"]
    last_progress = 0.0
    for _poll in range(window["max_polls"]):
        response = send_with_retry(
            transport,
            method="GET",
            url=status_url,
            headers=headers,
            body=None,
            timeout=settings.timeout,
            attempts=settings.attempts,
            sleeper=settings.sleeper,
            retry_timeout=True,
        )
        data = _json_object(response.body)
        state = str(data.get("status") or "")
        newer = _fal_queue_url(data.get("response_url"))
        if newer:
            result_url = newer
        problem = _provider_error_message(data)
        if state == "COMPLETED":
            finished = send_with_retry(
                transport,
                method="GET",
                url=result_url,
                headers=headers,
                body=None,
                timeout=settings.timeout,
                attempts=settings.attempts,
                sleeper=settings.sleeper,
                retry_timeout=True,
            )
            payload = _json_object(finished.body)
            rejected = _provider_error_message(payload)
            if rejected:
                raise ProviderRejected(
                    f"The provider rejected the request. {rejected} Nothing was produced."
                )
            return payload
        if state in {"FAILED", "ERROR"}:
            if problem:
                raise ProviderRejected(
                    f"The provider rejected the request. {problem} Nothing was produced."
                )
            detail = data.get("error") or state
            raise ProviderFailure(redact(str(detail)))
        if interval <= 0:
            continue
        remaining = window["wait"] - waited
        if remaining <= 0:
            break
        sleep_for = min(interval, remaining)
        settings.sleeper(sleep_for)
        waited += sleep_for
        if window["every"] > 0 and waited - last_progress >= window["every"] - 1e-9:
            _announce_wait(settings, waited, state, data)
            last_progress = waited
        if waited >= window["wait"] - 1e-9:
            break
        interval = min(window["maximum"], interval + window["step"])
    raise HttpTimeout("The provider did not finish before the poll limit.")


def _announce_wait(settings: CallSettings, waited: float, state: str, data: dict) -> None:
    """One short line while fal is still working. No key, no request body."""
    status = state or "UNKNOWN"
    line = f"Waiting {int(waited)}s. fal status {status}."
    position = data.get("queue_position")
    if position is not None and position != "":
        line = f"{line} Queue position {position}."
    printer = settings.progress or print
    printer(line)


def _finish(
    producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id,
    label, kind, payload, override_id, allowance, settings: CallSettings, model: str = "",
) -> dict:
    actual = _reported_cost(payload)
    source = "estimate" if actual is None else "provider"
    usage_note = ""
    if kind == "text":
        usage = _usage_dollars(payload, model, settings.rates_path)
        if usage is None:
            actual = None
            source = "estimate"
        else:
            actual, usage_note = usage
            source = "usage"
    output = None
    text = None
    try:
        if kind == "video":
            media = _download_media(payload, settings)
            relative = _relative_name("video", label, request_hash, ".mp4")
            _write_bytes(producer, relative, media)
            output = relative
        elif kind == "audio":
            media = payload.get("audio") if isinstance(payload, dict) else None
            if not isinstance(media, bytes) or not media:
                raise ProviderFailure("The provider returned no audio.")
            relative = _relative_name("audio", label, request_hash, ".mp3")
            _write_bytes(producer, relative, media)
            output = relative
        else:
            text = redact(_anthropic_text(payload))
            if not text:
                raise ProviderFailure("The model returned no text.")
            relative = _relative_name("text", label, request_hash, ".txt")
            _write_bytes(producer, relative, text.encode("utf-8"))
            output = relative
            limit = _output_limit(payload, cached.get("max_tokens"))
            cached["stop_reason"] = limit["stop_reason"]
            cached["output_tokens"] = limit["output_tokens"]
            cached["truncated"] = limit["truncated"]
    except (HttpTimeout, HttpConnectionError, HttpStatusError, ProviderFailure) as exc:
        return _keep(
            producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, "failed",
            f"The provider answered, but the file was not saved. {exc} "
            "The estimate stays booked. It was not sent again. The pipeline is still at this stage.",
        )

    booked = estimate if actual is None else actual
    if source == "usage":
        description = (
            f"Settled. Estimate ${money_number(estimate):.4f}. "
            f"Booked ${money_number(actual):.4f} from the reported token usage. "
            f"{usage_note} Request {request_hash[:12]}."
        )
    elif actual is None:
        description = (
            f"Settled. Estimate ${money_number(estimate):.2f}. "
            "The provider did not report a dollar amount, so the booked amount stays the estimate. "
            "The ledger records this as an estimate, not a measured charge. "
            f"Request {request_hash[:12]}."
        )
    else:
        description = (
            f"Settled. Estimate ${money_number(estimate):.2f}. "
            f"The provider reported ${money_number(actual):.2f}. "
            f"Request {request_hash[:12]}."
        )
    if kind == "text" and source != "usage":
        usage = _token_note(payload)
        if usage:
            description = f"{description} {usage}"
    producer.set_ledger_amount(entry_id, booked, description)
    producer.annotate_ledger(
        entry_id,
        estimate_usd=money_number(estimate),
        actual_usd=None if actual is None else money_number(actual),
        actual_source=source,
        request_hash=request_hash,
        call_phase="settled",
    )
    if override_id:
        producer.consume_request(override_id)
    if allowance is not None:
        producer.consume_request(allowance["request_id"])
    cached.update(
        {
            "status": "settled",
            "entry_id": entry_id,
            "estimate_usd": money_number(estimate),
            "actual_usd": None if actual is None else money_number(actual),
            "actual_source": source,
            "output": output,
            "text": text,
        }
    )
    cache.setdefault("calls", {})[request_hash] = cached
    _save_cache(producer, cache)
    if source == "usage":
        money_line = (
            f"Booked ${money_number(actual):.4f} from the reported token usage. "
        )
    elif actual is not None:
        money_line = f"The provider reported ${money_number(actual):.2f}. "
    else:
        money_line = (
            "The provider did not report a dollar amount. The booked amount stays the estimate. "
            "The ledger records this as an estimate, not a measured charge. "
        )
    shown = money_number(estimate)
    estimate_text = f"${shown:.4f}" if kind == "text" else f"${shown:.2f}"
    message = (
        f"The provider returned {label}. Estimate {estimate_text}. "
        + money_line
        + f"The file is {output}, under { _location_name() }. The pipeline stays at this stage."
    )
    if kind == "text" and cached.get("truncated"):
        message += " " + _limit_sentence(cached)
    producer.run.data["notes"] = redact(message)
    producer.run.save()
    return _stopped(
        "generated",
        message,
        shot_id=shot_id,
        cue_id=cue_id,
        request_hash=request_hash,
        estimate_usd=estimate,
        actual_usd=actual,
        output=output,
        text=text,
        cost_usd=booked,
        stop_reason=cached.get("stop_reason"),
        output_tokens=cached.get("output_tokens"),
        max_tokens=cached.get("max_tokens"),
        truncated=bool(cached.get("truncated")),
    )


def _download_media(payload: dict, settings: CallSettings) -> bytes:
    url = _media_url(payload)
    if not url:
        raise ProviderFailure("The provider finished and did not name a file.")
    transport = settings.transport or UrllibTransport()
    response = send_with_retry(
        transport,
        method="GET",
        url=url,
        headers={},
        body=None,
        timeout=settings.timeout,
        attempts=settings.attempts,
        sleeper=settings.sleeper,
        retry_timeout=True,
    )
    if not response.body:
        raise ProviderFailure("The provider file was empty.")
    return response.body


def _keep(producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, phase, message):
    message = redact(message)
    cached["status"] = phase
    cached["entry_id"] = entry_id
    cache.setdefault("calls", {})[request_hash] = cached
    _save_cache(producer, cache)
    producer.annotate_ledger(
        entry_id,
        call_phase="unknown" if phase == "unknown" else "settled" if phase == "failed" else phase,
        estimate_usd=money_number(estimate),
        actual_usd=None,
        request_hash=request_hash,
        description=message,
    )
    producer.hold_for_review(message)
    return _stopped(
        "failed",
        message,
        shot_id=shot_id,
        cue_id=cue_id,
        request_hash=request_hash,
        estimate_usd=estimate,
        cost_usd=estimate,
    )


def _release(producer, cache, cached, entry_id, request_hash, shot_id, cue_id, message):
    message = redact(message)
    from movie_swarm.line_producer import LineProducerError

    try:
        producer.release_booked_estimate(entry_id, by="line-producer", note=message)
    except LineProducerError:
        producer.annotate_ledger(
            entry_id,
            call_phase="released",
            actual_usd=0,
            request_hash=request_hash,
        )
    cached["status"] = "released"
    cached["entry_id"] = entry_id
    cache.setdefault("calls", {})[request_hash] = cached
    _save_cache(producer, cache)
    producer.hold_for_review(message)
    return _stopped(
        "failed",
        message,
        shot_id=shot_id,
        cue_id=cue_id,
        request_hash=request_hash,
        estimate_usd=0,
        cost_usd=0,
    )


def _replay(producer, stage, request_hash, cached, shot_id, cue_id, estimate) -> dict:
    producer.note_dry_run(
        stage,
        0,
        f"Replayed cached call {request_hash[:12]}. Not charged again.",
    )
    replay_id = producer.record["ledger"][-1]["entry_id"]
    producer.annotate_ledger(
        replay_id,
        request_hash=request_hash,
        call_phase="replayed",
        estimate_usd=cached.get("estimate_usd"),
        actual_usd=cached.get("actual_usd"),
    )
    message = (
        f"This request was already sent ({request_hash[:12]}). "
        "The cached file was used. Nothing was charged again."
    )
    if cached.get("output"):
        message += f" The file is {cached['output']}."
    if cached.get("truncated"):
        message += " " + _limit_sentence(cached)
    return _stopped(
        "replayed",
        message,
        shot_id=shot_id,
        cue_id=cue_id,
        request_hash=request_hash,
        estimate_usd=cached.get("estimate_usd", estimate),
        actual_usd=cached.get("actual_usd"),
        output=cached.get("output"),
        text=cached.get("text"),
        cost_usd=0,
        stop_reason=cached.get("stop_reason"),
        output_tokens=cached.get("output_tokens"),
        max_tokens=cached.get("max_tokens"),
        truncated=bool(cached.get("truncated")),
    )


def _resolve_override(producer, stage, request_hash, model, price_override, price_note, *, shot_id, cue_id):
    mark = f"{PRICE_MARK}{request_hash}"
    existing = _find_mark(producer, mark, approved_only=False)
    if existing and existing["status"] == "approved" and not existing.get("consumed"):
        if price_override is not None and as_money(existing["amount_usd"]) != as_money(price_override):
            message = (
                f"{existing['request_id']} approved ${money_number(existing['amount_usd']):.2f} "
                f"for this call. The command asked for ${money_number(price_override):.2f}. Nothing was sent."
            )
            return None, None, _stopped("refused", message, shot_id=shot_id, cue_id=cue_id, request_hash=request_hash)
        return as_money(existing["amount_usd"]), existing["request_id"], None
    if price_override is None:
        message = (
            f"{price_note} The estimate is unknown. This is not a price of zero. "
            "Pass --price-override with the dollars for this one call, then approve that request. "
            "Nothing was sent."
        )
        return None, None, _stopped("refused", message, shot_id=shot_id, cue_id=cue_id, request_hash=request_hash)
    if existing and existing["status"] == "pending":
        message = (
            f"{existing['reason']} Approval request {existing['request_id']} is waiting for Ron."
        )
        return None, None, _stopped("refused", message, shot_id=shot_id, cue_id=cue_id, request_hash=request_hash)
    reason = (
        f"The rate card has no published price for {model}. "
        f"This request asks Ron to approve ${money_number(price_override):.2f} for this one call. "
        "Nothing was sent."
    )
    request = producer._new_request(
        "extra-spend",
        stage,
        as_money(price_override),
        reason,
        books_money=False,
        description=f"{mark} {model}",
    )
    producer.hold_for_review(reason)
    message = f"{reason} Approval request {request['request_id']} is waiting for Ron."
    return None, None, _stopped("refused", message, shot_id=shot_id, cue_id=cue_id, request_hash=request_hash)


def _find_mark(producer, mark: str, *, approved_only: bool) -> dict | None:
    found = None
    for request in producer.record["requests"]:
        if mark not in (request.get("description") or ""):
            continue
        if request.get("consumed"):
            continue
        if approved_only and request["status"] != "approved":
            continue
        found = request
    return found


# English is often about 4 characters per token. The paid treatment calls were
# denser than that. The Opus final pass used about 2.5 characters per input
# token, so character count / 4 priced the call below what was booked.
# The quote divides by 3, adds 25 percent, adds a fixed overhead, and rounds up.
# The ceiling check uses this figure, not the old character count / 4.
_INPUT_CHARS_PER_TOKEN = 3
_INPUT_SAFETY_NUMERATOR = 5
_INPUT_SAFETY_DENOMINATOR = 4
_INPUT_TOKEN_OVERHEAD = 200


def estimate_input_tokens(char_count: int) -> int:
    """A high input-token estimate from a character count.

    ``ceil(characters / 3 * 1.25) + 200``. Zero characters still count the
    overhead, so a short call is not quoted as free.
    """
    chars = max(int(char_count or 0), 0)
    if chars == 0:
        return _INPUT_TOKEN_OVERHEAD
    divisor = _INPUT_CHARS_PER_TOKEN * _INPUT_SAFETY_DENOMINATOR
    scaled = (chars * _INPUT_SAFETY_NUMERATOR + divisor - 1) // divisor
    return scaled + _INPUT_TOKEN_OVERHEAD


def quote_text_call(
    model: str,
    system: str,
    prompt: str,
    max_tokens: int | None,
    rates_path=None,
    label: str = "",
) -> dict:
    """The quote for one text call. Nothing is sent.

    Input tokens are a conservative estimate of ``system`` plus ``prompt``.
    That prompt is the full user message the call would send, including the
    screenplay. A longer screenplay raises this worst case, and the ceiling
    check uses it. The line says that number is an estimate. The worst case
    prices that estimate plus every output token the call is allowed to write.
    """
    output_tokens = int(max_tokens or 4000)
    input_tokens = estimate_input_tokens(len(system or "") + len(prompt or ""))
    name = model or "(unset)"
    shown = label or name
    row = generator_rate(load_rate_card(rates_path), model) if model else None
    prices = token_prices(row, input_tokens)
    worst = None if prices is None else token_dollars(input_tokens, output_tokens, prices[0], prices[1])
    text = (
        f"Writing quote for {shown}. Model: {name}. "
        f"Input tokens: {input_tokens} (estimate, character count / 3, plus 25 percent, plus {_INPUT_TOKEN_OVERHEAD} tokens). "
        f"Max output tokens: {output_tokens}."
    )
    if worst is None:
        text += f" The rate card has no published price for {name}."
    else:
        text += f" Worst case: ${money_number(worst):.4f} from the rate card."
    return {
        "model": name,
        "input_tokens_estimate": input_tokens,
        "max_output_tokens": output_tokens,
        "worst_case_usd": None if worst is None else money_number(worst),
        "text": text,
        "worst": worst,
    }


def _writing_preflight(
    producer: LineProducer,
    *,
    stage: str,
    model: str,
    prompt: str,
    system: str | None,
    max_tokens: int | None,
    role: str | None,
    purpose: str | None,
    label: str,
    rates_path,
    shot_id,
    cue_id,
):
    """Quote, approval, and the stage line. Returns ``(stop or None, estimate)``.

    A call that was already reserved keeps going, so a retry does not turn
    into a second quote. A new call with no writing approval stops here.
    """
    quote = quote_text_call(model, system or "", prompt, max_tokens, rates_path, label)
    request_hash = _request_hash(
        {
            "kind": "text",
            "stage": stage,
            "provider": "anthropic",
            "model": model,
            "endpoint": ANTHROPIC_URL,
            "prompt": prompt,
            "system": system or "",
            "billed_seconds": None,
            "duration_seconds": None,
            "shot_id": shot_id or "",
            "cue_id": cue_id or "",
            "voice_id": "",
            "role": role or "",
            "purpose": purpose or "",
            "max_tokens": max_tokens or 0,
            "aspect_ratio": "",
        }
    )
    cached = (_load_cache(producer).get("calls") or {}).get(request_hash) or {}
    if cached.get("status") in {"settled", "replayed", "failed", "unknown", "sending", "submitted", "reserved"}:
        estimate = quote["worst"]
        if estimate is None:
            estimate = as_money(cached.get("estimate_usd") or 0)
        return None, estimate

    if quote["worst"] is None:
        return _stop_writing(
            "refused", quote["text"], "", shot_id=shot_id, cue_id=cue_id, request_hash=request_hash,
        ), None

    worst = quote["worst"]
    approval = producer.record.get("writing_approval") or {}
    if approval.get("status") != "approved":
        return _stop_writing(
            "quoted",
            quote["text"],
            "Record a writing approval for this run before a text call is sent.",
            shot_id=shot_id,
            cue_id=cue_id,
            request_hash=request_hash,
            estimate_usd=worst,
        ), None

    room = as_money(approval.get("max_usd") or 0) - writing_booked(producer.record)
    if room < 0:
        room = as_money(0)
    if as_money(worst) > room:
        return _stop_writing(
            "refused",
            quote["text"],
            (
                f"The writing approval has ${money_number(room):.4f} left "
                f"of ${money_number(approval.get('max_usd') or 0):.4f}."
            ),
            shot_id=shot_id,
            cue_id=cue_id,
            request_hash=request_hash,
            estimate_usd=worst,
        ), None

    line_stop = _writing_line_stop(
        producer, stage, worst, quote["text"], shot_id=shot_id, cue_id=cue_id, request_hash=request_hash,
    )
    if line_stop is not None:
        return line_stop, None
    return None, worst


def _writing_line_stop(producer, stage, worst, quote, *, shot_id, cue_id, request_hash):
    """The run's stage line when it is locked. Otherwise budget.json has to exist.

    The film cap and the budget.json line are checked again with the other
    spends, once a key is present. This stop is only the missing line.
    """
    from movie_swarm.budget import load_film_budget

    allocations = producer.record.get("stage_allocations") or {}
    locked = allocations.get("status") == "approved"
    split = allocations.get("split") or {}
    has_budget = load_film_budget(producer.production_dir) is not None
    if locked:
        if stage not in split:
            return _stop_writing(
                "refused",
                quote,
                f"The locked split has no {stage} line.",
                shot_id=shot_id,
                cue_id=cue_id,
                request_hash=request_hash,
                estimate_usd=worst,
            )
        spent = as_money(producer.stage_spent(stage))
        ceiling = as_money(split[stage])
        if spent + as_money(worst) > ceiling:
            return _stop_writing(
                "refused",
                quote,
                (
                    f"This ${money_number(worst):.4f} {stage} writing call would put that line at "
                    f"${money_number(spent + as_money(worst)):.4f}, "
                    f"over its ${money_number(ceiling):.4f} stage line."
                ),
                shot_id=shot_id,
                cue_id=cue_id,
                request_hash=request_hash,
                estimate_usd=worst,
            )
        return None
    if not has_budget:
        return _stop_writing(
            "refused",
            quote,
            (
                f"This film has no budget.json, and this run has no locked {stage} line, "
                "so the call has no line to check."
            ),
            shot_id=shot_id,
            cue_id=cue_id,
            request_hash=request_hash,
            estimate_usd=worst,
        )
    return None


def _stop_writing(status, quote, reason, **kwargs):
    message = quote if not reason else f"{quote} {reason}"
    if "Nothing was sent." not in message:
        message = f"{message} Nothing was sent."
    return _stopped(status, message, **kwargs)


def _usage_dollars(payload, model: str, rates_path):
    """The dollar amount from reported tokens, or None when usage is missing."""
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None
    if usage.get("input_tokens") is None or usage.get("output_tokens") is None:
        return None
    try:
        input_tokens = int(usage["input_tokens"])
        output_tokens = int(usage["output_tokens"])
    except (TypeError, ValueError):
        return None
    if input_tokens < 0 or output_tokens < 0:
        return None
    row = generator_rate(load_rate_card(rates_path), model) if model else None
    prices = token_prices(row, input_tokens)
    if prices is None:
        return None
    amount = token_dollars(input_tokens, output_tokens, prices[0], prices[1])
    note = (
        f"The provider reported {input_tokens} input tokens and {output_tokens} output tokens."
    )
    return amount, note


def _estimate(model: str, duration, rates_path):
    if not model:
        return None, None, "No model is configured for this call."
    card = load_rate_card(rates_path)
    row = generator_rate(card, model)
    if row is None or row.get("usd_per_second") in (None, ""):
        return None, None, f"The rate card has no published price for {model}."
    if duration is None:
        return None, None, f"The rate card prices {model} per second, and this call has no length."
    from movie_swarm.generation import _pass_cost

    priced = _pass_cost({"duration_seconds": duration}, model, card)
    if not priced["priced"]:
        return None, None, f"The rate card has no published price for {model}."
    return priced["usd"], priced["billed"], ""


def _provider_name(kind: str, provider: str, model: str, rates_path) -> str:
    if kind == "text":
        return "anthropic"
    if kind == "audio":
        return "elevenlabs"
    row = generator_rate(load_rate_card(rates_path), model) if model else None
    if row and row.get("provider"):
        return str(row["provider"])
    return provider or "fal.ai"


def _endpoint(kind: str, model: str, row: dict | None, voice_id: str | None) -> str | None:
    if kind == "text":
        return ANTHROPIC_URL
    if kind == "audio":
        return ELEVEN_SFX
    if row and row.get("endpoint"):
        return str(row["endpoint"])
    return None


def _needs_voice(kind: str, purpose: str | None) -> bool:
    return kind == "audio" and (purpose or "") == "dialogue"


def _request_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _cache_path(producer: LineProducer) -> Path:
    return record_path(producer.production_dir, producer.run.data["run_id"]).with_name("provider-cache.json")


def _load_cache(producer: LineProducer) -> dict:
    path = _cache_path(producer)
    if not path.is_file():
        return {"calls": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"calls": {}}
    if not isinstance(data, dict):
        return {"calls": {}}
    data.setdefault("calls", {})
    return data


def _save_cache(producer: LineProducer, cache: dict) -> None:
    path = _cache_path(producer)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(json.dumps(_plain(cache), indent=2) + "\n"), encoding="utf-8")


def _write_test_record(producer: LineProducer, result: dict) -> None:
    path = record_path(producer.production_dir, producer.run.data["run_id"]).with_name("test-shot.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = {
        "status": result.get("status"),
        "shot_id": result.get("shot_id"),
        "message": result.get("message"),
        "estimate_usd": result.get("estimate_usd"),
        "actual_usd": result.get("actual_usd"),
        "output": result.get("output"),
        "request_hash": result.get("request_hash"),
        "location": result.get("location") or _location_name(),
        "sent": result.get("sent"),
    }
    path.write_text(redact(json.dumps(_plain(kept), indent=2) + "\n"), encoding="utf-8")


def _write_bytes(producer: LineProducer, relative: str, payload: bytes) -> None:
    path = resolve_asset(producer.production_dir, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _relative_name(kind: str, label: str, request_hash: str, suffix: str) -> str:
    safe = re.sub(r"[^a-z0-9-]+", "-", str(label).lower()).strip("-") or "clip"
    return f"live/{kind}/{safe}-{request_hash[:12]}{suffix}"


def _location_name() -> str:
    if os.environ.get(ASSET_ROOT_ENV, "").strip():
        return ASSET_ROOT_ENV
    try:
        config = load_asset_config()
    except Exception:
        return "production-folder"
    if config.get("asset_root"):
        return "asset_root"
    return "production-folder"


def _aspect_ratio(production_dir: Path) -> str | None:
    path = Path(production_dir) / "treatment" / "treatment.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    ratio = (data.get("deliverables") or {}).get("aspect_ratio")
    text = str(ratio).strip() if ratio else ""
    return text or None


def _media_url(payload: dict) -> str | None:
    if not isinstance(payload, dict):
        return None
    video = payload.get("video")
    if isinstance(video, dict) and video.get("url"):
        return str(video["url"])
    if isinstance(video, str) and video.startswith("http"):
        return video
    for key in ("video_url", "url", "audio_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    images = payload.get("images")
    if isinstance(images, list) and images and isinstance(images[0], dict) and images[0].get("url"):
        return str(images[0]["url"])
    return None


def _reported_cost(payload):
    if not isinstance(payload, dict):
        return None
    for key in ("cost_usd", "cost"):
        if payload.get(key) not in (None, ""):
            try:
                return as_money(payload[key])
            except ValueError:
                return None
    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and metrics.get("cost") not in (None, ""):
        try:
            return as_money(metrics["cost"])
        except ValueError:
            return None
    return None


def _anthropic_text(payload: dict) -> str:
    parts = []
    for block in payload.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
    return "\n".join(parts).strip()


def _token_note(payload: dict) -> str:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return ""
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is None and output_tokens is None:
        return ""
    return (
        f"The provider reported {input_tokens} input tokens and {output_tokens} output tokens. "
        "That is not a dollar amount."
    )


def _json_object(body: bytes) -> dict:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProviderFailure("The provider response was not JSON.") from exc
    if not isinstance(data, dict):
        raise ProviderFailure("The provider response was not a JSON object.")
    return data


def _as_generate_response(result: dict) -> dict:
    return {
        "status": result["status"],
        "cost_usd": result.get("cost_usd") or 0,
        "shot_id": result.get("shot_id"),
        "cue_id": result.get("cue_id"),
        "detail": result["message"],
        "clip_ref": result.get("output"),
        "estimate_usd": result.get("estimate_usd"),
        "actual_usd": result.get("actual_usd"),
        "request_hash": result.get("request_hash"),
        "text": result.get("text"),
    }


def _stopped(
    status: str,
    message: str,
    *,
    shot_id=None,
    cue_id=None,
    request_hash=None,
    estimate_usd=None,
    actual_usd=None,
    output=None,
    text=None,
    cost_usd=None,
    stop_reason=None,
    output_tokens=None,
    max_tokens=None,
    truncated=False,
) -> dict:
    sent = status in {"generated", "replayed"}
    return {
        "status": status,
        "sent": sent,
        "message": redact(message),
        "shot_id": shot_id,
        "cue_id": cue_id,
        "request_hash": request_hash,
        "estimate_usd": None if estimate_usd is None else money_number(estimate_usd),
        "actual_usd": None if actual_usd is None else money_number(actual_usd),
        "output": output,
        "text": redact(text) if text else None,
        "cost_usd": 0 if cost_usd is None else money_number(cost_usd),
        "location": _location_name(),
        "stop_reason": stop_reason,
        "output_tokens": output_tokens,
        "max_tokens": max_tokens,
        "truncated": bool(truncated),
    }


def _output_limit(payload: dict, max_tokens) -> dict:
    """Whether the provider stopped because the reply filled its output cap."""
    stop = payload.get("stop_reason") if isinstance(payload, dict) else None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    output = None
    if isinstance(usage, dict) and usage.get("output_tokens") is not None:
        try:
            output = int(usage["output_tokens"])
        except (TypeError, ValueError):
            output = None
    limit = None
    if max_tokens not in (None, ""):
        try:
            limit = int(max_tokens)
        except (TypeError, ValueError):
            limit = None
    hit = isinstance(stop, str) and stop.lower() in {"max_tokens", "length"}
    if output is not None and limit is not None and output >= limit:
        hit = True
    return {"stop_reason": stop if isinstance(stop, str) else None, "output_tokens": output, "truncated": hit}


def _limit_sentence(cached: dict) -> str:
    stop = cached.get("stop_reason") or "max_tokens"
    output = cached.get("output_tokens")
    limit = cached.get("max_tokens")
    sentence = f"The reply hit the output limit (stop_reason {stop})."
    if output is not None and limit:
        sentence += f" Output tokens {output} reached the max of {limit}."
    return sentence


def _plain(value):
    if isinstance(value, Decimal):
        return money_number(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _video_request_refusal(model: str, row: dict, duration) -> str | None:
    """Stop one call that the model's published duration or resolution cannot carry."""
    allowed = row.get("allowed_resolutions")
    resolution = row.get("resolution")
    if allowed and resolution and resolution not in allowed:
        names = ", ".join(str(item) for item in allowed)
        return f"{model} does not accept {resolution}. Allowed resolutions: {names}. Nothing was sent."
    if duration is None:
        return None
    lengths, _notes = clip_lengths(duration, row)
    if len(lengths) <= 1:
        return None
    shown = " and ".join(f"{seconds_text(piece)} seconds" for piece in lengths)
    cap = seconds_text(row["max_seconds"]) if row.get("max_seconds") not in (None, "") else "its maximum"
    return (
        f"This shot is {seconds_text(duration)} seconds. {row.get('label') or model} accepts at most "
        f"{cap} seconds in one call, so the quote is {shown}. One test shot sends one call. Nothing was sent."
    )


def _fal_queue_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith(f"{FAL_QUEUE}/"):
        return text
    return None


def _fal_app_id(endpoint: str) -> str:
    """The owner and the app. fal status URLs use those two segments, not the full endpoint."""
    parts = [part for part in str(endpoint).strip("/").split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return "/".join(parts)


def _fal_status_url(endpoint: str, request_id: str) -> str:
    return f"{FAL_QUEUE}/{_fal_app_id(endpoint)}/requests/{request_id}/status"


def _fal_result_url(endpoint: str, request_id: str) -> str:
    return f"{FAL_QUEUE}/{_fal_app_id(endpoint)}/requests/{request_id}"


def _provider_error_message(data: dict) -> str | None:
    if not isinstance(data, dict):
        return None
    if "detail" in data:
        return _detail_message(data.get("detail"))
    error = data.get("error")
    if error in (None, ""):
        return None
    if isinstance(error, dict):
        text = error.get("message") or error.get("type") or error
        return redact(str(text))
    return redact(str(error))


def _detail_message(detail) -> str:
    if isinstance(detail, str):
        return redact(detail) or "The provider rejected the request."
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = [
                    str(part)
                    for part in item.get("loc") or []
                    if str(part) not in {"body", "input"}
                ]
                msg = str(item.get("msg") or "rejected")
                where = ".".join(loc)
                parts.append(f"{where}: {msg}" if where else msg)
            else:
                parts.append(str(item))
        text = "; ".join(part for part in parts if part) or "The provider rejected the request."
        return redact(text)
    if detail in (None, ""):
        return "The provider rejected the request."
    return redact(str(detail))


def _seconds_text(value) -> str:
    number = as_money(value)
    if number == number.to_integral():
        return str(int(number))
    return format(number.normalize(), "f")
