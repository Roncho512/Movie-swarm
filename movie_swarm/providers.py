"""Live provider calls for text, picture, and sound.

A real call is sent only when every one of these is true:

- the command passed ``live=True`` (the ``--live`` flag)
- the generation gate is approved
- the stage split is locked and the estimate fits that line and the film cap
- the provider key is in the environment
- the rate card has a price, or Ron has approved a one-call price override

Offline is the default. The same request hash is not sent twice, so a re-run
does not pay twice. Keys are read from the environment and stripped from
anything this module saves or returns.

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
from movie_swarm.http_retry import (
    HttpConnectionError,
    HttpResult,
    HttpStatusError,
    HttpTimeout,
    UrllibTransport,
    send_with_retry,
)
from movie_swarm.line_producer import LineProducer, record_path
from movie_swarm.models import resolve_model
from movie_swarm.money import as_money, money_number
from movie_swarm.rates import generator_rate, load_rate_card
from movie_swarm.redact import redact
from movie_swarm.roles import (
    COLOR_MIX_BILLING,
    DAILIES_BILLING,
    DELIVERY_BILLING,
    PHASE2_BILLING,
    SOUND_BILLING,
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
    """Knobs for one live attempt. Tests pass a fake transport and a sleeper."""

    transport: object | None = None
    sleeper: object = time.sleep
    attempts: int = 3
    timeout: float = 60
    poll_interval: float = 2.0
    max_polls: int = 40
    rates_path: str | Path | None = None
    price_override: float | None = None


def billing_stage(role: str) -> str:
    """The locked line a role spends against. No new line is added."""
    return (
        PHASE2_BILLING.get(role)
        or DAILIES_BILLING.get(role)
        or SOUND_BILLING.get(role)
        or COLOR_MIX_BILLING.get(role)
        or DELIVERY_BILLING.get(role)
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
        producer.annotate_ledger(
            entry_id,
            estimate_usd=money_number(estimate),
            actual_usd=None,
            request_hash=request_hash,
            call_phase="reserved",
        )
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
                label, kind, early, override_id, allowance, settings,
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
        label, kind, payload, override_id, allowance, settings,
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
        from movie_swarm.llm import LLMError

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
        if result["status"] != "generated" and result["status"] != "replayed":
            raise LLMError(result["message"])
        return result.get("text") or ""


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
    for _poll in range(settings.max_polls):
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
        settings.sleeper(settings.poll_interval)
    raise HttpTimeout("The provider did not finish before the poll limit.")


def _finish(
    producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id,
    label, kind, payload, override_id, allowance, settings: CallSettings,
) -> dict:
    actual = _reported_cost(payload)
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
    except (HttpTimeout, HttpConnectionError, HttpStatusError, ProviderFailure) as exc:
        return _keep(
            producer, cache, cached, entry_id, request_hash, estimate, shot_id, cue_id, "failed",
            f"The provider answered, but the file was not saved. {exc} "
            "The estimate stays booked. It was not sent again. The pipeline is still at this stage.",
        )

    booked = estimate if actual is None else actual
    if actual is None:
        description = (
            f"Settled. Estimate ${money_number(estimate):.2f}. "
            "The provider did not report a dollar amount, so the booked amount stays the estimate. "
            f"Request {request_hash[:12]}."
        )
    else:
        description = (
            f"Settled. Estimate ${money_number(estimate):.2f}. "
            f"The provider reported ${money_number(actual):.2f}. "
            f"Request {request_hash[:12]}."
        )
    if kind == "text":
        usage = _token_note(payload)
        if usage:
            description = f"{description} {usage}"
    producer.set_ledger_amount(entry_id, booked, description)
    producer.annotate_ledger(
        entry_id,
        estimate_usd=money_number(estimate),
        actual_usd=None if actual is None else money_number(actual),
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
            "output": output,
            "text": text,
        }
    )
    cache.setdefault("calls", {})[request_hash] = cached
    _save_cache(producer, cache)
    message = (
        f"The provider returned {label}. Estimate ${money_number(estimate):.2f}. "
        + (
            f"The provider reported ${money_number(actual):.2f}. "
            if actual is not None
            else "The provider did not report a dollar amount. The booked amount stays the estimate. "
        )
        + f"The file is {output}, under { _location_name() }. The pipeline stays at this stage."
    )
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
    }


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
