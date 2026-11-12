"""Sound Designer and Composer: spot a cue sheet onto a picture-locked cut.

Dialogue, effects, foley, ambience, and music are timed to the edit. The
words, the tempo, and the props come from the production folder. This module
does not know which film it is reading. It does not call a paid model.
ffmpeg renders placeholder stems when it is installed. When it is not, the
cue sheet is still written. JSON is the source of truth.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from movie_swarm.continuity import load_prop_lock
from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.models import ModelRoutingError, resolve_model
from movie_swarm.money import as_money, money_number
from movie_swarm.rates import RateCardError, generator_rate, load_rate_card, usd_per_second


class SoundError(Exception):
    """The cue sheet cannot be built. The message says what is missing."""


# Half a second. A production file can set a different tolerance.
_SYNC_TOLERANCE_SECONDS = 0.5
_SAMPLE_RATE = 44100
_STEMS = (
    ("dialogue", {"dialogue"}, "sine", 440),
    ("effects", {"sfx", "foley", "ambience"}, "noise", 180),
    ("music", {"music"}, "sine", 220),
)
_TYPE_BY_ASSET = {
    "dialogue": "dialogue",
    "sfx": "sfx",
    "foley": "foley",
    "ambient": "ambience",
    "ambience": "ambience",
    "music": "music",
}


class OfflineSoundClient:
    """The client this build uses. It records nothing on a provider."""

    def generate(self, request: dict) -> dict:
        return {
            "status": "not-sent",
            "cost_usd": 0,
            "cue_id": request.get("cue_id"),
            "detail": "No live provider is connected. The call was not sent. No audio was made.",
        }


def spot_production(
    production_dir: str | Path,
    *,
    picture_lock_approved: bool = False,
    allocations: dict | None = None,
    stage_spent: float = 0,
    rates_path: str | Path | None = None,
) -> dict:
    """Spot the cue sheet. Nothing is spent.

    ``picture_lock_approved`` is the Line Producer's edit gate. Sound does
    not run while that gate is closed.
    """
    if not picture_lock_approved:
        raise SoundError(
            "The edit gate is still closed. Ron has not approved picture lock, so sound was not spotted."
        )
    folder = Path(production_dir)
    edl, cut_source = _load_cut(folder)
    prompts, prompts_source = _load_json(folder / "audio" / "sound-prompts.json")
    brief, brief_source = _load_json(folder / "audio" / "score-brief.json")
    lock = load_prop_lock(folder)
    props_source = _props_source(folder)
    events = [event for event in edl.get("events") or [] if isinstance(event, dict) and event.get("shot_id")]
    by_shot = {str(event["shot_id"]): event for event in events}
    runtime = _number(edl.get("runtime_seconds")) or 0.0
    tolerance = _tolerance(prompts, brief)
    props_by_shot = _props_by_shot(folder)
    silence_shots = _silence_shots(brief)

    cues: list[dict] = []
    unplaced: list[str] = []
    missing: list[dict] = []
    _spot_prompts(folder, prompts, by_shot, silence_shots, cues, unplaced, missing)
    _spot_props(lock, props_by_shot, by_shot, cues)
    _spot_score(brief, by_shot, silence_shots, cues, missing)

    sync = _sync_findings(cues, missing, by_shot, events, runtime, tolerance)
    continuity = _continuity_findings(cues, props_by_shot, lock)
    ready = bool(events) and all(item["status"] == "pass" for item in sync + continuity)
    budget = _price(cues, allocations or {}, stage_spent, rates_path)
    render = _render_stems(folder, cues, runtime)
    return {
        "version": "1.0.0",
        "production_id": folder.name,
        "kind": "cue-sheet",
        "created_at": _now(),
        "cut_runtime_seconds": round(float(runtime), 3),
        "sync_tolerance_seconds": round(float(tolerance), 3),
        "ready_for_sound_approval": ready,
        "sound_approved": False,
        "spent_usd": 0,
        "cut_source": cut_source,
        "sources": {
            "edit": cut_source,
            "sound_prompts": prompts_source,
            "score_brief": brief_source,
            "props": props_source,
        },
        "cues": cues,
        "sync": sync,
        "continuity": continuity,
        "unplaced": unplaced,
        "budget": budget,
        "render": render,
        "models": {
            "sound-designer": _admin_model("sound-designer"),
            "composer": _admin_model("composer"),
        },
        "draft_method": "offline-deterministic",
    }


def request_paid_sound(cues: list[dict], *, client, gate_open: bool) -> dict:
    """Hand generated cues to ``client`` only when the generation gate is open.

    A closed gate returns before ``client.generate`` is called. Library and
    silence cues are not a paid call. The result does not book money.
    """
    if not gate_open:
        return {
            "status": "paused",
            "called": False,
            "cue_count": 0,
            "spent_usd": 0,
            "message": "The generation gate is closed. No provider was called.",
        }
    if client is None:
        client = OfflineSoundClient()
    results = []
    for cue in cues:
        if cue.get("source") != "generated":
            continue
        request = {
            "cue_id": cue.get("cue_id"),
            "type": cue.get("type"),
            "prompt": cue.get("prompt") or "",
            "duration_seconds": _number(cue.get("end_seconds")) - _number(cue.get("start_seconds"))
            if cue.get("end_seconds") is not None
            else None,
            "model": cue.get("model") or "",
        }
        if cue.get("voice_id"):
            request["voice_id"] = cue.get("voice_id")
        results.append(client.generate(request))
    live_statuses = {"refused", "failed", "generated", "replayed", "offline"}
    if results and all((item or {}).get("status") == "not-sent" for item in results):
        message = "No live provider is connected. The call was not sent. No audio was made."
    elif results and any((item or {}).get("status") in live_statuses for item in results):
        message = " ".join(
            str((item or {}).get("detail") or (item or {}).get("status"))
            for item in results
            if (item or {}).get("status") in live_statuses
        )
    elif results:
        message = "The client was asked. No money was booked. This build does not send a paid sound or music call."
    else:
        message = "No generated cue needed a provider. Nothing was charged."
    spent = as_money(0)
    for item in results:
        if (item or {}).get("status") in {"generated", "failed"}:
            spent += as_money((item or {}).get("cost_usd") or 0)
    return {
        "status": "prepared",
        "called": bool(results),
        "cue_count": len(results),
        "spent_usd": money_number(spent),
        "message": message,
        "results": results,
    }


def render_report(sheet: dict) -> str:
    """The cue sheet as a table a person can read before the sound gate."""
    lines = [
        f"Sound and score for {sheet['production_id']}",
        "",
        "No money was spent. JSON is the cue sheet.",
        "",
        (
            f"The cut is {sheet['cut_runtime_seconds']:.2f}s. "
            f"Sync tolerance is {sheet['sync_tolerance_seconds']:.2f}s."
        ),
        "",
        "| Cue | Type | Start | End | Shots | Source | Role |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not sheet["cues"]:
        lines.append("| | | | | | No cue was spotted. | |")
    for cue in sheet["cues"]:
        shots = ", ".join(cue["shot_ids"])
        lines.append(
            f"| {cue['cue_id']} | {cue['type']} | {cue['start_seconds']:.2f} | "
            f"{cue['end_seconds']:.2f} | {shots} | {cue['source']} | {cue['role']} |"
        )
    lines.extend(["", "Sync:"])
    if not sheet["sync"]:
        lines.append("No cue to check.")
    for item in sheet["sync"]:
        lines.append(f"- {item['cue_id']}: {item['status']}. {item['detail']}")
    lines.extend(["", "Continuity:"])
    if not sheet["continuity"]:
        lines.append("No cue to check.")
    for item in sheet["continuity"]:
        lines.append(f"- {item['cue_id']}: {item['status']}. {item['detail']}")
    if sheet["unplaced"]:
        lines.extend(["", "Not spotted:"])
        for note in sheet["unplaced"]:
            lines.append(f"- {note}")
    budget = sheet["budget"]
    lines.extend(["", "Budget:", budget["note"]])
    render = sheet["render"]
    lines.extend(["", f"Stems: {render['status']}. {render['note']}"])
    if sheet["ready_for_sound_approval"]:
        lines.append(
            "This cue sheet is ready for the sound gate. It is not approved until Ron says so. "
            "Color and mix wait on that approval."
        )
    else:
        lines.append(
            "This cue sheet is not ready for the sound gate. "
            "Color and mix still wait until Ron approves it."
        )
    return "\n".join(lines).rstrip() + "\n"


def write_sound(sheet: dict, production_dir: str | Path) -> tuple[Path, Path]:
    """Write the cue sheet. A flagged sheet is still saved so it can be read."""
    folder = Path(production_dir) / "sound"
    folder.mkdir(parents=True, exist_ok=True)
    data_path = folder / "cue-sheet.json"
    text_path = folder / "cue-sheet.md"
    write_handoff(data_path, sheet, schema="cue-sheet")
    text_path.write_text(render_report(sheet), encoding="utf-8")
    return data_path, text_path


def run_sound(producer, call) -> str:
    """The Director's spot or generate command. It does not spend."""
    production = Path(call.production_dir or producer.production_dir)
    if not producer.gate_is_open("edit"):
        raise SoundError(
            "The edit gate is still closed. Ron has not approved picture lock, so sound was not spotted."
        )
    from movie_swarm.budget import lines_for_check

    filmed = lines_for_check(producer.production_dir)
    allocations = {}
    record = producer.record["stage_allocations"]
    if filmed is not None:
        allocations = filmed
    elif record.get("status") == "approved":
        allocations = dict(record.get("split") or {})
    sheet = spot_production(
        production,
        picture_lock_approved=True,
        allocations=allocations,
        stage_spent=producer.stage_spent("sound-designer"),
    )
    _data_path, text_path = write_sound(sheet, production)
    producer.ensure_artifact("cue-sheet", "sound/cue-sheet.json", "cue-sheet.schema.json")
    producer.ensure_artifact("cue-sheet-notes", "sound/cue-sheet.md")
    render = sheet["render"]
    if render["status"] == "rendered":
        for name in ("dialogue", "effects", "music", "mix"):
            if render.get(name):
                producer.ensure_artifact(f"sound-{name}", render[name])
    role, credit = _credit_for(call.agent)
    _ensure_credit(producer, role, credit)
    paid_note = ""
    if call.command == "generate":
        if not producer.gate_is_open("generation"):
            raise SoundError("The generation gate is closed. No provider was called.")
        client = call.client
        if client is None and getattr(call, "live", False):
            from movie_swarm.providers import CallSettings, LiveSoundClient

            client = LiveSoundClient(
                producer,
                live=True,
                settings=CallSettings(price_override=getattr(call, "price_override", None)),
            )
        paid = request_paid_sound(sheet["cues"], client=client, gate_open=True)
        paid_note = "\n" + paid["message"]
    if producer.gate_decision("sound") == "approved":
        producer.run.data["notes"] = (
            "Sound was spotted again after Ron approved the sound gate. "
            "The approval still stands until Ron rejects it. Color and mix wait on that approval."
        )
        producer.run.save()
    else:
        producer.set_stage("sound", "waiting-for-review")
        producer.run.data["notes"] = (
            "The cue sheet is waiting on Ron. Color and mix do not run until Ron approves the sound gate."
        )
        producer.run.save()
    return render_report(sheet) + paid_note + f"\nWrote {text_path}."


