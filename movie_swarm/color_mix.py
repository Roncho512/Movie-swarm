"""Colorist and Re-recording Mixer: grade the locked picture and mix the stems.

The look, the grade numbers, the cue sheet, and the loudness target come from
the production folder. This module does not know which film it is reading.
It does not call a paid model. ffmpeg grades, mixes, and measures when it is
installed. When it is not, the plans are still written. JSON is the source
of truth.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.models import ModelRoutingError, resolve_model


class ColorMixError(Exception):
    """Color or mix cannot be built. The message says what is missing."""


# How far two adjacent shots in one scene may differ before a flag.
# A production grade file can set a different pair. The scale is 0 to 1.
_DEFAULT_BRIGHTNESS_TOLERANCE = 0.12
_DEFAULT_COLOR_TOLERANCE = 0.12

# EBU R128 programme loudness. A production mix-targets file can replace this.
_EBU_INTEGRATED_LUFS = -23.0
_EBU_TRUE_PEAK_DBTP = -1.0
_EBU_TOLERANCE_LUFS = 0.5
_EBU_STANDARD = "EBU R128"
_EBU_CITATION = (
    "EBU R128, Loudness normalisation and permitted maximum level of audio signals "
    "(https://tech.ebu.ch/docs/r/r128.pdf). "
    "The target programme loudness is -23.0 LUFS and the maximum true peak is -1.0 dBTP. "
    "A mix more than 0.5 LU from that target is flagged. "
    "That is the deviation EBU R128 allows when a programme cannot be normalised exactly. "
    "The meter is the one in EBU Tech 3341, which ffmpeg reports as ebur128 or loudnorm."
)

# Dialogue stays at unity. Music and effects sit lower, then duck further
# under dialogue. These are studio defaults, not a film's facts.
_DEFAULT_DIALOGUE_DB = 0.0
_DEFAULT_EFFECTS_DB = -8.0
_DEFAULT_MUSIC_DB = -12.0
_DEFAULT_DUCK_DB = -8.0
_DEFAULT_FADE_SECONDS = 0.5

_PREVIEW_SIZE = "160:90"
_FRAME_RATE = 24
_SAMPLE_RATE = 44100
_GRADE_KEYS = ("time_of_day", "contrast", "saturation", "warmth", "brightness", "gamma")
_STILL_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_NEUTRAL = {
    "time_of_day": "unspecified",
    "contrast": 1.0,
    "saturation": 1.0,
    "warmth": 0.0,
    "brightness": 0.0,
    "gamma": 1.0,
}


def grade_production(
    production_dir: str | Path,
    *,
    picture_lock_approved: bool = False,
    sound_approved: bool = False,
) -> dict:
    """Build the grade plan. Nothing is spent.

    Both gates have to be open. The edit gate is picture lock. The sound
    gate is the approved cue sheet. The plan does not approve itself.
    """
    _require_approvals(picture_lock_approved, sound_approved)
    folder = Path(production_dir)
    edl, cut_source = _load_cut(folder)
    look, look_source = _load_look(folder)
    grade_file, grade_source = _load_optional(folder, folder / "look" / "grade.json", "grade")
    events = _events(folder, edl)
    base, base_parts = _base_grade(look, grade_file)
    adjustments, by_shot = _adjustments(events, look, grade_file, base)
    lut = _resolve_lut(folder, grade_file)
    render, segments = _render_grade(folder, events, by_shot, lut)
    tolerance, tolerance_source = _tolerance(grade_file)
    checks = _consistency(events, segments, tolerance)
    shutil.rmtree(folder / "color" / "preview-work", ignore_errors=True)
    ready = bool(events) and all(item["status"] != "fail" for item in checks)
    plan = {
        "version": "1.0.0",
        "production_id": folder.name,
        "kind": "grade-plan",
        "created_at": _now(),
        "cut_runtime_seconds": round(_number(edl.get("runtime_seconds")) or 0.0, 3),
        "ready_for_color_mix_approval": ready,
        "color_mix_approved": False,
        "spent_usd": 0,
        "cut_source": cut_source,
        "sources": {"edit": cut_source, "look": look_source, "grade": grade_source},
        "look_reference": _look_reference(look),
        "base": {**base, "source": _source_label(base_parts, grade_source)},
        "adjustments": adjustments,
        "applied": [_public_applied(item) for item in by_shot],
        "consistency": {
            "brightness_tolerance": tolerance["brightness"],
            "color_tolerance": tolerance["color"],
            "tolerance_source": tolerance_source,
            "checks": checks,
        },
        "lut": lut["relative"] if lut else None,
        "render": render,
        "budget": _budget("editor"),
        "models": {"colorist": _model("colorist", "grade"), "render": "ffmpeg"},
        "draft_method": "offline-deterministic",
    }
    return plan


def mix_production(
    production_dir: str | Path,
    *,
    picture_lock_approved: bool = False,
    sound_approved: bool = False,
) -> dict:
    """Build the mix plan from the cue sheet and the stems. Nothing is spent."""
    _require_approvals(picture_lock_approved, sound_approved)
    folder = Path(production_dir)
    edl, cut_source = _load_cut(folder)
    sheet, cue_source = _load_cue_sheet(folder)
    targets, targets_source = _load_optional(folder, folder / "audio" / "mix-targets.json", "mix-targets")
    runtime = _number(edl.get("runtime_seconds")) or _number(sheet.get("cut_runtime_seconds")) or 0.0
    levels = _levels(targets)
    ducking = _ducking(sheet, targets)
    fades = _fades(edl, targets)
    loudness = _loudness_target(targets, targets_source)
    stems = _stem_files(folder, sheet)
    render = _render_mix(folder, stems, levels, ducking, fades, runtime)
    measurement = _measure_mix(folder / "color" / "mix.wav" if render["status"] == "rendered" else None, loudness)
    ready = measurement["status"] != "measured" or measurement["within_target"] is True
    return {
        "version": "1.0.0",
        "production_id": folder.name,
        "kind": "mix-plan",
        "created_at": _now(),
        "cut_runtime_seconds": round(float(runtime), 3),
        "ready_for_color_mix_approval": bool(ready),
        "color_mix_approved": False,
        "spent_usd": 0,
        "cut_source": cut_source,
        "cue_source": cue_source,
        "sources": {
            "edit": cut_source,
            "cue_sheet": cue_source,
            "mix_targets": targets_source,
            "stems": [item["relative"] for item in stems if item["path"].is_file()],
        },
        "levels": levels,
        "ducking": ducking,
        "fades": fades,
        "loudness": loudness,
        "measurement": measurement,
        "render": render,
        "budget": _budget("sound-designer"),
        "models": {"mixer": _model("mixer", "mix"), "notes": _model("mixer", "notes")},
        "draft_method": "offline-deterministic",
    }


def marry_preview(production_dir: str | Path, plan: dict) -> None:
    """Join the graded picture and the mix when both files are already on disk.

    Updates ``plan`` and, when the other plan was written earlier, that file.
    A missing piece leaves the plans unjoined.
    """
    folder = Path(production_dir)
    ffmpeg = shutil.which("ffmpeg")
    video = folder / "color" / "graded-preview.mp4"
    audio = folder / "color" / "mix.wav"
    if not ffmpeg or not video.is_file() or not audio.is_file():
        return
    dest = folder / "color" / "married-preview.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run_ffmpeg(
            [
                ffmpeg,
                "-y",
                "-i",
                str(video),
                "-i",
                str(audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(dest),
            ]
        )
    except ColorMixError as exc:
        plan["render"]["note"] = (
            plan["render"]["note"].rstrip() + f" The picture and the mix were not married. {exc}"
        )
        return
    relative = "color/married-preview.mp4"
    plan["render"]["married"] = relative
    plan["render"]["note"] = (
        plan["render"]["note"].rstrip()
        + " The graded picture and the mix were married into a low-resolution preview."
    )
    other = "mix-plan.json" if plan.get("kind") == "grade-plan" else "grade-plan.json"
    other_schema = "mix-plan" if other == "mix-plan.json" else "grade-plan"
    _stamp_married(folder, other, other_schema, relative)


def render_grade_report(plan: dict) -> str:
    """The grade as a table a person can read before the color-mix gate."""
    lines = [
        f"Color grade for {plan['production_id']}",
        "",
        "No money was spent. JSON is the grade plan.",
        "",
        f"Look: {plan['look_reference']['look_name']}. {plan['look_reference']['summary']}",
        "",
        (
            f"Base grade, stated once, from {plan['base']['source']}. "
            f"Time of day {plan['base']['time_of_day']}. "
            f"Contrast {plan['base']['contrast']}. Saturation {plan['base']['saturation']}. "
            f"Warmth {plan['base']['warmth']}. Brightness {plan['base']['brightness']}."
        ),
        "",
        "| Adjustment | Scope | Scene | Shots | Contrast | Saturation | Warmth |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not plan["adjustments"]:
        lines.append("| base only | | | | The cut uses the base grade. | | |")
    for item in plan["adjustments"]:
        shots = ", ".join(item["shot_ids"])
        lines.append(
            f"| {item['adjustment_id']} | {item['scope']} | {item['scene_id']} | {shots} | "
            f"{item['contrast']} | {item['saturation']} | {item['warmth']} |"
        )
    lines.extend(["", "Shot to shot, inside a scene:"])
    checks = plan["consistency"]["checks"]
    if not checks:
        lines.append("No adjacent pair in the same scene.")
    for item in checks:
        lines.append(
            f"- {item['previous_shot_id']} to {item['shot_id']}: {item['status']}. {item['detail']}"
        )
    render = plan["render"]
    lines.extend(["", f"Preview: {render['status']}. {render['note']}", "", plan["budget"]["note"]])
    lines.append(_approval_line(plan["ready_for_color_mix_approval"]))
    return "\n".join(lines).rstrip() + "\n"


def render_mix_report(plan: dict) -> str:
    """The mix as a table a person can read before the color-mix gate."""
    lines = [
        f"Mix for {plan['production_id']}",
        "",
        "No money was spent. JSON is the mix plan.",
        "",
        f"Loudness target: {plan['loudness']['integrated_lufs']} LUFS ({plan['loudness']['standard']}).",
        plan["loudness"]["citation"],
        "",
        "| Stem | Gain | Priority |",
        "| --- | --- | --- |",
    ]
    for level in plan["levels"]:
        lines.append(f"| {level['stem']} | {level['gain_db']} dB | {level['priority']} |")
    lines.extend(["", "Dialogue ducking:"])
    if not plan["ducking"]:
        lines.append("No dialogue cue to duck under.")
    for item in plan["ducking"]:
        lines.append(
            f"- {item['stem']} under {item['under']} "
            f"({item['start_seconds']:.2f}s to {item['end_seconds']:.2f}s, {item['duck_db']} dB) "
            f"for {item['cue_id']}."
        )
    lines.extend(["", "Scene fades:"])
    if not plan["fades"]:
        lines.append("No scene change in this cut.")
    for fade in plan["fades"]:
        lines.append(
            f"- {fade['time_seconds']:.2f}s into {fade['scene_id']}, {fade['fade_seconds']:.2f}s."
        )
    measured = plan["measurement"]
    lines.extend(["", f"Loudness: {measured['status']}. {measured['note']}"])
    for flag in measured["flags"]:
        lines.append(f"- {flag['kind']}: {flag['detail']}")
    render = plan["render"]
    lines.extend(["", f"Mix: {render['status']}. {render['note']}", "", plan["budget"]["note"]])
    lines.append(_approval_line(plan["ready_for_color_mix_approval"]))
    return "\n".join(lines).rstrip() + "\n"


def write_grade(plan: dict, production_dir: str | Path) -> tuple[Path, Path]:
    """Write the grade plan. A flagged plan is still saved so it can be read."""
    folder = Path(production_dir) / "color"
    folder.mkdir(parents=True, exist_ok=True)
    data_path = folder / "grade-plan.json"
    text_path = folder / "grade-plan.md"
    write_handoff(data_path, plan, schema="grade-plan")
    text_path.write_text(render_grade_report(plan), encoding="utf-8")
    return data_path, text_path


def write_mix(plan: dict, production_dir: str | Path) -> tuple[Path, Path]:
    """Write the mix plan. A flagged plan is still saved so it can be read."""
    folder = Path(production_dir) / "color"
    folder.mkdir(parents=True, exist_ok=True)
    data_path = folder / "mix-plan.json"
    text_path = folder / "mix-plan.md"
    write_handoff(data_path, plan, schema="mix-plan")
    text_path.write_text(render_mix_report(plan), encoding="utf-8")
    return data_path, text_path


def run_color_mix(producer, call) -> str:
    """The Director's grade or mix command. It does not spend."""
    production = Path(call.production_dir or producer.production_dir)
    if not producer.gate_is_open("edit") or not producer.gate_is_open("sound"):
        _require_approvals(producer.gate_is_open("edit"), producer.gate_is_open("sound"))
    if call.agent == "colorist":
        plan = grade_production(production, picture_lock_approved=True, sound_approved=True)
        marry_preview(production, plan)
        _data_path, text_path = write_grade(plan, production)
        producer.ensure_artifact("grade-plan", "color/grade-plan.json", "grade-plan.schema.json")
        producer.ensure_artifact("grade-plan-notes", "color/grade-plan.md")
        if plan["render"]["status"] == "rendered" and plan["render"]["preview"]:
            producer.ensure_artifact("graded-preview", plan["render"]["preview"])
        _ensure_credit(producer, "Colorist", "Colorist")
        report = render_grade_report(plan)
    else:
        plan = mix_production(production, picture_lock_approved=True, sound_approved=True)
        marry_preview(production, plan)
        _data_path, text_path = write_mix(plan, production)
        producer.ensure_artifact("mix-plan", "color/mix-plan.json", "mix-plan.schema.json")
        producer.ensure_artifact("mix-plan-notes", "color/mix-plan.md")
        if plan["render"]["status"] == "rendered" and plan["render"]["mix"]:
            producer.ensure_artifact("final-mix", plan["render"]["mix"])
        _ensure_credit(producer, "Re-recording Mixer", "Re-recording Mixer")
        report = render_mix_report(plan)
    if plan["render"].get("married"):
        producer.ensure_artifact("married-preview", plan["render"]["married"])
    if producer.gate_decision("color-mix") == "approved":
        producer.run.data["notes"] = (
            "Color and mix were written again after Ron approved the color-mix gate. "
            "The approval still stands until Ron rejects it. Final delivery waits on that approval."
        )
        producer.run.save()
    else:
        producer.set_stage("color-mix", "waiting-for-review")
        producer.run.data["notes"] = (
            "The grade and the mix are waiting on Ron. "
            "Final delivery does not run until Ron approves the color-mix gate."
        )
        producer.run.save()
    return report + f"\nWrote {text_path}."


