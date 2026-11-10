"""Read and write agent handoff files.

A handoff is a JSON file checked against its schema. An invalid file raises
``HandoffError`` and, on write, is not saved.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.validate import SchemaLookupError, load_schema, matching_schema_name, resolve_schema_path, validate_data


class HandoffError(Exception):
    """The handoff cannot be used. The message names the file and the problem."""

    def __init__(self, message: str, *, path: Path | None = None, errors: list[str] | None = None):
        super().__init__(message)
        self.path = path
        self.errors = errors or []


def _schema_for(path: Path, schema: str | Path | None) -> tuple[Path, dict]:
    try:
        if schema is None:
            inferred = matching_schema_name(path)
            if inferred is None:
                raise HandoffError(
                    f"Invalid handoff: {path}\n"
                    "No schema matches this file name. Pass schema='shot-list' "
                    "(or another checklist name), or name the file after its schema, "
                    "for example shot-list.json.",
                    path=path,
                )
            schema_path = resolve_schema_path(inferred)
        else:
            schema_path = resolve_schema_path(schema)
        return schema_path, load_schema(schema_path)
    except SchemaLookupError as exc:
        raise HandoffError(str(exc), path=path) from exc


def _invalid_message(path: Path, schema_name: str, errors: list[str]) -> str:
    bullets = "\n".join(f"  - {error}" for error in errors)
    return (
        f"Invalid handoff: {path}\n"
        f"Schema: {schema_name}\n"
        f"{bullets}\n"
        "This file was not accepted. Fix it before the next agent uses it."
    )


def read_handoff(path: str | Path, schema: str | Path | None = None) -> dict:
    """Load a handoff and check it. Raises ``HandoffError`` when it cannot be used."""
    document = Path(path)
    schema_path, schema_data = _schema_for(document, schema)
    if not document.is_file():
        raise HandoffError(f"Handoff file not found: {document}", path=document)
    try:
        data = json.loads(document.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HandoffError(
            f"Invalid handoff: {document}\nFile is not valid JSON: {exc}",
            path=document,
        ) from exc
    errors = validate_data(data, schema_data)
    if errors:
        raise HandoffError(
            _invalid_message(document, schema_path.name, errors),
            path=document,
            errors=errors,
        )
    if not isinstance(data, dict):
        raise HandoffError(
            f"Invalid handoff: {document}\nSchema: {schema_path.name}\n"
            "  - The file must be a JSON object.",
            path=document,
        )
    return data


def write_handoff(path: str | Path, data: dict, schema: str | Path | None = None) -> Path:
    """Check ``data`` and write it. An invalid handoff is not written."""
    document = Path(path)
    schema_path, schema_data = _schema_for(document, schema)
    errors = validate_data(data, schema_data)
    if errors:
        raise HandoffError(
            _invalid_message(document, schema_path.name, errors),
            path=document,
            errors=errors,
        )
    document.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    temporary = document.with_suffix(document.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(document)
    return document
