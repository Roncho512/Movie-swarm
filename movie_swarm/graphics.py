"""Title and Graphic Design: research, a brand guide, then the graphics.

The Art Director owns the in-film look. This role reads that work and designs
the titles, the credits, the subtitle style, the key art, and the collateral.
It does not invent a fact the production documents do not state.

Research is written first. The brand guide is built only from that research.
Graphics are built only from an approved guide. Offline is the default. A
model reply that adds a fact is discarded. This module does not read a key,
does not open a network connection, and does not pass ``--live``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff
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


class GraphicsError(PrevisError):
    """A graphics step stopped. The message says what is missing."""


_TOPICS = ("director", "setting", "genre", "period", "references")
_SLUGLINE = re.compile(r"^(?:INT\.?/EXT\.?|EXT\.?/INT\.?|I/E\.?|INT\.?|EXT\.?|EST\.?)\b", re.I)
_RESOLUTION = re.compile(r"(\d{2,5})\s*[x×]\s*(\d{2,5})")
_FONT = re.compile(r"(?im)^(?:font family|typeface)\s*:\s*(.+)$")


def research_path(production_dir: Path) -> Path:
    return Path(production_dir) / "graphics" / "research.json"


def guide_path(production_dir: Path) -> Path:
    return Path(production_dir) / "graphics" / "brand-guide.json"


def graphics_path(production_dir: Path) -> Path:
    return Path(production_dir) / "graphics" / "graphics.json"


def write_research(production_dir: Path, llm=None) -> dict:
    """Write ``graphics/research.json`` from the production's own documents."""
    production_dir = Path(production_dir)
    document = _guard(_research_document, production_dir)
    document = _agreed(llm, document, "research", "items", document)
    save_pair(research_path(production_dir), document, "graphics-research", _research_markdown(document))
    return document


def write_guide(production_dir: Path, llm=None) -> dict:
    """Write the brand guide from research. Missing or stale research is an error."""
    production_dir = Path(production_dir)
    research = _require_research(production_dir)
    try:
        _require_fresh(production_dir, research, for_guide=True)
    except GraphicsError:
        raise
    except PrevisError as exc:
        raise GraphicsError(str(exc)) from exc
    fresh = _guide_document(production_dir, research)
    fresh = _agreed(llm, fresh, "guide", "rules_fingerprint", fresh)
    old = _read_json(guide_path(production_dir))
    document = _merge_guide(old, fresh)
    save_pair(guide_path(production_dir), document, "graphics-brand-guide", _guide_markdown(document))
    return document


def guide_is_approved(production_dir: Path) -> bool:
    data = _read_json(guide_path(production_dir))
    return bool(data) and data.get("status") == "approved"


def record_guide_decision(production_dir: Path, decision: str, by: str, note: str, decided_at: str) -> str:
    """Stamp the brand guide when the graphics gate is approved or rejected."""
    path = guide_path(production_dir)
    data = _read_json(path)
    if not data:
        return "No brand guide was on disk to stamp."
    if decision == "approved" and data.get("status") == "approved":
        return "The brand guide was already approved."
    data["status"] = "approved" if decision == "approved" else "draft"
    data["note"] = (
        "Approved at the graphics gate. Built from graphics/research.json."
        if decision == "approved"
        else "Rejected at the graphics gate. The guide is draft."
    )
    change = "Approved at the graphics gate." if decision == "approved" else "Rejected at the graphics gate."
    who = by.strip() or "recorded"
    if note.strip():
        change = f"{change} {note.strip()}"
    data.setdefault("change_log", []).append(
        {"version": str(data.get("version") or "1.0.0"), "at": decided_at, "change": f"{change} By {who}."}
    )
    save_pair(path, data, "graphics-brand-guide", _guide_markdown(data))
    if decision == "approved":
        return "The brand guide is approved."
    return "The brand guide is back to draft."


def build_graphics(production_dir: Path, llm=None) -> dict:
    """Write the graphic specs. The guide must already be approved."""
    production_dir = Path(production_dir)
    research = _require_research(production_dir)
    _require_fresh(production_dir, research, for_guide=False)
    guide = _require_approved_guide(production_dir)
    document = _guard(_graphics_document, production_dir, research, guide)
    document = _agreed(llm, document, "build", "package_fingerprint", document)
    _render_placeholders(production_dir, document)
    save_pair(graphics_path(production_dir), document, "graphics-package", _graphics_markdown(document))
    return document


def overlay_markdown(production_dir: Path, audience: str) -> str:
    """Title and credit notes for the editor or the colorist, when a package exists."""
    data = _read_json(graphics_path(production_dir))
    if not data:
        return ""
    handoff = data.get("handoff") or {}
    if audience not in (handoff.get("for") or []):
        return ""
    lines = ["", f"## Title and credit overlays for the {audience}", ""]
    lines.append(str(handoff.get("note") or "Apply these before the master."))
    lines.append("")
    title = (data.get("main_title") or {}).get("text")
    if title:
        lines.append(f"- Main title: {title}")
    for card in data.get("title_cards") or []:
        if isinstance(card, dict) and card.get("text"):
            lines.append(f"- Title card: {card['text']}")
    lines.append("- End credits: graphics/graphics.json. That file is refreshed before the master.")
    lines.append("- Subtitle timing stays with the Post Supervisor.")
    lines.append("")
    return "\n".join(lines)