def _require_approvals(picture_lock_approved: bool, sound_approved: bool) -> None:
    missing = []
    if not picture_lock_approved:
        missing.append("the edit gate (picture lock)")
    if not sound_approved:
        missing.append("the sound gate")
    if missing:
        joined = " and ".join(missing)
        raise ColorMixError(f"Color and mix did not run. Ron has not approved {joined}.")


def _approval_line(ready: bool) -> str:
    if ready:
        return (
            "This plan is ready for the color-mix gate. It is not approved until Ron says so. "
            "Final delivery waits on that approval."
        )
    return (
        "This plan is not ready for the color-mix gate. "
        "Final delivery still waits until Ron approves it."
    )


def _budget(stage: str) -> dict:
    if stage == "editor":
        line = "The color grade is checked against the editor allocation. No new budget line was added."
    else:
        line = (
            "The mix is checked against the sound-designer allocation, which is the Sound line. "
            "No new budget line was added."
        )
    return {
        "stage": stage,
        "estimated_usd": None,
        "rate_status": "unknown",
        "note": (
            f"{line} No color or mix rate is on the rate card. "
            "A paid grade or a paid mix would be unknown, and this build does not call one. "
            "ffmpeg is local. Nothing was charged."
        ),
    }


def _load_cut(folder: Path) -> tuple[dict, str]:
    path = folder / "edit" / "picture-lock.json"
    if not path.is_file():
        raise ColorMixError(
            "No picture-lock file at edit/picture-lock.json. "
            "The cut is not locked, so color and mix did not run."
        )
    try:
        data = read_handoff(path, schema="edit-decision-list")
    except HandoffError as exc:
        raise ColorMixError(str(exc)) from exc
    if data.get("kind") != "picture-lock":
        raise ColorMixError("edit/picture-lock.json is not a picture-lock cut, so color and mix did not run.")
    if not data.get("events"):
        raise ColorMixError("The picture-lock cut has no shots, so color and mix did not run.")
    return data, "edit/picture-lock.json"