def _spot_prompts(folder, prompts, by_shot, silence_shots, cues, unplaced, missing) -> None:
    if not prompts:
        return
    for key in ("dialogue", "sfx", "music"):
        for asset in prompts.get(key) or []:
            if isinstance(asset, dict):
                _spot_asset(folder, asset, by_shot, silence_shots, cues, unplaced, missing)
    for asset in prompts.get("foley") or []:
        if isinstance(asset, dict):
            _spot_asset(folder, asset, by_shot, silence_shots, cues, unplaced, missing)
    for asset in prompts.get("ambience") or []:
        if isinstance(asset, dict):
            _spot_asset(folder, asset, by_shot, silence_shots, cues, unplaced, missing)


def _spot_asset(folder, asset, by_shot, silence_shots, cues, unplaced, missing) -> None:
    asset_id = _slug(str(asset.get("asset_id") or "cue"))
    cue_type = _TYPE_BY_ASSET.get(str(asset.get("asset_type") or "").casefold())
    if cue_type is None:
        cue_type = "sfx"
    shots = [str(shot) for shot in asset.get("assigned_shots") or [] if str(shot).strip()]
    if not shots:
        unplaced.append(f"{asset_id} names no shot, so it was not spotted.")
        return
    prompt = str(asset.get("prompt") or "")
    description = str(asset.get("text") or asset.get("layer_notes") or prompt)
    source = _source(folder, asset)
    prop_id = asset.get("prop_id")
    prop_id = str(prop_id) if prop_id else None
    role = "composer" if cue_type == "music" else "sound-designer"
    model = "" if source != "generated" else _paid_model(cue_type)
    offset = asset.get("start_offset_seconds")
    shifted = offset is not None and offset != ""
    for shot_id in shots:
        if cue_type == "music" and shot_id in silence_shots:
            unplaced.append(
                f"{asset_id} is assigned to {shot_id}, and the score brief leaves that shot silent."
            )
            continue
        event = by_shot.get(shot_id)
        cue_id = _slug(f"{asset_id}-{shot_id}")
        if event is None:
            missing.append(
                {
                    "cue_id": cue_id,
                    "shot_id": shot_id,
                    "detail": (
                        f"{asset_id} is assigned to {shot_id}, and that shot is not in the cut. "
                        "The cue was not placed."
                    ),
                }
            )
            continue
        start, end = _window(event, asset, shifted)
        cues.append(
            _cue(
                cue_id=cue_id,
                cue_type=cue_type,
                start=start,
                end=end,
                shot_ids=[shot_id],
                prompt=prompt,
                description=description,
                source=source,
                prop_id=prop_id,
                role=role,
                model=model,
                voice_id=asset.get("voice_id"),
            )
        )


