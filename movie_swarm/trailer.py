"""Trailer Editor: one role, two deliverables, after picture lock.

The teaser carries tone and mood. The trailer may show the premise, the main
character, and the stakes, and it stops before the ending. Both are cut in
16:9 and 9:16 from approved takes. This role does not request or generate a
new shot.

Research, the spoiler guard, and the plan are production data. The procedure
lives in the skill file. A film that leaves the trailer off is unchanged.

Offline is the default. This module does not read a key and does not pass
``--live``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from movie_swarm.budget import trailer_enabled
from movie_swarm.handoff import write_handoff
from movie_swarm.models import resolve_model
from movie_swarm.previs_common import PrevisError, now, read_brief, save_pair
from movie_swarm.treatment_doc import load_treatment


class TrailerError(PrevisError):
    """The trailer stopped. The message says what is missing."""


# Lengths used only when the production does not name its own.
DEFAULT_TEASER_SECONDS = 15
DEFAULT_TRAILER_SECONDS = 45

_TOPICS = ("treatment", "director", "brand", "genre", "period", "trailer-form")


def marketing_dir(production_dir: Path) -> Path:
    return Path(production_dir) / "marketing"


def research_path(production_dir: Path) -> Path:
    return marketing_dir(production_dir) / "trailer-research.json"


def guard_path(production_dir: Path) -> Path:
    return marketing_dir(production_dir) / "spoiler-guard.json"


def plan_path(production_dir: Path) -> Path:
    return marketing_dir(production_dir) / "trailer-plan.json"


def cut_path(production_dir: Path) -> Path:
    return marketing_dir(production_dir) / "trailer-cut.json"


def request_shot(*_args, **_kwargs) -> None:
    """The trailer never asks for a new shot. Callers hit this on purpose in tests."""
    raise TrailerError(
        "The Trailer Editor cannot request or generate a new shot. "
        "Use an approved take, or drop the beat and log the gap."
    )


def write_research(production_dir: Path, llm=None) -> dict:
    """Write marketing/trailer-research.json from the production's own documents."""
    production_dir = Path(production_dir)
    _require_on(production_dir)
    document = _research_document(production_dir)
    document = _keep_offline(llm, document, "research")
    save_pair(research_path(production_dir), document, "trailer-research", _research_markdown(document))
    return document


def write_guard(production_dir: Path, llm=None) -> dict:
    """Write the spoiler guard. Research has to exist first."""
    production_dir = Path(production_dir)
    _require_on(production_dir)
    _require_research(production_dir)
    document = _guard_document(production_dir)
    document = _keep_offline(llm, document, "guard")
    save_pair(guard_path(production_dir), document, "spoiler-guard", _guard_markdown(document))
    return document


def sign_guard(production_dir: Path, by: str = "Director", note: str = "") -> dict:
    """The Director signs the spoiler guard. This is not Ron's trailer gate."""
    production_dir = Path(production_dir)
    path = guard_path(production_dir)
    if not path.is_file():
        raise TrailerError("There is no spoiler guard to sign. Write the guard after the research.")
    data = json.loads(path.read_text(encoding="utf-8"))
    who = by.strip() or "Director"
    data["director_signed"] = True
    data["signed_by"] = who
    data["signed_at"] = now()
    data["sign_note"] = note.strip()
    save_pair(path, data, "spoiler-guard", _guard_markdown(data))
    return data


def write_plan(production_dir: Path, llm=None) -> dict:
    """Write the beat plan. Research and a signed guard are required."""
    production_dir = Path(production_dir)
    _require_on(production_dir)
    _require_research(production_dir)
    guard = _require_signed_guard(production_dir)
    document = _plan_document(production_dir, guard)
    document = _keep_offline(llm, document, "plan")
    save_pair(plan_path(production_dir), document, "trailer-plan", _plan_markdown(document))
    return document