def _load_look(folder: Path) -> tuple[dict, str]:
    path = folder / "look" / "look.json"
    if not path.is_file():
        raise ColorMixError(
            "No look file at look/look.json. The grade is read from the production, so color did not run."
        )
    try:
        data = read_handoff(path, schema="look")
    except HandoffError as exc:
        raise ColorMixError(str(exc)) from exc
    return data, "look/look.json"


def _load_cue_sheet(folder: Path) -> tuple[dict, str]:
    path = folder / "sound" / "cue-sheet.json"
    if not path.is_file():
        raise ColorMixError(
            "No cue sheet at sound/cue-sheet.json. The mix is read from that sheet, so the mix did not run."
        )
    try:
        data = read_handoff(path, schema="cue-sheet")
    except HandoffError as exc:
        raise ColorMixError(str(exc)) from exc
    return data, "sound/cue-sheet.json"


def _load_optional(folder: Path, path: Path, schema: str) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, None
    try:
        data = read_handoff(path, schema=schema)
    except HandoffError as exc:
        raise ColorMixError(str(exc)) from exc
    return data, _relative(folder, path)


def _events(folder: Path, edl: dict) -> list[dict]:
    events = []
    for event in edl.get("events") or []:
        if not isinstance(event, dict) or not event.get("shot_id"):
            continue
        source = str(event.get("source_file") or "")
        path = (folder / source).resolve() if source else None
        events.append(
            {
                "shot_id": str(event["shot_id"]),
                "scene_id": str(event.get("scene_id") or "unassigned"),
                "source": path,
                "source_in": _number(event.get("source_in")) or 0.0,
                "duration": _number(event.get("duration_seconds")) or 0.0,
                "record_in": _number(event.get("record_in")) or 0.0,
            }
        )
    return events


