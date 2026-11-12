"""Editor: assemble circled takes into a rough cut, then a picture-lock candidate.

The shot order, the phrases, and the runtime come from the production folder.
This module does not know which film it is reading. It does not call a paid
model. ffmpeg renders a low-resolution preview when it is installed. When it
is not, the edit decision list is still written. JSON is the source of truth.
A CMX3600 file is a reading copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from movie_swarm.continuity import (
    load_costume_lock,
    load_makeup_lock,
    load_prop_lock,
    locked_character_drift,
    locked_picture_drift,
)
from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.models import ModelRoutingError, resolve_model


class EditError(Exception):
    """The cut cannot be built. The message says what is missing."""


# A cut this short is the floor when the shot itself is longer.
_FLOOR_SECONDS = 0.5
# One second, or ten percent of the target, whichever is larger.
_TOLERANCE_FLOOR_SECONDS = 1.0
_TOLERANCE_RATIO = 0.10
_FRAME_RATE = 24
_PREVIEW_SIZE = "160:90"
_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
_STILL_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def assemble_production(
    production_dir: str | Path,
    *,
    dailies_approved: bool = False,
    report_path: str | Path | None = None,
) -> dict:
    """Build the edit decision list. Nothing is spent.

    ``dailies_approved`` is the Line Producer's dailies gate. The cut does
    not run while that gate is closed.
    """
    if not dailies_approved:
        raise EditError(
            "The dailies gate is still closed. Ron has not approved the circled takes, "
            "so the editor did not cut."
        )
    folder = Path(production_dir)
    report, dailies_source = _load_dailies(folder, report_path)
    shots, order_source = _load_order(folder)
    style, style_source = _load_style(folder)
    lock = load_prop_lock(folder)
    costume = load_costume_lock(folder)
    makeup = load_makeup_lock(folder)
    labels = _scene_labels(folder)
    target, runtime_source = _target_runtime(folder)
    tolerance = _tolerance(style, target)
    circled = _circled_index(report)

    events = []
    blockers = []
    texts = []
    for shot in shots:
        shot_id = shot["shot_id"]
        row = circled.get(shot_id)
        take = (row or {}).get("take")
        if take is None:
            blockers.append(_missing_blocker(shot_id, row))
            continue
        source = _source_file(folder, str(take["file"]))
        planned = shot["duration_seconds"]
        available = _available_seconds(source, _media_kind(source), planned)
        if planned is None:
            duration = available
        else:
            duration = min(planned, available)
        if duration <= 0:
            duration = available if available > 0 else 1.0
        transition, transition_duration = _transition_for(shot, style, incoming=bool(events))
        events.append(
            {
                "shot_id": shot_id,
                "scene_id": shot["scene_id"] or "unassigned",
                "take_id": str(take["take_id"]),
                "source_file": _relative_source(folder, source, str(take["file"])),
                "source_in": 0.0,
                "source_out": duration,
                "duration_seconds": duration,
                "available_seconds": available,
                "transition": transition,
                "transition_duration_seconds": transition_duration,
                "_path": source,
            }
        )
        texts.append(
            {
                "shot_id": shot_id,
                "scene_id": shot.get("scene_id") or "",
                "props": shot["props"],
                "characters": shot.get("characters") or [],
                "text": _shot_text(shot, row.get("shot") if row else None, take),
            }
        )

    _fit_runtime(events, target, tolerance)
    runtime = _place(events)
    continuity = _cross_cut(texts, lock, costume=costume, makeup=makeup)
    markers = _markers(events, labels)
    delta, within, note = _runtime_judgement(runtime, target, tolerance)
    continuity_clear = all(item["status"] == "pass" for item in continuity)
    ready = bool(events) and not blockers and continuity_clear and within
    public_events = [_public_event(item) for item in events]
    render = _render_preview(folder, events)
    try:
        model = str(resolve_model("editor", purpose="assemble").get("model") or "")
    except ModelRoutingError:
        model = ""
    return {
        "version": "1.0.0",
        "production_id": folder.name,
        "kind": "rough-cut",
        "created_at": _now(),
        "target_runtime_seconds": target,
        "tolerance_seconds": round(tolerance, 3),
        "runtime_seconds": runtime,
        "runtime_delta_seconds": delta,
        "within_tolerance": within,
        "runtime_note": note,
        "ready_for_picture_lock": ready,
        "picture_lock": False,
        "spent_usd": 0,
        "order_source": order_source,
        "sources": {
            "order": order_source,
            "dailies": dailies_source,
            "editing_style": style_source,
            "runtime": runtime_source,
        },
        "events": public_events,
        "scene_markers": markers,
        "blockers": blockers,
        "continuity": continuity,
        "render": render,
        "model": model,
        "draft_method": "offline-deterministic",
    }


def render_report(edl: dict) -> str:
    """The cut as a table a person can read before picture lock."""
    lines = [
        f"Edit for {edl['production_id']}",
        "",
        "No money was spent. JSON is the cut. The CMX file is a reading copy.",
        "",
        edl["runtime_note"],
        "",
        "| Event | Shot | Take | In | Out | Duration | Transition |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not edl["events"]:
        lines.append("| | | | | | | No circled shot was cut. |")
    for event in edl["events"]:
        lines.append(
            f"| {event['event']} | {event['shot_id']} | {event['take_id']} | "
            f"{event['source_in']:.2f} | {event['source_out']:.2f} | "
            f"{event['duration_seconds']:.2f} | {event['transition']} |"
        )
    lines.extend(["", "Scene markers:"])
    if not edl["scene_markers"]:
        lines.append("None.")
    for marker in edl["scene_markers"]:
        lines.append(f"- {marker['record_in']:.2f}s {marker['scene_id']}: {marker['label']}")
    lines.extend(["", "Missing coverage, not cut:"])
    if not edl["blockers"]:
        lines.append("None.")
    for blocker in edl["blockers"]:
        lines.append(f"- {blocker['shot_id']} routed to {blocker['routed_to']}. {blocker['detail']}")
    lines.extend(["", "Continuity across adjacent cuts:"])
    if not edl["continuity"]:
        lines.append("No adjacent pair was cut.")
    for item in edl["continuity"]:
        lines.append(
            f"- {item['from_shot_id']} to {item['to_shot_id']}: {item['status']}. {item['detail']}"
        )
    render = edl["render"]
    lines.extend(["", f"Preview: {render['status']}. {render['note']}"])
    if edl["ready_for_picture_lock"]:
        lines.append(
            "This cut is ready for picture lock. It is not locked until Ron approves the edit gate. "
            "Sound waits on that approval."
        )
    else:
        lines.append(
            "This cut is not ready for picture lock. "
            "A missing shot goes back to dailies or generation. Sound still waits on the edit gate."
        )
    return "\n".join(lines).rstrip() + "\n"


def render_cmx(edl: dict) -> str:
    """A CMX3600 reading copy. The JSON file remains the source of truth."""
    title = edl["production_id"].replace("-", " ").upper()[:70] or "CUT"
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    for event in edl["events"]:
        lines.append(_cmx_event(event))
        lines.append(f"* FROM CLIP NAME: {event['take_id']}")
        lines.append(f"* SHOT: {event['shot_id']}")
        lines.append(f"* SCENE: {event['scene_id']}")
        if event["transition"] != "cut":
            lines.append(f"* TRANSITION: {event['transition'].upper()}")
        lines.append("")
    if not edl["events"]:
        lines.append("* NO EVENTS. A shot with no circled take was not invented.")
        lines.append("")
    for marker in edl["scene_markers"]:
        lines.append(f"* LOC: {_timecode(marker['record_in'])} {marker['scene_id']} {marker['label']}")
    return "\n".join(lines).rstrip() + "\n"


def write_edit(edl: dict, production_dir: str | Path) -> tuple[Path, Path, Path]:
    """Write the checklist file, the readable table, and the CMX copy.

    A picture-lock file is written only when the cut is ready for Ron.
    An invalid cut is not saved.
    """
    folder = Path(production_dir) / "edit"
    folder.mkdir(parents=True, exist_ok=True)
    data_path = folder / "rough-cut.json"
    text_path = folder / "rough-cut.md"
    cmx_path = folder / "assembly.edl"
    lock_path = folder / "picture-lock.json"
    write_handoff(data_path, edl, schema="edit-decision-list")
    from movie_swarm.graphics import overlay_markdown
    from movie_swarm.vfx import turnover_markdown

    text_path.write_text(
        render_report(edl)
        + turnover_markdown(production_dir, "editor")
        + overlay_markdown(production_dir, "editor"),
        encoding="utf-8",
    )
    cmx_path.write_text(render_cmx(edl), encoding="utf-8")
    if edl["ready_for_picture_lock"]:
        locked = json.loads(json.dumps(edl))
        locked["kind"] = "picture-lock"
        locked["picture_lock"] = False
        write_handoff(lock_path, locked, schema="edit-decision-list")
    elif lock_path.is_file():
        lock_path.unlink()
    return data_path, text_path, cmx_path


def run_edit(producer, call) -> str:
    """The Director's assemble command. It writes the cut and does not spend."""
    production = Path(call.production_dir or producer.production_dir)
    edl = assemble_production(
        production,
        dailies_approved=producer.gate_is_open("dailies"),
    )
    _data_path, text_path, _cmx_path = write_edit(edl, production)
    producer.ensure_artifact("rough-cut", "edit/rough-cut.json", "edit-decision-list.schema.json")
    producer.ensure_artifact("rough-cut-notes", "edit/rough-cut.md")
    producer.ensure_artifact("assembly-edl", "edit/assembly.edl")
    if edl["ready_for_picture_lock"]:
        producer.ensure_artifact("picture-lock", "edit/picture-lock.json", "edit-decision-list.schema.json")
    else:
        producer.run.data["artifacts"] = [
            item for item in producer.run.data["artifacts"] if item.get("path") != "edit/picture-lock.json"
        ]
    if edl["render"]["status"] == "rendered" and edl["render"]["path"]:
        producer.ensure_artifact("rough-cut-preview", edl["render"]["path"])
    _ensure_credit(producer)
    if edl["ready_for_picture_lock"]:
        waiting = (
            "The rough cut is ready for picture lock. "
            "Sound does not run until Ron approves the edit gate."
        )
    else:
        waiting = (
            "The rough cut is not ready for picture lock. Read edit/rough-cut.md. "
            "Sound does not run until Ron approves the edit gate."
        )
    if producer.gate_decision("edit") == "approved":
        producer.run.data["notes"] = (
            "The edit was assembled again after Ron approved picture lock. "
            "The approval still stands until Ron rejects it. " + waiting
        )
        producer.run.save()
    else:
        producer.set_stage("edit", "waiting-for-review")
        producer.run.data["notes"] = waiting
        producer.run.save()
    return render_report(edl) + f"\nWrote {text_path}."