def _spot_props(lock, props_by_shot, by_shot, cues) -> None:
    if not lock:
        return
    seen = {cue["cue_id"] for cue in cues}
    for prop in lock.get("props") or []:
        if not isinstance(prop, dict):
            continue
        sound = prop.get("sound")
        if not isinstance(sound, dict) or not str(sound.get("prompt") or "").strip():
            continue
        prop_id = str(prop.get("prop_id") or "")
        if not prop_id:
            continue
        source = str(sound.get("source") or "generated").casefold()
        if source not in {"generated", "library", "silence"}:
            source = "generated"
        prompt = str(sound.get("prompt") or "")
        for shot_id, event in by_shot.items():
            if not _prop_in_shot(prop, props_by_shot.get(shot_id, [])):
                continue
            cue_id = _slug(f"prop-{prop_id}-{shot_id}")
            if cue_id in seen:
                continue
            seen.add(cue_id)
            cues.append(
                _cue(
                    cue_id=cue_id,
                    cue_type="foley",
                    start=float(event["record_in"]),
                    end=float(event["record_out"]),
                    shot_ids=[shot_id],
                    prompt=prompt,
                    description=prompt,
                    source=source,
                    prop_id=prop_id,
                    role="sound-designer",
                    model="" if source != "generated" else _paid_model("foley"),
                )
            )


