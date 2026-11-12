"""Makeup and hair: lock the look the production already described.

Makeup, hair, and effects such as dirt, sweat, wounds, or aging come from
``makeup/makeup-definitions.json`` when that file exists. Nothing is invented.
"""

from __future__ import annotations

from pathlib import Path

from movie_swarm.prep_inputs import load_scenes
from movie_swarm.previs_common import (
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
    return production_dir / "makeup" / "makeup-definitions.json"


def locked_path(production_dir: Path) -> Path:
    return production_dir / "makeup" / "makeup-lock.json"


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
        return load_optional(path, "makeup-lock")
    except Exception:
        return None


def lock_makeup(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    scenes, scene_source = load_scenes(production_dir, treatment)
    defined = load_optional(definitions_path(production_dir), "makeup-lock")
    offline = _offline(production_dir, treatment, scenes, scene_source, defined)
    drafted = _from_model(llm, offline, treatment, defined)
    document = drafted or offline
    save_pair(locked_path(production_dir), document, "makeup-lock", _markdown(document))
    return document


def _offline(production_dir: Path, treatment: dict, scenes: list[dict], scene_source: str, defined: dict | None) -> dict:
    model = model_name("makeup-hair", "lock")
    if defined is not None:
        characters = [_with_scenes(dict(item), scenes) for item in defined.get("characters") or [] if isinstance(item, dict)]
        note = "Locked from the production's makeup definitions. No effect was added."
        source = "makeup/makeup-definitions.json"
    else:
        characters = []
        for person in treatment.get("characters") or []:
            if not isinstance(person, dict):
                continue
            named = str(person.get("makeup") or person.get("hair") or "").strip()
            name = str(person.get("name") or "").strip()
            if not name or not named:
                continue
            characters.append(_with_scenes(_from_treatment(name, person), scenes))
        source = "treatment"
        if characters:
            note = (
                "The production has no makeup/makeup-definitions.json. "
                "Locked only the makeup or hair lines on the approved treatment."
            )
        else:
            note = (
                "The production has no makeup/makeup-definitions.json and no makeup or hair lines "
                "on the treatment. No effect was invented."
            )
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "status": "locked",
        "source": source,
        "scene_source": scene_source,
        "characters": characters,
        "draft_method": "offline-deterministic",
        "model": model,
        "note": note,
        "locked_at": now(),
    }


def _from_treatment(name: str, person: dict) -> dict:
    makeup = str(person.get("makeup") or "not named")
    hair = str(person.get("hair") or "not named")
    effects = [str(item) for item in person.get("effects") or [] if str(item).strip()]
    spec = ", ".join(part for part in (makeup if makeup != "not named" else "", hair if hair != "not named" else "") if part)
    phrase = spec or name
    return {
        "character_id": slug(name, "character"),
        "name": name,
        "aliases": [],
        "locked_spec": phrase,
        "makeup": makeup,
        "hair": hair,
        "effects": effects,
        "changes": [],
        "attributes": [
            {
                "attribute_id": "look",
                "label": "makeup and hair",
                "value": phrase,
                "must_be_stated_when_visible": True,
                "required_phrases": [phrase],
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
            changes.append(_base_change(scene["scene_id"], character))
    for scene_id, change in supplied.items():
        if scene_id not in seen:
            changes.append(_change_row(change, character))
    character["changes"] = changes
    character.setdefault("aliases", [])
    character.setdefault("effects", [])
    character.setdefault("attributes", [])
    return character


def _base_change(scene_id: str, character: dict) -> dict:
    return {
        "scene_id": scene_id,
        "makeup": str(character.get("makeup") or "not named"),
        "hair": str(character.get("hair") or "not named"),
        "effects": list(character.get("effects") or []),
        "note": "Same as the locked spec. The production did not name a change for this scene.",
    }


def _change_row(change: dict, character: dict) -> dict:
    effects = change.get("effects")
    if effects is None:
        effects = character.get("effects") or []
    row = {
        "scene_id": str(change.get("scene_id")),
        "makeup": str(change.get("makeup") or character.get("makeup") or "not named"),
        "hair": str(change.get("hair") or character.get("hair") or "not named"),
        "effects": [str(item) for item in effects if str(item).strip()],
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
        role="makeup-hair",
        purpose="lock",
        system=system_prompt(
            "You are makeup and hair. Lock only the makeup, hair, and effects the documents already name."
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

        errors = validate_data(drafted, load_schema("makeup-lock"))
    except Exception:
        return None
    if errors:
        return None
    return drafted


def _markdown(document: dict) -> str:
    lines = ["# Locked makeup and hair", "", document.get("note") or "Locked makeup and hair.", ""]
    if not document.get("characters"):
        lines.append("No makeup or hair is locked.")
        lines.append("")
    for person in document.get("characters") or []:
        lines.append(f"## {person['name']}")
        lines.append("")
        lines.append(person.get("locked_spec") or "")
        lines.append("")
        lines.append(f"- Makeup: {person.get('makeup')}")
        lines.append(f"- Hair: {person.get('hair')}")
        effects = person.get("effects") or []
        lines.append("- Effects: " + (", ".join(effects) if effects else "none named"))
        for change in person.get("changes") or []:
            extra = ", ".join(change.get("effects") or []) or "no added effect"
            lines.append(f"- {change['scene_id']}: makeup {change['makeup']}, hair {change['hair']}, {extra}.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