def cut_trailer(production_dir: Path, llm=None) -> dict:
    """Cut from the plan. A beat with no approved take is dropped and logged."""
    production_dir = Path(production_dir)
    _require_on(production_dir)
    plan = _require_plan(production_dir)
    current = _lock_hash(production_dir)
    if plan.get("picture_lock_sha256") != current:
        raise TrailerError(
            "The locked cut changed after this plan was written. "
            "Write the plan again before cutting. Nothing was rendered."
        )
    document = _cut_document(production_dir, plan)
    document = _keep_offline(llm, document, "cut")
    _render_placeholders(production_dir, document)
    save_pair(cut_path(production_dir), document, "trailer-cut", _cut_markdown(document))
    return document


def recheck_trailer(production_dir: Path) -> dict:
    """Compare the trailer with the locked cut. A changed cut is marked stale."""
    production_dir = Path(production_dir)
    path = cut_path(production_dir)
    if not path.is_file():
        raise TrailerError("There is no trailer to re-check.")
    data = json.loads(path.read_text(encoding="utf-8"))
    current = _lock_hash(production_dir)
    stale = current != data.get("picture_lock_sha256")
    data["lock_status"] = "stale" if stale else "current"
    if stale:
        data["note"] = (
            "The locked cut changed after this trailer was made. "
            "Write the plan again, then cut again. Do not post the old files."
        )
    else:
        data["note"] = "The trailer still matches the locked cut."
    save_pair(path, data, "trailer-cut", _cut_markdown(data))
    return data


def record_trailer_decision(production_dir: Path, decision: str, by: str, note: str, decided_at: str) -> str:
    """Stamp the cut when Ron approves or rejects the trailer gate."""
    path = cut_path(production_dir)
    if not path.is_file():
        return "No trailer cut was on disk to stamp."
    data = json.loads(path.read_text(encoding="utf-8"))
    data["gate"] = "approved" if decision == "approved" else "rejected"
    data["gate_by"] = by.strip() or "recorded"
    data["gate_at"] = decided_at
    data["gate_note"] = note.strip()
    save_pair(path, data, "trailer-cut", _cut_markdown(data))
    if decision == "approved":
        return "The trailer gate is approved."
    return "The trailer gate was rejected. The film can still deliver without it."


def package_rows(production_dir: Path, package: Path) -> list[dict]:
    """Copy finished trailer files into delivery/marketing and list them.

    An absent trailer returns nothing. The film delivers either way.
    """
    production_dir = Path(production_dir)
    path = cut_path(production_dir)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    folder = package / "marketing"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    copied = _copy_into(path, folder / "trailer-cut.json")
    rows.append({"path": copied, "listed": _listed(package, copied), "label": "Trailer cut"})
    notes = path.with_suffix(".md")
    if notes.is_file():
        copied = _copy_into(notes, folder / "trailer-cut.md")
        rows.append({"path": copied, "listed": _listed(package, copied), "label": "Trailer cut, readable copy"})
    sheet = _usage_sheet(folder, data)
    rows.append({"path": sheet, "listed": _listed(package, sheet), "label": "Marketing usage sheet. Posting stays with Ron."})
    for item in data.get("files") or []:
        if not isinstance(item, dict):
            continue
        source = production_dir / str(item.get("filename") or "")
        name = Path(str(item.get("filename") or "clip.mp4")).name
        dest = folder / name
        if source.is_file():
            copied = _copy_into(source, dest)
            rows.append(
                {
                    "path": copied,
                    "listed": _listed(package, copied),
                    "label": f"{item.get('deliverable') or 'trailer'} {item.get('aspect_ratio') or ''}".strip(),
                }
            )
        else:
            rows.append(
                {
                    "path": dest,
                    "listed": _listed(package, dest),
                    "label": f"{item.get('deliverable') or 'trailer'} {item.get('aspect_ratio') or ''}".strip(),
                }
            )
    return rows


def qc_checks(production_dir: Path) -> list[dict]:
    """Continuity, card text, and the spoiler guard. Empty when there is no trailer."""
    production_dir = Path(production_dir)
    path = cut_path(production_dir)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    guard = _read_json(guard_path(production_dir))
    checks = [
        _qc(
            "trailer-spoiler-guard",
            "marketing/spoiler-guard.json",
            "pass" if guard.get("director_signed") else "fail",
            "The Director signed the spoiler guard."
            if guard.get("director_signed")
            else "The spoiler guard is not signed.",
        ),
        _qc(
            "trailer-card-text",
            "marketing/trailer-plan.json",
            "pass" if data.get("cards") else "fail",
            "The card list is on the cut." if data.get("cards") else "The cut has no card text.",
        ),
        _qc(
            "trailer-approved-takes",
            "marketing/trailer-cut.json",
            "pass",
            _gap_sentence(data),
        ),
    ]
    return checks