def _spot_score(brief, by_shot, silence_shots, cues, missing) -> None:
    if not brief:
        return
    for shot_id in sorted(silence_shots):
        if shot_id not in by_shot:
            missing.append(
                {
                    "cue_id": _slug(f"silence-{shot_id}"),
                    "shot_id": shot_id,
                    "detail": (
                        f"The score brief leaves {shot_id} silent, and that shot is not in the cut. "
                        "The cue was not placed."
                    ),
                }
            )
            continue
        event = by_shot[shot_id]
        reason = silence_shots[shot_id] or "The score brief leaves this shot silent."
        cues.append(
            _cue(
                cue_id=_slug(f"silence-{shot_id}"),
                cue_type="music",
                start=float(event["record_in"]),
                end=float(event["record_out"]),
                shot_ids=[shot_id],
                prompt=reason,
                description=reason,
                source="silence",
                prop_id=None,
                role="composer",
                model="",
            )
        )
    for motif in brief.get("motifs") or []:
        if not isinstance(motif, dict):
            continue
        motif_id = _slug(str(motif.get("motif_id") or "motif"))
        description = str(motif.get("description") or "")
        prompt = _music_prompt(brief, description)
        source = str(motif.get("source") or "generated").casefold()
        if source not in {"generated", "library", "silence"}:
            source = "generated"
        for shot_id in motif.get("shot_ids") or []:
            shot_id = str(shot_id)
            if shot_id in silence_shots:
                continue
            cue_id = _slug(f"motif-{motif_id}-{shot_id}")
            event = by_shot.get(shot_id)
            if event is None:
                missing.append(
                    {
                        "cue_id": cue_id,
                        "shot_id": shot_id,
                        "detail": (
                            f"Motif {motif_id} names {shot_id}, and that shot is not in the cut. "
                            "The cue was not placed."
                        ),
                    }
                )
                continue
            cues.append(
                _cue(
                    cue_id=cue_id,
                    cue_type="music",
                    start=float(event["record_in"]),
                    end=float(event["record_out"]),
                    shot_ids=[shot_id],
                    prompt=prompt,
                    description=description or prompt,
                    source=source,
                    prop_id=None,
                    role="composer",
                    model="" if source != "generated" else _paid_model("music"),
                )
            )


def _window(event: dict, asset: dict, shifted: bool) -> tuple[float, float]:
    record_in = float(event["record_in"])
    record_out = float(event["record_out"])
    if not shifted:
        return round(record_in, 3), round(record_out, 3)
    offset = _number(asset.get("start_offset_seconds")) or 0.0
    duration = _number(asset.get("duration"))
    if duration is None or duration <= 0:
        duration = max(0.001, record_out - record_in)
    start = record_in + offset
    end = start + duration
    return round(start, 3), round(end, 3)


def _cue(
    *,
    cue_id,
    cue_type,
    start,
    end,
    shot_ids,
    prompt,
    description,
    source,
    prop_id,
    role,
    model,
    voice_id=None,
) -> dict:
    cue = {
        "cue_id": cue_id,
        "type": cue_type,
        "start_seconds": round(float(start), 3),
        "end_seconds": round(float(end), 3),
        "shot_ids": list(shot_ids),
        "prompt": prompt,
        "description": description,
        "source": source,
        "prop_id": prop_id,
        "role": role,
        "model": model,
    }
    if voice_id:
        cue["voice_id"] = str(voice_id)
    return cue