def package_files(production_dir: Path) -> list[dict]:
    """Manifest rows for graphics that were written. Empty when the package is absent."""
    production_dir = Path(production_dir)
    path = graphics_path(production_dir)
    data = _read_json(path)
    if not data:
        return []
    rows = [
        {"path": path, "listed": "graphics/graphics.json", "label": "Graphic specs"},
    ]
    notes = path.with_suffix(".md")
    if notes.is_file():
        rows.append({"path": notes, "listed": "graphics/graphics.md", "label": "Graphic specs, readable copy"})
    key = data.get("key_art") or {}
    if key.get("filename"):
        rows.append(
            {
                "path": production_dir / str(key["filename"]),
                "listed": str(key["filename"]),
                "label": "Designed key art. Not the frame-grab poster.",
            }
        )
    for item in data.get("collateral") or []:
        if isinstance(item, dict) and item.get("filename"):
            rows.append(
                {
                    "path": production_dir / str(item["filename"]),
                    "listed": str(item["filename"]),
                    "label": f"Collateral {item.get('id') or 'card'}",
                }
            )
    return rows


def qc_checks(production_dir: Path) -> list[dict]:
    """Spelling, credits, safe area, and resolution against the approved guide."""
    production_dir = Path(production_dir)
    data = _read_json(graphics_path(production_dir))
    if not data:
        return []
    guide = _read_json(guide_path(production_dir)) or {}
    checks = [
        _spelling_check(production_dir, data),
        _credits_check(production_dir, data),
        _safe_check(data, guide),
        _resolution_check(production_dir, data),
    ]
    return checks


