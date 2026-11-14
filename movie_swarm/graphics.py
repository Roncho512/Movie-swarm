"""Title and Graphic Design: research, a brand guide, then the graphics.

The Art Director owns the in-film look. This role reads that work and designs
the titles, the credits, the subtitle style, the key art, and the collateral.

Research is written first. A fact from the production documents is sourced or
inferred. A suggestion from a design-reference pack is a designer proposal and
cites its reference. The brand guide is built only from that research, and it
stays a draft until the graphics gate. Graphics are built only from an
approved guide. Offline is the default. This module does not read a key, does
not open a network connection, and does not pass ``--live``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff
from movie_swarm.mentions import advertising_phrases, story_purpose_line
from movie_swarm.paths import config_dir, repo_root
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
from movie_swarm.validate import load_schema, validate_data


class GraphicsError(PrevisError):
    """A graphics step stopped. The message says what is missing."""


_TOPICS = ("director", "setting", "genre", "period", "references")
_FROM_DOCS = "SOURCED FROM PRODUCTION DOCS"
_PROPOSAL = "DESIGNER PROPOSAL"
_SLUGLINE = re.compile(r"^(?:INT\.?/EXT\.?|EXT\.?/INT\.?|I/E\.?|INT\.?|EXT\.?|EST\.?)\b", re.I)
_RESOLUTION = re.compile(r"(\d{2,5})\s*[x×]\s*(\d{2,5})")
_FONT = re.compile(r"(?im)^(?:font family|typeface)\s*:\s*(.+)$")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_DIRECTION_OPEN = re.compile(
    r"^(?:over|on|against|across|under|above|behind|through|into|onto|during|same|using|with|amid|amidst|upon|before|after|while|from|at)\b",
    re.I,
)
_STYLE_WORD = re.compile(r"\b(?:typography|typeface|typefaces|font|fonts|lettering|background)\b", re.I)
_TRANSITION = re.compile(r"^(?:FADE|CUT|DISSOLVE|SMASH|MATCH|JUMP|IRIS|WIPE|HOLD)\b", re.I)
_STYLE_CUE = re.compile(
    r"\b((?:[A-Za-z][\w'-]*\s+){0,5}(?:typography|typeface|lettering|font))\b",
    re.I,
)
_QUOTED = re.compile(r"[\"“]([^\"”]+)[\"”]")
_CARD_LABEL = re.compile(r"^TITLE\s+CARD\b", re.I)
_PROHIBITION = re.compile(r"^(?:do not|don't|never|no)\b", re.I)


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
    listed_key = key.get("filename")
    if key.get("render_status") == "external" and key.get("approved_file"):
        listed_key = key["approved_file"]
    if listed_key:
        rows.append(
            {
                "path": production_dir / str(listed_key),
                "listed": str(listed_key),
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

    def add(
        item_id: str,
        topic: str,
        text: str,
        basis: str,
        source_file: str | None,
        source_field: str | None,
        **extra,
    ) -> None:
        final = item_id
        count = 2
        while final in used:
            final = f"{item_id}-{count}"
            count += 1
        used.add(final)
        row = {
            "item_id": final,
            "topic": topic,
            "text": " ".join(text.split()),
            "basis": basis,
            "source_file": source_file,
            "source_field": source_field,
            "reference": extra.pop("reference", None),
        }
        for key, value in extra.items():
            if value is not None:
                row[key] = value
        items.append(row)

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
    genre_gap = True

    named_year = False
    for field in ("logline", "world_and_period"):
        year = _year_in(str(treatment.get(field) or ""))
        if not year:
            continue
        named_year = True
        add(
            f"period-year-{field.replace('_', '-')}",
            "period",
            f"Year: {year}.",
            "sourced",
            "treatment/treatment.json",
            field,
        )
    font_hit = _font_hit(treatment, brief, look, bible, notes)
    if font_hit:
        add("period-type", "period", f"Typeface: {font_hit[0]}.", "sourced", font_hit[1], font_hit[2])
    elif named_year:
        add(
            "period-type",
            "period",
            "The documents do not name a typeface or a print method.",
            "inferred",
            None,
            None,
        )
    else:
        add(
            "period-type",
            "period",
            "The documents do not name a typeface, a print method, or a year.",
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
            "The documents do not name a graphics-safe inset.",
            "inferred",
            None,
            None,
        )

    packs = _matched_packs(treatment, brief, look)
    term_packs = [pair for pair in packs if not (pair[1].get("match") or {}).get("always")]
    if term_packs:
        genre_gap = False
    if genre_gap:
        add(
            "genre-graphics-unnamed",
            "genre",
            "The documents do not name a title layout, a poster layout, or a credit style for this genre. Do not import one.",
            "inferred",
            None,
            None,
        )
    _add_pack_items(add, packs)
    _add_placement_items(add, brief)
    _add_card_items(add, production_dir, scripts)

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

    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "items": items,
        "fingerprints": {
            "style_bible": _fingerprint(production_dir, bible_path, bible),
            "look": _fingerprint(production_dir, look_path, look),
            "reference_packs": _pack_prints(packs),
        },
        "draft_method": "offline-deterministic",
        "model": model_name("title-graphic-design", "research"),
        "note": (
            "Production documents are sourced or inferred. "
            "A designer proposal cites its reference. Nothing here is approved."
        ),
        "written_at": now(),
    }
    spec = _pack_subtitle_spec(packs)
    if spec is not None:
        document["subtitle_spec"] = spec
    return document


def _guide_document(production_dir: Path, research: dict) -> dict:
    items = list(research["items"])
    by_id = {item["item_id"]: item for item in items}
    fonts = _font_roles(items, by_id["period-type"])
    palette = _palette_from(items)
    title_item = by_id["film-title"]
    title = title_item["text"].split(":", 1)[-1].strip().rstrip(".") if title_item["basis"] == "sourced" else "not named"
    safe_value, layout_rules = _layout_rules(by_id)
    if "look-summary" in by_id:
        look_trace = "look-summary"
    elif "references-unnamed" in by_id:
        look_trace = "references-unnamed"
    else:
        look_trace = next(item["item_id"] for item in items if item["topic"] == "references")
    look_text = by_id[look_trace]["text"] if look_trace in by_id else "No look is named."
    wordmark_rules = [_rule("wordmark-spelling", "Set the title as the research spells it.", title_item)]
    image_rules = [_rule("treatment-look", f"Image treatment follows the research. {look_text}", by_id[look_trace])]
    surface_key = {"title": "title", "poster": "poster", "key-art": "key_art", "credits": "credits"}
    surfaces = {name: [] for name in surface_key.values()}
    notes = []
    for item in items:
        if item["item_id"].startswith("typography-"):
            wordmark_rules.append(_rule(f"wordmark-{item['item_id']}", item["text"], item))
        kind = item.get("claim_kind")
        if kind == "lettering":
            wordmark_rules.append(_rule(f"wordmark-{item['item_id']}", item["text"], item))
        elif kind == "print":
            image_rules.append(_rule(f"treatment-{item['item_id']}", item["text"], item))
        elif kind == "layout" and item.get("surface") in surface_key:
            surfaces[surface_key[item["surface"]]].append(
                _rule(f"surface-{item['item_id']}", item["text"], item)
            )
        elif kind in {"artist", "convention", "credits", "other"}:
            notes.append(_rule(f"note-{item['item_id']}", item["text"], item))
    dos = [
        _rule(
            "do-palette",
            "Use only palette values that trace to research.",
            next(item for item in items if item["item_id"] == palette[0]["trace"]),
        )
    ]
    donts = [
        _rule(
            "dont-invent",
            "Do not treat a designer proposal as a fact the production documents stated. "
            "Do not add a typeface, a color, or a layout the research does not contain.",
            by_id["period-type"],
        )
    ]
    for item in items:
        if not item["item_id"].startswith("placement-"):
            continue
        if _PROHIBITION.match(item["text"]):
            donts.append(_rule(f"dont-{item['item_id']}", item["text"], item))
        else:
            dos.append(_rule(f"do-{item['item_id']}", item["text"], item))
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "status": "draft",
        "research": "graphics/research.json",
        "fonts": fonts,
        "palette": palette,
        "wordmark": {"title": title, "rules": wordmark_rules},
        "layout": {"safe_area": safe_value, "rules": layout_rules},
        "image_treatment": {"rules": image_rules},
        "dos": dos,
        "donts": donts,
        "fingerprints": research["fingerprints"],
        "change_log": [{"version": "1.0.0", "at": now(), "change": "Created from research."}],
        "draft_method": "offline-deterministic",
        "model": model_name("title-graphic-design", "guide"),
        "note": "Built only from graphics/research.json. Designer proposals are suggestions. Not approved yet.",
        "written_at": now(),
    }
    kept = {key: value for key, value in surfaces.items() if value}
    if kept:
        document["surfaces"] = kept
    if notes:
        document["notes"] = notes
    if isinstance(research.get("subtitle_spec"), dict):
        document["subtitle_spec"] = json.loads(json.dumps(research["subtitle_spec"]))
    lettering = next((item for item in items if item.get("lettering_name")), None)
    if lettering is not None:
        document["custom_title"] = {
            "name": lettering["lettering_name"],
            "style": lettering.get("lettering_style") or lettering["text"],
            "construction": lettering.get("lettering_construction") or "Description only. No font file is built.",
            "built": False,
            "provenance": _PROPOSAL,
            "reference": str(lettering.get("reference") or ""),
            "trace": lettering["item_id"],
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
        old_core = {key: value for key, value in (old.get("fingerprints") or {}).items() if key != "reference_packs"}
        new_core = {key: value for key, value in (fresh.get("fingerprints") or {}).items() if key != "reference_packs"}
        if old_core != new_core:
            change = "The style bible or the look changed. The guide was rebuilt from new research."
        else:
            change = "A design reference pack changed. The guide was rebuilt from new research."
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
    end_credits = _end_credits(production_dir)
    tagline = None
    if by_id.get("logline", {}).get("basis") == "sourced":
        tagline = by_id["logline"]["text"].split(":", 1)[-1].strip().rstrip(".")
    sizes = _sizes(production_dir)
    key_width, key_height, key_source = sizes["key"]
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "guide": "graphics/brand-guide.json",
        "guide_version": str(guide.get("version") or "1.0.0"),
        "main_title": _main_title(guide, title, safe),
        "title_cards": cards,
        "end_credits": end_credits,
        "subtitles": _subtitle_block(guide, safe),
        "key_art": _apply_approved_key_art(
            production_dir,
            {
                "filename": "graphics/key-art-poster.png",
                "kind": "designed",
                "distinct_from": "poster.png",
                "title": title,
                "tagline": tagline,
                "billing_block": [_credit_text(line) for line in end_credits.get("lines") or []],
                "width": key_width,
                "height": key_height,
                "size_source": key_source,
                "safe_area": safe,
                "render_status": "not-rendered",
            },
        ),
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
    placement = _placement_lines(research)
    if placement:
        document["key_art"]["placement_rules"] = placement
        for item in document["collateral"]:
            item["placement_rules"] = placement
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
        for card in _parse_title_cards(text):
            if not card["text"]:
                continue
            cards.append(
                {
                    "card_id": f"card-{len(cards) + 1}",
                    "text": card["text"],
                    "source_file": relative,
                    "source_line": card["line"],
                    "safe_area": safe,
                    "design_direction": card["direction"],
                }
            )
    return cards


def _parse_title_cards(text: str) -> list[dict]:
    """Split a TITLE CARD into the words on screen and the design direction.

    Direction is background, placement, or a typography note on the cue line.
    The displayed text is a quoted title, a following title line, or the cue
    line itself when that line is the card copy. Direction is never used as
    the words on screen.
    """
    found = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip().strip("*").strip()
        if not _CARD_LABEL.match(stripped):
            index += 1
            continue
        rest = _CARD_LABEL.sub("", stripped, count=1).strip(" .:-")
        quoted = [item.strip() for item in _QUOTED.findall(rest) if item.strip()]
        if quoted:
            display = _unwrap_copy(quoted[-1])
            direction = _QUOTED.sub(" ", rest)
            direction = " ".join(direction.split()).strip(" .:-")
            found.append(_card_record(index + 1, display, direction))
            index += 1
            continue
        if rest and not _looks_like_direction(rest):
            found.append(_card_record(index + 1, _unwrap_copy(rest), ""))
            index += 1
            continue
        follower = _following_copy(lines, index)
        if follower:
            line_number, display = follower
            found.append(_card_record(line_number, display, rest, cue_line=index + 1))
            index = line_number
            continue
        found.append(_card_record(index + 1, "", rest))
        index += 1
    return found


def _card_record(line: int, display: str, direction: str, cue_line: int | None = None) -> dict:
    direction = " ".join(direction.split()).strip()
    return {
        "line": line,
        "cue_line": cue_line or line,
        "text": " ".join(display.split()).strip(),
        "direction": direction,
        "cues": _style_cues(direction),
    }


def _following_copy(lines: list[str], index: int) -> tuple[int, str] | None:
    next_index = index + 1
    while next_index < len(lines) and not lines[next_index].strip():
        next_index += 1
    if next_index >= len(lines):
        return None
    raw = lines[next_index].strip()
    if _is_structural(raw):
        return None
    display = _unwrap_copy(raw)
    if not display or _looks_like_direction(display):
        return None
    marked = raw.lstrip().startswith("#") or "**" in raw or bool(_QUOTED.search(raw))
    if marked or _is_caps_title(display):
        return next_index + 1, display
    return None


def _is_structural(raw: str) -> bool:
    cleaned = _unwrap_copy(raw)
    if not cleaned:
        return True
    if _SLUGLINE.match(cleaned) or _CARD_LABEL.match(cleaned) or _TRANSITION.match(cleaned):
        return True
    return False


def _looks_like_direction(text: str) -> bool:
    body = text.strip()
    if not body:
        return False
    if _DIRECTION_OPEN.match(body) or _STYLE_WORD.search(body):
        return True
    return False


def _is_caps_title(text: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", text)
    if not letters or text != text.upper() or len(text.split()) > 12:
        return False
    return not _looks_like_direction(text)


def _unwrap_copy(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    changed = True
    while changed and text:
        changed = False
        for mark in ("**", "__"):
            if text.startswith(mark) and text.endswith(mark) and len(text) > len(mark) * 2:
                text = text[len(mark) : -len(mark)].strip()
                changed = True
    if len(text) >= 2 and text[0] in "\"'“" and text[-1] in "\"'”":
        text = text[1:-1].strip()
    return " ".join(text.split())


def _style_cues(direction: str) -> list[str]:
    found = []
    for match in _STYLE_CUE.finditer(direction):
        cue = re.sub(r"^(?:same|the|a|an)\s+", "", match.group(1).strip(), flags=re.I).strip()
        if cue and cue.casefold() not in {item.casefold() for item in found}:
            found.append(cue)
    return found


_FILM_CREDITS = "credits/film-credits.json"
_PLACEHOLDER_MARK = "FICTIONAL PLACEHOLDER"
_CREW_HEADING = "Made with Movie-swarm crew"
_APPROVED_KEY_ART = "graphics/brand/key-art-poster.png"
_GUIDE_FONT_KEYS = {
    "title": "title",
    "credits": "credits",
    "subtitles": "subtitles",
    "marketing": "marketing",
    "subheads": "subheads",
    "body": "body",
    "billing": "billing",
    "player-subtitles": "player_subtitles",
}
_REQUIRED_FONT_ROLES = ("title", "credits", "subtitles", "marketing")


def _main_title(guide: dict, title: str, safe: str) -> dict:
    font = guide["fonts"]["title"]
    record = {
        "text": title,
        "font": str(font.get("family") or "not named"),
        "safe_area": safe,
        "trace": "film-title",
    }
    stand_ins = [str(item.get("family")) for item in font.get("stand_ins") or [] if item.get("family")]
    if stand_ins:
        record["stand_ins"] = stand_ins
    custom = guide.get("custom_title") if isinstance(guide.get("custom_title"), dict) else {}
    if custom.get("name") and custom.get("name") == font.get("family") and custom.get("construction"):
        record["treatment"] = str(custom["construction"])
    return record


def _subtitle_block(guide: dict, safe: str) -> dict:
    spec = guide.get("subtitle_spec") if isinstance(guide.get("subtitle_spec"), dict) else None
    burned = spec.get("burned_in") if isinstance(spec, dict) and isinstance(spec.get("burned_in"), dict) else None
    player = spec.get("player") if isinstance(spec, dict) and isinstance(spec.get("player"), dict) else None
    if burned and burned.get("family"):
        family = str(burned["family"])
        color = str(burned.get("color") or "not named")
    else:
        family = str((guide.get("fonts") or {}).get("subtitles", {}).get("family") or "not named")
        palette = guide.get("palette") or []
        color = str(palette[0].get("value")) if palette and isinstance(palette[0], dict) else "not named"
    block = {
        "timing_owner": "post-supervisor",
        "note": "Timing stays with the Post Supervisor. This spec does not set cue times.",
        "family": family,
        "color": color,
        "safe_area": safe,
    }
    if burned:
        block["burned_in"] = burned
    if player:
        block["player"] = player
    return block


def _apply_approved_key_art(production_dir: Path, key_art: dict) -> dict:
    key_art["expected_approved_file"] = _APPROVED_KEY_ART
    path = production_dir / _APPROVED_KEY_ART
    if path.is_file() and path.stat().st_size > 0:
        key_art["approved_file"] = _APPROVED_KEY_ART
        key_art["render_status"] = "external"
        key_art["note"] = "The approved key art is the file in the film folder. This build does not draw a stand-in."
    else:
        key_art["render_status"] = "not-rendered"
        key_art["note"] = (
            "The approved key art belongs at graphics/brand/key-art-poster.png in the film folder. "
            "This build does not draw a stand-in."
        )
    return key_art


def _end_credits(production_dir: Path) -> dict:
    studio_lines, studio_source = _studio_credit_lines(production_dir)
    film_path = production_dir / _FILM_CREDITS
    if film_path.is_file():
        try:
            record = read_handoff(film_path, schema="film-credits")
        except HandoffError as exc:
            raise GraphicsError(str(exc)) from exc
        block = {"source": _FILM_CREDITS, "lines": _film_credit_lines(record)}
        if studio_lines and studio_source:
            block["studio_crew"] = {
                "heading": _CREW_HEADING,
                "source": studio_source,
                "lines": studio_lines,
            }
        return block
    return {"source": studio_source, "lines": studio_lines}


def _studio_credit_lines(production_dir: Path) -> tuple[list[dict], str | None]:
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


def _film_credit_lines(record: dict) -> list[dict]:
    lines = []
    company = record.get("production_company")
    if isinstance(company, dict) and str(company.get("name") or "").strip():
        row = {"role": "Production company", "name": str(company["name"]).strip()}
        site = str(company.get("site") or "").strip()
        if site:
            row["detail"] = site
        lines.append(row)
    for item in record.get("billing") or []:
        row = _person_line(item, cast=False)
        if row:
            lines.append(row)
    for item in record.get("cast") or []:
        row = _person_line(item, cast=True)
        if row:
            lines.append(row)
    for item in record.get("crew") or []:
        row = _person_line(item, cast=False)
        if row:
            lines.append(row)
    return lines


def _person_line(item: object, *, cast: bool) -> dict | None:
    if not isinstance(item, dict):
        return None
    role = str(item.get("role") or "").strip()
    name = str(item.get("name") or "").strip()
    if not role or not name:
        return None
    row = {"role": role, "name": name}
    if cast:
        row["billing"] = "as"
    if item.get("fictional_placeholder") is True:
        row["fictional_placeholder"] = True
        row["mark"] = _PLACEHOLDER_MARK
    return row


def _credit_text(line: dict) -> str:
    if line.get("billing") == "as":
        text = f"{line.get('name')} as {line.get('role')}"
    else:
        text = f"{line.get('role')}: {line.get('name')}"
        if line.get("detail"):
            text = f"{text} ({line['detail']})"
    if line.get("mark"):
        text = f"{text} — {line['mark']}"
    return text


def _credit_identity(item: dict) -> tuple[str, str, bool]:
    return (str(item.get("role")), str(item.get("name")), bool(item.get("fictional_placeholder")))


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
        if item.get("kind") == "designed":
            continue
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
    try:
        treatment = approved_treatment(production_dir)
    except PrevisError as exc:
        raise GraphicsError(str(exc)) from exc
    live_packs = _pack_prints(_matched_packs(treatment, read_brief(production_dir), _look_data(production_dir)))
    if list(stored.get("reference_packs") or []) != live_packs:
        if for_guide:
            raise GraphicsError(
                "A design reference pack changed after the research was written. "
                "Write the research again before the brand guide."
            )
        raise GraphicsError(
            "A design reference pack changed after the brand guide was approved. "
            "Update the research and the brand guide before building graphics."
        )
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
    got = [
        _credit_identity(item)
        for item in block.get("lines") or []
        if isinstance(item, dict) and item.get("role") and item.get("name")
    ]
    film = Path(str(source or "")).name == "film-credits.json"
    if not source:
        expect = []
    else:
        path = production_dir / str(source)
        schema = "film-credits" if film else "line-producer-record"
        try:
            record = read_handoff(path, schema=schema)
        except HandoffError as exc:
            return _check("graphics-credits", str(source), "fail", str(exc))
        if film:
            expect = [_credit_identity(item) for item in _film_credit_lines(record)]
        else:
            expect = [
                (str(item.get("role")), str(item.get("name")), False)
                for item in record.get("credits") or []
                if isinstance(item, dict) and item.get("role") and item.get("name")
            ]
    if got != expect:
        detail = (
            "The end credits do not match the film credits file."
            if film
            else "The end credits do not match the Line Producer credit record."
        )
        return _check("graphics-credits", str(source or "graphics/graphics.json"), "fail", detail)
    crew = block.get("studio_crew")
    if isinstance(crew, dict):
        crew_source = str(crew.get("source") or "")
        try:
            record = read_handoff(production_dir / crew_source, schema="line-producer-record")
        except HandoffError as exc:
            return _check("graphics-credits", crew_source or "graphics/graphics.json", "fail", str(exc))
        got_crew = [
            (str(item.get("role")), str(item.get("name")))
            for item in crew.get("lines") or []
            if isinstance(item, dict) and item.get("role") and item.get("name")
        ]
        expect_crew = [
            (str(item.get("role")), str(item.get("name")))
            for item in record.get("credits") or []
            if isinstance(item, dict) and item.get("role") and item.get("name")
        ]
        if got_crew != expect_crew:
            return _check(
                "graphics-credits",
                crew_source or "graphics/graphics.json",
                "fail",
                "The studio crew credits do not match the Line Producer credit record.",
            )
    where = "film credits" if film else "Line Producer record"
    return _check(
        "graphics-credits",
        str(source or "graphics/graphics.json"),
        "pass",
        f"{len(got)} credit(s) match the {where}. No name was added.",
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
    present = [
        item
        for item in targets
        if isinstance(item, dict) and item.get("render_status") in {"present", "external"}
    ]
    if not present:
        return _check(
            "graphics-resolution",
            "graphics/graphics.json",
            "skipped",
            "No graphic file was rendered, so resolution was not measured.",
        )
    problems = []
    measured = 0
    for item in present:
        named = item.get("approved_file") if item.get("render_status") == "external" else item.get("filename")
        path = production_dir / str(named or "")
        width, height = _probe_size(path)
        if width is None or height is None:
            if item.get("render_status") == "external":
                continue
            return _check(
                "graphics-resolution",
                str(item.get("filename") or path.name),
                "skipped",
                "Resolution was not read.",
            )
        measured += 1
        label = str(named or item.get("filename") or path.name)
        if int(width) != int(item.get("width") or -1) or int(height) != int(item.get("height") or -1):
            problems.append(
                f"{label} is {width}x{height}. The spec asks for {item.get('width')}x{item.get('height')}."
            )
    if problems:
        return _check("graphics-resolution", "graphics/graphics.json", "fail", " ".join(problems))
    if measured == 0:
        return _check(
            "graphics-resolution",
            "graphics/graphics.json",
            "skipped",
            "No graphic file was measured, so resolution was not checked.",
        )
    return _check(
        "graphics-resolution",
        "graphics/graphics.json",
        "pass",
        f"{measured} graphic file(s) match the spec size.",
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


def _year_in(text: str) -> str:
    """A four-digit year the text already states. Empty when it names none."""
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", text)
    if not match:
        return ""
    return match.group(1)


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
        "surfaces": document.get("surfaces"),
        "notes": document.get("notes"),
        "custom_title": document.get("custom_title"),
        "subtitle_spec": document.get("subtitle_spec"),
        "fingerprints": document.get("fingerprints"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _package_fingerprint(document: dict) -> str:
    payload = {
        "main_title": document.get("main_title"),
        "title_cards": document.get("title_cards"),
        "end_credits": document.get("end_credits"),
        "subtitles": document.get("subtitles"),
        "key_art": {
            key: value
            for key, value in (document.get("key_art") or {}).items()
            if key not in {"render_status"}
        },
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
        if item.get("basis") == "designer-proposal":
            where = f"DESIGNER PROPOSAL ({item.get('reference')})"
        elif item.get("basis") == "sourced":
            where = f"SOURCED FROM PRODUCTION DOCS ({item.get('source_file')} {item.get('source_field')})"
        else:
            where = "SOURCED FROM PRODUCTION DOCS (the documents do not state this)"
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
        lines.append(
            f"- {name}: {font.get('family')}. {font.get('licensing')} {_mark(font)}"
        )
        for alternate in font.get("alternates") or []:
            lines.append(f"  - alternate: {alternate.get('family')}. {alternate.get('licensing')} {_mark(alternate)}")
        for stand_in in font.get("stand_ins") or []:
            lines.append(
                f"  - mockup stand-in: {stand_in.get('family')}. {stand_in.get('licensing')} {_mark(stand_in)}"
            )
        fallback = font.get("glyph_fallback") or {}
        if fallback:
            glyphs = " ".join(str(glyph) for glyph in fallback.get("glyphs") or [])
            lines.append(
                f"  - glyph fallback: {fallback.get('family')} for {glyphs}. "
                f"{fallback.get('licensing')} {_mark(fallback)}"
            )
    if document.get("subtitle_spec"):
        burned = document["subtitle_spec"].get("burned_in") or {}
        player = document["subtitle_spec"].get("player") or {}
        lines.extend(
            [
                "",
                "## Subtitles",
                "",
                (
                    f"Burned in: {burned.get('family')} {burned.get('weight')}, {burned.get('case')} case, "
                    f"{burned.get('color_name')} {burned.get('color')}, {burned.get('edge')}, "
                    f"{burned.get('position')} {burned.get('picture')}. "
                    f"At most {burned.get('max_lines')} lines, about {burned.get('max_characters_per_line')} characters per line."
                ),
                f"Player files: {player.get('family')}. {player.get('note')}",
            ]
        )
    lines.extend(["", "## Palette", ""])
    for color in document.get("palette") or []:
        scope = " Print only." if color.get("scope") == "print" else ""
        lines.append(f"- {color.get('name')}: {color.get('value')}.{scope} {_mark(color)}")
    wordmark = document.get("wordmark") or {}
    lines.extend(["", "## Wordmark", "", str(wordmark.get("title") or ""), ""])
    for rule in wordmark.get("rules") or []:
        lines.append(f"- {rule.get('text')} {_mark(rule)}")
    layout = document.get("layout") or {}
    lines.extend(["", "## Layout", "", f"Safe area: {layout.get('safe_area')}.", ""])
    for rule in layout.get("rules") or []:
        lines.append(f"- {rule.get('text')} {_mark(rule)}")
    surfaces = document.get("surfaces") or {}
    for surface, rules in surfaces.items():
        lines.extend(["", f"## {surface}", ""])
        for rule in rules:
            lines.append(f"- {rule.get('text')} {_mark(rule)}")
    if document.get("custom_title"):
        custom = document["custom_title"]
        lines.extend(
            [
                "",
                "## Custom title lettering",
                "",
                f"{custom.get('name')}. {custom.get('style')} {custom.get('construction')} {_mark(custom)}",
                "No font file is built.",
            ]
        )
    lines.extend(["", "## Do", ""])
    for rule in document.get("dos") or []:
        lines.append(f"- {rule.get('text')} {_mark(rule)}")
    lines.extend(["", "## Don't", ""])
    for rule in document.get("donts") or []:
        lines.append(f"- {rule.get('text')} {_mark(rule)}")
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
            direction = card.get("design_direction") or ""
            extra = f" Direction: {direction}." if direction else ""
            lines.append(f"- {card.get('text')} ({card.get('source_file')}).{extra}")
        lines.append("")
    else:
        lines.append("No TITLE CARD lines were in the screenplay.")
        lines.append("")
    key = document.get("key_art") or {}
    if key.get("placement_rules"):
        lines.extend(["Placement:", ""])
        for rule in key["placement_rules"]:
            lines.append(f"- {rule}")
        lines.append("")
    end = document.get("end_credits") or {}
    credits = end.get("lines") or []
    lines.append("End credits:")
    lines.append("")
    if not credits:
        lines.append("No credit record. No name was added.")
    for line in credits:
        lines.append(f"- {_credit_text(line)}")
    crew = end.get("studio_crew") or {}
    if crew.get("lines"):
        lines.extend(["", f"{crew.get('heading')}:", ""])
        for line in crew["lines"]:
            lines.append(f"- {line.get('role')}: {line.get('name')}")
    lines.append("")
    subtitles = document.get("subtitles") or {}
    lines.append(subtitles.get("note") or "")
    burned = subtitles.get("burned_in") or {}
    if burned:
        lines.append(
            f"Burned in: {burned.get('family')} {burned.get('weight')}, {burned.get('case')} case, "
            f"{burned.get('color_name')} {burned.get('color')}, {burned.get('edge')}, "
            f"{burned.get('position')} {burned.get('picture')}."
        )
    player = subtitles.get("player") or {}
    if player:
        files = ", ".join(str(item) for item in player.get("files") or [])
        lines.append(f"Player files ({files}): {player.get('family')}. {player.get('note')}")
    key = document.get("key_art") or {}
    lines.extend(
        [
            "",
            f"Key art: {key.get('filename')} ({key.get('render_status')}). Distinct from {key.get('distinct_from')}.",
            str(key.get("note") or ""),
            "",
        ]
    )
    for item in document.get("collateral") or []:
        lines.append(f"- {item.get('id')}: {item.get('filename')} ({item.get('render_status')}).")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _mark(node: dict) -> str:
    label = node.get("provenance") or ""
    reference = node.get("reference")
    if label == _PROPOSAL and reference:
        return f"({label}: {reference})"
    if label:
        return f"({label})"
    return ""


def _label(item: dict) -> tuple[str, str | None]:
    if item.get("basis") == "designer-proposal":
        return _PROPOSAL, item.get("reference")
    return _FROM_DOCS, item.get("source_file")


def _rule(rule_id: str, text: str, item: dict) -> dict:
    label, reference = _label(item)
    return {
        "rule_id": rule_id,
        "text": " ".join(str(text).split()),
        "trace": item["item_id"],
        "provenance": label,
        "reference": reference,
    }


def _font_roles(items: list[dict], period_item: dict) -> dict:
    grouped = {role: [] for role in _GUIDE_FONT_KEYS}
    for item in items:
        if not item.get("family") or not str(item.get("item_id") or "").startswith("font-"):
            continue
        role = str(item.get("font_role") or "")
        if role not in grouped:
            role = str(item["item_id"]).split("-")[1]
        if role in grouped:
            grouped[role].append(item)
    lettering = next((item for item in items if item.get("lettering_name")), None)
    fonts = {}
    for role, proposals in grouped.items():
        built = _one_font(role, proposals, period_item, lettering)
        key = _GUIDE_FONT_KEYS[role]
        if built is None:
            if role in _REQUIRED_FONT_ROLES:
                fonts[key] = _unnamed_font(period_item)
            continue
        fonts[key] = built
    return fonts


def _one_font(role: str, proposals: list[dict], period_item: dict, lettering: dict | None) -> dict | None:
    stand_ins = [item for item in proposals if item.get("duty") == "mockup-stand-in"]
    fallbacks = [item for item in proposals if item.get("duty") == "glyph-fallback"]
    primaries = [item for item in proposals if item.get("duty") not in {"mockup-stand-in", "glyph-fallback"}]
    if role == "title" and period_item.get("basis") == "sourced":
        family = period_item["text"].split(":", 1)[-1].strip().rstrip(".")
        label, reference = _label(period_item)
        font = {
            "family": family,
            "licensing": "Use only the face the research names. Confirm the license before delivery.",
            "trace": "period-type",
            "provenance": label,
            "reference": reference,
        }
        _attach_font_extras(font, stand_ins, fallbacks, alternates_from=primaries)
        return font
    if role == "title" and lettering is not None and stand_ins and not primaries:
        label, reference = _label(lettering)
        font = {
            "family": str(lettering["lettering_name"]),
            "licensing": (
                "No font file is built. The final capitals are hand-drawn later. "
                "Do not trace the mockup stand-ins."
            ),
            "trace": lettering["item_id"],
            "provenance": label,
            "reference": reference,
            "stand_ins": [_alternate(item) for item in stand_ins],
        }
        return font
    if not primaries:
        return None
    primary = primaries[0]
    label, reference = _label(primary)
    font = {
        "family": primary["family"],
        "licensing": primary.get("license_name") or "The proposal names the license.",
        "trace": primary["item_id"],
        "provenance": label,
        "reference": reference,
    }
    if primary.get("category"):
        font["category"] = primary["category"]
    _attach_font_extras(font, stand_ins, fallbacks, alternates_from=primaries[1:])
    return font


def _attach_font_extras(font, stand_ins, fallbacks, *, alternates_from) -> None:
    extra = [_alternate(item) for item in alternates_from]
    if extra:
        font["alternates"] = extra
    if stand_ins:
        font["stand_ins"] = [_alternate(item) for item in stand_ins]
    fallback = next((item for item in fallbacks if item.get("fallback_glyphs")), None)
    if fallback is not None:
        font["glyph_fallback"] = _glyph_fallback(fallback)


def _unnamed_font(period_item: dict) -> dict:
    label, reference = _label(period_item)
    return {
        "family": "not named",
        "licensing": "No license is named in the documents. Do not assume a face is free to use.",
        "trace": "period-type",
        "provenance": label,
        "reference": reference,
    }


def _glyph_fallback(item: dict) -> dict:
    label, reference = _label(item)
    fallback = {
        "family": item["family"],
        "licensing": item.get("license_name") or "The proposal names the license.",
        "provenance": label,
        "reference": reference,
        "trace": item["item_id"],
        "glyphs": [str(glyph) for glyph in item.get("fallback_glyphs") or [] if str(glyph).strip()],
    }
    if item.get("category"):
        fallback["category"] = item["category"]
    return fallback


def _alternate(item: dict) -> dict:
    label, reference = _label(item)
    alternate = {
        "family": item["family"],
        "licensing": item.get("license_name") or "The proposal names the license.",
        "provenance": label,
        "reference": reference,
        "trace": item["item_id"],
    }
    if item.get("category"):
        alternate["category"] = item["category"]
    return alternate


def _palette_from(items: list[dict]) -> list[dict]:
    palette = []
    seen = set()
    for item in items:
        if not item["item_id"].startswith("palette-bible-"):
            continue
        name, hex_value = _split_palette(item["text"])
        palette.append(_swatch(name, hex_value, item))
        seen.add(name.casefold())
    for item in items:
        if not item["item_id"].startswith("palette-look-"):
            continue
        name = item["text"].split(":", 1)[-1].strip().rstrip(".")
        if name.casefold() in seen:
            continue
        palette.append(_swatch(name, name, item))
        seen.add(name.casefold())
    if not palette:
        unnamed = next(item for item in items if item["item_id"] == "palette-unnamed")
        palette.append(_swatch("not named", "not named", unnamed))
        seen.add("not named")
    fills = [item for item in items if item.get("hex") and item.get("swatch_name")]
    for color in palette:
        if _HEX.match(str(color["value"])):
            continue
        match = next((item for item in fills if item["swatch_name"].casefold() == color["name"].casefold()), None)
        if match is None:
            continue
        color["value"] = match["hex"]
        color["trace"] = match["item_id"]
        color["provenance"] = _PROPOSAL
        color["reference"] = match.get("reference")
    for item in fills:
        if item.get("swatch_use") != "propose":
            continue
        if item["swatch_name"].casefold() in seen:
            continue
        palette.append(_swatch(item["swatch_name"], item["hex"], item))
        seen.add(item["swatch_name"].casefold())
    for item in fills:
        scope = item.get("swatch_scope")
        if not scope:
            continue
        for color in palette:
            if color["name"].casefold() == item["swatch_name"].casefold() and "scope" not in color:
                color["scope"] = scope
    return palette


def _swatch(name: str, value: str, item: dict) -> dict:
    label, reference = _label(item)
    swatch = {
        "name": name,
        "value": value,
        "trace": item["item_id"],
        "provenance": label,
        "reference": reference,
    }
    if item.get("swatch_scope"):
        swatch["scope"] = item["swatch_scope"]
    return swatch


def _layout_rules(by_id: dict) -> tuple[str, list[dict]]:
    safe_item = by_id["safe-area"]
    proposal = by_id.get("safe-area-proposal")
    rules = [_rule("layout-safe", safe_item["text"], safe_item)]
    if safe_item.get("basis") == "sourced":
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", safe_item["text"])
        safe_value = match.group(1) if match else safe_item["text"]
    elif proposal:
        safe_value = _safe_summary(proposal["text"])
    else:
        safe_value = "not named"
    if proposal:
        rules.append(_rule("layout-safe-proposal", proposal["text"], proposal))
    return safe_value, rules


def _safe_summary(text: str) -> str:
    action = re.search(r"action inset ([0-9]+(?:\.[0-9]+)?)", text)
    graphics = re.search(r"graphics inset ([0-9]+(?:\.[0-9]+)?)", text)
    if action and graphics:
        return f"graphics {graphics.group(1)}% each edge; action {action.group(1)}% each edge"
    return text


def _placement_lines(research: dict) -> list[str]:
    return [
        str(item.get("text") or "")
        for item in research.get("items") or []
        if str(item.get("item_id") or "").startswith("placement-") and item.get("text")
    ]


def _look_data(production_dir: Path) -> dict | None:
    path = _first_file(production_dir, ("look/look.json",))
    if path is None:
        return None
    data = load_optional(path, "look")
    return data if isinstance(data, dict) else None


def _pack_directory() -> Path:
    return config_dir() / "design-references"


def _matched_packs(treatment: dict, brief: dict, look: dict | None, directory: Path | None = None) -> list[tuple[Path, dict]]:
    folder = directory or _pack_directory()
    if not folder.is_dir():
        return []
    schema = load_schema("design-reference")
    text = _match_text(treatment, brief, look)
    years = _story_years(treatment)
    matched = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise GraphicsError(f"{path.name} is not valid JSON. {exc}") from exc
        if not isinstance(data, dict):
            raise GraphicsError(f"{path.name} must be a JSON object.")
        errors = validate_data(data, schema)
        if errors:
            raise GraphicsError(path.name + " does not match the design reference schema. " + " ".join(errors))
        if _pack_matches(data, text, years):
            matched.append((path, data))
    return matched


def _pack_matches(pack: dict, text: str, years: list[int]) -> bool:
    match = pack.get("match") or {}
    if match.get("always"):
        return True
    terms = [str(term).strip() for term in match.get("terms") or [] if str(term).strip()]
    if not terms or not any(term.casefold() in text.casefold() for term in terms):
        return False
    if match.get("year_min") is None and match.get("year_max") is None:
        return True
    if not years:
        return not bool(match.get("require_year"))
    low = int(match.get("year_min") or 0)
    high = int(match.get("year_max") or 9999)
    return any(low <= year <= high for year in years)


def _match_text(treatment: dict, brief: dict, look: dict | None) -> str:
    parts = []
    tone = treatment.get("tone_and_genre") if isinstance(treatment.get("tone_and_genre"), dict) else {}
    parts.append(str((tone or {}).get("genre") or ""))
    parts.append(str((tone or {}).get("tone") or ""))
    parts.append(str(treatment.get("world_and_period") or ""))
    if isinstance(brief, dict):
        parts.append(str(brief.get("genre") or ""))
        parts.append(str(brief.get("tone") or ""))
        decisions = brief.get("decisions") or []
        if isinstance(decisions, list):
            parts.extend(str(item) for item in decisions)
    if isinstance(look, dict):
        parts.append(str(look.get("look_name") or ""))
        parts.append(str(look.get("summary") or ""))
    return "\n".join(parts)


def _story_years(treatment: dict) -> list[int]:
    found = []
    for field in ("logline", "world_and_period"):
        year = _year_in(str(treatment.get(field) or ""))
        if year:
            found.append(int(year))
    return found


def _pack_prints(packs: list[tuple[Path, dict]]) -> list[dict]:
    root = repo_root().resolve()
    rows = []
    for path, pack in packs:
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            relative = path.name
        rows.append(
            {
                "path": relative,
                "version": str(pack["version"]) if pack.get("version") else None,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return rows


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root().resolve()).as_posix()
    except ValueError:
        return path.name


def _pack_subtitle_spec(packs: list[tuple[Path, dict]]) -> dict | None:
    for _path, pack in packs:
        spec = pack.get("subtitle_spec")
        if isinstance(spec, dict):
            return json.loads(json.dumps(spec))
    return None


def _add_pack_items(add, packs: list[tuple[Path, dict]]) -> None:
    for path, pack in packs:
        relative = _repo_relative(path)
        pack_id = str(pack.get("id") or slug(path.stem, "pack"))
        for claim in pack.get("claims") or []:
            add(
                f"claim-{pack_id}-{claim['claim_id']}",
                claim["topic"],
                claim["text"],
                "designer-proposal",
                relative,
                f"claims.{claim['claim_id']}",
                reference=claim["url"],
                claim_kind=claim["kind"],
                surface=claim.get("surface"),
            )
        for font in pack.get("fonts") or []:
            family = str(font["family"])
            add(
                f"font-{font['role']}-{slug(family, 'face')}",
                "period",
                f"{font['role']} face proposal: {family}. {font['note']}",
                "designer-proposal",
                relative,
                f"fonts.{font['role']}.{slug(family, 'face')}",
                reference=font["license_url"],
                family=family,
                license_name=font["license_name"],
                category=font["category"],
                font_role=font["role"],
                duty=font.get("duty"),
                fallback_glyphs=list(font["fallback_glyphs"]) if font.get("fallback_glyphs") else None,
            )
        for color in pack.get("colors") or []:
            add(
                f"palette-proposal-{pack_id}-{slug(color['name'], 'color')}",
                "references",
                f"Palette proposal: {color['name']} {color['hex']}. {color['note']}",
                "designer-proposal",
                relative,
                f"colors.{slug(color['name'], 'color')}",
                reference=color["url"],
                hex=color["hex"],
                swatch_name=color["name"],
                swatch_use=color["use"],
                swatch_scope=color.get("scope"),
            )
        for layout in pack.get("layouts") or []:
            add(
                f"layout-{pack_id}-{layout['layout_id']}",
                "genre",
                layout["text"],
                "designer-proposal",
                relative,
                f"layouts.{layout['layout_id']}",
                reference=layout["url"],
                claim_kind="layout",
                surface=layout["surface"],
            )
        safe = pack.get("safe_area")
        if isinstance(safe, dict):
            add(
                "safe-area-proposal",
                "genre",
                (
                    f"Proposed safe area: action inset {safe['action_inset_percent']}% each edge, "
                    f"graphics inset {safe['graphics_inset_percent']}% each edge. {safe['note']}"
                ),
                "designer-proposal",
                relative,
                "safe_area",
                reference=safe["url"],
            )
        lettering = pack.get("custom_lettering")
        if isinstance(lettering, dict):
            add(
                f"custom-title-{pack_id}",
                "period",
                (
                    f"Custom title lettering proposal: {lettering['name']}. "
                    f"{lettering['style']} {lettering['construction']}"
                ),
                "designer-proposal",
                relative,
                "custom_lettering",
                reference=" ".join(lettering.get("urls") or []),
                lettering_name=lettering["name"],
                lettering_style=lettering["style"],
                lettering_construction=lettering["construction"],
            )


def _add_placement_items(add, brief: dict) -> None:
    featured = brief.get("featured_product") if isinstance(brief, dict) else None
    if not isinstance(featured, dict):
        return
    product = " ".join(str(featured.get("product") or "").split()).strip()
    if advertising_phrases(product):
        product = ""
    label = product or "This object"
    intent = " ".join(str(featured.get("placement_intent") or "").split()).strip()
    if intent:
        banned = bool(advertising_phrases(intent))
        add(
            "placement-intent",
            "references",
            _clean_placement(intent, label),
            "designer-proposal" if banned else "sourced",
            "production-brief.json",
            "featured_product.placement_intent",
            reference="Ron, 2026-11-13" if banned else None,
        )
    for index, rule in enumerate(featured.get("rules") or []):
        if not isinstance(rule, str) or not rule.strip():
            continue
        raw = " ".join(rule.split())
        banned = bool(advertising_phrases(raw))
        add(
            f"placement-rule-{index + 1}",
            "references",
            _clean_placement(raw, label),
            "designer-proposal" if banned else "sourced",
            "production-brief.json",
            f"featured_product.rules[{index}]",
            reference="Ron, 2026-11-13" if banned else None,
        )
    add(
        "placement-not-for-sale",
        "references",
        f"Do not present {label} as something for sale. Key art and collateral keep it inside the story.",
        "designer-proposal",
        "production-brief.json",
        "featured_product",
        reference="Ron, 2026-11-13",
    )


def _clean_placement(text: str, label: str) -> str:
    if advertising_phrases(text):
        return story_purpose_line(label)
    if text.endswith((".", "!", "?")):
        return text
    return text + "."


def _add_card_items(add, production_dir: Path, scripts: list[Path]) -> None:
    for path in scripts:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GraphicsError(f"Could not read the screenplay {path.name}. {exc}") from exc
        relative = _rel(production_dir, path)
        for card in _parse_title_cards(text):
            cue_line = card["cue_line"]
            if card["direction"]:
                add(
                    f"title-direction-{slug(path.stem, 'script')}-{cue_line}",
                    "references",
                    f"Title card direction: {card['direction']}.",
                    "sourced",
                    relative,
                    f"line {cue_line}",
                )
            for cue in card["cues"]:
                add(
                    f"typography-{slug(cue, 'style')}",
                    "period",
                    f"Typography style: {cue}.",
                    "sourced",
                    relative,
                    f"line {cue_line}",
                )