def _sync_findings(cues, missing, by_shot, events, runtime, tolerance) -> list[dict]:
    findings = []
    for item in missing:
        findings.append(
            {
                "cue_id": item["cue_id"],
                "status": "fail",
                "kind": "missing-shot",
                "detail": item["detail"],
            }
        )
    for cue in cues:
        reasons = []
        kind = "clear"
        if cue["start_seconds"] < -0.0005 or cue["end_seconds"] > float(runtime) + 0.0005:
            reasons.append(
                f"The cue runs {cue['start_seconds']:.2f}s to {cue['end_seconds']:.2f}s. "
                f"The cut runs 0.00s to {float(runtime):.2f}s."
            )
            kind = "outside-cut"
        if cue["end_seconds"] <= cue["start_seconds"]:
            reasons.append("The cue has no length inside the cut.")
            kind = "outside-cut"
        absent = [shot_id for shot_id in cue["shot_ids"] if shot_id not in by_shot]
        if absent:
            reasons.append("The cue names a shot that is not in the cut: " + ", ".join(absent) + ".")
            kind = "missing-shot"
        if cue["type"] in {"sfx", "foley"} and not absent:
            span_in = min(float(by_shot[shot_id]["record_in"]) for shot_id in cue["shot_ids"])
            span_out = max(float(by_shot[shot_id]["record_out"]) for shot_id in cue["shot_ids"])
            early = cue["start_seconds"] < span_in - tolerance - 0.0005
            late = cue["end_seconds"] > span_out + tolerance + 0.0005
            if early or late:
                reasons.append(
                    f"The effect is outside the sync tolerance of {tolerance:.2f}s. "
                    f"The shot runs {span_in:.2f}s to {span_out:.2f}s. "
                    f"The cue runs {cue['start_seconds']:.2f}s to {cue['end_seconds']:.2f}s."
                )
                if kind == "clear":
                    kind = "tolerance"
            between = _shots_between(cue, events, tolerance)
            if between:
                reasons.append("The cue spans a shot it is not linked to: " + ", ".join(between) + ".")
                if kind == "clear":
                    kind = "tolerance"
        if not reasons:
            detail = "The cue stays inside the cut."
            if cue["type"] in {"sfx", "foley"}:
                detail = "The cue stays inside the cut and within the sync tolerance of its shot."
        else:
            detail = " ".join(reasons)
        findings.append(
            {
                "cue_id": cue["cue_id"],
                "status": "fail" if reasons else "pass",
                "kind": kind,
                "detail": detail,
            }
        )
    return findings


def _shots_between(cue: dict, events: list[dict], tolerance: float) -> list[str]:
    """Shots the cue covers, past the sync tolerance, that the cue does not name."""
    linked = set(cue["shot_ids"])
    covered = []
    for event in events:
        shot_id = str(event["shot_id"])
        if shot_id in linked:
            continue
        start = float(event["record_in"])
        end = float(event["record_out"])
        overlap = min(cue["end_seconds"], end) - max(cue["start_seconds"], start)
        if overlap > tolerance + 0.0005:
            covered.append(shot_id)
    return covered


def _continuity_findings(cues, props_by_shot, lock) -> list[dict]:
    findings = []
    props = [prop for prop in (lock or {}).get("props") or [] if isinstance(prop, dict)]
    for cue in cues:
        if cue["source"] == "silence" or not props:
            findings.append(
                {
                    "cue_id": cue["cue_id"],
                    "status": "pass",
                    "kind": "clear",
                    "detail": "No locked prop sound is on this cue.",
                }
            )
            continue
        reasons = []
        named = cue.get("prop_id")
        if named:
            prop = _find_prop(props, named)
            if prop is None:
                reasons.append(f"{named} is not in the prop file, so the cue cannot be matched to a frame.")
            else:
                reasons.extend(_prop_frame_reasons(prop, cue, props_by_shot))
        text = f"{cue.get('prompt') or ''} {cue.get('description') or ''}"
        for prop in props:
            if named and str(prop.get("prop_id") or "") == named:
                continue
            if not _mentions(text, prop):
                continue
            reasons.extend(_prop_frame_reasons(prop, cue, props_by_shot))
        findings.append(
            {
                "cue_id": cue["cue_id"],
                "status": "fail" if reasons else "pass",
                "kind": "prop-sound" if reasons else "clear",
                "detail": " ".join(reasons) if reasons else "No locked prop is heard outside its shots.",
            }
        )
    return findings


def _prop_frame_reasons(prop: dict, cue: dict, props_by_shot: dict) -> list[str]:
    name = str(prop.get("name") or prop.get("prop_id") or "prop")
    reasons = []
    for shot_id in cue["shot_ids"]:
        if _prop_in_shot(prop, props_by_shot.get(shot_id, [])):
            continue
        reasons.append(
            f"The {name} is heard in {shot_id}. The shot list does not put that prop in the frame."
        )
    return reasons