def _look_reference(look: dict) -> dict:
    lighting = []
    for item in look.get("lighting") or []:
        if isinstance(item, dict) and str(item.get("description") or "").strip():
            lighting.append(str(item["description"]))
    palette = [str(item) for item in look.get("palette") or [] if str(item).strip()]
    return {
        "look_name": str(look.get("look_name") or "Unnamed look"),
        "summary": str(look.get("summary") or "The production names the look."),
        "palette": palette,
        "lighting": lighting,
    }


def _base_grade(look: dict, grade_file: dict | None) -> tuple[dict, list[str]]:
    """The whole-cut grade. Look numbers first, then a grade-file base, if one exists."""
    values = dict(_NEUTRAL)
    parts: list[str] = []
    look_grade = look.get("grade") if isinstance(look.get("grade"), dict) else None
    if _has_grade_values(look_grade):
        values = _overlay(values, look_grade)
        parts.append("look/look.json")
    file_base = (grade_file or {}).get("base") if isinstance((grade_file or {}).get("base"), dict) else None
    if _has_grade_values(file_base):
        values = _overlay(values, file_base)
        parts.append("look/grade.json")
    if not parts:
        parts.append("neutral")
    return values, parts


def _source_label(parts: list[str], grade_source: str | None) -> str:
    if parts == ["neutral"]:
        if grade_source:
            return "neutral. The look names the picture. It does not give grade numbers."
        return "neutral. The look names the picture. It does not give grade numbers."
    if parts == ["look/look.json", "look/grade.json"]:
        return "look/look.json and look/grade.json"
    return parts[-1] if parts[-1] != "neutral" else parts[0]


def _adjustments(events, look, grade_file, base) -> tuple[list[dict], list[dict]]:
    """One scene adjustment, stated once, plus a shot adjustment only where the production asks."""
    scenes: dict[str, dict] = {}
    shot_grades: dict[str, dict] = {}
    for source in (look.get("grade") if isinstance(look.get("grade"), dict) else None, grade_file):
        if not isinstance(source, dict):
            continue
        for item in source.get("scenes") or []:
            if isinstance(item, dict) and item.get("scene_id"):
                scenes[str(item["scene_id"])] = item
        for item in source.get("shots") or []:
            if isinstance(item, dict) and item.get("shot_id"):
                shot_grades[str(item["shot_id"])] = item

    shots_in_scene: dict[str, list[str]] = {}
    for event in events:
        shots_in_scene.setdefault(event["scene_id"], [])
        if event["shot_id"] not in shots_in_scene[event["scene_id"]]:
            shots_in_scene[event["scene_id"]].append(event["shot_id"])

    adjustments = []
    seen_scenes = set()
    seen_shots = set()
    for event in events:
        scene_id = event["scene_id"]
        if scene_id in scenes and scene_id not in seen_scenes:
            seen_scenes.add(scene_id)
            scene_grade = _overlay(base, scenes[scene_id])
            adjustments.append(
                _adjustment(
                    adjustment_id=_slug(f"scene-{scene_id}"),
                    scope="scene",
                    scene_id=scene_id,
                    shot_id=None,
                    shot_ids=shots_in_scene[scene_id],
                    grade=scene_grade,
                    note=str(scenes[scene_id].get("note") or "Scene grade, stated once."),
                )
            )
        shot_override = shot_grades.get(event["shot_id"])
        if shot_override and event["shot_id"] not in seen_shots:
            seen_shots.add(event["shot_id"])
            scene_grade = _overlay(base, scenes.get(scene_id))
            adjustments.append(
                _adjustment(
                    adjustment_id=_slug(f"shot-{event['shot_id']}"),
                    scope="shot",
                    scene_id=scene_id,
                    shot_id=event["shot_id"],
                    shot_ids=[event["shot_id"]],
                    grade=_overlay(scene_grade, shot_override),
                    note=str(shot_override.get("note") or "Shot grade."),
                )
            )

    applied = []
    for event in events:
        scene_grade = _overlay(base, scenes.get(event["scene_id"]))
        shot_override = shot_grades.get(event["shot_id"])
        if shot_override:
            resolved = _overlay(scene_grade, shot_override)
            adjustment_id = _slug(f"shot-{event['shot_id']}")
        elif event["scene_id"] in scenes:
            resolved = scene_grade
            adjustment_id = _slug(f"scene-{event['scene_id']}")
        else:
            resolved = dict(base)
            adjustment_id = "base"
        applied.append({"event": event, "adjustment_id": adjustment_id, "grade": resolved})
    return adjustments, applied


def _adjustment(*, adjustment_id, scope, scene_id, shot_id, shot_ids, grade, note) -> dict:
    return {
        "adjustment_id": adjustment_id,
        "scope": scope,
        "scene_id": scene_id,
        "shot_id": shot_id,
        "shot_ids": list(shot_ids),
        "time_of_day": grade["time_of_day"],
        "contrast": grade["contrast"],
        "saturation": grade["saturation"],
        "warmth": grade["warmth"],
        "brightness": grade["brightness"],
        "gamma": grade["gamma"],
        "note": note,
    }