def _missing_blocker(shot_id: str, row: dict | None) -> dict:
    verdict = (row or {}).get("verdict")
    if verdict == "retake":
        return {
            "shot_id": shot_id,
            "kind": "missing-coverage",
            "routed_to": "generation",
            "detail": (
                f"{shot_id} has no circled take. Dailies marked it retake. "
                "The editor did not invent a shot. The blocker goes back to dailies and to generation."
            ),
        }
    if verdict == "reject":
        return {
            "shot_id": shot_id,
            "kind": "missing-coverage",
            "routed_to": "dailies",
            "detail": (
                f"{shot_id} has no circled take. Dailies rejected the file. "
                "The editor did not invent a shot. The blocker goes back to dailies."
            ),
        }
    return {
        "shot_id": shot_id,
        "kind": "missing-coverage",
        "routed_to": "dailies",
        "detail": (
            f"{shot_id} has no circled take. "
            "The editor did not invent a shot. The blocker goes back to dailies."
        ),
    }


def _circled_index(report: dict) -> dict[str, dict]:
    found = {}
    for shot in report.get("shots") or []:
        if not isinstance(shot, dict) or not shot.get("shot_id"):
            continue
        shot_id = str(shot["shot_id"])
        take = None
        if shot.get("verdict") == "circle":
            wanted = shot.get("best_take")
            takes = [item for item in shot.get("takes") or [] if isinstance(item, dict)]
            take = next(
                (item for item in takes if item.get("take_id") == wanted and item.get("verdict") == "circle"),
                None,
            )
            if take is None:
                take = next((item for item in takes if item.get("verdict") == "circle"), None)
        found[shot_id] = {"take": take, "verdict": shot.get("verdict"), "shot": shot}
    return found