def _price(cues: list[dict], allocations: dict, stage_spent: float, rates_path) -> dict:
    """Quote generated cues from the rate card. A missing rate stays unknown."""
    try:
        card = load_rate_card(rates_path)
    except RateCardError as exc:
        card = {"by_model": {}, "checked_on": "", "error": str(exc)}
    locked = allocations.get("sound-designer") if "sound-designer" in allocations else None
    spent = money_number(stage_spent)
    generated = [cue for cue in cues if cue.get("source") == "generated"]
    checked_on = str(card.get("checked_on") or "")
    when = f" Rates were read on {checked_on}." if checked_on else ""
    line = _line_sentence(locked)
    if not generated:
        return {
            "stage": "sound-designer",
            "locked_usd": money_number(locked) if locked is not None else None,
            "spent_on_stage_usd": spent,
            "estimated_usd": 0,
            "rate_status": "not-charged",
            "within_allocation": None if locked is None else as_money(spent) <= as_money(locked),
            "models_without_a_rate": [],
            "note": (
                "No generated cue needs a provider. Library and silence are not charged. "
                f"{line} Nothing was charged.{when}"
            ).strip(),
        }
    unknown = []
    total = as_money(0)
    quotes = []
    for cue in generated:
        model = str(cue.get("model") or "")
        row = generator_rate(card, model) if model else None
        if not row or row.get("usd_per_second") in (None, ""):
            if model and model not in unknown:
                unknown.append(model)
            elif not model and "(unset)" not in unknown:
                unknown.append("(unset)")
            continue
        seconds = as_money(float(cue["end_seconds"]) - float(cue["start_seconds"]))
        if seconds < 0:
            seconds = as_money(0)
        total += usd_per_second(row) * seconds
        if not any(item["model"] == model for item in quotes):
            quotes.append(row)
    if unknown:
        names = ", ".join(sorted(unknown))
        return {
            "stage": "sound-designer",
            "locked_usd": money_number(locked) if locked is not None else None,
            "spent_on_stage_usd": spent,
            "estimated_usd": None,
            "rate_status": "unknown",
            "within_allocation": None,
            "models_without_a_rate": sorted(unknown),
            "note": (
                f"The rate card has no published price for {names}. "
                "The estimate is unknown. This is not a price of zero. "
                f"{line} Nothing was charged.{when}"
            ).strip(),
        }
    estimated = as_money(total)
    quoted = " ".join(_rate_sentence(row) for row in quotes)
    if locked is None:
        within = None
        fit = "No locked Sound line was on the split, so the quote was not compared with a ceiling."
    else:
        room = as_money(locked) - as_money(spent) - estimated
        within = room >= 0
        if within:
            fit = (
                f"The quote fits the Sound line of ${money_number(locked):.2f}. "
                f"Room left: ${money_number(room):.2f}."
            )
        else:
            fit = (
                f"The quote is over the Sound line of ${money_number(locked):.2f} "
                f"by ${money_number(abs(room)):.2f}."
            )
    return {
        "stage": "sound-designer",
        "locked_usd": money_number(locked) if locked is not None else None,
        "spent_on_stage_usd": spent,
        "estimated_usd": money_number(estimated),
        "rate_status": "priced",
        "within_allocation": within,
        "models_without_a_rate": [],
        "note": f"{quoted} Estimated ${money_number(estimated):.2f}. {fit} {line} Nothing was charged.{when}".strip(),
    }


def _line_sentence(locked) -> str:
    if locked is None:
        return "The Sound line is the sound-designer allocation."
    return f"The Sound line is the sound-designer allocation of ${money_number(locked):.2f}."


def _rate_sentence(row: dict) -> str:
    label = row.get("label") or row.get("model")
    price = row.get("usd_per_second")
    source = row.get("source") or "the rate card"
    quote = row.get("quote") or ""
    text = f"{label} is ${price} per second. Source: {source}."
    if quote:
        text += f" {quote}"
    return text