def run_trailer(call) -> str:
    """One trailer command. A film with the trailer off skips cleanly."""
    production = Path(call.production_dir)
    if not trailer_enabled(production):
        return "The trailer is off for this film. Nothing was written. The film can deliver without one."
    command = call.command
    llm = getattr(call, "llm", None)
    if command == "research":
        document = write_research(production, llm=llm)
        return f"Trailer research: {len(document['items'])} item(s). File: marketing/trailer-research.json"
    if command == "guard":
        document = write_guard(production, llm=llm)
        return f"Spoiler guard: {len(document['hold_back'])} beat(s) held back. File: marketing/spoiler-guard.json"
    if command == "sign":
        document = sign_guard(production)
        return f"The Director signed the spoiler guard. Signed: {document['director_signed']}."
    if command == "plan":
        document = write_plan(production, llm=llm)
        return f"Trailer plan: {len(document['beats'])} beat(s). File: marketing/trailer-plan.json"
    if command == "cut":
        document = cut_trailer(production, llm=llm)
        return (
            f"Trailer cut: {len(document['kept'])} beat(s), {len(document['gaps'])} gap(s). "
            "File: marketing/trailer-cut.json"
        )
    if command == "recheck":
        document = recheck_trailer(production)
        return f"Trailer re-check: {document['lock_status']}."
    raise TrailerError(f"The Trailer Editor has no command named {command}.")


def _require_on(production_dir: Path) -> None:
    if not trailer_enabled(production_dir):
        raise TrailerError("The trailer is off for this film. Nothing was written.")


