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
    r"^(?P<int_ext>INT\.?/EXT\.?|EXT\.?/INT\.?|I/E\.?|INT\.?|EXT\.?)\s+"
    r"(?P<location>.+?)(?:\s+-\s+(?P<time>.+))?$",
    re.I,
)


def load_shots(production_dir: Path) -> tuple[list[dict], str]:
    """Normalized shots, and the file they came from.

    The storyboard shot list wins. A production shot list is the fallback.
    """
    folder = Path(production_dir)
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = folder / relative
        if not path.is_file():
            continue
        data = _read_json(path, relative)
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
            return scenes, "scene-manifest/scene-manifest.json"
    scenes = []
    for index, scene in enumerate(treatment.get("scenes") or [], start=1):
        if isinstance(scene, dict):
            scenes.append(_treatment_scene(scene, index))
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
    """Split a slugline into interior/exterior, place, and time. Unknown parts stay unnamed."""
    text = " ".join(str(heading or "").split())
    match = _HEADING.match(text)
    if not match:
        place = text or "not named"
        return {"int_ext": "not named", "location": place, "time_of_day": "not named"}
    int_ext = match.group("int_ext").upper().rstrip(".")
    if int_ext in {"I/E", "INT/EXT", "EXT/INT"}:
        int_ext = int_ext
    location = " ".join(match.group("location").split()) or "not named"
    time_of_day = " ".join((match.group("time") or "").split()) or "not named"
    return {"int_ext": int_ext, "location": location, "time_of_day": time_of_day}


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