def _public_applied(item: dict) -> dict:
    grade = item["grade"]
    event = item["event"]
    return {
        "shot_id": event["shot_id"],
        "scene_id": event["scene_id"],
        "adjustment_id": item["adjustment_id"],
        "time_of_day": grade["time_of_day"],
        "contrast": grade["contrast"],
        "saturation": grade["saturation"],
        "warmth": grade["warmth"],
        "brightness": grade["brightness"],
        "gamma": grade["gamma"],
    }


def _tolerance(grade_file: dict | None) -> tuple[dict, str]:
    raw = (grade_file or {}).get("consistency") if isinstance((grade_file or {}).get("consistency"), dict) else {}
    brightness = raw.get("brightness")
    color = raw.get("color")
    source = "look/grade.json" if brightness is not None or color is not None else "studio default"
    return (
        {
            "brightness": _clamp(brightness, 0.0, 1.0, _DEFAULT_BRIGHTNESS_TOLERANCE),
            "color": _clamp(color, 0.0, 1.0, _DEFAULT_COLOR_TOLERANCE),
        },
        source,
    )


def _resolve_lut(folder: Path, grade_file: dict | None) -> dict | None:
    raw = (grade_file or {}).get("lut") if grade_file else None
    if not raw:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "null":
        return None
    path = (folder / text).resolve()
    try:
        path.relative_to(folder.resolve())
    except ValueError:
        return None
    if path.suffix.lower() != ".cube" or not path.is_file():
        return None
    return {"path": path, "relative": _relative(folder, path)}


def _consistency(events, segments, tolerance) -> list[dict]:
    ffmpeg = shutil.which("ffmpeg")
    checks = []
    previous = None
    previous_measure = None
    for event in events:
        path = segments.get(event["shot_id"]) or event.get("source")
        measure = _measure_color(ffmpeg, path) if ffmpeg else None
        if previous is not None and previous["scene_id"] == event["scene_id"]:
            checks.append(_compare(previous, event, previous_measure, measure, tolerance))
        previous = event
        previous_measure = measure
    return checks


def _compare(previous, event, previous_measure, measure, tolerance) -> dict:
    row = {
        "shot_id": event["shot_id"],
        "previous_shot_id": previous["shot_id"],
        "scene_id": event["scene_id"],
        "status": "skipped",
        "kind": "unmeasured",
        "brightness_delta": None,
        "color_delta": None,
        "detail": (
            f"{previous['shot_id']} and {event['shot_id']} are adjacent in {event['scene_id']}. "
            "ffmpeg could not measure them, so this pair was not judged."
        ),
    }
    if not shutil.which("ffmpeg"):
        row["detail"] = (
            f"{previous['shot_id']} and {event['shot_id']} are adjacent in {event['scene_id']}. "
            "ffmpeg is not installed, so this pair was not judged."
        )
        return row
    if previous_measure is None or measure is None:
        return row
    brightness = abs(previous_measure[0] - measure[0])
    color = math.hypot(previous_measure[1] - measure[1], previous_measure[2] - measure[2])
    bright_flag = brightness > tolerance["brightness"]
    color_flag = color > tolerance["color"]
    row["brightness_delta"] = round(brightness, 4)
    row["color_delta"] = round(color, 4)
    if bright_flag and color_flag:
        row["status"] = "fail"
        row["kind"] = "both"
    elif bright_flag:
        row["status"] = "fail"
        row["kind"] = "brightness"
    elif color_flag:
        row["status"] = "fail"
        row["kind"] = "color"
    else:
        row["status"] = "pass"
        row["kind"] = "clear"
    if row["status"] == "fail":
        row["detail"] = (
            f"{previous['shot_id']} and {event['shot_id']} are adjacent in {event['scene_id']}. "
            f"Brightness differs by {row['brightness_delta']} and color by {row['color_delta']}. "
            f"The tolerance is {tolerance['brightness']} brightness and {tolerance['color']} color."
        )
    else:
        row["detail"] = (
            f"{previous['shot_id']} and {event['shot_id']} stay inside the tolerance for {event['scene_id']}."
        )
    return row


def _measure_color(ffmpeg: str | None, path: Path | None):
    if not ffmpeg or path is None or not Path(path).is_file():
        return None
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-i",
                str(path),
                "-vf",
                "signalstats,metadata=mode=print",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (completed.stderr or "") + "\n" + (completed.stdout or "")
    y_vals = _stat_values(text, "YAVG")
    u_vals = _stat_values(text, "UAVG")
    v_vals = _stat_values(text, "VAVG")
    count = min(len(y_vals), len(u_vals), len(v_vals))
    if count == 0:
        return None
    y_avg = sum(y_vals[:count]) / count
    u_avg = sum(u_vals[:count]) / count
    v_avg = sum(v_vals[:count]) / count
    scale = 255.0 if max(abs(y_avg), abs(u_avg), abs(v_avg)) > 1.5 else 1.0
    return (y_avg / scale, u_avg / scale, v_avg / scale)


def _render_grade(folder: Path, events, applied, lut) -> tuple[dict, dict]:
    empty = {"status": "skipped", "preview": None, "married": None, "note": ""}
    segments: dict[str, Path] = {}
    if not events:
        return {**empty, "note": "The cut has no shots, so the graded preview was not rendered."}, segments
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            **empty,
            "note": "ffmpeg is not installed, so the graded preview was not rendered. The grade plan is still written.",
        }, segments
    missing = [item["event"]["shot_id"] for item in applied if not item["event"]["source"] or not item["event"]["source"].is_file()]
    if missing:
        names = ", ".join(missing)
        return {
            **empty,
            "note": (
                f"These source files are not on disk, so the graded preview was not rendered: {names}. "
                "The grade plan is still written."
            ),
        }, segments
    work = folder / "color" / "preview-work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    preview = folder / "color" / "graded-preview.mp4"
    curves = _curves_filter(folder)
    try:
        pieces = []
        for index, item in enumerate(applied, start=1):
            segment = work / f"grade-{index:03d}.mp4"
            _grade_segment(ffmpeg, item["event"], item["grade"], lut, curves, segment)
            pieces.append(segment)
            segments[item["event"]["shot_id"]] = segment
        _concat(ffmpeg, pieces, preview)
    except ColorMixError as exc:
        return {
            "status": "failed",
            "preview": None,
            "married": None,
            "note": f"ffmpeg could not render the graded preview. The grade plan is still written. {exc}",
        }, segments
    tool = "the production LUT, then eq and colorbalance" if lut else "eq and colorbalance"
    if curves:
        tool += " and curves"
    return {
        "status": "rendered",
        "preview": "color/graded-preview.mp4",
        "married": None,
        "note": (
            f"A low-resolution graded preview was rendered with {tool}. "
            "A scene grade is stated once and applied to each shot in that scene."
        ),
    }, segments