def _shot_text(shot: dict, dailies_shot: dict | None, take: dict | None) -> str:
    parts = [shot.get("description") or "", shot.get("framing_notes") or "", shot.get("prompt") or ""]
    if dailies_shot:
        parts.extend(str(item) for item in dailies_shot.get("reasons") or [])
    if take:
        parts.extend(str(item) for item in take.get("reasons") or [])
        checks = take.get("checks") or {}
        if isinstance(checks, dict):
            for check in checks.values():
                if isinstance(check, dict) and check.get("detail"):
                    parts.append(str(check["detail"]))
    return " ".join(part.strip() for part in parts if str(part).strip())


def _cross_cut(texts: list[dict], lock: dict | None, costume=None, makeup=None) -> list[dict]:
    """The same locked-phrase check the Prop Master and the Script Supervisor use.

    It runs on each adjacent pair in the cut, not on the shoot order.
    Wardrobe and makeup use that same comparison when both shots list the person.
    """
    rows = []
    if len(texts) < 2:
        return rows
    for left, right in zip(texts, texts[1:]):
        shared = _shared_props(left["props"], right["props"], lock)
        reasons = []
        if shared and lock:
            for prop in shared:
                labels = [prop.get("prop_id") or "", prop.get("name") or ""]
                reasons.extend(_pair_reasons(left, right, labels, lock, locked_picture_drift))
        character_reasons = []
        for character_lock in (costume, makeup):
            shared_people = _shared_people(left.get("characters"), right.get("characters"), character_lock)
            for person in shared_people:
                labels = [person.get("character_id") or "", person.get("name") or ""]
                scene_id = left.get("scene_id") if left.get("scene_id") == right.get("scene_id") else None
                character_reasons.extend(
                    _pair_reasons(
                        left,
                        right,
                        labels,
                        character_lock,
                        locked_character_drift,
                        scene_id=scene_id,
                    )
                )
        reasons.extend(character_reasons)
        if not shared and not character_reasons:
            detail = "No locked prop is in both shots."
            status = "pass"
        elif reasons:
            detail = " ".join(reasons)
            status = "fail"
        elif shared:
            detail = "The locked props match across this cut."
            status = "pass"
        else:
            detail = "The locked wardrobe and makeup match across this cut."
            status = "pass"
        rows.append(
            {
                "from_shot_id": left["shot_id"],
                "to_shot_id": right["shot_id"],
                "status": status,
                "detail": detail,
            }
        )
    return rows