def _require_research(production_dir: Path) -> dict:
    path = research_path(production_dir)
    if not path.is_file():
        raise TrailerError(
            "There is no trailer research. Write marketing/trailer-research.json before the guard or the plan."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _require_signed_guard(production_dir: Path) -> dict:
    path = guard_path(production_dir)
    if not path.is_file():
        raise TrailerError("There is no spoiler guard. Write it from the research before the plan.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("director_signed"):
        raise TrailerError("The Director has not signed the spoiler guard. The plan was not written.")
    return data


def _require_plan(production_dir: Path) -> dict:
    path = plan_path(production_dir)
    if not path.is_file():
        raise TrailerError("There is no trailer plan. Cut only after the plan is written.")
    return json.loads(path.read_text(encoding="utf-8"))


def _research_document(production_dir: Path) -> dict:
    treatment = load_treatment(production_dir)
    brief = read_brief(production_dir)
    items = []

    def add(item_id: str, topic: str, text: str, basis: str, source_file: str | None, source_field: str | None) -> None:
        items.append(
            {
                "item_id": item_id,
                "topic": topic,
                "text": " ".join(text.split()),
                "basis": basis,
                "source_file": source_file,
                "source_field": source_field,
            }
        )

    title = str(treatment.get("title") or "").strip()
    if title:
        add("title", "treatment", f"Title: {title}.", "sourced", "treatment/treatment.json", "title")
    logline = str(treatment.get("logline") or "").strip()
    if logline:
        add("logline", "treatment", f"Logline: {logline}.", "sourced", "treatment/treatment.json", "logline")
    tone = (treatment.get("tone_and_genre") or {}) if isinstance(treatment.get("tone_and_genre"), dict) else {}
    if str(tone.get("tone") or "").strip():
        add("tone", "treatment", f"Tone: {tone['tone']}.", "sourced", "treatment/treatment.json", "tone_and_genre.tone")
    if str(tone.get("genre") or "").strip():
        add("genre", "genre", f"Genre: {tone['genre']}.", "sourced", "treatment/treatment.json", "tone_and_genre.genre")
    else:
        add("genre", "genre", "The treatment does not name a genre.", "inferred", None, None)
    period = str(treatment.get("world_and_period") or "").strip()
    if period:
        add("period", "period", f"Period: {period}.", "sourced", "treatment/treatment.json", "world_and_period")
    else:
        add("period", "period", "The documents do not name a period.", "inferred", None, None)
    notes = production_dir / "director" / "notes.md"
    if notes.is_file() and notes.read_text(encoding="utf-8").strip():
        text = " ".join(notes.read_text(encoding="utf-8").split())
        add("director-notes", "director", text[:500], "sourced", "director/notes.md", "text")
    else:
        add("director-notes", "director", "No director notes were on disk.", "inferred", None, None)
    guide = production_dir / "graphics" / "brand-guide.json"
    if guide.is_file():
        add(
            "brand-guide",
            "brand",
            "A brand guide is on disk. Cards use that guide.",
            "sourced",
            "graphics/brand-guide.json",
            "status",
        )
    else:
        add("brand-guide", "brand", "No brand guide is on disk yet. Card text stays short.", "inferred", None, None)
    genre_name = str(tone.get("genre") or "this genre")
    add(
        "trailer-form",
        "trailer-form",
        (
            f"The documents do not say how trailers in {genre_name} were cut. "
            "The teaser stays with tone and mood. The trailer may show the premise, "
            "the main character, and the stakes, and it stops before the ending."
        ),
        "inferred",
        None,
        None,
    )
    if not any(item["topic"] == "treatment" for item in items):
        add("treatment-empty", "treatment", "The treatment did not yield a title or a logline.", "inferred", None, None)
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "items": items,
        "draft_method": "offline-deterministic",
        "model": resolve_model("trailer-editor", purpose="research")["model"],
        "note": "Research is written before the guard and the plan. Each item is sourced or inferred.",
        "written_at": now(),
    }


def _guard_document(production_dir: Path) -> dict:
    treatment = load_treatment(production_dir)
    may_show = []
    hold_back = []
    logline = str(treatment.get("logline") or "").strip()
    if logline:
        may_show.append({"id": "premise", "text": logline, "source_field": "logline"})
    for person in treatment.get("characters") or []:
        if isinstance(person, dict) and person.get("role") == "protagonist" and person.get("name"):
            may_show.append(
                {"id": "character", "text": str(person["name"]), "source_field": "characters"}
            )
            break
    theme = (treatment.get("theme_and_emotional_intent") or {}) if isinstance(treatment.get("theme_and_emotional_intent"), dict) else {}
    if str(theme.get("theme") or "").strip():
        may_show.append({"id": "stakes", "text": str(theme["theme"]), "source_field": "theme_and_emotional_intent.theme"})
    scenes = [scene for scene in treatment.get("scenes") or [] if isinstance(scene, dict)]
    if scenes:
        last = scenes[-1]
        sentences = _sentences(str(last.get("what_happens") or ""))
        for earlier in scenes[:-1]:
            for index, sentence in enumerate(_sentences(str(earlier.get("what_happens") or "")), start=1):
                may_show.append(
                    {
                        "id": f"scene-{earlier.get('scene_id') or index}-{index}",
                        "text": sentence,
                        "source_field": "scenes",
                    }
                )
        if len(sentences) > 1:
            for index, sentence in enumerate(sentences[:-1], start=1):
                may_show.append({"id": f"setup-{index}", "text": sentence, "source_field": "scenes"})
        ending = sentences[-1] if sentences else "The last scene."
        hold_back.append(
            {
                "id": "ending",
                "text": ending,
                "source_field": "scenes",
                "reason": "The trailer stops before the ending.",
            }
        )
    else:
        hold_back.append(
            {
                "id": "ending",
                "text": "The treatment has no scenes, so the ending is not named.",
                "source_field": "scenes",
                "reason": "Nothing is shown until the treatment names the ending to hold back.",
            }
        )
    tone = (treatment.get("tone_and_genre") or {}) if isinstance(treatment.get("tone_and_genre"), dict) else {}
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "may_show": may_show,
        "hold_back": hold_back,
        "teaser_rule": "Tone and mood only. Do not give the story away.",
        "trailer_rule": "Premise, main character, and stakes. Stop before the ending.",
        "tone": str(tone.get("tone") or ""),
        "director_signed": False,
        "signed_by": None,
        "signed_at": None,
        "sign_note": "",
        "draft_method": "offline-deterministic",
        "model": resolve_model("trailer-editor", purpose="guard")["model"],
        "note": "Built from the treatment. The Director signs this before the plan.",
        "written_at": now(),
    }


