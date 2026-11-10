"""Cinematographer: build a camera package from the production's look.

A look file, when the production has one, supplies the lenses, the framing,
and the lighting. Otherwise the package quotes the treatment and the brief
and leaves the lens list empty. It does not invent a look.
"""

from __future__ import annotations

from pathlib import Path

from movie_swarm.previs_common import (
    approved_treatment,
    grounded,
    load_optional,
    model_name,
    now,
    read_brief,
    save_pair,
    source_blob,
    system_prompt,
    try_model_json,
)
from movie_swarm.validate import load_schema, validate_data


def look_path(production_dir: Path) -> Path:
    return production_dir / "look" / "look.json"


def package_path(production_dir: Path) -> Path:
    return production_dir / "camera" / "camera-package.json"


def build_package(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    brief = read_brief(production_dir)
    look = load_optional(look_path(production_dir), "look")
    offline = _offline(production_dir, treatment, brief, look)
    drafted = _from_model(llm, offline, treatment, brief, look)
    document = drafted or offline
    save_pair(package_path(production_dir), document, "camera-package", _markdown(document))
    return document


def _offline(production_dir: Path, treatment: dict, brief: dict, look: dict | None) -> dict:
    model = model_name("cinematographer", "package")
    if look is not None:
        document = {
            "version": "1.0.0",
            "production_id": production_dir.name,
            "look_name": look["look_name"],
            "summary": look["summary"],
            "lenses": list(look.get("lenses") or []),
            "framing": list(look.get("framing") or []),
            "lighting": list(look.get("lighting") or []),
            "source": "look/look.json",
            "draft_method": "offline-deterministic",
            "model": model,
            "created_at": now(),
        }
        if look.get("aspect_ratio"):
            document["aspect_ratio"] = look["aspect_ratio"]
        if look.get("palette"):
            document["palette"] = list(look["palette"])
        if not document["lenses"]:
            document["lens_note"] = "The look file did not name lenses."
        if not document["framing"]:
            document["framing"] = [{"id": "stated-look", "description": look["summary"]}]
        if not document["lighting"]:
            document["lighting"] = [{"id": "stated-look", "description": look["summary"]}]
        return document
    summary = _summary_from_treatment(treatment, brief)
    framing = summary
    lighting = str(treatment.get("color_and_light_plan") or summary)
    palette = list(((brief.get("visual_style") or {}).get("color_palette")) or [])
    aspect = ((treatment.get("deliverables") or {}).get("aspect_ratio")) or ""
    look_name = _look_name(treatment, brief)
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "look_name": look_name,
        "summary": summary,
        "lenses": [],
        "lens_note": "The production did not name lenses. None were invented.",
        "framing": [{"id": "stated-look", "description": framing}],
        "lighting": [{"id": "stated-look", "description": lighting}],
        "source": "treatment",
        "draft_method": "offline-deterministic",
        "model": model,
        "created_at": now(),
    }
    if aspect:
        document["aspect_ratio"] = aspect
    if palette:
        document["palette"] = palette
    return document


def _summary_from_treatment(treatment: dict, brief: dict) -> str:
    camera = str(treatment.get("camera_lens_film_stock") or "").strip()
    if camera:
        return camera
    description = str(((brief.get("visual_style") or {}).get("description")) or "").strip()
    if description:
        return description
    tone = ((treatment.get("tone_and_genre") or {}).get("tone")) or ""
    if str(tone).strip():
        return str(tone).strip()
    return "The production has not named a look."


def _look_name(treatment: dict, brief: dict) -> str:
    films = ((brief.get("visual_style") or {}).get("reference_films")) or []
    if films:
        return str(films[0])
    lookbook = treatment.get("reference_lookbook") or []
    if lookbook and lookbook[0].get("reference"):
        return str(lookbook[0]["reference"])
    genre = ((treatment.get("tone_and_genre") or {}).get("genre")) or ""
    if str(genre).strip():
        return str(genre).strip()
    return "Unnamed look"


def _from_model(llm, offline: dict, treatment: dict, brief: dict, look: dict | None) -> dict | None:
    if llm is None:
        return None
    source = source_blob(look, treatment.get("camera_lens_film_stock"), treatment.get("color_and_light_plan"), brief.get("visual_style"))
    drafted = try_model_json(
        llm,
        role="cinematographer",
        purpose="package",
        system=system_prompt(
            "You are the Cinematographer. Build the camera package from the look in the user message."
        ),
        user=source,
    )
    if not drafted:
        return None
    drafted["production_id"] = offline["production_id"]
    drafted["draft_method"] = "model"
    drafted["model"] = offline["model"]
    drafted["created_at"] = offline["created_at"]
    drafted["source"] = offline["source"]
    if not grounded(str(drafted.get("look_name") or ""), source):
        return None
    if not grounded(str(drafted.get("summary") or ""), source):
        return None
    for lens in drafted.get("lenses") or []:
        if not isinstance(lens, dict) or not grounded(str(lens.get("name") or ""), source):
            return None
        if lens.get("use") and not grounded(str(lens["use"]), source):
            return None
    for item in list(drafted.get("framing") or []) + list(drafted.get("lighting") or []):
        if not isinstance(item, dict) or not grounded(str(item.get("description") or ""), source):
            return None
    errors = validate_data(drafted, load_schema("camera-package"))
    if errors:
        return None
    return drafted


def _markdown(document: dict) -> str:
    lines = [
        f"# Camera package: {document['look_name']}",
        "",
        document["summary"],
        "",
        "## Lenses",
        "",
    ]
    if document.get("lens_note"):
        lines.append(document["lens_note"])
        lines.append("")
    if not document["lenses"]:
        lines.append("No lenses were named.")
        lines.append("")
    for lens in document["lenses"]:
        focal = f" ({lens['focal_length']})" if lens.get("focal_length") else ""
        lines.append(f"- {lens['name']}{focal}: {lens['use']}")
    lines.extend(["", "## Framing", ""])
    for item in document["framing"]:
        lines.append(f"- {item['description']}")
    lines.extend(["", "## Lighting", ""])
    for item in document["lighting"]:
        lines.append(f"- {item['description']}")
    if document.get("palette"):
        lines.extend(["", "## Palette", "", ", ".join(document["palette"]), ""])
    return "\n".join(lines).rstrip() + "\n"