def _pair_reasons(left, right, labels, lock, checker, scene_id=None) -> list[str]:
    if checker is locked_character_drift:
        drift_left = checker(left["text"], labels, lock, scene_id=scene_id)
        drift_right = checker(right["text"], labels, lock, scene_id=scene_id)
    else:
        drift_left = checker(left["text"], labels, lock)
        drift_right = checker(right["text"], labels, lock)
    name = labels[1] or labels[0] or "item"
    disagreed = set(drift_left["required_missing"]) != set(drift_right["required_missing"])
    forbidden = bool(drift_left["forbidden_hit"] or drift_right["forbidden_hit"])
    if not disagreed and not forbidden:
        return []
    pieces = [f"{name} is not consistent from {left['shot_id']} to {right['shot_id']}."]
    if drift_left["reasons"]:
        pieces.append(f"{left['shot_id']}: {' '.join(drift_left['reasons'])}")
    if drift_right["reasons"]:
        pieces.append(f"{right['shot_id']}: {' '.join(drift_right['reasons'])}")
    return [" ".join(pieces)]


def _shared_props(left_labels, right_labels, lock: dict | None) -> list[dict]:
    if not lock:
        return []
    shared = []
    for prop in lock.get("props") or []:
        if not isinstance(prop, dict):
            continue
        if _prop_listed(prop, left_labels) and _prop_listed(prop, right_labels):
            shared.append(prop)
    return shared


def _shared_people(left_labels, right_labels, lock: dict | None) -> list[dict]:
    if not lock:
        return []
    shared = []
    for person in lock.get("characters") or []:
        if not isinstance(person, dict):
            continue
        if _prop_listed(person, left_labels) and _prop_listed(person, right_labels):
            shared.append(person)
    return shared


def _prop_listed(prop: dict, labels) -> bool:
    names = [
        prop.get("prop_id") or "",
        prop.get("character_id") or "",
        prop.get("name") or "",
        *(prop.get("aliases") or []),
    ]
    folded = {str(name).casefold() for name in names if str(name).strip()}
    for label in labels or []:
        if str(label).strip().casefold() in folded:
            return True
    return False


def _fit_runtime(events: list[dict], target: float | None, tolerance: float) -> None:
    """Shorten a cut that runs long. A short cut is reported and not padded."""
    if not events or target is None:
        return
    current = _timeline_runtime(events)
    if current <= target + tolerance:
        return
    if current <= 0:
        return
    scale = target / current
    for event in events:
        desired = event["duration_seconds"] * scale
        floor = min(_FLOOR_SECONDS, event["available_seconds"])
        duration = min(event["available_seconds"], max(floor, desired))
        event["duration_seconds"] = duration
        event["source_out"] = event["source_in"] + duration
    _nudge(events, target)
    for _ in range(50):
        runtime = _timeline_runtime(events)
        if runtime <= target + tolerance:
            break
        spare = []
        for event in events:
            floor = min(_FLOOR_SECONDS, event["available_seconds"])
            extra = event["duration_seconds"] - floor
            if extra > 0.001:
                spare.append((extra, event))
        if not spare:
            break
        extra, event = max(spare, key=lambda item: item[0])
        cut = min(extra, runtime - target)
        event["duration_seconds"] -= cut
        event["source_out"] = event["source_in"] + event["duration_seconds"]
    _nudge(events, target)