def _research_document(production_dir: Path) -> dict:
    treatment = approved_treatment(production_dir)
    brief = read_brief(production_dir)
    look_path = _first_file(production_dir, ("look/look.json",))
    bible_path = _first_file(
        production_dir,
        ("visual-style-bible.json", "art/visual-style-bible.json", "look/visual-style-bible.json"),
    )
    spec_path = _first_file(production_dir, ("delivery/delivery-spec.json",))
    look = load_optional(look_path, "look") if look_path else None
    bible = load_optional(bible_path, "visual-style-bible") if bible_path else None
    spec = load_optional(spec_path, "delivery-spec") if spec_path else None
    scripts = _screenplay_files(production_dir, brief)
    notes = _note_files(production_dir)
    items: list[dict] = []
    used: set[str] = set()

    def add(item_id: str, topic: str, text: str, basis: str, source_file: str | None, source_field: str | None) -> None:
        final = item_id
        count = 2
        while final in used:
            final = f"{item_id}-{count}"
            count += 1
        used.add(final)
        items.append(
            {
                "item_id": final,
                "topic": topic,
                "text": " ".join(text.split()),
                "basis": basis,
                "source_file": source_file,
                "source_field": source_field,
            }
        )

    title = str(treatment.get("title") or "").strip()
    if title:
        add("film-title", "director", f"Title: {title}.", "sourced", "treatment/treatment.json", "title")
    else:
        add("film-title", "director", "The treatment does not name a title.", "inferred", None, None)
    tone = str((treatment.get("tone_and_genre") or {}).get("tone") or "").strip()
    if tone:
        add("director-tone", "director", f"Tone: {tone}.", "sourced", "treatment/treatment.json", "tone_and_genre.tone")
    theme = (treatment.get("theme_and_emotional_intent") or {})
    if str(theme.get("theme") or "").strip():
        add(
            "director-theme",
            "director",
            f"Theme: {theme['theme']}.",
            "sourced",
            "treatment/treatment.json",
            "theme_and_emotional_intent.theme",
        )
    if str(theme.get("emotional_intent") or "").strip():
        add(
            "director-intent",
            "director",
            f"Emotional intent: {theme['emotional_intent']}.",
            "sourced",
            "treatment/treatment.json",
            "theme_and_emotional_intent.emotional_intent",
        )
    camera = str(treatment.get("camera_lens_film_stock") or "").strip()
    if camera:
        add(
            "director-camera",
            "references",
            f"Camera note: {camera}.",
            "sourced",
            "treatment/treatment.json",
            "camera_lens_film_stock",
        )
    color = str(treatment.get("color_and_light_plan") or "").strip()
    if color:
        add(
            "director-color",
            "references",
            f"Color and light: {color}.",
            "sourced",
            "treatment/treatment.json",
            "color_and_light_plan",
        )
    logline = str(treatment.get("logline") or "").strip()
    if logline:
        add("logline", "director", f"Logline: {logline}.", "sourced", "treatment/treatment.json", "logline")
    named_director = False
    for index, (relative, field, text) in enumerate(notes, start=1):
        named_director = True
        add(f"director-note-{index}", "director", text, "sourced", relative, field)
    if not named_director:
        add(
            "director-unnamed",
            "director",
            "The documents do not name a director. The treatment notes above are the directing reference.",
            "inferred",
            None,
            None,
        )

    scenes = treatment.get("scenes") or []
    found_setting = False
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        heading = str(scene.get("heading") or "").strip()
        if not heading:
            continue
        found_setting = True
        scene_id = slug(str(scene.get("scene_id") or f"s{index + 1:02d}"), "scene")
        add(
            f"setting-{scene_id}",
            "setting",
            f"Setting: {heading}.",
            "sourced",
            "treatment/treatment.json",
            f"scenes[{index}].heading",
        )
    if not found_setting:
        add("setting-unnamed", "setting", "The treatment does not name a place.", "inferred", None, None)
    add(
        "vernacular-unnamed",
        "setting",
        "The documents do not name local lettering, signage, or print. Do not invent a regional style.",
        "inferred",
        None,
        None,
    )

    genre = str((treatment.get("tone_and_genre") or {}).get("genre") or "").strip()
    if isinstance(brief, dict) and str(brief.get("genre") or "").strip() and not genre:
        genre = str(brief["genre"]).strip()
        add("genre-name", "genre", f"Genre: {genre}.", "sourced", "production-brief.json", "genre")
    elif genre:
        add("genre-name", "genre", f"Genre: {genre}.", "sourced", "treatment/treatment.json", "tone_and_genre.genre")
    else:
        add("genre-name", "genre", "The documents do not name a genre.", "inferred", None, None)
    add(
        "genre-graphics-unnamed",
        "genre",
        "The documents do not name a title layout, a poster layout, or a credit style for this genre. Do not import one.",
        "inferred",
        None,
        None,
    )

    font_hit = _font_hit(treatment, brief, look, bible, notes)
    if font_hit:
        add("period-type", "period", f"Typeface: {font_hit[0]}.", "sourced", font_hit[1], font_hit[2])
    else:
        add(
            "period-type",
            "period",
            "The documents do not name a typeface, a print method, or a year. Do not add one.",
            "inferred",
            None,
            None,
        )

    if look and str(look.get("summary") or "").strip():
        add("look-summary", "references", f"Look: {look['summary']}.", "sourced", _rel(production_dir, look_path), "summary")
    if look and look.get("look_name"):
        add(
            "look-name",
            "references",
            f"Look name: {look['look_name']}.",
            "sourced",
            _rel(production_dir, look_path),
            "look_name",
        )
    for index, name in enumerate(_look_palette(look)):
        add(
            f"palette-look-{slug(name, 'color')}",
            "references",
            f"Palette name: {name}.",
            "sourced",
            _rel(production_dir, look_path),
            f"palette[{index}]",
        )
    for index, color in enumerate(_bible_palette(bible)):
        add(
            f"palette-bible-{slug(color['name'], 'color')}",
            "references",
            f"Palette: {color['name']} {color['hex']}.",
            "sourced",
            _rel(production_dir, bible_path),
            f"color_system.palette[{index}]",
        )
    if bible and isinstance(bible.get("style_summary"), dict):
        description = str(bible["style_summary"].get("description") or "").strip()
        if description:
            add(
                "style-summary",
                "references",
                f"Style bible: {description}.",
                "sourced",
                _rel(production_dir, bible_path),
                "style_summary.description",
            )
    if not any(item["topic"] == "references" for item in items):
        add(
            "references-unnamed",
            "references",
            "The production has no look file and no style bible. Do not invent reference art.",
            "inferred",
            None,
            None,
        )
    if not any(item["item_id"].startswith("palette-") for item in items):
        add(
            "palette-unnamed",
            "references",
            "The documents do not name a color. Do not invent a palette value.",
            "inferred",
            None,
            None,
        )

    inset = _inset(spec)
    if inset is not None:
        add(
            "safe-area",
            "genre",
            f"Graphics-safe inset: {inset}.",
            "sourced",
            _rel(production_dir, spec_path),
            "safe_graphics_inset_percent",
        )
    else:
        add(
            "safe-area",
            "genre",
            "The documents do not name a graphics-safe inset. Do not invent one.",
            "inferred",
            None,
            None,
        )

    for path in scripts:
        add(
            f"screenplay-{slug(path.stem, 'script')}",
            "references",
            f"Screenplay read: {_rel(production_dir, path)}.",
            "sourced",
            _rel(production_dir, path),
            "text",
        )
    if spec_path:
        add(
            "delivery-spec",
            "references",
            "Delivery spec read for sizes. It does not replace the brand guide.",
            "sourced",
            _rel(production_dir, spec_path),
            "master",
        )

    missing = [topic for topic in _TOPICS if not any(item["topic"] == topic for item in items)]
    if missing:
        raise GraphicsError("Research could not cover: " + ", ".join(missing) + ".")

    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "items": items,
        "fingerprints": {
            "style_bible": _fingerprint(production_dir, bible_path, bible),
            "look": _fingerprint(production_dir, look_path, look),
        },
        "draft_method": "offline-deterministic",
        "model": model_name("title-graphic-design", "research"),
        "note": "Research from the production documents. Each item is sourced or inferred. Nothing was added.",
        "written_at": now(),
    }