def _plan_document(production_dir: Path, guard: dict) -> dict:
    lengths, length_source, length_note = _lengths(production_dir)
    lock = _read_json(production_dir / "edit" / "picture-lock.json")
    circled = _circled_ids(production_dir)
    held = [str(item.get("text") or "") for item in guard.get("hold_back") or [] if item.get("text")]
    events = [event for event in lock.get("events") or [] if isinstance(event, dict)]
    beats = []
    gaps = []
    teaser_used = 0.0
    trailer_used = 0.0
    for event in events:
        shot_id = str(event.get("shot_id") or "")
        if not shot_id:
            continue
        if shot_id not in circled:
            gaps.append(
                {
                    "shot_id": shot_id,
                    "reason": "This shot is not an approved take. It was dropped. No new shot was requested.",
                }
            )
            continue
        text = _event_text(production_dir, event)
        if any(phrase and phrase.casefold() in text.casefold() for phrase in held):
            gaps.append(
                {
                    "shot_id": shot_id,
                    "reason": "This shot gives away a held beat. It stays out of the trailer.",
                }
            )
            continue
        duration = _event_duration(event)
        record_in = _as_float(event.get("record_in"))
        record_out = _as_float(event.get("record_out"))
        if teaser_used < lengths["teaser_seconds"]:
            beats.append(
                _beat("teaser", shot_id, event, duration, record_in, record_out, guard.get("tone") or "Tone and mood.")
            )
            teaser_used += duration
        if trailer_used < lengths["trailer_seconds"]:
            beats.append(
                _beat("trailer", shot_id, event, duration, record_in, record_out, _card_text(guard))
            )
            trailer_used += duration
    cards = [
        {"id": "teaser-card", "text": str(guard.get("tone") or "Tone and mood."), "for": "title-graphic-design"},
        {"id": "trailer-card", "text": _card_text(guard), "for": "title-graphic-design"},
    ]
    safe = _safe_area(production_dir)
    music = _music_cue(production_dir)
    loudness = _loudness(production_dir)
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "lengths": lengths,
        "length_source": length_source,
        "length_note": length_note,
        "picture_lock_sha256": _lock_hash(production_dir),
        "beats": beats,
        "gaps": gaps,
        "cards": cards,
        "music": music,
        "loudness": loudness,
        "safe_area": safe,
        "versions": ["16:9", "9:16"],
        "handoff": {
            "cards_to": "title-graphic-design",
            "timeline_to": "mixer",
            "qa": ["continuity", "card text", "spoiler guard"],
            "files_to": "post-supervisor",
        },
        "draft_method": "offline-deterministic",
        "model": resolve_model("trailer-editor", purpose="plan")["model"],
        "note": "The plan uses approved takes from the locked cut. A missing beat is a gap, not a new shot.",
        "written_at": now(),
    }