def _render_stems(folder: Path, cues: list[dict], runtime: float) -> dict:
    empty = {"status": "skipped", "dialogue": None, "effects": None, "music": None, "mix": None}
    if runtime <= 0 or not cues:
        return {
            **empty,
            "note": "The cut has no length to fill, so the stems were not rendered. The cue sheet is still written.",
        }
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            **empty,
            "note": "ffmpeg is not installed, so the stems were not rendered. The cue sheet is still written.",
        }
    work = folder / "sound" / "stem-work"
    stems_dir = folder / "sound" / "stems"
    if work.exists():
        shutil.rmtree(work)
    stems_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    written = {}
    try:
        for name, types, kind, tone in _STEMS:
            audible = [
                cue
                for cue in cues
                if cue["type"] in types and cue["source"] != "silence" and cue["end_seconds"] > cue["start_seconds"]
            ]
            dest = stems_dir / f"{name}.wav"
            _render_stem(ffmpeg, audible, runtime, dest, work / name, kind, tone)
            written[name] = f"sound/stems/{name}.wav"
        mix = stems_dir / "mix-preview.wav"
        _render_mix(
            ffmpeg,
            [stems_dir / "dialogue.wav", stems_dir / "effects.wav", stems_dir / "music.wav"],
            mix,
        )
        written["mix"] = "sound/stems/mix-preview.wav"
    except (OSError, subprocess.TimeoutExpired, SoundError) as exc:
        shutil.rmtree(work, ignore_errors=True)
        return {
            **empty,
            "note": f"ffmpeg could not render the stems. The cue sheet is still written. {exc}",
        }
    shutil.rmtree(work, ignore_errors=True)
    return {
        "status": "rendered",
        "dialogue": written["dialogue"],
        "effects": written["effects"],
        "music": written["music"],
        "mix": written["mix"],
        "note": "Placeholder stems and a temp mix were rendered. They are not a finished mix.",
    }