def _guide_document(production_dir: Path, research: dict) -> dict:
    by_id = {item["item_id"]: item for item in research["items"]}
    fonts = {}
    for key in ("title", "credits", "subtitles", "marketing"):
        if by_id["period-type"]["basis"] == "sourced" and key == "title":
            family = by_id["period-type"]["text"].split(":", 1)[-1].strip().rstrip(".")
            licensing = "Use only the face the research names. Confirm the license before delivery."
        else:
            family = "not named"
            licensing = "No license is named in the documents. Do not assume a face is free to use."
        fonts[key] = {"family": family, "licensing": licensing, "trace": "period-type"}

    palette = []
    seen = set()
    for item in research["items"]:
        if not item["item_id"].startswith("palette-bible-"):
            continue
        name, hex_value = _split_palette(item["text"])
        palette.append({"name": name, "value": hex_value, "trace": item["item_id"]})
        seen.add(name.casefold())
    for item in research["items"]:
        if not item["item_id"].startswith("palette-look-"):
            continue
        name = item["text"].split(":", 1)[-1].strip().rstrip(".")
        if name.casefold() in seen:
            continue
        palette.append({"name": name, "value": name, "trace": item["item_id"]})
        seen.add(name.casefold())
    if not palette:
        palette.append({"name": "not named", "value": "not named", "trace": "palette-unnamed"})

    title_item = by_id["film-title"]
    title = title_item["text"].split(":", 1)[-1].strip().rstrip(".") if title_item["basis"] == "sourced" else "not named"
    safe = by_id["safe-area"]["text"]
    safe_value = "not named"
    if by_id["safe-area"]["basis"] == "sourced":
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", safe)
        safe_value = match.group(1) if match else safe
    if "look-summary" in by_id:
        look_trace = "look-summary"
    elif "references-unnamed" in by_id:
        look_trace = "references-unnamed"
    else:
        look_trace = next(item["item_id"] for item in research["items"] if item["topic"] == "references")
    look_text = by_id[look_trace]["text"] if look_trace in by_id else "No look is named."
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "status": "draft",
        "research": "graphics/research.json",
        "fonts": fonts,
        "palette": palette,
        "wordmark": {
            "title": title,
            "rules": [
                {
                    "rule_id": "wordmark-spelling",
                    "text": "Set the title as the research spells it.",
                    "trace": "film-title",
                }
            ],
        },
        "layout": {
            "safe_area": safe_value,
            "rules": [
                {
                    "rule_id": "layout-safe",
                    "text": by_id["safe-area"]["text"],
                    "trace": "safe-area",
                }
            ],
        },
        "image_treatment": {
            "rules": [
                {
                    "rule_id": "treatment-look",
                    "text": f"Image treatment follows the research. {look_text}",
                    "trace": look_trace,
                }
            ],
        },
        "dos": [
            {
                "rule_id": "do-palette",
                "text": "Use only palette values that trace to research.",
                "trace": palette[0]["trace"],
            }
        ],
        "donts": [
            {
                "rule_id": "dont-invent",
                "text": "Do not add a typeface, a print method, a year, or a layout the research does not name.",
                "trace": "period-type",
            }
        ],
        "fingerprints": research["fingerprints"],
        "change_log": [
            {"version": "1.0.0", "at": now(), "change": "Created from research."}
        ],
        "draft_method": "offline-deterministic",
        "model": model_name("title-graphic-design", "guide"),
        "note": "Built only from graphics/research.json. Not approved yet.",
        "written_at": now(),
    }
    document["rules_fingerprint"] = _rules_fingerprint(document)
    return document


def _merge_guide(old: dict | None, fresh: dict) -> dict:
    if not old:
        return fresh
    same_rules = old.get("rules_fingerprint") == fresh.get("rules_fingerprint")
    same_files = old.get("fingerprints") == fresh.get("fingerprints")
    if same_rules and same_files:
        return old
    version = _bump(str(old.get("version") or "1.0.0"))
    if old.get("fingerprints") != fresh.get("fingerprints"):
        change = "The style bible or the look changed. The guide was rebuilt from new research."
    else:
        change = "Rebuilt from research."
    fresh["version"] = version
    fresh["status"] = "draft"
    fresh["note"] = "Rebuilt from research. Approval does not carry over."
    fresh["change_log"] = list(old.get("change_log") or []) + [
        {"version": version, "at": fresh["written_at"], "change": change}
    ]
    fresh["rules_fingerprint"] = _rules_fingerprint(fresh)
    return fresh


def _graphics_document(production_dir: Path, research: dict, guide: dict) -> dict:
    by_id = {item["item_id"]: item for item in research["items"]}
    title = str(guide["wordmark"]["title"])
    safe = str(guide["layout"]["safe_area"])
    cards = _title_cards(production_dir, read_brief(production_dir), safe)
    credits, credit_source = _credit_lines(production_dir)
    tagline = None
    if by_id.get("logline", {}).get("basis") == "sourced":
        tagline = by_id["logline"]["text"].split(":", 1)[-1].strip().rstrip(".")
    sizes = _sizes(production_dir)
    subtitle_color = guide["palette"][0]["value"] if guide.get("palette") else "not named"
    key_width, key_height, key_source = sizes["key"]
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "guide": "graphics/brand-guide.json",
        "guide_version": str(guide.get("version") or "1.0.0"),
        "main_title": {
            "text": title,
            "font": guide["fonts"]["title"]["family"],
            "safe_area": safe,
            "trace": "film-title",
        },
        "title_cards": cards,
        "end_credits": {"source": credit_source, "lines": credits},
        "subtitles": {
            "timing_owner": "post-supervisor",
            "note": "Timing stays with the Post Supervisor. This spec does not set cue times.",
            "family": guide["fonts"]["subtitles"]["family"],
            "color": subtitle_color,
            "safe_area": safe,
        },
        "key_art": {
            "filename": "graphics/key-art-poster.png",
            "kind": "designed",
            "distinct_from": "poster.png",
            "title": title,
            "tagline": tagline,
            "billing_block": [f"{line['role']}: {line['name']}" for line in credits],
            "width": key_width,
            "height": key_height,
            "size_source": key_source,
            "safe_area": safe,
            "render_status": "not-rendered",
        },
        "collateral": [
            _collateral("thumbnail-16x9", "16:9", "graphics/thumbnail-16x9.png", sizes["thumbnail_16x9"], safe),
            _collateral("thumbnail-9x16", "9:16", "graphics/thumbnail-9x16.png", sizes["thumbnail_9x16"], safe),
            _collateral("social-card", "9:16", "graphics/social-card.png", sizes["social"], safe),
        ],
        "handoff": {
            "for": ["editor", "colorist", "post-supervisor"],
            "overlays_before_master": True,
            "note": (
                "Hand the title and credit overlays to the editor and the colorist before the master. "
                "The designed poster is key-art-poster.png. The frame grab stays poster.png. "
                "QA checks spelling, credits, safe areas, and resolution against the brand guide."
            ),
        },
        "draft_method": "offline-deterministic",
        "model": model_name("title-graphic-design", "build"),
        "note": "Specs from the approved brand guide. Placeholder frames are not a designed picture.",
        "written_at": now(),
    }
    document["package_fingerprint"] = _package_fingerprint(document)
    return document