def _curves_filter(folder: Path) -> str | None:
    path = folder / "look" / "grade.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    raw = str((data or {}).get("curves") or "").strip()
    if not raw or not re.fullmatch(r"[0-9./ ]+", raw):
        return None
    return f"curves=all='{raw}'"


def _grade_segment(ffmpeg, event, grade, lut, curves, dest: Path) -> None:
    filters = [_eq_and_balance(grade)]
    if curves:
        filters.append(curves)
    if lut:
        filters.append(_lut_filter(lut["path"]))
    filters.append(
        f"scale={_PREVIEW_SIZE}:force_original_aspect_ratio=decrease,"
        f"pad={_PREVIEW_SIZE}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )
    vf = ",".join(filters)
    source = event["source"]
    duration = event["duration"] if event["duration"] > 0 else 1.0
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
            vf,
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
            f"{event['source_in']:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vf",
            vf,
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


def _eq_and_balance(grade: dict) -> str:
    warmth = grade["warmth"]
    return (
        "eq="
        f"contrast={grade['contrast']:.4f}:"
        f"brightness={grade['brightness']:.4f}:"
        f"saturation={grade['saturation']:.4f}:"
        f"gamma={grade['gamma']:.4f},"
        "colorbalance="
        f"rm={warmth:.4f}:bm={-warmth:.4f}:rh={warmth * 0.6:.4f}:bh={-warmth * 0.6:.4f}"
    )


def _lut_filter(path: Path) -> str:
    escaped = str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"lut3d=file='{escaped}'"


def _concat(ffmpeg: str, segments: list[Path], dest: Path) -> None:
    listing = segments[0].parent / "concat.txt"
    lines = []
    for path in segments:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dest.parent.mkdir(parents=True, exist_ok=True)
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


def _levels(targets: dict | None) -> list[dict]:
    targets = targets or {}
    return [
        {"stem": "dialogue", "gain_db": _clamp(targets.get("dialogue_db"), -60.0, 12.0, _DEFAULT_DIALOGUE_DB), "priority": "dialogue"},
        {"stem": "effects", "gain_db": _clamp(targets.get("effects_db"), -60.0, 12.0, _DEFAULT_EFFECTS_DB), "priority": "bed"},
        {"stem": "music", "gain_db": _clamp(targets.get("music_db"), -60.0, 12.0, _DEFAULT_MUSIC_DB), "priority": "bed"},
    ]


def _ducking(sheet: dict, targets: dict | None) -> list[dict]:
    duck_db = _clamp((targets or {}).get("duck_db"), -40.0, 0.0, _DEFAULT_DUCK_DB)
    windows = []
    for cue in sheet.get("cues") or []:
        if not isinstance(cue, dict):
            continue
        if cue.get("type") != "dialogue" or cue.get("source") == "silence":
            continue
        start = _number(cue.get("start_seconds"))
        end = _number(cue.get("end_seconds"))
        cue_id = str(cue.get("cue_id") or "")
        if start is None or end is None or end <= start or not cue_id:
            continue
        windows.append((start, end, cue_id))
    rows = []
    for stem in ("effects", "music"):
        for start, end, cue_id in windows:
            rows.append(
                {
                    "stem": stem,
                    "under": "dialogue",
                    "cue_id": cue_id,
                    "duck_db": duck_db,
                    "start_seconds": round(start, 3),
                    "end_seconds": round(end, 3),
                }
            )
    return rows


def _fades(edl: dict, targets: dict | None) -> list[dict]:
    fade_seconds = _clamp((targets or {}).get("fade_seconds"), 0.0, 5.0, _DEFAULT_FADE_SECONDS)
    fades = []
    markers = [item for item in edl.get("scene_markers") or [] if isinstance(item, dict)]
    if markers:
        for marker in markers:
            moment = _number(marker.get("record_in")) or 0.0
            if moment <= 0.01:
                continue
            fades.append(
                {
                    "scene_id": str(marker.get("scene_id") or "scene"),
                    "time_seconds": round(moment, 3),
                    "fade_seconds": fade_seconds,
                    "kind": "scene-change",
                }
            )
        return fades
    previous = None
    for event in edl.get("events") or []:
        if not isinstance(event, dict):
            continue
        scene_id = str(event.get("scene_id") or "")
        if previous and scene_id and scene_id != previous:
            fades.append(
                {
                    "scene_id": scene_id,
                    "time_seconds": round(_number(event.get("record_in")) or 0.0, 3),
                    "fade_seconds": fade_seconds,
                    "kind": "scene-change",
                }
            )
        previous = scene_id or previous
    return fades


def _loudness_target(targets: dict | None, source: str | None) -> dict:
    targets = targets or {}
    if source and any(key in targets for key in ("integrated_lufs", "true_peak_dbtp", "tolerance_lufs", "standard")):
        standard = str(targets.get("standard") or _EBU_STANDARD)
        citation = str(targets.get("citation") or f"The production set this target in {source}.")
        return {
            "integrated_lufs": _clamp(targets.get("integrated_lufs"), -70.0, 0.0, _EBU_INTEGRATED_LUFS),
            "true_peak_dbtp": _clamp(targets.get("true_peak_dbtp"), -20.0, 0.0, _EBU_TRUE_PEAK_DBTP),
            "tolerance_lufs": _clamp(targets.get("tolerance_lufs"), 0.0, 20.0, _EBU_TOLERANCE_LUFS),
            "standard": standard,
            "citation": citation,
            "source": source,
        }
    return {
        "integrated_lufs": _EBU_INTEGRATED_LUFS,
        "true_peak_dbtp": _EBU_TRUE_PEAK_DBTP,
        "tolerance_lufs": _EBU_TOLERANCE_LUFS,
        "standard": _EBU_STANDARD,
        "citation": _EBU_CITATION,
        "source": _EBU_STANDARD,
    }


def _stem_files(folder: Path, sheet: dict) -> list[dict]:
    render = sheet.get("render") if isinstance(sheet.get("render"), dict) else {}
    named = {
        "dialogue": render.get("dialogue") or "sound/stems/dialogue.wav",
        "effects": render.get("effects") or "sound/stems/effects.wav",
        "music": render.get("music") or "sound/stems/music.wav",
    }
    stems = []
    for stem, relative in named.items():
        text = str(relative)
        path = folder / text
        stems.append({"stem": stem, "relative": text, "path": path})
    return stems


def _render_mix(folder, stems, levels, ducking, fades, runtime) -> dict:
    empty = {"status": "skipped", "mix": None, "married": None, "note": ""}
    if runtime <= 0:
        return {**empty, "note": "The cut has no length, so the mix was not rendered. The mix plan is still written."}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            **empty,
            "note": "ffmpeg is not installed, so the mix was not rendered. The mix plan is still written.",
        }
    present = [item for item in stems if item["path"].is_file()]
    if not present:
        return {
            **empty,
            "note": "No stems were on disk, so the mix was not rendered. The mix plan is still written.",
        }
    dest = folder / "color" / "mix.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        _mix_stems(ffmpeg, present, levels, ducking, fades, runtime, dest)
    except ColorMixError as exc:
        return {
            "status": "failed",
            "mix": None,
            "married": None,
            "note": f"ffmpeg could not render the mix. The mix plan is still written. {exc}",
        }
    missing = [item["stem"] for item in stems if item not in present]
    note = "The mix was rendered from the stems. Dialogue stays in front. Music and effects duck under dialogue."
    if missing:
        note += " Missing stems were left out: " + ", ".join(missing) + "."
    if fades:
        note += " Scene changes fade."
    return {"status": "rendered", "mix": "color/mix.wav", "married": None, "note": note}


