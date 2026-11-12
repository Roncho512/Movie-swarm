"""Read the shot list and the scenes a later prep role needs.

The words come from the production. This module does not name a film.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff
from movie_swarm.previs_common import PrevisError


_HEADING = re.compile(
    r"^(?P<int_ext>INT\.?/EXT\.?|EXT\.?/INT\.?|I/E\.?|INT\.?|EXT\.?)\s+(?P<rest>.+)$",
    re.I,
)

# A heading that means "same time as the previous scene", not a new time of day.
_CARRY_TIMES = (
    "moments later",
    "a moment later",
    "continuous action",
    "continuous",
    "same time",
    "same",
    "later",
)

# Longer phrases first so "late afternoon" is not read as "day".
_CONCRETE_TIMES = (
    "late afternoon",
    "early afternoon",
    "late morning",
    "early morning",
    "late night",
    "golden hour",
    "blue hour",
    "magic hour",
    "pre-dusk",
    "pre dusk",
    "afternoon",
    "morning",
    "evening",
    "sunrise",
    "sunset",
    "twilight",
    "midnight",
    "night",
    "dawn",
    "dusk",
    "noon",
    "day",
)


def load_shots(production_dir: Path) -> tuple[list[dict], str]:
    """Normalized shots, and the file they came from.

    The storyboard shot list wins. A production shot list is the fallback.
    A list marked superseded is not a source for later stages.
    """
    folder = Path(production_dir)
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = folder / relative
        if not path.is_file():
            continue
        data = _read_json(path, relative)
        if data.get("superseded") is True:
            continue
        shots = [_shot(item, index) for index, item in enumerate(data.get("shots") or [], start=1) if isinstance(item, dict)]
        shots = [shot for shot in shots if shot["shot_id"]]
        if shots:
            return shots, relative
    raise PrevisError(
        "No shot list. Write the storyboard, or add shot-lists/shot-list.json, before this call."
    )


def load_scenes(production_dir: Path, treatment: dict) -> tuple[list[dict], str]:
    """Scenes from the scene manifest when the production has one, otherwise the treatment."""
    folder = Path(production_dir)
    path = folder / "scene-manifest" / "scene-manifest.json"
    if path.is_file():
        try:
            data = read_handoff(path, schema="scene-manifest")
        except HandoffError as exc:
            raise PrevisError(str(exc)) from exc
        scenes = [_manifest_scene(item, index) for index, item in enumerate(data.get("scenes") or [], start=1)]
        if scenes:
            carry_scene_times(scenes)
            return scenes, "scene-manifest/scene-manifest.json"
    scenes = []
    for index, scene in enumerate(treatment.get("scenes") or [], start=1):
        if isinstance(scene, dict):
            scenes.append(_treatment_scene(scene, index))
    carry_scene_times(scenes)
    return scenes, "treatment/treatment.json"


def scene_for_shot(shot: dict, scenes: list[dict]) -> dict | None:
    scene_id = shot.get("scene_id") or ""
    for scene in scenes:
        if scene["scene_id"] == scene_id:
            return scene
    number = shot.get("scene_number")
    if number is None:
        return None
    for scene in scenes:
        if scene.get("scene_number") == number:
            return scene
    return None


def parse_heading(heading: str) -> dict:
    """Split a slugline into interior/exterior, place, and time.

    The time of day is the last segment. Earlier segments stay with the place.
    ``LATE AFTERNOON`` is a time. ``MOMENTS LATER`` and ``CONTINUOUS`` are not a
    new time; ``carry_scene_times`` keeps the previous one.
    """
    text = " ".join(str(heading or "").split())
    match = _HEADING.match(text)
    if not match:
        place = text or "not named"
        return {"int_ext": "not named", "location": place, "time_of_day": "not named"}
    int_ext = match.group("int_ext").upper().rstrip(".")
    pieces = [part.strip() for part in re.split(r"\s+-\s+", match.group("rest")) if part.strip()]
    if len(pieces) >= 2:
        location = " - ".join(pieces[:-1]) or "not named"
        time_of_day = pieces[-1]
    elif pieces:
        location = pieces[0]
        time_of_day = "not named"
    else:
        location = "not named"
        time_of_day = "not named"
    return {"int_ext": int_ext, "location": location, "time_of_day": time_of_day}


def is_carry_time(text: str) -> bool:
    """True for MOMENTS LATER, CONTINUOUS, and the other 'same time' headings."""
    folded = " ".join(str(text or "").casefold().split())
    if not folded or folded == "not named":
        return False
    last = folded.split(" - ")[-1].strip()
    for phrase in _CARRY_TIMES:
        if last == phrase or last.endswith(" " + phrase):
            return True
    return False


def concrete_time(text: str) -> str:
    """The time-of-day words in text, in the text's own spelling. Empty when there are none."""
    raw = " ".join(str(text or "").split())
    folded = raw.casefold()
    if not folded or folded == "not named" or is_carry_time(raw):
        return ""
    for phrase in _CONCRETE_TIMES:
        match = re.search(rf"\b{re.escape(phrase)}\b", raw, re.I)
        if match:
            return match.group(0)
    return ""


def carry_scene_times(scenes: list[dict]) -> None:
    """Fill MOMENTS LATER and CONTINUOUS from the previous concrete time.

    A scene that already names a concrete time keeps that wording. A heading
    that only says the time continues is not left as ``not named``.
    """
    previous = ""
    for scene in scenes:
        heading_time = parse_heading(scene.get("heading") or "")["time_of_day"]
        stated = str(scene.get("time_of_day") or "not named")
        stated_concrete = concrete_time(stated)
        heading_concrete = concrete_time(heading_time)
        if stated_concrete and not is_carry_time(stated):
            chosen = stated
        elif is_carry_time(heading_time) or is_carry_time(stated):
            chosen = previous or heading_concrete or stated_concrete or "not named"
        elif heading_concrete:
            chosen = heading_time if heading_time.casefold() == heading_concrete.casefold() else heading_concrete
        elif heading_time not in {"", "not named"}:
            chosen = heading_time
        else:
            chosen = previous or "not named"
        scene["time_of_day"] = chosen
        if concrete_time(chosen) and not is_carry_time(chosen):
            previous = chosen


