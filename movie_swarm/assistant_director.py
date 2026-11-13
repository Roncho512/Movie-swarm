"""Assistant Director: a shooting schedule and a call sheet.

Shots stay in storyboard order. They are grouped by location, then by setup.
Cast and props are the ones the shot list already names. A beat from the
Stunt Coordinator is flagged on the shot it matches, with that beat's safety line.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.gaffer import plan_path
from movie_swarm.mentions import mentioned, prop_labels
from movie_swarm.prep_inputs import load_scenes, load_shots, scene_for_shot
from movie_swarm.prop_master import locked_path as props_locked_path
from movie_swarm.previs_common import (
    PrevisError,
    approved_treatment,
    load_optional,
    model_name,
    now,
    save_pair,
    source_blob,
    system_prompt,
    try_model_json,
)
from movie_swarm.stunts import breakdown_path


def schedule_path(production_dir: Path) -> Path:
    return production_dir / "schedule" / "shooting-schedule.json"


def build_schedule(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    shots, shot_source = load_shots(production_dir)
    scenes, scene_source = load_scenes(production_dir, treatment)
    stunts = _stunts(production_dir)
    gaffer = load_optional(plan_path(production_dir), "lighting-plan")
    props = _hero_props(production_dir)
    offline = _offline(
        production_dir,
        treatment,
        shots,
        shot_source,
        scenes,
        scene_source,
        stunts,
        gaffer,
        props,
    )
    drafted = _from_model(llm, offline)
    document = drafted or offline
    save_pair(schedule_path(production_dir), document, "shooting-schedule", _markdown(document))
    return document


def _stunts(production_dir: Path) -> dict | None:
    path = breakdown_path(production_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrevisError(f"stunts/action-breakdown.json is not valid JSON. {exc}") from exc
    return data if isinstance(data, dict) else None


def _hero_props(production_dir: Path) -> list[dict]:
    path = props_locked_path(production_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    return [prop for prop in data.get("props") or [] if isinstance(prop, dict)]


def _offline(production_dir, treatment, shots, shot_source, scenes, scene_source, stunts, gaffer, props) -> dict:
    ordered = sorted(shots, key=lambda shot: (shot["order"], shot["shot_id"]))
    lighting = {}
    if gaffer:
        for scene in gaffer.get("scenes") or []:
            if isinstance(scene, dict) and scene.get("scene_id"):
                lighting[scene["scene_id"]] = scene
    safety_rows = []
    planned = []
    for shot in ordered:
        scene = scene_for_shot(shot, scenes)
        flags = _safety_flags(shot, stunts)
        safety_rows.extend(flags)
        cast = _cast(shot, treatment)
        planned.append(
            {
                "shot": shot,
                "scene": scene,
                "cast": cast,
                "props": _prop_names(shot, props),
                "safety": flags[0] if flags else None,
                "lighting_id": _lighting_id(lighting.get(shot.get("scene_id"))),
            }
        )
    days = _days(planned)
    _cover_every_beat(safety_rows, stunts)
    source = {
        "shots": shot_source,
        "scenes": scene_source,
        "stunts": "stunts/action-breakdown.json" if stunts else None,
        "lighting": "lighting/lighting-plan.json" if gaffer else None,
    }
    note = (
        "Call sheet for production. Shot order is the storyboard. "
        "Locations and setups are grouped. Stunt beats are flagged from the action breakdown."
    )
    if stunts is None:
        note += " No action breakdown was found, so no safety beat was invented."
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "kind": "shooting-schedule",
        "source": source,
        "days": days,
        "safety": safety_rows,
        "shot_count": len(ordered),
        "draft_method": "offline-deterministic",
        "model": model_name("assistant-director", "schedule"),
        "note": note,
        "created_at": now(),
    }


def _lighting_id(scene: dict | None) -> str:
    if not scene:
        return "not-named"
    practicals = str(scene.get("practicals") or "")
    if practicals and practicals != "not named":
        return "practical"
    if str(scene.get("key") or "") not in {"", "not named"}:
        return "key"
    return "not-named"


def _prop_names(shot: dict, props: list[dict]) -> list[str]:
    """Hero prop names for this shot, then any other prop the shot list already named."""
    raw = [str(item).strip() for item in shot.get("props") or [] if str(item).strip()]
    blob = " ".join(part for part in (shot.get("text") or "", *raw) if part)
    named = []
    used = set()
    for prop in props:
        labels = prop_labels(prop)
        if not labels or not mentioned(blob, labels):
            continue
        name = str(prop.get("name") or prop.get("prop_id") or "").strip()
        if name and name not in named:
            named.append(name)
        used.add(str(prop.get("prop_id") or "").casefold())
        used.add(name.casefold())
    for item in raw:
        if item.casefold() in used:
            continue
        if any(item.casefold().startswith(token) for token in used if token):
            continue
        if item not in named:
            named.append(item)
    return named


def _cast(shot: dict, treatment: dict) -> list[str]:
    names = list(shot.get("characters") or [])
    if names:
        return names
    text = shot.get("text") or ""
    found = []
    for person in treatment.get("characters") or []:
        if not isinstance(person, dict):
            continue
        name = str(person.get("name") or "")
        if len(name) >= 2 and name.casefold() in text.casefold() and name not in found:
            found.append(name)
    return found


def _days(planned: list[dict]) -> list[dict]:
    day_buckets: dict[str, dict] = {}
    for item in planned:
        scene = item["scene"] or {}
        location = scene.get("location") or "not named"
        time_of_day = scene.get("time_of_day") or "not named"
        int_ext = scene.get("int_ext") or "not named"
        day_key = location.casefold()
        day = day_buckets.get(day_key)
        if day is None:
            day = {
                "location": location,
                "int_ext": int_ext,
                "time_of_day": time_of_day,
                "setups": {},
            }
            day_buckets[day_key] = day
        scene_id = (scene.get("scene_id") if scene else None) or item["shot"]["scene_id"] or "unassigned"
        setup_key = f"{scene_id}|{item['lighting_id']}|{time_of_day.casefold()}"
        setup = day["setups"].get(setup_key)
        if setup is None:
            setup = {
                "scene_ids": [],
                "lighting_setup": item["lighting_id"],
                "time_of_day": time_of_day,
                "cast": [],
                "props": [],
                "shots": [],
            }
            day["setups"][setup_key] = setup
        if scene_id not in setup["scene_ids"]:
            setup["scene_ids"].append(scene_id)
        for name in item["cast"]:
            if name not in setup["cast"]:
                setup["cast"].append(name)
        for prop in item["props"]:
            if prop not in setup["props"]:
                setup["props"].append(prop)
        shot_row = {
            "order": item["shot"]["order"],
            "shot_id": item["shot"]["shot_id"],
            "scene_id": scene_id,
            "cast": item["cast"],
            "props": item["props"],
            "safety": item["safety"] is not None,
        }
        setup["shots"].append(shot_row)
    days = []
    for index, day in enumerate(day_buckets.values(), start=1):
        setups = []
        for setup_index, setup in enumerate(day["setups"].values(), start=1):
            setups.append(
                {
                    "setup_id": f"setup-{setup_index:03d}",
                    "scene_ids": setup["scene_ids"],
                    "lighting_setup": setup["lighting_setup"],
                    "time_of_day": setup["time_of_day"],
                    "cast": setup["cast"],
                    "props": setup["props"],
                    "shots": setup["shots"],
                }
            )
        days.append(
            {
                "day_id": f"day-{index:03d}",
                "location": day["location"],
                "int_ext": day["int_ext"],
                "time_of_day": day["time_of_day"],
                "setups": setups,
            }
        )
    return days


def _cover_every_beat(safety_rows: list[dict], stunts: dict | None) -> None:
    """Every stunt beat is on the safety list, even when no shot text overlaps it."""
    if not stunts:
        return
    present = {str(row.get("beat_id") or "") for row in safety_rows}
    policy = str(stunts.get("safety_policy") or "").strip()
    for beat in stunts.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        if not beat_id or beat_id in present:
            continue
        stunt_shot = ""
        plausible = True
        for stunt_shot_row in beat.get("shots") or []:
            if not isinstance(stunt_shot_row, dict):
                continue
            stunt_shot = stunt_shot or str(stunt_shot_row.get("shot_id") or "")
            if not stunt_shot_row.get("plausible", True):
                plausible = False
        safety_rows.append(
            {
                "shot_id": stunt_shot or beat_id,
                "beat_id": beat_id,
                "stunt_shot_id": stunt_shot,
                "plausible": plausible,
                "note": _beat_safety_line(beat, policy),
            }
        )
        present.add(beat_id)


def _beat_safety_line(beat: dict, policy: str) -> str:
    """The full safety sentence from the beat, or the stunt rules when the beat has none."""
    lines = []
    for shot in beat.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        text = " ".join(str(shot.get("safety") or "").split()).strip()
        if text and text not in lines:
            lines.append(text)
    line = lines[0] if lines else policy
    if not line:
        return "No special safety needs, per stunt rules."
    if "no special safety" in line.casefold():
        return "No special safety needs, per stunt rules."
    if line[-1] not in ".!?":
        line += "."
    return line


def _safety_flags(shot: dict, stunts: dict | None) -> list[dict]:
    if not stunts:
        return []
    text = shot.get("text") or ""
    flags = []
    for beat in stunts.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        for stunt_shot in beat.get("shots") or []:
            if not isinstance(stunt_shot, dict):
                continue
            action = str(stunt_shot.get("action") or "")
            if not _overlaps(text, action):
                continue
            flags.append(
                {
                    "shot_id": shot["shot_id"],
                    "beat_id": str(beat.get("beat_id") or ""),
                    "stunt_shot_id": str(stunt_shot.get("shot_id") or ""),
                    "plausible": bool(stunt_shot.get("plausible", True)),
                    "note": str(stunt_shot.get("safety") or stunts.get("safety_policy") or ""),
                }
            )
    return flags


def _overlaps(shot_text: str, action: str) -> bool:
    left = " ".join(shot_text.casefold().split())
    right = " ".join(action.casefold().split())
    if len(right) >= 12 and (right in left or left in right):
        return True
    right_words = right.split()
    if len(right_words) < 4:
        return False
    for size in range(4, len(right_words) + 1):
        for start in range(0, len(right_words) - size + 1):
            phrase = " ".join(right_words[start : start + size])
            if phrase in left:
                return True
    return False


def _from_model(llm, offline) -> dict | None:
    if llm is None:
        return None
    drafted = try_model_json(
        llm,
        role="assistant-director",
        purpose="schedule",
        system=system_prompt(
            "You are the Assistant Director. Rewrite the note only. Do not change the schedule. "
            "Return {\"note\": \"...\"}."
        ),
        user=source_blob(offline.get("note")),
    )
    if not drafted:
        return None
    text = drafted.get("note")
    if not isinstance(text, str) or not text.strip():
        return None
    document = dict(offline)
    document["note"] = text.strip()
    document["draft_method"] = "model"
    return document


def _markdown(document: dict) -> str:
    lines = ["# Shooting schedule", "", document.get("note") or "", ""]
    for day in document.get("days") or []:
        lines.append(f"## {day['day_id']} — {day['int_ext']} {day['location']} — {day['time_of_day']}")
        lines.append("")
        for setup in day.get("setups") or []:
            lines.append(f"### {setup['setup_id']}")
            lines.append("")
            if setup.get("cast"):
                lines.append("Cast: " + ", ".join(setup["cast"]))
            if setup.get("props"):
                lines.append("Props: " + ", ".join(setup["props"]))
            for shot in setup.get("shots") or []:
                mark = " Safety." if shot.get("safety") else ""
                lines.append(f"- {shot['order']}. {shot['shot_id']}{mark}")
            lines.append("")
    safety_by_shot = {}
    for item in document.get("safety") or []:
        safety_by_shot.setdefault(item["shot_id"], str(item.get("note") or "").strip())
    if document.get("safety"):
        lines.append("## Safety")
        lines.append("")
        for item in document["safety"]:
            lines.append(f"- {item['shot_id']} ({item['beat_id']}): {item['note']}")
        lines.append("")
    # Rewrite shot lines that only said "Safety." as the stunt rule in a full sentence.
    rewritten = []
    for line in lines:
        if line.startswith("- ") and line.endswith(" Safety."):
            body = line[: -len(" Safety.")]
            shot_id = body.split(". ", 1)[-1].strip()
            sentence = safety_by_shot.get(shot_id) or "Follow the stunt safety rules for this beat."
            if sentence and sentence[-1] not in ".!?":
                sentence += "."
            rewritten.append(f"{body}. {sentence}")
        else:
            rewritten.append(line)
    return "\n".join(rewritten).rstrip() + "\n"