def _mix_stems(ffmpeg, stems, levels, ducking, fades, runtime, dest: Path) -> None:
    by_stem = {item["stem"]: item["gain_db"] for item in levels}
    command = [ffmpeg, "-y"]
    filters = []
    labels = []
    for index, item in enumerate(stems):
        command.extend(["-i", str(item["path"])])
        windows = [
            (row["start_seconds"], row["end_seconds"])
            for row in ducking
            if row["stem"] == item["stem"]
        ]
        duck_db = next((row["duck_db"] for row in ducking if row["stem"] == item["stem"]), _DEFAULT_DUCK_DB)
        gain = _ffmpeg_expr(_gain_expression(by_stem.get(item["stem"], 0.0), windows, duck_db, fades))
        label = f"s{index}"
        filters.append(f"[{index}:a]volume='{gain}':eval=frame[{label}]")
        labels.append(f"[{label}]")
    count = len(labels)
    filters.append("".join(labels) + f"amix=inputs={count}:duration=longest:dropout_transition=0:normalize=0[mix]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[mix]",
            "-t",
            f"{runtime:.3f}",
            "-ac",
            "1",
            "-ar",
            str(_SAMPLE_RATE),
            str(dest),
        ]
    )
    _run_ffmpeg(command)


def _gain_expression(base_db: float, windows, duck_db: float, fades) -> str:
    full = 10 ** (base_db / 20.0)
    ducked = 10 ** ((base_db + duck_db) / 20.0)
    gain = f"{full:.6f}"
    for start, end in windows:
        gain = f"if(between(t,{start:.3f},{end:.3f}),{ducked:.6f},{gain})"
    fade_factor = "1"
    for fade in fades:
        moment = fade["time_seconds"]
        length = fade["fade_seconds"]
        if length <= 0 or moment <= 0:
            continue
        start = max(0.0, moment - length)
        fade_factor = (
            f"({fade_factor})*if(between(t,{start:.3f},{moment:.3f}),({moment:.3f}-t)/{length:.3f},"
            f"if(between(t,{moment:.3f},{moment + length:.3f}),(t-{moment:.3f})/{length:.3f},1))"
        )
    if fade_factor == "1":
        return gain
    return f"({gain})*({fade_factor})"


def _measure_mix(path: Path | None, loudness: dict) -> dict:
    skipped = {
        "status": "skipped",
        "meter": None,
        "integrated_lufs": None,
        "true_peak_dbtp": None,
        "within_target": None,
        "flags": [],
        "note": "The mix was not rendered, so loudness was not measured. The mix plan is still written.",
    }
    if path is None or not path.is_file():
        return skipped
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        skipped["note"] = "ffmpeg is not installed, so loudness was not measured. The mix plan is still written."
        return skipped
    integrated, peak, meter = _read_loudness(ffmpeg, path)
    if integrated is None and peak is None:
        return {
            "status": "failed",
            "meter": None,
            "integrated_lufs": None,
            "true_peak_dbtp": None,
            "within_target": None,
            "flags": [],
            "note": "ffmpeg could not read integrated loudness or true peak. The mix plan is still written.",
        }
    flags = []
    if integrated is not None and abs(integrated - loudness["integrated_lufs"]) > loudness["tolerance_lufs"]:
        flags.append(
            {
                "kind": "integrated-loudness",
                "status": "fail",
                "detail": (
                    f"Integrated loudness is {integrated:.1f} LUFS. "
                    f"The target is {loudness['integrated_lufs']:.1f} LUFS, "
                    f"plus or minus {loudness['tolerance_lufs']:.1f}."
                ),
            }
        )
    if peak is not None and peak > loudness["true_peak_dbtp"] + 0.05:
        flags.append(
            {
                "kind": "true-peak",
                "status": "fail",
                "detail": (
                    f"True peak is {peak:.1f} dBTP. "
                    f"The limit is {loudness['true_peak_dbtp']:.1f} dBTP."
                ),
            }
        )
    within = not flags
    if within:
        note = (
            f"Integrated loudness is {integrated if integrated is not None else 'unread'} LUFS "
            f"and true peak is {peak if peak is not None else 'unread'} dBTP, inside the target. "
            f"Measured with {meter}."
        )
    else:
        note = f"The mix is outside the loudness target. Measured with {meter}."
    return {
        "status": "measured",
        "meter": meter,
        "integrated_lufs": None if integrated is None else round(integrated, 2),
        "true_peak_dbtp": None if peak is None else round(peak, 2),
        "within_target": within,
        "flags": flags,
        "note": note,
    }