def mark_superseded_shot_list(production_dir: Path) -> dict | None:
    """Mark ``shot-lists/shot-list.json`` when the storyboard list is the one to use.

    The older file is kept. A field is written on it, or a sidecar note when it
    is not JSON. Nothing is deleted. Returns the skip record, or None.
    """
    folder = Path(production_dir)
    current = folder / "storyboard" / "shot-list.json"
    older = folder / "shot-lists" / "shot-list.json"
    if not current.is_file() or not older.is_file():
        return None
    marked = _storyboard_marks_shot_list(folder)
    newer = current.stat().st_mtime >= older.stat().st_mtime
    if not marked and not newer:
        return None
    reason = (
        "Superseded by storyboard/shot-list.json. "
        "This older list is not checked for drift and is not sent to generation."
    )
    record = {"path": "shot-lists/shot-list.json", "reason": reason}
    try:
        payload = json.loads(older.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        sidecar = older.with_name("shot-list.superseded.txt")
        sidecar.write_text(reason + "\n", encoding="utf-8")
        record["note"] = "shot-lists/shot-list.superseded.txt"
        return record
    if not isinstance(payload, dict):
        return None
    if payload.get("superseded") is True and payload.get("superseded_reason") == reason:
        return record
    payload["superseded"] = True
    payload["superseded_by"] = "storyboard/shot-list.json"
    payload["superseded_reason"] = reason
    older.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return record


def _storyboard_marks_shot_list(production_dir: Path) -> bool:
    path = production_dir / "storyboard" / "storyboard.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    listed = str(data.get("shot_list_path") or "").replace("\\", "/")
    return listed.endswith("storyboard/shot-list.json")


def _shot(shot: dict, index: int) -> dict:
    shot_id = str(shot.get("shot_id") or "")
    scene_number = shot.get("scene_number")
    scene_id = str(shot.get("scene_id") or "")
    if not scene_id and scene_number is not None:
        try:
            scene_id = f"s{int(scene_number):02d}"
        except (TypeError, ValueError):
            scene_id = ""
    if not scene_id and "-sh" in shot_id:
        scene_id = shot_id.split("-sh")[0]
    order = shot.get("sequence_position") or shot.get("order") or index
    try:
        order = int(order)
    except (TypeError, ValueError):
        order = index
    characters = []
    for item in shot.get("characters_in_shot") or shot.get("characters") or []:
        if isinstance(item, str) and item.strip():
            characters.append(item.strip())
        elif isinstance(item, dict) and item.get("name"):
            characters.append(str(item["name"]))
    props = []
    for item in shot.get("props_in_shot") or shot.get("props_in_frame") or shot.get("props") or []:
        if isinstance(item, str) and item.strip():
            props.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("prop_id") or item.get("name") or ""
            note = item.get("visibility_note") or ""
            text = str(label)
            if note:
                text = f"{text}: {note}".strip(": ")
            if text:
                props.append(text)
    description = str(shot.get("description") or "")
    prompt = str(shot.get("generation_prompt") or shot.get("prompt") or "")
    continuity = str(shot.get("continuity_notes") or "")
    color = str(shot.get("color_notes") or "")
    movement = str(shot.get("camera_movement") or "")
    text = " ".join(part for part in (description, prompt, continuity, color, movement) if part)
    return {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "scene_number": scene_number,
        "order": order,
        "shot_type": str(shot.get("shot_type") or ""),
        "description": description,
        "prompt": prompt,
        "continuity_notes": continuity,
        "color_notes": color,
        "camera_movement": movement,
        "characters": characters,
        "props": props,
        "text": text,
    }


def _treatment_scene(scene: dict, index: int) -> dict:
    scene_id = str(scene.get("scene_id") or f"s{index:02d}")
    heading = str(scene.get("heading") or "")
    parsed = parse_heading(heading)
    text = " ".join(part for part in (heading, scene.get("what_happens")) if part)
    return {
        "scene_id": scene_id,
        "scene_number": index,
        "heading": heading,
        "location": parsed["location"],
        "int_ext": parsed["int_ext"],
        "time_of_day": parsed["time_of_day"],
        "text": text,
    }


def _manifest_scene(scene: dict, index: int) -> dict:
    scene_id = str(scene.get("scene_id") or f"s{index:02d}")
    heading = str(scene.get("heading") or "")
    parsed = parse_heading(heading)
    location = str(scene.get("location") or parsed["location"])
    time_of_day = str(scene.get("time_of_day") or parsed["time_of_day"])
    blocks = []
    for block in scene.get("action_blocks") or []:
        if isinstance(block, dict):
            blocks.append(str(block.get("text") or block.get("description") or ""))
        elif isinstance(block, str):
            blocks.append(block)
    text = " ".join(part for part in (heading, location, time_of_day, *blocks) if part)
    number = scene.get("scene_number") or index
    try:
        number = int(number)
    except (TypeError, ValueError):
        number = index
    return {
        "scene_id": scene_id,
        "scene_number": number,
        "heading": heading,
        "location": location,
        "int_ext": parsed["int_ext"],
        "time_of_day": time_of_day,
        "text": text,
    }


def _read_json(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrevisError(f"{label} is not valid JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise PrevisError(f"{label} must be a JSON object.")
    return data
