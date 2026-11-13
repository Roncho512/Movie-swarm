"""Prop Master: lock the hero props a production already defined.

The definitions live in the production folder. This module copies them into
the locked handoff. It does not invent a prop or a side.
"""

from __future__ import annotations

from pathlib import Path

from movie_swarm.previs_common import (
    PrevisError,
    approved_treatment,
    load_optional,
    model_name,
    now,
    read_brief,
    save_pair,
    slug,
    source_blob,
    system_prompt,
    try_model_json,
)


def definitions_path(production_dir: Path) -> Path:
    return production_dir / "props" / "prop-definitions.json"


def locked_path(production_dir: Path) -> Path:
    return production_dir / "props" / "hero-props.json"


def lock_props(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    brief = read_brief(production_dir)
    defined = load_optional(definitions_path(production_dir), "hero-props")
    offline = _offline(production_dir, treatment, brief, defined)
    drafted = _from_model(llm, offline, treatment, brief, defined)
    document = drafted or offline
    _refuse_unknown_props(document, treatment, defined)
    save_pair(
        locked_path(production_dir),
        document,
        "hero-props",
        _markdown(document),
    )
    return document


def _offline(production_dir: Path, treatment: dict, brief: dict, defined: dict | None) -> dict:
    model = model_name("prop-master", "lock")
    if defined is not None:
        document = {
            "version": "1.0.0",
            "production_id": production_dir.name,
            "status": "locked",
            "source": "props/prop-definitions.json",
            "props": defined.get("props") or [],
            "draft_method": "offline-deterministic",
            "model": model,
            "note": "Locked from the production's prop definitions. No prop was added.",
            "locked_at": now(),
        }
        if defined.get("facts"):
            document["facts"] = defined["facts"]
        return document
    props = []
    for prop in treatment.get("hero_props") or []:
        props.append(_prop_from_treatment(prop))
    for prop in brief.get("hero_props") or []:
        if any(item["name"].casefold() == str(prop.get("name", "")).casefold() for item in props):
            continue
        if prop.get("name"):
            props.append(_prop_from_brief(prop))
    facts = _facts_from_brief(brief)
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "status": "locked",
        "source": "treatment",
        "props": props,
        "draft_method": "offline-deterministic",
        "model": model,
        "note": (
            "The production has no props/prop-definitions.json. "
            "Locked only the props named on the approved treatment and the brief."
        ),
        "locked_at": now(),
    }
    if facts:
        document["facts"] = facts
    return document


def _prop_from_treatment(prop: dict) -> dict:
    name = str(prop.get("name") or "Unnamed prop")
    sidedness = str(prop.get("sidedness") or "").strip()
    attributes = []
    if sidedness and sidedness.casefold() not in {"not locked", "locked", "locked as drafted"}:
        attributes.append(
            {
                "attribute_id": "sidedness",
                "label": "sidedness",
                "value": sidedness,
                "must_be_stated_when_visible": True,
                "required_phrases": [sidedness],
                "forbidden_phrases": [],
            }
        )
    explicit = [str(alias).strip() for alias in prop.get("aliases") or [] if str(alias).strip()]
    aliases = explicit or [name]
    if name and name not in aliases:
        aliases = [name, *aliases]
    locked = {
        "prop_id": slug(name, "prop"),
        "name": name,
        "kind": "prop",
        "aliases": aliases,
        "locked_spec": str(prop.get("locked_spec") or name),
        "reference_images": list(prop.get("reference_images") or []),
        "attributes": attributes,
    }
    parts = [str(part).strip() for part in prop.get("parts") or [] if str(part).strip()]
    if parts:
        locked["parts"] = parts
    return locked


def _prop_from_brief(prop: dict) -> dict:
    return _prop_from_treatment(
        {
            "name": prop.get("name"),
            "locked_spec": prop.get("description") or prop.get("name"),
            "sidedness": prop.get("sidedness") or "",
            "reference_images": [],
        }
    )


def _facts_from_brief(brief: dict) -> list[dict]:
    setting = brief.get("setting") or {}
    facts = []
    year = str(setting.get("year") or "").strip()
    if year:
        facts.append(
            {
                "fact_id": "setting-year",
                "label": "setting year",
                "value": year,
                "required_phrases": [],
                "forbidden_phrases": [],
                "must_be_stated": False,
            }
        )
    place = str(setting.get("place") or "").strip()
    if place:
        facts.append(
            {
                "fact_id": "setting-place",
                "label": "setting place",
                "value": place,
                "required_phrases": [],
                "forbidden_phrases": [],
                "must_be_stated": False,
            }
        )
    return facts


def _from_model(llm, offline: dict, treatment: dict, brief: dict, defined: dict | None) -> dict | None:
    if llm is None:
        return None
    drafted = try_model_json(
        llm,
        role="prop-master",
        purpose="lock",
        system=system_prompt(
            "You are the Prop Master. Lock the hero props that the documents already name."
        ),
        user=source_blob(defined, treatment.get("hero_props"), brief.get("hero_props"), brief.get("setting")),
    )
    if not drafted:
        return None
    drafted["production_id"] = offline["production_id"]
    drafted["status"] = "locked"
    drafted["draft_method"] = "model"
    drafted["model"] = offline["model"]
    drafted["locked_at"] = offline["locked_at"]
    drafted.setdefault("source", offline["source"])
    drafted.setdefault("props", offline["props"])
    try:
        from movie_swarm.validate import load_schema, validate_data

        errors = validate_data(drafted, load_schema("hero-props"))
    except Exception:
        return None
    if errors:
        return None
    if drafted.get("props") != offline.get("props"):
        return None
    if (drafted.get("facts") or []) != (offline.get("facts") or []):
        return None
    return drafted


def _refuse_unknown_props(document: dict, treatment: dict, defined: dict | None) -> None:
    if defined is None:
        return
    names = {prop.get("name", "").casefold() for prop in document.get("props") or []}
    missing = []
    for prop in treatment.get("hero_props") or []:
        name = str(prop.get("name") or "")
        if name and name.casefold() not in names:
            missing.append(name)
    if missing:
        raise PrevisError(
            "The treatment names props that the definitions file does not: "
            + ", ".join(missing)
            + ". Add them to props/prop-definitions.json. Nothing was locked."
        )


def _markdown(document: dict) -> str:
    lines = [
        "# Locked hero props",
        "",
        document.get("note") or "Locked props.",
        "",
    ]
    for fact in document.get("facts") or []:
        lines.append(f"- Fact: {fact['label']} is {fact['value']}.")
    if document.get("facts"):
        lines.append("")
    if not document.get("props"):
        lines.append("No hero props are locked.")
        lines.append("")
    for prop in document.get("props") or []:
        lines.append(f"## {prop['name']}")
        lines.append("")
        lines.append(prop["locked_spec"])
        lines.append("")
        for attribute in prop.get("attributes") or []:
            lines.append(f"- {attribute['label']}: {attribute['value']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
