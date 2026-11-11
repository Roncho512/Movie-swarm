"""Costume Designer: lock wardrobe the production already described.

A character's garment, color, condition, and scene changes come from
``wardrobe/costume-definitions.json`` when that file exists. Otherwise the
lock uses the wardrobe line on the approved treatment. It does not invent a
garment.
"""

from __future__ import annotations

from pathlib import Path

from movie_swarm.prep_inputs import load_scenes
from movie_swarm.previs_common import (
    PrevisError,
    approved_treatment,
    load_optional,
    model_name,
    now,
    save_pair,
    slug,
    source_blob,
    system_prompt,
    try_model_json,
)


def definitions_path(production_dir: Path) -> Path:
    return production_dir / "wardrobe" / "costume-definitions.json"


def locked_path(production_dir: Path) -> Path:
    return production_dir / "wardrobe" / "costume-lock.json"


def load_locked(production_dir: Path) -> dict | None:
    return _load_one(locked_path(production_dir))


def load_for_check(production_dir: Path) -> dict | None:
    """The locked file, or the definitions when that is all the production has."""
    for path in (locked_path(production_dir), definitions_path(production_dir)):
        data = _load_one(path)
        if data and data.get("characters"):
            return data
    return None


def _load_one(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return load_optional(path, "costume-lock")
    except PrevisError:
        return None


def lock_costumes(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    scenes, scene_source = load_scenes(production_dir, treatment)
    defined = load_optional(definitions_path(production_dir), "costume-lock")
    offline = _offline(production_dir, treatment, scenes, scene_source, defined)
    drafted = _from_model(llm, offline, treatment, defined)
    document = drafted or offline
    save_pair(locked_path(production_dir), document, "costume-lock", _markdown(document))
    return document


def _offline(production_dir: Path, treatment: dict, scenes: list[dict], scene_source: str, defined: dict | None) -> dict:
    model = model_name("costume-designer", "lock")
    if defined is not None:
        characters = [_with_scenes(dict(item), scenes) for item in defined.get("characters") or [] if isinstance(item, dict)]
        return {
            "version": "1.0.0",
            "production_id": production_dir.name,
            "status": "locked",
            "source": "wardrobe/costume-definitions.json",
            "scene_source": scene_source,
            "characters": characters,
            "draft_method": "offline-deterministic",
            "model": model,
            "note": "Locked from the production's costume definitions. No garment was added.",
            "locked_at": now(),
        }
    characters = []
    for person in treatment.get("characters") or []:
        if not isinstance(person, dict):
            continue
        wardrobe = str(person.get("wardrobe") or "").strip()
        name = str(person.get("name") or "").strip()
        if not name or not wardrobe:
            continue
        characters.append(_with_scenes(_from_wardrobe(name, wardrobe), scenes))
    note = (
        "The production has no wardrobe/costume-definitions.json. "
        "Locked only the wardrobe lines on the approved treatment."
    )
    if not characters:
        note = (
            "The production has no wardrobe/costume-definitions.json and no wardrobe lines "
            "on the treatment. No garment was invented."
        )
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "status": "locked",
        "source": "treatment",
        "scene_source": scene_source,
        "characters": characters,
        "draft_method": "offline-deterministic",
        "model": model,
        "note": note,
        "locked_at": now(),
    }


def _from_wardrobe(name: str, wardrobe: str) -> dict:
    return {
        "character_id": slug(name, "character"),
        "name": name,
        "aliases": [],
        "locked_spec": wardrobe,
        "garment": wardrobe,
        "color": "not named",
        "condition": "not named",
        "changes": [],
        "attributes": [
            {
                "attribute_id": "wardrobe",
                "label": "wardrobe",
                "value": wardrobe,
                "must_be_stated_when_visible": True,
                "required_phrases": [wardrobe],
                "forbidden_phrases": [],
            }
        ],
    }


def _with_scenes(character: dict, scenes: list[dict]) -> dict:
    supplied = {}
    for change in character.get("changes") or []:
        if isinstance(change, dict) and change.get("scene_id"):
            supplied[str(change["scene_id"])] = change
    changes = []
    seen = set()
    for scene in scenes:
        if not _appears(character, scene["text"]) and scene["scene_id"] not in supplied:
            continue
        seen.add(scene["scene_id"])
        if scene["scene_id"] in supplied:
            changes.append(_change_row(supplied[scene["scene_id"]], character))
        else:
            changes.append(
                {
                    "scene_id": scene["scene_id"],
                    "garment": str(character.get("garment") or "not named"),
                    "color": str(character.get("color") or "not named"),
                    "condition": str(character.get("condition") or "not named"),
                    "note": "Same as the locked spec. The production did not name a change for this scene.",
                }
            )
    for scene_id, change in supplied.items():
        if scene_id not in seen:
            changes.append(_change_row(change, character))
    character["changes"] = changes
    character.setdefault("aliases", [])
    character.setdefault("attributes", [])
    return character


def _change_row(change: dict, character: dict) -> dict:
    row = {
        "scene_id": str(change.get("scene_id")),
        "garment": str(change.get("garment") or character.get("garment") or "not named"),
        "color": str(change.get("color") or character.get("color") or "not named"),
        "condition": str(change.get("condition") or character.get("condition") or "not named"),
    }
    if change.get("note"):
        row["note"] = str(change["note"])
    return row


def _appears(character: dict, text: str) -> bool:
    haystack = text.casefold()
    names = [character.get("name") or "", *(character.get("aliases") or [])]
    return any(len(str(name)) >= 2 and str(name).casefold() in haystack for name in names)


def _from_model(llm, offline: dict, treatment: dict, defined: dict | None) -> dict | None:
    if llm is None:
        return None
    drafted = try_model_json(
        llm,
        role="costume-designer",
        purpose="lock",
        system=system_prompt(
            "You are the Costume Designer. Lock only the wardrobe the documents already name."
        ),
        user=source_blob(defined, treatment.get("characters")),
    )
    if not drafted:
        return None
    drafted["production_id"] = offline["production_id"]
    drafted["status"] = "locked"
    drafted["draft_method"] = "model"
    drafted["model"] = offline["model"]
    drafted["locked_at"] = offline["locked_at"]
    drafted["source"] = offline["source"]
    drafted["scene_source"] = offline["scene_source"]
    drafted["note"] = offline["note"]
    if drafted.get("characters") != offline.get("characters"):
        return None
    try:
        from movie_swarm.validate import load_schema, validate_data

        errors = validate_data(drafted, load_schema("costume-lock"))
    except Exception:
        return None
    if errors:
        return None
    return drafted


def _markdown(document: dict) -> str:
    lines = ["# Locked wardrobe", "", document.get("note") or "Locked wardrobe.", ""]
    if not document.get("characters"):
        lines.append("No wardrobe is locked.")
        lines.append("")
    for person in document.get("characters") or []:
        lines.append(f"## {person['name']}")
        lines.append("")
        lines.append(person.get("locked_spec") or "")
        lines.append("")
        lines.append(f"- Garment: {person.get('garment')}")
        lines.append(f"- Color: {person.get('color')}")
        lines.append(f"- Condition: {person.get('condition')}")
        for change in person.get("changes") or []:
            lines.append(
                f"- {change['scene_id']}: {change['garment']}, {change['color']}, {change['condition']}."
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