def _cut_document(production_dir: Path, plan: dict) -> dict:
    circled = _circled_ids(production_dir)
    locked_ids = {
        str(event.get("shot_id"))
        for event in (_read_json(production_dir / "edit" / "picture-lock.json").get("events") or [])
        if isinstance(event, dict) and event.get("shot_id")
    }
    kept = []
    gaps = list(plan.get("gaps") or [])
    seen = {item.get("shot_id") for item in gaps if isinstance(item, dict)}
    for beat in plan.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        shot_id = str(beat.get("shot_id") or "")
        if shot_id in circled and shot_id in locked_ids:
            kept.append(beat)
            continue
        if shot_id not in seen:
            gaps.append(
                {
                    "shot_id": shot_id or "missing-shot",
                    "reason": "This beat cannot be made from an approved take in the locked cut. It was dropped. No new shot was requested.",
                }
            )
            seen.add(shot_id)
    grade = production_dir / "color" / "graded-preview.mp4"
    picture = "color/graded-preview.mp4" if grade.is_file() else "edit/picture-lock.json"
    picture_note = (
        "Selects come from the graded picture."
        if grade.is_file()
        else "No graded picture was on disk. Selects come from the locked cut."
    )
    files = []
    for deliverable, seconds in (
        ("teaser", (plan.get("lengths") or {}).get("teaser_seconds")),
        ("trailer", (plan.get("lengths") or {}).get("trailer_seconds")),
    ):
        for ratio, width, height in (("16:9", 320, 180), ("9:16", 180, 320)):
            files.append(
                {
                    "deliverable": deliverable,
                    "aspect_ratio": ratio,
                    "filename": f"marketing/{deliverable}-{ratio.replace(':', 'x')}.mp4",
                    "width": width,
                    "height": height,
                    "target_seconds": seconds,
                    "render_status": "not-rendered",
                    "safe_area": plan.get("safe_area") or {},
                }
            )
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "picture_lock_sha256": plan.get("picture_lock_sha256"),
        "lock_status": "current",
        "picture": picture,
        "picture_note": picture_note,
        "kept": kept,
        "gaps": gaps,
        "cards": plan.get("cards") or [],
        "files": files,
        "loudness": plan.get("loudness") or {},
        "gate": "pending",
        "gate_by": None,
        "gate_at": None,
        "gate_note": "",
        "draft_method": "offline-deterministic",
        "model": resolve_model("trailer-editor", purpose="cut")["model"],
        "note": "Cut from approved takes only. " + picture_note,
        "written_at": now(),
    }


def _beat(deliverable, shot_id, event, duration, record_in, record_out, card) -> dict:
    return {
        "deliverable": deliverable,
        "shot_id": shot_id,
        "source_file": str(event.get("source_file") or ""),
        "record_in": record_in,
        "record_out": record_out,
        "duration_seconds": duration,
        "card_text": card,
        "music": "Use the music cue on the cue sheet when one is named.",
    }


def _card_text(guard: dict) -> str:
    parts = []
    for item in guard.get("may_show") or []:
        if isinstance(item, dict) and item.get("id") in {"premise", "character", "stakes"} and item.get("text"):
            parts.append(str(item["text"]))
    return " ".join(parts) or "Premise."


def _lengths(production_dir: Path) -> tuple[dict, str, str]:
    found = {}
    source = None
    for relative in (
        "marketing/trailer-spec.json",
        "delivery/delivery-spec.json",
        "production-brief.json",
    ):
        data = _read_json(production_dir / relative)
        trailer = data.get("trailer") if isinstance(data.get("trailer"), dict) else data
        teaser = _as_float(trailer.get("teaser_seconds") if isinstance(trailer, dict) else None)
        full = _as_float(trailer.get("trailer_seconds") if isinstance(trailer, dict) else None)
        if teaser or full:
            if teaser:
                found["teaser_seconds"] = teaser
            if full:
                found["trailer_seconds"] = full
            source = relative
            break
    treatment = _read_json(production_dir / "treatment" / "treatment.json")
    deliverables = treatment.get("deliverables") if isinstance(treatment.get("deliverables"), dict) else {}
    if "teaser_seconds" not in found:
        teaser = _as_float(deliverables.get("teaser_seconds"))
        if teaser:
            found["teaser_seconds"] = teaser
            source = source or "treatment/treatment.json"
    if "trailer_seconds" not in found:
        full = _as_float(deliverables.get("trailer_seconds"))
        if full:
            found["trailer_seconds"] = full
            source = source or "treatment/treatment.json"
    notes = []
    if "teaser_seconds" not in found:
        found["teaser_seconds"] = DEFAULT_TEASER_SECONDS
        notes.append(f"Teaser length was not named. The default is {DEFAULT_TEASER_SECONDS} seconds.")
    if "trailer_seconds" not in found:
        found["trailer_seconds"] = DEFAULT_TRAILER_SECONDS
        notes.append(f"Trailer length was not named. The default is {DEFAULT_TRAILER_SECONDS} seconds.")
    if notes:
        return found, "default", " ".join(notes)
    return found, "production", f"Lengths come from {source}."