def _render_stem(ffmpeg, cues, runtime, dest: Path, work: Path, kind: str, tone: float) -> None:
    if not cues:
        _silence(ffmpeg, runtime, dest)
        return
    work.mkdir(parents=True, exist_ok=True)
    inputs = ["-f", "lavfi", "-i", _silence_source(runtime)]
    filters = []
    mix_inputs = ["[0]"]
    for index, cue in enumerate(cues, start=1):
        duration = max(0.05, float(cue["end_seconds"]) - float(cue["start_seconds"]))
        source = _tone_source(kind, tone, duration)
        inputs.extend(["-f", "lavfi", "-i", source])
        delay = max(0, int(round(float(cue["start_seconds"]) * 1000)))
        label = f"[c{index}]"
        filters.append(f"[{index}]adelay={delay}:all=1{label}")
        mix_inputs.append(label)
    count = len(mix_inputs)
    filters.append(
        "".join(mix_inputs) + f"amix=inputs={count}:duration=first:dropout_transition=0:normalize=0[out]"
    )
    command = [
        ffmpeg,
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[out]",
        "-t",
        f"{runtime:.3f}",
        "-ac",
        "1",
        "-ar",
        str(_SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    try:
        _run_ffmpeg(command)
    except SoundError:
        if kind != "noise":
            raise
        _render_stem(ffmpeg, cues, runtime, dest, work, "sine", tone)


def _render_mix(ffmpeg, stems: list[Path], dest: Path) -> None:
    inputs: list[str] = []
    for path in stems:
        inputs.extend(["-i", str(path)])
    _run_ffmpeg(
        [
            ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            "[0][1][2]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0[out]",
            "-map",
            "[out]",
            "-ac",
            "1",
            "-ar",
            str(_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )


def _silence(ffmpeg, runtime: float, dest: Path) -> None:
    _run_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            _silence_source(runtime),
            "-t",
            f"{runtime:.3f}",
            "-ac",
            "1",
            "-ar",
            str(_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )


def _silence_source(runtime: float) -> str:
    return f"anullsrc=channel_layout=mono:sample_rate={_SAMPLE_RATE}:duration={runtime:.3f}"


def _tone_source(kind: str, tone: float, duration: float) -> str:
    if kind == "noise":
        return (
            f"anoisesrc=color=white:sample_rate={_SAMPLE_RATE}:amplitude=0.2:duration={duration:.3f}"
        )
    return f"sine=frequency={int(tone)}:sample_rate={_SAMPLE_RATE}:duration={duration:.3f}"


def _run_ffmpeg(command: list[str]) -> None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SoundError("ffmpeg did not finish the stems.") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or "").strip().splitlines()
        detail = tail[-1] if tail else "ffmpeg failed."
        raise SoundError(detail)


def _load_cut(folder: Path) -> tuple[dict, str]:
    path = folder / "edit" / "picture-lock.json"
    if not path.is_file():
        raise SoundError(
            "No picture-lock file at edit/picture-lock.json. "
            "The cut is not ready, so sound was not spotted."
        )
    try:
        data = read_handoff(path, schema="edit-decision-list")
    except HandoffError as exc:
        raise SoundError(str(exc)) from exc
    if data.get("kind") != "picture-lock":
        raise SoundError("edit/picture-lock.json is not a picture-lock cut, so sound was not spotted.")
    return data, "edit/picture-lock.json"


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SoundError(f"{path.name} is not valid JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise SoundError(f"{path.name} must be a JSON object.")
    try:
        source = str(path.resolve().relative_to(path.parents[1].resolve()))
    except ValueError:
        source = path.name
    return data, source


def _props_source(folder: Path) -> str | None:
    for relative in ("props/hero-props.json", "props/prop-definitions.json"):
        if (folder / relative).is_file():
            return relative
    return None


def _props_by_shot(folder: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    board = folder / "storyboard" / "storyboard.json"
    if board.is_file():
        try:
            frames = json.loads(board.read_text(encoding="utf-8")).get("frames") or []
        except json.JSONDecodeError:
            frames = []
        for frame in frames:
            if isinstance(frame, dict) and frame.get("shot_id"):
                found[str(frame["shot_id"])] = _labels(frame.get("props_in_frame"))
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = folder / relative
        if not path.is_file():
            continue
        try:
            shots = json.loads(path.read_text(encoding="utf-8")).get("shots") or []
        except json.JSONDecodeError:
            continue
        for shot in shots:
            if not isinstance(shot, dict) or not shot.get("shot_id"):
                continue
            shot_id = str(shot["shot_id"])
            labels = _labels(shot.get("props_in_shot") or shot.get("props_in_frame") or shot.get("props"))
            if shot_id not in found:
                found[shot_id] = labels
    return found


def _labels(props) -> list[str]:
    labels = []
    for item in props or []:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            for key in ("prop_id", "name"):
                if item.get(key):
                    labels.append(str(item[key]))
    return labels


def _silence_shots(brief: dict | None) -> dict[str, str]:
    found = {}
    if not brief:
        return found
    for item in brief.get("silence") or []:
        if not isinstance(item, dict) or not item.get("shot_id"):
            continue
        found[str(item["shot_id"])] = str(item.get("reason") or "").strip()
    return found


def _music_prompt(brief: dict, description: str) -> str:
    parts = []
    tempo = brief.get("tempo_bpm")
    if tempo not in (None, ""):
        parts.append(f"Tempo {tempo} bpm.")
    instruments = [str(item).strip() for item in brief.get("instrumentation") or [] if str(item).strip()]
    if instruments:
        parts.append("Instrumentation: " + ", ".join(instruments) + ".")
    if description:
        parts.append(description)
    return " ".join(parts).strip()


def _tolerance(prompts: dict | None, brief: dict | None) -> float:
    for source in (prompts, brief):
        if not source or source.get("sync_tolerance_seconds") in (None, ""):
            continue
        value = _number(source.get("sync_tolerance_seconds"))
        if value is not None and value >= 0:
            return value
    return _SYNC_TOLERANCE_SECONDS


def _source(folder: Path, asset: dict) -> str:
    named = str(asset.get("source") or "").strip().casefold()
    if named in {"generated", "library", "silence"}:
        return named
    dest = asset.get("dest_path")
    if dest and (folder / str(dest)).is_file():
        return "library"
    return "generated"


def _prop_in_shot(prop: dict, labels: list[str]) -> bool:
    names = [prop.get("prop_id") or "", prop.get("name") or "", *(prop.get("aliases") or [])]
    folded = {str(name).casefold() for name in names if str(name).strip()}
    for label in labels or []:
        text = str(label).strip().casefold()
        if text in folded:
            return True
        if any(len(name) >= 3 and name.casefold() in text for name in names if str(name).strip()):
            return True
    return False


def _mentions(text: str, prop: dict) -> bool:
    haystack = text.casefold()
    names = [prop.get("prop_id") or "", prop.get("name") or "", *(prop.get("aliases") or [])]
    for name in names:
        token = str(name).strip()
        if len(token) >= 3 and token.casefold() in haystack:
            return True
    return False


def _find_prop(props: list[dict], prop_id: str) -> dict | None:
    for prop in props:
        if str(prop.get("prop_id") or "") == prop_id:
            return prop
        if str(prop.get("name") or "").casefold() == prop_id.casefold():
            return prop
    return None


def _paid_model(cue_type: str) -> str:
    if cue_type == "dialogue":
        purpose = "dialogue"
    elif cue_type == "music":
        purpose = "score"
    else:
        purpose = "sfx"
    try:
        return str(resolve_model("sound-designer", purpose=purpose).get("model") or "")
    except ModelRoutingError:
        return ""


def _admin_model(role: str) -> str:
    try:
        return str(resolve_model(role, purpose="spot").get("model") or "")
    except ModelRoutingError:
        return ""


def _credit_for(agent: str) -> tuple[str, str]:
    if agent == "composer":
        return "Composer", "Composer"
    return "Sound Designer", "Sound Designer"


def _ensure_credit(producer, role: str, name: str) -> None:
    have = {item["role"] for item in producer.record["credits"]}
    if role in have:
        return
    producer.record["credits"].append({"role": role, "name": name})
    producer._save_record()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", value.casefold()).strip("-")
    return cleaned or "cue"


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