def _nudge(events: list[dict], target: float) -> None:
    if not events:
        return
    gap = target - _timeline_runtime(events)
    if abs(gap) < 0.0005:
        return
    event = events[-1]
    floor = min(_FLOOR_SECONDS, event["available_seconds"])
    candidate = event["duration_seconds"] + gap
    if candidate < floor - 1e-9 or candidate > event["available_seconds"] + 1e-9:
        return
    event["duration_seconds"] = candidate
    event["source_out"] = event["source_in"] + candidate


def _timeline_runtime(events: list[dict]) -> float:
    cursor = 0.0
    for index, event in enumerate(events):
        overlap = _overlap(events, index)
        record_in = max(0.0, cursor - overlap)
        cursor = record_in + event["duration_seconds"]
    return cursor


def _overlap(events: list[dict], index: int) -> float:
    if index <= 0:
        return 0.0
    event = events[index]
    if event["transition"] not in {"dissolve", "fade"}:
        return 0.0
    return min(
        float(event["transition_duration_seconds"]),
        float(event["duration_seconds"]),
        float(events[index - 1]["duration_seconds"]),
    )


def _place(events: list[dict]) -> float:
    for event in events:
        event["source_in"] = round(float(event["source_in"]), 3)
        event["duration_seconds"] = round(float(event["duration_seconds"]), 3)
        event["source_out"] = round(event["source_in"] + event["duration_seconds"], 3)
        if event["transition"] == "cut":
            event["transition_duration_seconds"] = 0.0
        else:
            event["transition_duration_seconds"] = round(float(event["transition_duration_seconds"]), 3)
    cursor = 0.0
    for index, event in enumerate(events):
        overlap = _overlap(events, index)
        record_in = round(max(0.0, cursor - overlap), 3)
        record_out = round(record_in + event["duration_seconds"], 3)
        event["event"] = index + 1
        event["record_in"] = record_in
        event["record_out"] = record_out
        cursor = record_out
    return round(cursor, 3)


def _public_event(event: dict) -> dict:
    return {
        "event": event["event"],
        "shot_id": event["shot_id"],
        "scene_id": event["scene_id"],
        "take_id": event["take_id"],
        "source_file": event["source_file"],
        "source_in": event["source_in"],
        "source_out": event["source_out"],
        "record_in": event["record_in"],
        "record_out": event["record_out"],
        "duration_seconds": event["duration_seconds"],
        "transition": event["transition"],
        "transition_duration_seconds": event["transition_duration_seconds"],
    }


def _markers(events: list[dict], labels: dict[str, str]) -> list[dict]:
    markers = []
    seen = set()
    for event in events:
        scene_id = event["scene_id"]
        if scene_id in seen:
            continue
        seen.add(scene_id)
        markers.append(
            {
                "scene_id": scene_id,
                "label": labels.get(scene_id) or scene_id,
                "record_in": event["record_in"],
            }
        )
    return markers


def _runtime_judgement(runtime: float, target: float | None, tolerance: float):
    if target is None:
        return (
            0.0,
            True,
            "No target runtime was in the production brief, the scene list, or the treatment. The cut was not trimmed.",
        )
    delta = round(runtime - float(target), 3)
    within = abs(delta) <= tolerance + 0.0005
    if abs(delta) < 0.0005:
        relation = "The cut matches the target."
    elif delta > 0:
        relation = f"The cut is {delta:.2f}s over."
    else:
        relation = f"The cut is {abs(delta):.2f}s under."
    fit = "It is inside the tolerance." if within else "It is outside the tolerance."
    note = (
        f"Runtime is {runtime:.2f}s. The target is {float(target):.2f}s. "
        f"Tolerance is {tolerance:.2f}s. {relation} {fit}"
    )
    return delta, within, note


def _transition_for(shot: dict, style: dict, *, incoming: bool) -> tuple[str, float]:
    chosen = _style_transition(style, shot["shot_id"])
    if chosen is None and shot.get("transition"):
        chosen = {
            "transition": shot["transition"],
            "duration_seconds": shot.get("transition_duration_seconds"),
        }
    if chosen is None:
        default = str(style.get("default_transition") or "cut")
        chosen = {"transition": default, "duration_seconds": None}
    name = str(chosen.get("transition") or "cut").strip().casefold()
    if name not in {"cut", "dissolve", "fade"}:
        name = "cut"
    if name == "cut" or not incoming and name == "dissolve":
        # A dissolve needs an outgoing shot. The first event is a cut unless it is a fade in.
        if name == "dissolve":
            name = "cut"
    if name == "cut":
        return "cut", 0.0
    duration = chosen.get("duration_seconds")
    if duration is None:
        duration = 0.5
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        seconds = 0.5
    if seconds <= 0:
        return "cut", 0.0
    return name, seconds