def _safe_area(production_dir: Path) -> dict:
    from movie_swarm.delivery import _ACTION_INSET, _GRAPHICS_INSET, _SAFE_CITATION

    spec = _read_json(production_dir / "delivery" / "delivery-spec.json")
    action = spec.get("safe_action_inset_percent")
    graphics = spec.get("safe_graphics_inset_percent")
    try:
        action_value = float(action) if action is not None else _ACTION_INSET
    except (TypeError, ValueError):
        action_value = _ACTION_INSET
    try:
        graphics_value = float(graphics) if graphics is not None else _GRAPHICS_INSET
    except (TypeError, ValueError):
        graphics_value = _GRAPHICS_INSET
    source = "delivery spec" if action is not None or graphics is not None else "default"
    return {
        "action_inset_percent": action_value,
        "graphics_inset_percent": graphics_value,
        "source": source,
        "citation": _SAFE_CITATION,
    }


def _music_cue(production_dir: Path) -> dict:
    sheet = _read_json(production_dir / "sound" / "cue-sheet.json")
    for cue in sheet.get("cues") or []:
        if isinstance(cue, dict) and str(cue.get("kind") or cue.get("layer") or "").casefold() in {"music", "score"}:
            return {"cue_id": cue.get("cue_id") or cue.get("id"), "source": "sound/cue-sheet.json"}
    return {"cue_id": None, "source": None, "note": "No music cue was on the cue sheet."}


def _loudness(production_dir: Path) -> dict:
    plan = _read_json(production_dir / "color" / "mix-plan.json")
    loudness = plan.get("loudness") if isinstance(plan.get("loudness"), dict) else {}
    if loudness.get("integrated_lufs") is not None:
        return {
            "integrated_lufs": loudness.get("integrated_lufs"),
            "standard": loudness.get("standard") or "production",
            "source": "color/mix-plan.json",
        }
    return {
        "integrated_lufs": -23.0,
        "standard": "EBU R128",
        "source": "default",
        "note": "The mix plan does not name a target. The trailer mix uses EBU R128, -23.0 LUFS.",
    }


def _circled_ids(production_dir: Path) -> set[str]:
    report = _read_json(production_dir / "dailies" / "dailies-report.json")
    found = set()
    for shot in report.get("shots") or []:
        if isinstance(shot, dict) and shot.get("verdict") == "circle" and shot.get("shot_id"):
            found.add(str(shot["shot_id"]))
    return found


def _event_text(production_dir: Path, event: dict) -> str:
    parts = [str(event.get("description") or "")]
    shot_id = str(event.get("shot_id") or "")
    board = _read_json(production_dir / "storyboard" / "shot-list.json")
    for shot in board.get("shots") or []:
        if isinstance(shot, dict) and str(shot.get("shot_id")) == shot_id:
            parts.append(str(shot.get("description") or ""))
            parts.append(str(shot.get("prompt") or ""))
    return " ".join(part for part in parts if part)


def _event_duration(event: dict) -> float:
    duration = _as_float(event.get("duration_seconds"))
    if duration and duration > 0:
        return duration
    start = _as_float(event.get("record_in")) or 0
    end = _as_float(event.get("record_out")) or start
    if end > start:
        return end - start
    return 1.0