def _title_cards(production_dir: Path, brief: dict, safe: str) -> list[dict]:
    cards = []
    for path in _screenplay_files(production_dir, brief):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GraphicsError(f"Could not read the screenplay {path.name}. {exc}") from exc
        relative = _rel(production_dir, path)
        for line_number, card_text in _card_lines(text):
            cards.append(
                {
                    "card_id": f"card-{len(cards) + 1}",
                    "text": card_text,
                    "source_file": relative,
                    "source_line": line_number,
                    "safe_area": safe,
                }
            )
    return cards


def _card_lines(text: str) -> list[tuple[int, str]]:
    found = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip().strip("*").strip()
        upper = stripped.upper().rstrip(".")
        if not upper.startswith("TITLE CARD"):
            index += 1
            continue
        rest = stripped[len("TITLE CARD") :].strip(" .:-")
        if rest:
            found.append((index + 1, rest))
            index += 1
            continue
        follower = ""
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if next_index < len(lines):
            candidate = lines[next_index].strip().strip("*").strip()
            if candidate and not _SLUGLINE.match(candidate) and not candidate.upper().startswith("TITLE CARD"):
                follower = candidate
        if follower:
            found.append((next_index + 1, follower))
        index = next_index + 1 if follower else index + 1
    return found


def _credit_lines(production_dir: Path) -> tuple[list[dict], str | None]:
    runs = production_dir / "runs"
    if not runs.is_dir():
        return [], None
    paths = [path for path in runs.glob("*/line-producer.json") if path.is_file()]
    if not paths:
        return [], None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    try:
        record = read_handoff(path, schema="line-producer-record")
    except HandoffError as exc:
        raise GraphicsError(str(exc)) from exc
    lines = []
    for item in record.get("credits") or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        name = str(item.get("name") or "").strip()
        if role and name:
            lines.append({"role": role, "name": name})
    return lines, str(path.relative_to(production_dir))


def _sizes(production_dir: Path) -> dict:
    treatment = approved_treatment(production_dir)
    spec_path = production_dir / "delivery" / "delivery-spec.json"
    spec = load_optional(spec_path, "delivery-spec") if spec_path.is_file() else None
    treatment_box = _resolution_box((treatment.get("deliverables") or {}).get("resolution"))
    treatment_aspect = str((treatment.get("deliverables") or {}).get("aspect_ratio") or "")
    key = (None, None, None)
    if isinstance(spec, dict) and isinstance(spec.get("master"), dict):
        master = spec["master"]
        if master.get("width") and master.get("height"):
            key = (int(master["width"]), int(master["height"]), "delivery/delivery-spec.json#master")
    if key[0] is None and treatment_box:
        key = (*treatment_box, "treatment/treatment.json#deliverables.resolution")
    wide = _variant_box(spec, aspect="16:9", use=None)
    if wide[0] is None and treatment_aspect == "16:9" and treatment_box:
        wide = (*treatment_box, "treatment/treatment.json#deliverables.resolution")
    tall = _variant_box(spec, aspect="9:16", use=None)
    social = _variant_box(spec, aspect=None, use="social")
    if social[0] is None:
        social = tall
    return {"key": key, "thumbnail_16x9": wide, "thumbnail_9x16": tall, "social": social}


def _variant_box(spec: dict | None, aspect: str | None, use: str | None) -> tuple:
    if not isinstance(spec, dict):
        return (None, None, None)
    for entry in spec.get("variants") or []:
        if not isinstance(entry, dict):
            continue
        if aspect and str(entry.get("aspect_ratio") or "") != aspect:
            continue
        if use and str(entry.get("use") or "") != use:
            continue
        if entry.get("width") and entry.get("height"):
            field = f"variants.{entry.get('id') or aspect or use}"
            return (int(entry["width"]), int(entry["height"]), f"delivery/delivery-spec.json#{field}")
    return (None, None, None)


def _collateral(item_id: str, aspect: str, filename: str, size: tuple, safe: str) -> dict:
    width, height, source = size
    return {
        "id": item_id,
        "aspect_ratio": aspect,
        "filename": filename,
        "width": width,
        "height": height,
        "size_source": source,
        "safe_area": safe,
        "render_status": "not-rendered",
    }