def _style_transition(style: dict, shot_id: str) -> dict | None:
    table = style.get("transitions")
    if isinstance(table, dict) and shot_id in table and isinstance(table[shot_id], dict):
        return table[shot_id]
    if isinstance(table, list):
        for item in table:
            if isinstance(item, dict) and str(item.get("shot_id") or "") == shot_id:
                return item
    return None


def _load_dailies(folder: Path, report_path: str | Path | None) -> tuple[dict, str]:
    path = Path(report_path) if report_path else folder / "dailies" / "dailies-report.json"
    if not path.is_file():
        raise EditError(
            f"No dailies report at {path}. "
            "The editor needs circled takes. Run the dailies review first."
        )
    try:
        data = read_handoff(path, schema="dailies-report")
    except HandoffError as exc:
        raise EditError(str(exc)) from exc
    try:
        source = str(path.resolve().relative_to(folder.resolve()))
    except ValueError:
        source = path.name
    return data, source


def _load_order(folder: Path) -> tuple[list[dict], str]:
    index: dict[str, dict] = {}
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = folder / relative
        if not path.is_file():
            continue
        for shot in _read_json(path).get("shots") or []:
            if isinstance(shot, dict) and shot.get("shot_id"):
                index[str(shot["shot_id"])] = _normalize_shot(shot)
        if index:
            break
    board = folder / "storyboard" / "storyboard.json"
    if board.is_file():
        data = _read_json(board)
        frames = [frame for frame in data.get("frames") or [] if isinstance(frame, dict) and frame.get("shot_id")]
        frames.sort(key=lambda frame: int(frame.get("order") or 0))
        by_frame = {str(frame["shot_id"]): frame for frame in frames}
        order = [str(shot_id) for shot_id in (data.get("animatic") or {}).get("order") or [] if str(shot_id).strip()]
        if not order:
            order = [str(frame["shot_id"]) for frame in frames]
        if order:
            shots = [_merge(index.get(shot_id, {}), by_frame.get(shot_id, {}), shot_id) for shot_id in order]
            return shots, "storyboard/storyboard.json"
    if index:
        source = "storyboard/shot-list.json" if (folder / "storyboard" / "shot-list.json").is_file() else "shot-lists/shot-list.json"
        ordered = _sorted_shots(index)
        return ordered, source
    raise EditError(
        "No storyboard or shot list. The editor has no shot order, so it did not invent one."
    )


def _sorted_shots(index: dict[str, dict]) -> list[dict]:
    shots = list(index.values())

    def key(shot: dict):
        scene = shot.get("_scene_number")
        number = shot.get("_shot_number")
        position = shot.get("_sequence")
        if position is not None:
            return (0, position, shot["shot_id"])
        if scene is not None and number is not None:
            return (1, scene, number, shot["shot_id"])
        return (2, 0, 0, shot["shot_id"])

    shots.sort(key=key)
    return shots


def _normalize_shot(shot: dict) -> dict:
    scene = shot.get("scene_id")
    scene_number = shot.get("scene_number")
    if not scene and scene_number is not None:
        scene = f"s{int(scene_number):02d}"
    props = shot.get("props_in_shot") or shot.get("props_in_frame") or shot.get("props") or []
    return {
        "shot_id": str(shot.get("shot_id") or ""),
        "scene_id": str(scene or ""),
        "description": str(shot.get("description") or ""),
        "framing_notes": str(shot.get("framing_notes") or ""),
        "prompt": str(shot.get("generation_prompt") or shot.get("description") or ""),
        "props": _prop_labels(props),
        "characters": _prop_labels(shot.get("characters_in_shot") or shot.get("characters")),
        "duration_seconds": _duration(shot.get("target_duration_seconds", shot.get("duration_seconds"))),
        "transition": str(shot.get("transition") or ""),
        "transition_duration_seconds": _duration(shot.get("transition_duration_seconds")),
        "_scene_number": _int_or_none(scene_number),
        "_shot_number": _int_or_none(shot.get("shot_number")),
        "_sequence": _int_or_none(shot.get("sequence_position")),
    }