def _lock_hash(production_dir: Path) -> str:
    path = production_dir / "edit" / "picture-lock.json"
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_placeholders(production_dir: Path, document: dict) -> None:
    ffmpeg = shutil.which("ffmpeg")
    for item in document.get("files") or []:
        if not ffmpeg:
            item["render_status"] = "not-rendered"
            continue
        dest = production_dir / str(item["filename"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=black:size={item['width']}x{item['height']}:rate=24:duration=1",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-t",
                    "1",
                    str(dest),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            item["render_status"] = "not-rendered"
            continue
        item["render_status"] = "rendered" if dest.is_file() and dest.stat().st_size > 0 else "not-rendered"


def _usage_sheet(folder: Path, data: dict) -> Path:
    lines = [
        "Marketing files",
        "",
        "These files belong to the film. Posting them stays with Ron.",
        "",
        data.get("picture_note") or "",
        "",
    ]
    for item in data.get("files") or []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('deliverable')} {item.get('aspect_ratio')}: {item.get('filename')} ({item.get('render_status')})"
            )
    if data.get("gaps"):
        lines.extend(["", "Gaps, not new shots:"])
        for gap in data["gaps"]:
            if isinstance(gap, dict):
                lines.append(f"- {gap.get('shot_id')}: {gap.get('reason')}")
    path = folder / "usage-sheet.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _copy_into(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    return dest


def _listed(package: Path, path: Path) -> str:
    try:
        return str(path.relative_to(package.parent))
    except ValueError:
        return str(path)


def _gap_sentence(data: dict) -> str:
    gaps = [item for item in data.get("gaps") or [] if isinstance(item, dict)]
    if not gaps:
        return "Every kept beat comes from an approved take. No gap was logged."
    return f"{len(gaps)} beat(s) could not be made from approved takes. They were dropped and logged. No new shot was requested."


def _qc(check_id: str, target: str, status: str, detail: str) -> dict:
    return {
        "check_id": check_id,
        "target": target,
        "kind": "trailer",
        "status": status,
        "detail": detail,
    }


def _keep_offline(llm, document: dict, purpose: str) -> dict:
    """A model reply is discarded. The offline document is the one that is saved."""
    if llm is not None:
        document = dict(document)
        document["note"] = document.get("note", "") + " A model reply was not used."
    return document


def _research_markdown(document: dict) -> str:
    lines = [f"Trailer research for {document['production_id']}", ""]
    for item in document["items"]:
        source = item["source_file"] or "inferred"
        lines.append(f"- {item['topic']}: {item['text']} ({item['basis']}, {source})")
    lines.extend(["", document["note"]])
    return "\n".join(lines).rstrip() + "\n"


def _guard_markdown(document: dict) -> str:
    lines = [
        f"Spoiler guard for {document['production_id']}",
        "",
        document["teaser_rule"],
        document["trailer_rule"],
        "",
        "May show:",
    ]
    for item in document["may_show"]:
        lines.append(f"- {item['text']}")
    lines.append("")
    lines.append("Hold back:")
    for item in document["hold_back"]:
        lines.append(f"- {item['text']}")
    signed = "signed" if document.get("director_signed") else "not signed"
    lines.extend(["", f"Director: {signed}."])
    return "\n".join(lines).rstrip() + "\n"


def _plan_markdown(document: dict) -> str:
    lines = [
        f"Trailer plan for {document['production_id']}",
        "",
        document["length_note"],
        "",
    ]
    for beat in document["beats"]:
        lines.append(
            f"- {beat['deliverable']} {beat['shot_id']} "
            f"{beat.get('record_in')}–{beat.get('record_out')} {beat.get('card_text')}"
        )
    if document["gaps"]:
        lines.extend(["", "Gaps:"])
        for gap in document["gaps"]:
            lines.append(f"- {gap.get('shot_id')}: {gap.get('reason')}")
    lines.extend(["", document["note"]])
    return "\n".join(lines).rstrip() + "\n"


def _cut_markdown(document: dict) -> str:
    lines = [
        f"Trailer cut for {document['production_id']}",
        "",
        document.get("picture_note") or "",
        f"Lock: {document.get('lock_status')}.",
        "",
    ]
    lines.append(f"Kept {len(document.get('kept') or [])} beat(s).")
    if document.get("gaps"):
        lines.append("Gaps:")
        for gap in document["gaps"]:
            if isinstance(gap, dict):
                lines.append(f"- {gap.get('shot_id')}: {gap.get('reason')}")
    lines.extend(["", document.get("note") or ""])
    return "\n".join(lines).rstrip() + "\n"


def _sentences(text: str) -> list[str]:
    parts = [part.strip() for part in text.replace("?", ".").replace("!", ".").split(".")]
    return [part for part in parts if part]


def _as_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
