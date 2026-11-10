"""Read a screenplay or a partial treatment from disk.

A screenplay can be Markdown, Fountain, PDF, or Word (.docx). A partial
treatment is JSON, or a Markdown worksheet that already uses treatment
labels such as ``Logline:``. One intake can take a screenplay, a partial
treatment, or both.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


_HEADING = re.compile(
    r"^(?:#{1,6}\s+)?((?:INT\.?/EXT\.?|INT\.|EXT\.|EST\.|I/E\.?)(?:[ \t].*)?)$",
    re.IGNORECASE | re.MULTILINE,
)
_TITLE_LINE = re.compile(r"(?im)^title:\s*(.+)$")


@dataclass
class ParsedSource:
    """One input file, normalized to text plus any treatment fields already filled."""

    path: str
    kind: str
    title: str
    text: str
    scenes: list[dict] = field(default_factory=list)
    partial: dict | None = None


def load_source(path: str | Path) -> ParsedSource:
    """Load one screenplay or partial treatment. Raises ``ValueError`` when the file cannot be read."""
    document = Path(path)
    if not document.is_file():
        raise ValueError(f"Input file not found: {document}")
    suffix = document.suffix.lower()
    if suffix == ".pdf":
        text = _pdf_text(document)
        return _from_screenplay(document, "pdf", text)
    if suffix == ".docx":
        text = _docx_text(document)
        return _from_screenplay(document, "docx", text)
    if suffix == ".json":
        try:
            data = json.loads(document.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{document} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict) or not _looks_like_treatment(data):
            raise ValueError(
                f"{document} is JSON but not a treatment. "
                "A partial treatment needs a logline, a theme, or scene beats."
            )
        title = str(data.get("title") or document.stem)
        return ParsedSource(
            path=str(document),
            kind="treatment-json",
            title=title,
            text="",
            scenes=[],
            partial=data,
        )

    text = document.read_text(encoding="utf-8")
    if suffix in {".fountain", ".fou"}:
        return _from_screenplay(document, "fountain", text)
    if _looks_like_treatment_markdown(text):
        partial = _partial_from_markdown(text)
        scenes = _scenes_from_text(text)
        return ParsedSource(
            path=str(document),
            kind="treatment-markdown",
            title=str(partial.get("title") or _title_from_text(text) or document.stem),
            text=text,
            scenes=scenes,
            partial=partial,
        )
    kind = "fountain" if suffix in {".fountain", ".fou"} else "markdown"
    return _from_screenplay(document, kind, text)


def _from_screenplay(path: Path, kind: str, text: str) -> ParsedSource:
    return ParsedSource(
        path=str(path),
        kind=kind,
        title=_title_from_text(text) or path.stem,
        text=text,
        scenes=_scenes_from_text(text),
        partial=None,
    )


def _looks_like_treatment(data: dict) -> bool:
    if "logline" in data or "theme_and_emotional_intent" in data:
        return True
    scenes = data.get("scenes")
    if isinstance(scenes, list) and scenes and isinstance(scenes[0], dict):
        return "what_happens" in scenes[0]
    return False


def _looks_like_treatment_markdown(text: str) -> bool:
    return bool(re.search(r"(?im)^logline\s*:", text))


def _partial_from_markdown(text: str) -> dict:
    """Pull a few labeled lines out of a worksheet. Scene headings are parsed separately."""
    labels = {
        "logline": "logline",
        "title": "title",
        "theme": "theme",
        "emotional intent": "emotional_intent",
        "tone": "tone",
        "genre": "genre",
        "world": "world_and_period",
        "world and period": "world_and_period",
    }
    found: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        key = labels.get(label.strip().lower())
        if key and value.strip():
            found[key] = value.strip()
    partial: dict = {}
    if "title" in found:
        partial["title"] = found["title"]
    if "logline" in found:
        partial["logline"] = found["logline"]
    if "theme" in found or "emotional_intent" in found:
        partial["theme_and_emotional_intent"] = {
            "theme": found.get("theme", ""),
            "emotional_intent": found.get("emotional_intent", ""),
        }
    if "tone" in found or "genre" in found:
        partial["tone_and_genre"] = {
            "tone": found.get("tone", ""),
            "genre": found.get("genre", ""),
        }
    if "world_and_period" in found:
        partial["world_and_period"] = found["world_and_period"]
    return partial


def _title_from_text(text: str) -> str:
    titled = _TITLE_LINE.search(text)
    if titled:
        return _clean_title(titled.group(1))
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return _clean_title(stripped.lstrip("#").strip())
    return ""


def _clean_title(raw: str) -> str:
    cleaned = raw.replace("*", "").replace('"', "").replace("“", "").replace("”", "").strip()
    if cleaned.isupper():
        return cleaned.title()
    return cleaned


def _scenes_from_text(text: str) -> list[dict]:
    matches = list(_HEADING.finditer(text))
    scenes = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        body = re.split(r"\n(?:#{2,}\s|END\.)", body, maxsplit=1)[0].strip()
        scenes.append({"heading": match.group(1).strip(), "body": body})
    return scenes


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("Install pypdf to read a PDF screenplay.") from exc
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _docx_text(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError("Install python-docx to read a Word screenplay.") from exc
    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)
