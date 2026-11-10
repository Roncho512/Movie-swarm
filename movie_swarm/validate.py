"""Validate JSON documents against the schemas in ``schemas/``.

Use ``validate_file`` from Python. The command-line wrapper is
``scripts/validate-schema.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

from movie_swarm.paths import config_dir, repo_root, schemas_dir


# File name -> schema file. QA reports use the continuity-report checklist
# even though the agent saved them as qa-report-vN.json.
_SCHEMA_BY_FILENAME = {
    "production-brief.json": "production-brief.schema.json",
    "scene-manifest.json": "scene-manifest.schema.json",
    "visual-style-bible.json": "visual-style-bible.schema.json",
    "shot-list.json": "shot-list.schema.json",
    "clip-metadata.json": "clip-metadata.schema.json",
    "audio-manifest.json": "audio-manifest.schema.json",
    "continuity-report.json": "continuity-report.schema.json",
    "run-state.json": "run-state.schema.json",
    "gates.json": "gate-config.schema.json",
    "model-routing.json": "model-routing.schema.json",
    "assets.json": "asset-config.schema.json",
    "treatment.json": "treatment.schema.json",
    "line-producer.json": "line-producer-record.schema.json",
    "questions.json": "director-questions.schema.json",
    "hero-props.json": "hero-props.schema.json",
    "prop-definitions.json": "hero-props.schema.json",
    "continuity-check.json": "continuity-check.schema.json",
    "look.json": "look.schema.json",
    "camera-package.json": "camera-package.schema.json",
    "storyboard.json": "storyboard.schema.json",
    "action-breakdown.json": "action-breakdown.schema.json",
}

_QUESTIONS_ROUND = re.compile(r"^questions-round-\d+\.json$")


class SchemaLookupError(Exception):
    """The caller asked for a schema this repo does not have."""


@dataclass
class ValidationResult:
    """Outcome of checking one JSON file."""

    path: Path
    schema_name: str | None
    ok: bool
    errors: list[str] = field(default_factory=list)

    def text(self) -> str:
        label = "PASS" if self.ok else "FAIL"
        lines = [f"{label}  {self.path}"]
        if self.schema_name:
            lines.append(f"Schema: {self.schema_name}")
        else:
            lines.append("Schema: (none)")
        for error in self.errors:
            lines.append(f"  - {error}")
        return "\n".join(lines)


def matching_schema_name(path: str | Path) -> str | None:
    """Return the schema file name for a document, or None when nothing matches."""
    name = Path(path).name
    if name in _SCHEMA_BY_FILENAME:
        return _SCHEMA_BY_FILENAME[name]
    if name.startswith("qa-report") and name.endswith(".json"):
        return "continuity-report.schema.json"
    if _QUESTIONS_ROUND.match(name):
        return "director-questions.schema.json"
    return None


def resolve_schema_path(schema: str | Path) -> Path:
    """Find a schema by file path or by short name such as ``shot-list``."""
    raw = Path(schema)
    if raw.is_file():
        return raw.resolve()

    name = raw.name
    if name.endswith(".schema.json"):
        candidate = schemas_dir() / name
    elif name.endswith(".json"):
        candidate = schemas_dir() / name
        if not candidate.is_file():
            candidate = schemas_dir() / f"{name[:-5]}.schema.json"
    else:
        candidate = schemas_dir() / f"{name}.schema.json"

    if not candidate.is_file():
        known = ", ".join(sorted(p.name for p in schemas_dir().glob("*.schema.json")))
        raise SchemaLookupError(
            f"No schema named '{schema}' in {schemas_dir()}. Schemas on disk: {known}."
        )
    return candidate


def load_schema(schema: str | Path) -> dict:
    path = resolve_schema_path(schema)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaLookupError(f"Schema file is not valid JSON: {path}\n{exc}") from exc
    if not isinstance(data, dict):
        raise SchemaLookupError(f"Schema file must be a JSON object: {path}")
    return data


def _registry() -> Registry:
    resources = []
    for path in sorted(schemas_dir().glob("*.schema.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        resources.append((contents.get("$id", path.name), Resource.from_contents(contents)))
    return Registry().with_resources(resources)


def check_schema_document(schema: dict) -> None:
    """Raise SchemaError when ``schema`` is not a valid JSON Schema."""
    Draft202012Validator.check_schema(schema)


def validate_data(data, schema: dict) -> list[str]:
    """Return human-readable errors. An empty list means the data matches."""
    validator = Draft202012Validator(
        schema,
        registry=_registry(),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    errors = sorted(
        validator.iter_errors(data),
        key=lambda err: ([str(part) for part in err.absolute_path], err.message),
    )
    lines = []
    for err in errors:
        location = "/".join(str(part) for part in err.absolute_path) or "(root)"
        lines.append(f"{location}: {err.message}")
    return lines


def validate_file(path: str | Path, schema: str | Path | None = None) -> ValidationResult:
    """Validate one JSON file. Does not raise for invalid documents."""
    document = Path(path)
    schema_name = None
    try:
        if schema is None:
            inferred = matching_schema_name(document)
            if inferred is None:
                return ValidationResult(
                    path=document,
                    schema_name=None,
                    ok=False,
                    errors=[
                        "No matching schema. Name the file after its checklist "
                        "(for example shot-list.json) or pass the schema name."
                    ],
                )
            schema_path = resolve_schema_path(inferred)
        else:
            schema_path = resolve_schema_path(schema)
        schema_name = schema_path.name
        if not document.is_file():
            return ValidationResult(
                path=document,
                schema_name=schema_name,
                ok=False,
                errors=[f"File not found: {document}"],
            )
        try:
            data = json.loads(document.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return ValidationResult(
                path=document,
                schema_name=schema_name,
                ok=False,
                errors=[f"File is not valid JSON: {exc}"],
            )
        schema_data = load_schema(schema_path)
        errors = validate_data(data, schema_data)
    except SchemaLookupError as exc:
        return ValidationResult(
            path=document,
            schema_name=schema_name,
            ok=False,
            errors=[str(exc)],
        )
    return ValidationResult(
        path=document,
        schema_name=schema_name,
        ok=not errors,
        errors=errors,
    )


def load_known_mismatches() -> dict[str, str]:
    """Historical files that are allowed to fail the production audit."""
    path = config_dir() / "known-schema-mismatches.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["path"]: item["reason"] for item in data["files"]}


@dataclass
class AuditItem:
    """One file in a production-folder audit."""

    path: str
    schema_name: str | None
    status: str  # pass, known, fail, skip
    errors: list[str] = field(default_factory=list)
    reason: str = ""


def audit_production(production_dir: str | Path) -> list[AuditItem]:
    """Check every JSON file under a production folder.

    Files with no schema are skipped. Files listed in
    ``config/known-schema-mismatches.json`` are reported as known mismatches
    so the historical pilot can be audited without hiding a new failure.
    """
    folder = Path(production_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"Production folder not found: {folder}")

    known = load_known_mismatches()
    root = repo_root()
    items: list[AuditItem] = []
    for path in sorted(folder.rglob("*.json")):
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = resolved.as_posix()
        schema_name = matching_schema_name(path)
        if schema_name is None:
            items.append(AuditItem(path=rel, schema_name=None, status="skip"))
            continue
        result = validate_file(path, schema_name)
        if result.ok:
            items.append(AuditItem(path=rel, schema_name=schema_name, status="pass"))
            continue
        if rel in known:
            items.append(
                AuditItem(
                    path=rel,
                    schema_name=schema_name,
                    status="known",
                    errors=result.errors,
                    reason=known[rel],
                )
            )
            continue
        items.append(
            AuditItem(
                path=rel,
                schema_name=schema_name,
                status="fail",
                errors=result.errors,
            )
        )
    return items


def format_audit(items: list[AuditItem]) -> str:
    lines = []
    for item in items:
        if item.status == "pass":
            lines.append(f"PASS   {item.path}  ({item.schema_name})")
        elif item.status == "skip":
            lines.append(f"SKIP   {item.path}  (no schema for this file)")
        elif item.status == "known":
            lines.append(f"KNOWN  {item.path}  ({item.schema_name})")
            lines.append(f"       {item.reason}")
            for error in item.errors:
                lines.append(f"       - {error}")
        else:
            lines.append(f"FAIL   {item.path}  ({item.schema_name})")
            for error in item.errors:
                lines.append(f"       - {error}")
    counts = {status: sum(1 for item in items if item.status == status) for status in ("pass", "known", "fail", "skip")}
    lines.append(
        f"Summary: {counts['pass']} passed, {counts['known']} known mismatches, "
        f"{counts['fail']} failed, {counts['skip']} skipped."
    )
    return "\n".join(lines)


def audit_exit_code(items: list[AuditItem]) -> int:
    """Zero when every unexpected file passed. Known mismatches do not fail the audit."""
    return 1 if any(item.status == "fail" for item in items) else 0


# Re-export so callers can catch schema-document problems by name.
__all__ = [
    "AuditItem",
    "SchemaLookupError",
    "ValidationResult",
    "audit_exit_code",
    "audit_production",
    "check_schema_document",
    "format_audit",
    "load_known_mismatches",
    "load_schema",
    "matching_schema_name",
    "resolve_schema_path",
    "validate_data",
    "validate_file",
]