def _render_placeholders(production_dir: Path, document: dict) -> None:
    targets = [document["key_art"], *document["collateral"]]
    ffmpeg = shutil.which("ffmpeg")
    for item in targets:
        width = item.get("width")
        height = item.get("height")
        dest = production_dir / str(item["filename"])
        if not ffmpeg or not width or not height:
            item["render_status"] = "not-rendered"
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x202020:s={int(width)}x{int(height)}:d=1",
            "-frames:v",
            "1",
            str(dest),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if completed is not None and completed.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            item["render_status"] = "present"
        else:
            if dest.is_file():
                dest.unlink()
            item["render_status"] = "not-rendered"


def _require_research(production_dir: Path) -> dict:
    path = research_path(production_dir)
    if not path.is_file():
        raise GraphicsError("No graphics research. Write graphics/research.json before the brand guide.")
    try:
        data = read_handoff(path, schema="graphics-research")
    except HandoffError as exc:
        raise GraphicsError(str(exc)) from exc
    return data


def _require_approved_guide(production_dir: Path) -> dict:
    path = guide_path(production_dir)
    if not path.is_file():
        raise GraphicsError(
            "The brand guide is missing. Write graphics/brand-guide.json and approve it before building graphics."
        )
    try:
        data = read_handoff(path, schema="graphics-brand-guide")
    except HandoffError as exc:
        raise GraphicsError(str(exc)) from exc
    if data.get("status") != "approved":
        raise GraphicsError("The brand guide is still a draft. Approve the graphics gate before building graphics.")
    return data


def _require_fresh(production_dir: Path, research: dict, *, for_guide: bool) -> None:
    current = {
        "style_bible": _live_fingerprint(production_dir, "style_bible"),
        "look": _live_fingerprint(production_dir, "look"),
    }
    stored = research.get("fingerprints") or {}
    for key in ("style_bible", "look"):
        old = stored.get(key)
        now_fp = current[key]
        old_hash = old.get("sha256") if isinstance(old, dict) else None
        new_hash = now_fp.get("sha256") if isinstance(now_fp, dict) else None
        if old_hash != new_hash:
            if for_guide:
                raise GraphicsError(
                    "The style bible or the look changed after the research was written. "
                    "Write the research again before the brand guide."
                )
            raise GraphicsError(
                "The style bible or the look changed after the brand guide was approved. "
                "Update the research and the brand guide before building graphics."
            )


def _live_fingerprint(production_dir: Path, kind: str) -> dict | None:
    if kind == "look":
        path = _first_file(production_dir, ("look/look.json",))
        schema = "look"
    else:
        path = _first_file(
            production_dir,
            ("visual-style-bible.json", "art/visual-style-bible.json", "look/visual-style-bible.json"),
        )
        schema = "visual-style-bible"
    if path is None:
        return None
    data = load_optional(path, schema)
    return _fingerprint(production_dir, path, data)


