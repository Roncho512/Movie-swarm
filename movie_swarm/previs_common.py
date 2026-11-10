"""Shared helpers for the phase 2 roles.

Nothing in this file names a film, a prop, or a look. Those live in the
production folder. A schema is the checklist a JSON file must match.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.models import resolve_model
from movie_swarm.treatment_doc import extract_json_object, load_treatment


class PrevisError(Exception):
    """A phase 2 role stopped. The message says what is missing."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug(text: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text).casefold()).strip("-")
    return cleaned or fallback


def read_brief(production_dir: Path) -> dict:
    path = production_dir / "production-brief.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrevisError(f"The production brief is not valid JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise PrevisError("The production brief must be a JSON object.")
    return data


def approved_treatment(production_dir: Path) -> dict:
    try:
        treatment = load_treatment(production_dir)
    except HandoffError as exc:
        raise PrevisError(str(exc)) from exc
    if treatment.get("status") != "approved":
        raise PrevisError(
            "The treatment is not approved. Phase 2 reads the approved treatment. "
            "Ron approves it with the Line Producer."
        )
    return treatment


def load_optional(path: Path, schema: str) -> dict | None:
    if not path.is_file():
        return None
    try:
        return read_handoff(path, schema=schema)
    except HandoffError as exc:
        raise PrevisError(str(exc)) from exc


def save_pair(path: Path, data: dict, schema: str, markdown: str) -> None:
    write_handoff(path, data, schema=schema)
    notes = path.with_suffix(".md")
    notes.write_text(markdown, encoding="utf-8")


def model_name(role: str, purpose: str) -> str:
    chosen = resolve_model(role, purpose=purpose)
    model = chosen.get("model")
    if not model:
        raise PrevisError(
            f"No model is configured for {role} / {purpose}. "
            "Set one in config/model-routing.json."
        )
    return str(model)


def source_blob(*documents) -> str:
    parts = []
    for document in documents:
        if not document:
            continue
        parts.append(json.dumps(document, ensure_ascii=False))
    return "\n".join(parts)


def try_model_json(llm, *, role: str, purpose: str, system: str, user: str) -> dict | None:
    """Ask the configured model for one JSON object. None means use the offline draft."""
    if llm is None:
        return None
    try:
        raw = llm.complete(role=role, purpose=purpose, system=system, user=user, max_tokens=4000)
        data = extract_json_object(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def grounded(text: str, source: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return cleaned.casefold() in source.casefold()


_SYSTEM = (
    "Return one JSON object and nothing else. Use only facts that appear in the user message. "
    "Do not add a prop, a place, a year, or a look that the documents do not already state. "
    "Do not approve your own work."
)


def system_prompt(role_sentence: str) -> str:
    return role_sentence + " " + _SYSTEM