def _merge(shot: dict, frame: dict, shot_id: str) -> dict:
    scene = str(frame.get("scene_id") or shot.get("scene_id") or "")
    duration = _duration(frame.get("duration_seconds"))
    if duration is None:
        duration = shot.get("duration_seconds")
    description = str(frame.get("what_we_see") or shot.get("description") or "")
    props = frame.get("props_in_frame")
    if props is None:
        props = shot.get("props") or []
    transition = str(frame.get("transition") or shot.get("transition") or "")
    transition_duration = frame.get("transition_duration_seconds", shot.get("transition_duration_seconds"))
    return {
        "shot_id": shot_id,
        "scene_id": scene,
        "description": description,
        "framing_notes": str(shot.get("framing_notes") or ""),
        "prompt": str(frame.get("board_prompt") or shot.get("prompt") or description),
        "props": _prop_labels(props),
        "characters": _prop_labels(frame.get("characters_in_shot") or shot.get("characters") or []),
        "duration_seconds": duration,
        "transition": transition,
        "transition_duration_seconds": _duration(transition_duration),
    }


def _prop_labels(props) -> list[str]:
    labels = []
    for item in props or []:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            for key in ("prop_id", "name"):
                if item.get(key):
                    labels.append(str(item[key]))
    return labels


def _load_style(folder: Path) -> tuple[dict, str | None]:
    path = folder / "edit" / "editing-style.json"
    if not path.is_file():
        return {}, None
    return _read_json(path), "edit/editing-style.json"


def _scene_labels(folder: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    manifest = folder / "scene-manifest" / "scene-manifest.json"
    if manifest.is_file():
        for scene in _read_json(manifest).get("scenes") or []:
            if isinstance(scene, dict) and scene.get("scene_id"):
                labels[str(scene["scene_id"])] = str(scene.get("heading") or scene.get("location") or scene["scene_id"])
    treatment = folder / "treatment" / "treatment.json"
    if treatment.is_file():
        try:
            data = _read_json(treatment)
        except EditError:
            data = {}
        for index, scene in enumerate(data.get("scenes") or [], start=1):
            if not isinstance(scene, dict):
                continue
            scene_id = str(scene.get("scene_id") or f"s{index:02d}")
            if scene_id not in labels:
                labels[scene_id] = str(scene.get("heading") or scene_id)
    return labels


def _target_runtime(folder: Path) -> tuple[float | None, str | None]:
    brief = folder / "production-brief.json"
    if brief.is_file():
        value = _duration(_read_json(brief).get("target_runtime_seconds"))
        if value is not None:
            return value, "production-brief.json"
    manifest = folder / "scene-manifest" / "scene-manifest.json"
    if manifest.is_file():
        value = _duration(_read_json(manifest).get("target_runtime_seconds"))
        if value is not None:
            return value, "scene-manifest/scene-manifest.json"
    treatment = folder / "treatment" / "treatment.json"
    if treatment.is_file():
        total = 0.0
        seen = False
        for scene in _read_json(treatment).get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            value = _duration(scene.get("approximate_duration_seconds"))
            if value is None:
                continue
            total += value
            seen = True
        if seen:
            return total, "treatment/treatment.json"
    return None, None


def _tolerance(style: dict, target: float | None) -> float:
    if style.get("runtime_tolerance_seconds") is not None:
        value = _duration(style.get("runtime_tolerance_seconds"))
        if value is not None:
            return value
    if style.get("runtime_tolerance_ratio") is not None and target is not None:
        value = _duration(style.get("runtime_tolerance_ratio"))
        if value is not None:
            return value * float(target)
    if target is None:
        return 0.0
    return max(_TOLERANCE_FLOOR_SECONDS, _TOLERANCE_RATIO * float(target))


def _media_kind(path: Path) -> str:
    if path.suffix.lower() in _VIDEO_SUFFIXES:
        return "clip"
    return "frame"


def _available_seconds(path: Path, kind: str, planned: float | None) -> float:
    if kind == "clip" and path.is_file():
        probed = _probe_duration(path)
        if probed is not None and probed > 0:
            return probed
    if planned is not None and planned > 0:
        return planned
    return 1.0


def _source_file(folder: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return folder / relative


def _relative_source(folder: Path, path: Path, original: str) -> str:
    try:
        return str(path.resolve().relative_to(folder.resolve()))
    except ValueError:
        return original


def _probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (completed.stdout or "").strip()
    if completed.returncode != 0 or not text or text == "N/A":
        return None
    try:
        seconds = float(text)
    except ValueError:
        return None
    return seconds if seconds > 0 else None


def _render_preview(folder: Path, events: list[dict]) -> dict:
    if not events:
        return {
            "status": "skipped",
            "path": None,
            "note": "No circled shot was cut, so the preview was not rendered. The edit decision list is still written.",
        }
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            "status": "skipped",
            "path": None,
            "note": "ffmpeg is not installed, so the rough-cut preview was not rendered. The edit decision list is still written.",
        }
    missing = [event["shot_id"] for event in events if not Path(event["_path"]).is_file()]
    if missing:
        names = ", ".join(missing)
        return {
            "status": "skipped",
            "path": None,
            "note": (
                f"These source files are not on disk, so the preview was not rendered: {names}. "
                "The edit decision list is still written."
            ),
        }
    work = folder / "edit" / "preview-work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    preview = folder / "edit" / "rough-cut.mp4"
    try:
        segments = []
        for event in events:
            segment = work / f"seg-{event['event']:03d}.mp4"
            _segment(ffmpeg, Path(event["_path"]), event["source_in"], event["duration_seconds"], segment)
            segments.append(segment)
        dissolves = any(
            event["transition"] in {"dissolve", "fade"} and event["transition_duration_seconds"] > 0
            for event in events
        )
        if dissolves and len(segments) > 1:
            _render_xfade(ffmpeg, segments, events, preview)
        else:
            _render_concat(ffmpeg, segments, preview)
        shutil.rmtree(work, ignore_errors=True)
    except (OSError, subprocess.TimeoutExpired, EditError) as exc:
        return {
            "status": "failed",
            "path": None,
            "note": f"ffmpeg could not render the preview. The edit decision list is still written. {exc}",
        }
    return {
        "status": "rendered",
        "path": "edit/rough-cut.mp4",
        "note": "A low-resolution preview was rendered. It is a picture reference. It is not the picture lock.",
    }


def _segment(ffmpeg: str, source: Path, start: float, duration: float, dest: Path) -> None:
    scale = (
        f"scale={_PREVIEW_SIZE}:force_original_aspect_ratio=decrease,"
        f"pad={_PREVIEW_SIZE}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )
    if source.suffix.lower() in _STILL_SUFFIXES:
        command = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(_FRAME_RATE),
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vf",
            scale,
            "-r",
            str(_FRAME_RATE),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            str(dest),
        ]
    else:
        command = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vf",
            scale,
            "-r",
            str(_FRAME_RATE),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            str(dest),
        ]
    _run_ffmpeg(command)