def _read_loudness(ffmpeg: str, path: Path):
    integrated, peak = _read_ebur128(ffmpeg, path)
    if integrated is not None or peak is not None:
        return integrated, peak, "ebur128"
    integrated, peak = _read_loudnorm(ffmpeg, path)
    if integrated is not None or peak is not None:
        return integrated, peak, "loudnorm"
    return None, None, None


def _read_ebur128(ffmpeg: str, path: Path):
    try:
        completed = subprocess.run(
            [ffmpeg, "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    text = completed.stderr or ""
    summary = text.split("Summary:")[-1] if "Summary:" in text else ""
    if not summary:
        return None, None
    integrated = _last_float(r"I:\s*(-?[0-9.]+)\s*LUFS", summary)
    peak = _last_float(r"Peak:\s*(-?[0-9.]+)\s*dB", summary)
    return integrated, peak


def _read_loudnorm(ffmpeg: str, path: Path):
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-i",
                str(path),
                "-af",
                "loudnorm=I=-23:TP=-1:LRA=11:print_format=json",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    text = completed.stderr or ""
    match = None
    for candidate in re.finditer(r"\{[^{}]*\"input_i\"[^{}]*\}", text, re.DOTALL):
        match = candidate
    if match is None:
        return None, None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None, None
    return _signed(data.get("input_i")), _signed(data.get("input_tp"))


def _stamp_married(folder: Path, filename: str, schema: str, relative: str) -> None:
    path = folder / "color" / filename
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict) or "render" not in data:
        return
    data["render"]["married"] = relative
    note = str(data["render"].get("note") or "")
    if "married" not in note.casefold():
        data["render"]["note"] = note.rstrip() + " The graded picture and the mix were married into a low-resolution preview."
    try:
        write_handoff(path, data, schema=schema)
    except HandoffError:
        return
    text_path = path.with_suffix(".md")
    if filename == "grade-plan.json":
        text_path.write_text(render_grade_report(data), encoding="utf-8")
    elif filename == "mix-plan.json":
        text_path.write_text(render_mix_report(data), encoding="utf-8")


def _stat_values(text: str, name: str) -> list[float]:
    values = []
    for raw in re.findall(rf"signalstats\.{name}=([0-9.+-]+)", text):
        number = _signed(raw)
        if number is not None:
            values.append(number)
    return values


def _ffmpeg_expr(expr: str) -> str:
    """Escape commas so ffmpeg treats the expression as one filter argument."""
    return expr.replace(",", "\\,")


def _has_grade_values(grade: dict | None) -> bool:
    if not isinstance(grade, dict):
        return False
    return any(grade.get(key) not in (None, "") for key in _GRADE_KEYS)


def _overlay(base: dict, extra: dict | None) -> dict:
    merged = {
        "time_of_day": base["time_of_day"],
        "contrast": base["contrast"],
        "saturation": base["saturation"],
        "warmth": base["warmth"],
        "brightness": base["brightness"],
        "gamma": base["gamma"],
    }
    if not isinstance(extra, dict):
        return merged
    if str(extra.get("time_of_day") or "").strip():
        merged["time_of_day"] = str(extra["time_of_day"]).strip()
    merged["contrast"] = _clamp(extra.get("contrast"), 0.0, 3.0, merged["contrast"])
    merged["saturation"] = _clamp(extra.get("saturation"), 0.0, 3.0, merged["saturation"])
    merged["warmth"] = _clamp(extra.get("warmth"), -1.0, 1.0, merged["warmth"])
    merged["brightness"] = _clamp(extra.get("brightness"), -1.0, 1.0, merged["brightness"])
    merged["gamma"] = _clamp(extra.get("gamma"), 0.1, 4.0, merged["gamma"])
    return merged


def _clamp(value, low: float, high: float, default: float) -> float:
    number = _number(value)
    if number is None:
        return round(float(default), 4)
    return round(max(low, min(high, number)), 4)


def _model(role: str, purpose: str) -> str:
    try:
        return str(resolve_model(role, purpose=purpose).get("model") or "")
    except ModelRoutingError:
        return ""


def _ensure_credit(producer, role: str, name: str) -> None:
    have = {item["role"] for item in producer.record["credits"]}
    if role in have:
        return
    producer.record["credits"].append({"role": role, "name": name})
    producer._save_record()


def _relative(folder: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(folder.resolve()))
    except ValueError:
        return path.name


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", value.casefold()).strip("-")
    return cleaned or "grade"


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _signed(value):
    if value is None:
        return None
    text = str(value).strip().replace("−", "-")
    if text in {"", "-inf", "inf", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _last_float(pattern: str, text: str):
    found = None
    for match in re.finditer(pattern, text):
        found = _signed(match.group(1))
    return found


def _run_ffmpeg(command: list[str]) -> None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ColorMixError("ffmpeg did not finish.") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or "").strip().splitlines()
        detail = tail[-1] if tail else "ffmpeg failed."
        raise ColorMixError(detail)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