def _fingerprint(production_dir: Path, path: Path | None, data: dict | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    version = None
    if isinstance(data, dict) and data.get("version"):
        version = str(data["version"])
    return {
        "path": _rel(production_dir, path),
        "version": version,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _spelling_check(production_dir: Path, data: dict) -> dict:
    problems = []
    try:
        treatment = approved_treatment(production_dir)
    except PrevisError as exc:
        return _check("graphics-spelling", "graphics/graphics.json", "fail", str(exc))
    title = str(treatment.get("title") or "")
    main = str((data.get("main_title") or {}).get("text") or "")
    if main != title:
        problems.append(f"The main title is {main!r}. The treatment title is {title!r}.")
    for card in data.get("title_cards") or []:
        if not isinstance(card, dict):
            continue
        source = production_dir / str(card.get("source_file") or "")
        card_text = str(card.get("text") or "")
        if not source.is_file() or card_text not in source.read_text(encoding="utf-8"):
            problems.append(f"Title card {card_text!r} is not in {card.get('source_file')}.")
    if problems:
        return _check("graphics-spelling", "graphics/graphics.json", "fail", " ".join(problems))
    count = len(data.get("title_cards") or [])
    return _check(
        "graphics-spelling",
        "graphics/graphics.json",
        "pass",
        f"The main title matches the treatment. {count} title card(s) match the screenplay.",
    )


def _credits_check(production_dir: Path, data: dict) -> dict:
    block = data.get("end_credits") or {}
    source = block.get("source")
    got = [(str(item.get("role")), str(item.get("name"))) for item in block.get("lines") or [] if isinstance(item, dict)]
    if not source:
        expect = []
    else:
        path = production_dir / str(source)
        try:
            record = read_handoff(path, schema="line-producer-record")
        except HandoffError as exc:
            return _check("graphics-credits", str(source), "fail", str(exc))
        expect = [
            (str(item.get("role")), str(item.get("name")))
            for item in record.get("credits") or []
            if isinstance(item, dict) and item.get("role") and item.get("name")
        ]
    if got != expect:
        return _check(
            "graphics-credits",
            str(source or "graphics/graphics.json"),
            "fail",
            "The end credits do not match the Line Producer credit record.",
        )
    return _check(
        "graphics-credits",
        str(source or "graphics/graphics.json"),
        "pass",
        f"{len(got)} credit(s) match the Line Producer record. No name was added.",
    )


def _safe_check(data: dict, guide: dict) -> dict:
    expected = str((guide.get("layout") or {}).get("safe_area") or "")
    problems = []
    for label, value in _safe_values(data):
        if str(value) != expected:
            problems.append(f"{label} safe area is {value!r}. The guide says {expected!r}.")
    if problems:
        return _check("graphics-safe-area", "graphics/brand-guide.json", "fail", " ".join(problems))
    return _check(
        "graphics-safe-area",
        "graphics/brand-guide.json",
        "pass",
        f"Safe area is {expected!r} on every graphic, matching the brand guide.",
    )


def _safe_values(data: dict) -> list[tuple[str, object]]:
    found = [("main title", (data.get("main_title") or {}).get("safe_area"))]
    for card in data.get("title_cards") or []:
        if isinstance(card, dict):
            found.append((f"title card {card.get('card_id')}", card.get("safe_area")))
    found.append(("subtitles", (data.get("subtitles") or {}).get("safe_area")))
    found.append(("key art", (data.get("key_art") or {}).get("safe_area")))
    for item in data.get("collateral") or []:
        if isinstance(item, dict):
            found.append((str(item.get("id")), item.get("safe_area")))
    return found


def _resolution_check(production_dir: Path, data: dict) -> dict:
    targets = [data.get("key_art") or {}, *(data.get("collateral") or [])]
    present = [item for item in targets if isinstance(item, dict) and item.get("render_status") == "present"]
    if not present:
        return _check(
            "graphics-resolution",
            "graphics/graphics.json",
            "skipped",
            "No graphic file was rendered, so resolution was not measured.",
        )
    problems = []
    for item in present:
        path = production_dir / str(item.get("filename") or "")
        width, height = _probe_size(path)
        if width is None or height is None:
            return _check(
                "graphics-resolution",
                str(item.get("filename") or path.name),
                "skipped",
                "Resolution was not read.",
            )
        if int(width) != int(item.get("width") or -1) or int(height) != int(item.get("height") or -1):
            problems.append(
                f"{item.get('filename')} is {width}x{height}. The spec asks for {item.get('width')}x{item.get('height')}."
            )
    if problems:
        return _check("graphics-resolution", "graphics/graphics.json", "fail", " ".join(problems))
    return _check(
        "graphics-resolution",
        "graphics/graphics.json",
        "pass",
        f"{len(present)} graphic file(s) match the spec size.",
    )


def _probe_size(path: Path) -> tuple[int | None, int | None]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.is_file():
        return None, None
    try:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json", "-show_streams", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None, None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, None
    for stream in payload.get("streams") or []:
        if stream.get("width") and stream.get("height"):
            return int(stream["width"]), int(stream["height"])
    return None, None


def _check(check_id: str, target: str, status: str, detail: str) -> dict:
    return {
        "check_id": check_id,
        "target": target,
        "kind": "graphics",
        "status": status,
        "detail": detail,
    }


def _agreed(llm, offline: dict, purpose: str, key: str, sources) -> dict:
    """Keep the offline document unless the model repeats it without new facts."""
    if llm is None:
        return offline
    drafted = try_model_json(
        llm,
        role="title-graphic-design",
        purpose=purpose,
        system=system_prompt(
            "You are Title and Graphic Design. Repeat only the facts already in the documents."
        ),
        user=source_blob(offline, sources),
    )
    if not isinstance(drafted, dict):
        return offline
    if drafted.get(key) != offline.get(key):
        return offline
    agreed = dict(offline)
    agreed["draft_method"] = "model"
    agreed["note"] = offline["note"]
    return agreed


def _screenplay_files(production_dir: Path, brief: dict) -> list[Path]:
    found: list[Path] = []
    relative = brief.get("screenplay_path") if isinstance(brief, dict) else None
    if relative:
        path = production_dir / str(relative)
        if path.is_file():
            found.append(path)
    folder = production_dir / "screenplay"
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.lower() in {".md", ".fountain", ".txt"} and path not in found:
                found.append(path)
    return found


def _note_files(production_dir: Path) -> list[tuple[str, str, str]]:
    found = []
    for relative in ("director/notes.md", "director/notes.txt", "notes/director.md"):
        path = production_dir / relative
        if path.is_file():
            text = " ".join(path.read_text(encoding="utf-8").split())
            if text:
                found.append((relative, "text", text))
    path = production_dir / "director" / "notes.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GraphicsError(f"director/notes.json is not valid JSON. {exc}") from exc
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value.strip():
                    found.append(("director/notes.json", str(key), " ".join(value.split())))
    return found


def _font_hit(treatment, brief, look, bible, notes) -> tuple[str, str, str] | None:
    blobs = [
        ("treatment/treatment.json", "text", json.dumps(treatment, ensure_ascii=False)),
        ("production-brief.json", "text", json.dumps(brief, ensure_ascii=False) if brief else ""),
        ("look/look.json", "text", json.dumps(look, ensure_ascii=False) if look else ""),
        ("visual-style-bible.json", "text", json.dumps(bible, ensure_ascii=False) if bible else ""),
    ]
    for relative, field, text in notes:
        blobs.append((relative, field, text))
    for relative, field, text in blobs:
        match = _FONT.search(text)
        if match:
            return match.group(1).strip(), relative, field
    return None


def _look_palette(look: dict | None) -> list[str]:
    if not isinstance(look, dict):
        return []
    names = []
    for item in look.get("palette") or []:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names


def _bible_palette(bible: dict | None) -> list[dict]:
    if not isinstance(bible, dict):
        return []
    colors = []
    palette = (bible.get("color_system") or {}).get("palette") or []
    for item in palette:
        if isinstance(item, dict) and item.get("name") and item.get("hex"):
            colors.append({"name": str(item["name"]).strip(), "hex": str(item["hex"]).strip()})
    return colors


def _inset(spec: dict | None):
    if not isinstance(spec, dict):
        return None
    value = spec.get("safe_graphics_inset_percent")
    if value is None:
        return None
    return value


def _resolution_box(value) -> tuple[int, int] | None:
    if not value:
        return None
    match = _RESOLUTION.search(str(value))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _split_palette(text: str) -> tuple[str, str]:
    body = text.split(":", 1)[-1].strip().rstrip(".")
    parts = body.split()
    if parts and parts[-1].startswith("#"):
        return " ".join(parts[:-1]) or body, parts[-1]
    return body, body


def _first_file(production_dir: Path, relatives: tuple[str, ...]) -> Path | None:
    for relative in relatives:
        path = production_dir / relative
        if path.is_file():
            return path
    return None


def _rel(production_dir: Path, path: Path | None) -> str:
    if path is None:
        return ""
    return path.resolve().relative_to(production_dir.resolve()).as_posix()


def _bump(version: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return "1.0.1"
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def _rules_fingerprint(document: dict) -> str:
    payload = {
        "fonts": document.get("fonts"),
        "palette": document.get("palette"),
        "wordmark": document.get("wordmark"),
        "layout": document.get("layout"),
        "image_treatment": document.get("image_treatment"),
        "dos": document.get("dos"),
        "donts": document.get("donts"),
        "fingerprints": document.get("fingerprints"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _package_fingerprint(document: dict) -> str:
    payload = {
        "main_title": document.get("main_title"),
        "title_cards": document.get("title_cards"),
        "end_credits": document.get("end_credits"),
        "subtitles": document.get("subtitles"),
        "key_art": {key: value for key, value in (document.get("key_art") or {}).items() if key != "render_status"},
        "collateral": [
            {key: value for key, value in item.items() if key != "render_status"}
            for item in document.get("collateral") or []
            if isinstance(item, dict)
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _guard(function, *args):
    try:
        return function(*args)
    except GraphicsError:
        raise
    except PrevisError as exc:
        raise GraphicsError(str(exc)) from exc


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _research_markdown(document: dict) -> str:
    lines = ["# Graphics research", "", document.get("note") or "", ""]
    for item in document.get("items") or []:
        where = "inferred"
        if item.get("basis") == "sourced":
            where = f"sourced from {item.get('source_file')} {item.get('source_field')}"
        lines.append(f"- {item['topic']}: {item['text']} ({where})")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _guide_markdown(document: dict) -> str:
    lines = [
        "# Brand guide",
        "",
        document.get("note") or "",
        "",
        f"Status: {document.get('status')}. Version {document.get('version')}.",
        "",
        "## Fonts",
        "",
    ]
    for name, font in (document.get("fonts") or {}).items():
        lines.append(f"- {name}: {font.get('family')}. {font.get('licensing')}")
    lines.extend(["", "## Palette", ""])
    for color in document.get("palette") or []:
        lines.append(f"- {color.get('name')}: {color.get('value')}")
    wordmark = document.get("wordmark") or {}
    lines.extend(["", "## Wordmark", "", str(wordmark.get("title") or ""), ""])
    for rule in wordmark.get("rules") or []:
        lines.append(f"- {rule.get('text')}")
    layout = document.get("layout") or {}
    lines.extend(["", "## Layout", "", f"Safe area: {layout.get('safe_area')}.", ""])
    for rule in layout.get("rules") or []:
        lines.append(f"- {rule.get('text')}")
    lines.extend(["", "## Do", ""])
    for rule in document.get("dos") or []:
        lines.append(f"- {rule.get('text')}")
    lines.extend(["", "## Don't", ""])
    for rule in document.get("donts") or []:
        lines.append(f"- {rule.get('text')}")
    lines.extend(["", "## Change log", ""])
    for entry in document.get("change_log") or []:
        lines.append(f"- {entry.get('version')}: {entry.get('change')}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _graphics_markdown(document: dict) -> str:
    lines = ["# Graphics", "", document.get("note") or "", ""]
    title = document.get("main_title") or {}
    lines.append(f"Main title: {title.get('text')}.")
    lines.append("")
    if document.get("title_cards"):
        lines.append("Title cards:")
        lines.append("")
        for card in document["title_cards"]:
            lines.append(f"- {card.get('text')} ({card.get('source_file')})")
        lines.append("")
    else:
        lines.append("No TITLE CARD lines were in the screenplay.")
        lines.append("")
    credits = (document.get("end_credits") or {}).get("lines") or []
    lines.append("End credits:")
    lines.append("")
    if not credits:
        lines.append("No Line Producer credit record. No name was added.")
    for line in credits:
        lines.append(f"- {line.get('role')}: {line.get('name')}")
    lines.append("")
    subtitles = document.get("subtitles") or {}
    lines.append(subtitles.get("note") or "")
    key = document.get("key_art") or {}
    lines.extend(
        [
            "",
            f"Key art: {key.get('filename')} ({key.get('render_status')}). Distinct from {key.get('distinct_from')}.",
            "",
        ]
    )
    for item in document.get("collateral") or []:
        lines.append(f"- {item.get('id')}: {item.get('filename')} ({item.get('render_status')}).")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