def _render_concat(ffmpeg: str, segments: list[Path], dest: Path) -> None:
    listing = segments[0].parent / "concat.txt"
    lines = []
    for path in segments:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(dest),
        ]
    )


def _render_xfade(ffmpeg: str, segments: list[Path], events: list[dict], dest: Path) -> None:
    inputs: list[str] = []
    for path in segments:
        inputs.extend(["-i", str(path)])
    filters = []
    previous = "[0:v]"
    accumulated = events[0]["duration_seconds"]
    for index in range(1, len(events)):
        event = events[index]
        name = "fade" if event["transition"] == "fade" else "dissolve"
        duration = event["transition_duration_seconds"]
        if event["transition"] == "cut" or duration <= 0:
            name = "fade"
            duration = 1 / _FRAME_RATE
        offset = max(0.0, accumulated - duration)
        output = f"[v{index}]" if index < len(events) - 1 else "[vout]"
        filters.append(
            f"{previous}[{index}:v]xfade=transition={name}:duration={duration:.3f}:offset={offset:.3f}{output}"
        )
        previous = output
        accumulated = accumulated + event["duration_seconds"] - duration
    _run_ffmpeg(
        [
            ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            str(dest),
        ]
    )


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
        raise EditError("ffmpeg did not finish the preview.") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or "").strip().splitlines()
        detail = tail[-1] if tail else "ffmpeg failed."
        raise EditError(detail)


def _cmx_event(event: dict) -> str:
    number = f"{int(event['event']):03d}"
    src_in = _timecode(event["source_in"])
    src_out = _timecode(event["source_out"])
    rec_in = _timecode(event["record_in"])
    rec_out = _timecode(event["record_out"])
    if event["transition"] == "cut":
        return f"{number}  AX       V     C        {src_in} {src_out} {rec_in} {rec_out}"
    frames = max(1, int(round(event["transition_duration_seconds"] * _FRAME_RATE)))
    return f"{number}  AX       V     D    {frames:03d} {src_in} {src_out} {rec_in} {rec_out}"


def _timecode(seconds: float) -> str:
    frames_total = int(round(max(0.0, float(seconds)) * _FRAME_RATE))
    frames = frames_total % _FRAME_RATE
    whole = frames_total // _FRAME_RATE
    secs = whole % 60
    minutes = (whole // 60) % 60
    hours = whole // 3600
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def _ensure_credit(producer) -> None:
    have = {item["role"] for item in producer.record["credits"]}
    if "Editor" in have:
        return
    producer.record["credits"].append({"role": "Editor", "name": "Editor"})
    producer._save_record()


def _duration(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _int_or_none(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EditError(f"{path.name} is not valid JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise EditError(f"{path.name} must be a JSON object.")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
