"""Storyboards and an animatic plan from the approved treatment.

An animatic is the boards in order, each with a duration. Image generation
runs only when a caller passes a client. The offline path stores the prompt
and does not make a picture.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.handoff import write_handoff
from movie_swarm.previs_common import approved_treatment, model_name, now, save_pair
from movie_swarm.prop_master import locked_path


_SHOT_WORDS = (
    ("extreme wide", "extreme-wide"),
    ("extreme close", "extreme-close"),
    ("medium close", "medium-close"),
    ("medium wide", "medium-wide"),
    ("low angle", "low-angle"),
    ("high angle", "high-angle"),
    ("over the shoulder", "over-shoulder"),
    ("over-shoulder", "over-shoulder"),
    ("tracking", "tracking"),
    ("detail", "detail"),
    ("pov", "pov"),
    ("close", "close"),
    ("wide", "wide"),
)


def storyboard_path(production_dir: Path) -> Path:
    return production_dir / "storyboard" / "storyboard.json"


def shot_list_path(production_dir: Path) -> Path:
    return production_dir / "storyboard" / "shot-list.json"


def build_boards(production_dir: Path, llm=None, image_client=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    package = _package(production_dir)
    props = _props(production_dir)
    model = model_name("cinematographer", "boards")
    shots, frames = _frames(production_dir.name, treatment, package, props, image_client)
    shot_list = {
        "production_id": production_dir.name,
        "version": "1.0.0",
        "total_shots": len(shots),
        "shots": shots,
        "created_at": now(),
    }
    write_handoff(shot_list_path(production_dir), shot_list, schema="shot-list")
    total = round(sum(frame["duration_seconds"] for frame in frames), 3)
    used_client = image_client is not None
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "shot_list_path": "storyboard/shot-list.json",
        "frames": frames,
        "animatic": {
            "total_duration_seconds": total,
            "order": [frame["shot_id"] for frame in frames],
            "note": "Play the boards in this order. Durations come from the treatment scenes.",
        },
        "image_generation": "fake-client" if used_client else "not-run",
        "draft_method": "offline-deterministic",
        "model": model,
        "created_at": shot_list["created_at"],
    }
    if llm is not None:
        document["animatic"]["note"] += (
            " A model was available. The prompts stayed offline so a locked phrase cannot be dropped."
        )
    save_pair(storyboard_path(production_dir), document, "storyboard", _markdown(document, package))
    return document


def _package(production_dir: Path) -> dict:
    path = production_dir / "camera" / "camera-package.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _props(production_dir: Path) -> list[dict]:
    if not locked_path(production_dir).is_file():
        return []
    try:
        data = json.loads(locked_path(production_dir).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return list(data.get("props") or [])


def _frames(production_id: str, treatment: dict, package: dict, props: list[dict], image_client):
    shots = []
    frames = []
    order = 1
    scenes = treatment.get("scenes") or []
    for index, scene in enumerate(scenes, start=1):
        scene_id = str(scene.get("scene_id") or f"s{index:02d}")
        types = _shot_types(str(scene.get("coverage_intent") or ""))
        duration = _duration(scene, len(types))
        visible = _visible_props(scene, props)
        for shot_number, shot_type in enumerate(types, start=1):
            shot_id = f"{_scene_slug(scene_id, index)}-sh{shot_number:02d}"
            prompt = _prompt(shot_type, scene, package, visible)
            description = _short(str(scene.get("what_happens") or scene_id), 280)
            framing = _first_text(package.get("framing"))
            lighting = _first_text(package.get("lighting"))
            shot = {
                "shot_id": shot_id,
                "scene_number": _scene_number(scene_id, index),
                "shot_number": shot_number,
                "sequence_position": order,
                "shot_type": shot_type,
                "description": description,
                "framing_notes": framing,
                "generation_prompt": prompt,
                "negative_prompt": _negative(visible),
                "tool_routing": {
                    "primary_tool": "veo-3.1-lite",
                    "rationale": "Storyboard pass. A prompt for a board, not a finished picture.",
                    "iteration_first": True,
                    "requires_native_audio": False,
                },
                "target_duration_seconds": duration,
                "continuity_notes": _continuity(visible),
                "color_notes": lighting,
            }
            people = _people(scene, treatment)
            if people:
                shot["characters_in_shot"] = people
            prop_refs, vehicle_refs = _shot_refs(visible)
            if prop_refs:
                shot["props_in_shot"] = prop_refs
            if vehicle_refs:
                shot["vehicles_in_shot"] = vehicle_refs
            shots.append(shot)
            image_ref = None
            image_status = "not-generated"
            if image_client is not None:
                image_ref = str(image_client.generate(prompt))
                image_status = "fake-client"
            frames.append(
                {
                    "order": order,
                    "shot_id": shot_id,
                    "scene_id": scene_id,
                    "board_prompt": prompt,
                    "duration_seconds": duration,
                    "image_status": image_status,
                    "image_ref": image_ref,
                }
            )
            order += 1
    if not frames:
        raise ValueError("The approved treatment has no scenes to board.")
    return shots, frames


def _shot_types(coverage: str) -> list[str]:
    lowered = coverage.casefold()
    found = []
    cursor = lowered
    while cursor:
        matched = False
        for phrase, shot_type in _SHOT_WORDS:
            if phrase in cursor:
                if shot_type not in found:
                    found.append(shot_type)
                cursor = cursor.replace(phrase, " ", 1)
                matched = True
                break
        if not matched:
            break
    return found or ["wide"]


def _duration(scene: dict, count: int) -> float:
    raw = scene.get("approximate_duration_seconds")
    try:
        total = float(raw)
    except (TypeError, ValueError):
        total = 4.0 * count
    if total <= 0:
        total = 4.0 * count
    each = total / max(count, 1)
    return round(max(each, 0.5), 3)


def _scene_slug(scene_id: str, index: int) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in scene_id.casefold()).strip("-")
    if cleaned and cleaned[0].isalpha():
        return cleaned
    return f"s{index:02d}"


def _scene_number(scene_id: str, index: int) -> int:
    digits = "".join(ch for ch in scene_id if ch.isdigit())
    if digits:
        return int(digits[:4])
    return index


def _visible_props(scene: dict, props: list[dict]) -> list[dict]:
    text = " ".join(
        str(scene.get(key) or "") for key in ("heading", "what_happens", "coverage_intent")
    ).casefold()
    visible = []
    for prop in props:
        names = [prop.get("name") or "", *(prop.get("aliases") or [])]
        if any(len(name) >= 3 and name.casefold() in text for name in names):
            visible.append(prop)
    return visible


def _prompt(shot_type: str, scene: dict, package: dict, props: list[dict]) -> str:
    parts = [shot_type.replace("-", " ") + "."]
    if package.get("summary"):
        parts.append("Look: " + str(package["summary"]))
    framing = _first_text(package.get("framing"))
    if framing:
        parts.append("Frame: " + framing)
    lighting = _first_text(package.get("lighting"))
    if lighting:
        parts.append("Light: " + lighting)
    palette = package.get("palette") or []
    if palette:
        parts.append("Palette: " + ", ".join(str(color) for color in palette) + ".")
    action = _short(str(scene.get("what_happens") or ""), 500)
    if action:
        parts.append("Action: " + action)
    for prop in props:
        parts.append(f"Locked prop {prop['name']}: {prop.get('locked_spec') or prop['name']}.")
        for attribute in prop.get("attributes") or []:
            phrases = attribute.get("required_phrases") or []
            if phrases:
                parts.append(phrases[0] + ".")
    return " ".join(parts)


def _negative(props: list[dict]) -> str:
    phrases = []
    for prop in props:
        for attribute in prop.get("attributes") or []:
            for phrase in attribute.get("forbidden_phrases") or []:
                if phrase not in phrases:
                    phrases.append(phrase)
    if not phrases:
        return "Do not contradict a locked prop."
    return "Do not show: " + "; ".join(phrases) + "."


def _continuity(props: list[dict]) -> str:
    if not props:
        return "No locked prop was named in this scene."
    bits = []
    for prop in props:
        for attribute in prop.get("attributes") or []:
            if attribute.get("value"):
                bits.append(f"{prop['name']} {attribute['label']} stays {attribute['value']}")
    if not bits:
        return "Keep the locked prop specs."
    return ". ".join(bits) + "."


def _people(scene: dict, treatment: dict) -> list[str]:
    text = str(scene.get("what_happens") or "")
    names = []
    for person in treatment.get("characters") or []:
        name = str(person.get("name") or "")
        if name and name.casefold() in text.casefold():
            names.append(name)
    return names


def _shot_refs(props: list[dict]) -> tuple[list[dict], list[str]]:
    prop_refs = []
    vehicles = []
    for prop in props:
        if str(prop.get("kind") or "").casefold() == "vehicle":
            vehicles.append(prop["prop_id"])
        else:
            prop_refs.append({"prop_id": prop["prop_id"], "visibility_note": prop.get("locked_spec") or ""})
    return prop_refs, vehicles


def _first_text(items) -> str:
    if not items:
        return ""
    first = items[0]
    if isinstance(first, dict):
        return str(first.get("description") or "")
    return str(first)


def _short(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _markdown(document: dict, package: dict) -> str:
    lines = [
        "# Storyboard and animatic",
        "",
        f"Look: {package.get('look_name') or 'the treatment'}.",
        f"Images: {document['image_generation']}.",
        f"Animatic length: {document['animatic']['total_duration_seconds']} seconds.",
        "",
    ]
    for frame in document["frames"]:
        lines.append(f"## {frame['order']}. {frame['shot_id']}")
        lines.append("")
        lines.append(f"{frame['duration_seconds']} seconds. Image: {frame['image_status']}.")
        lines.append("")
        lines.append(frame["board_prompt"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
