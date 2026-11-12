"""Stunt and Action Coordinator.

Each action beat on the approved treatment becomes one or more shots.
The beat text is the production's. The safety line is the same for every film.
"""

from __future__ import annotations

import re
from pathlib import Path

from movie_swarm.previs_common import (
    PrevisError,
    approved_treatment,
    grounded,
    model_name,
    now,
    save_pair,
    source_blob,
    system_prompt,
    try_model_json,
)
from movie_swarm.validate import load_schema, validate_data


SAFETY = (
    "Stage the beat as separate shots. One movement per shot. "
    "Do not ask anyone to take a real impact, a real fall from height, or a real fire. "
    "Keep the body supported. The action has to be possible in the place the scene already describes."
)

_IMPOSSIBLE = re.compile(
    r"\b(flies|flying|teleports?|teleporting|hovers forever|floats forever)\b",
    re.I,
)


def breakdown_path(production_dir: Path) -> Path:
    return production_dir / "stunts" / "action-breakdown.json"


def build_breakdown(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    beats = [str(beat).strip() for beat in treatment.get("action_and_stunt_beats") or [] if str(beat).strip()]
    staged = []
    for beat in beats:
        actions, notes = split_beat(beat)
        if actions:
            staged.append((beat, actions, notes))
    if not staged:
        raise PrevisError(
            "The approved treatment has no action beats. There is nothing for the stunt pass to break down."
        )
    offline = _offline(production_dir, staged)
    drafted = _from_model(llm, offline, beats)
    document = drafted or offline
    save_pair(breakdown_path(production_dir), document, "action-breakdown", _markdown(document))
    return document


def _offline(production_dir: Path, beats: list[tuple[str, list[str], list[str]]]) -> dict:
    items = []
    for index, (beat, actions, notes) in enumerate(beats, start=1):
        shots = []
        for shot_index, sentence in enumerate(actions, start=1):
            possible = _IMPOSSIBLE.search(sentence) is None
            shot = {
                "shot_id": f"stunt-{index:02d}-sh{shot_index:02d}",
                "action": sentence,
                "plausible": possible,
                "safety": SAFETY,
            }
            if not possible:
                shot["note"] = "This beat asks for an action that is not physically possible. Stage a possible version, or cut it."
            shots.append(shot)
        item = {"beat_id": f"beat-{index:03d}", "source": beat, "shots": shots}
        if notes:
            item["notes"] = notes
        items.append(item)
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "safety_policy": SAFETY,
        "beats": items,
        "draft_method": "offline-deterministic",
        "model": model_name("stunt-coordinator", "breakdown"),
        "created_at": now(),
    }


def _sentences(beat: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", beat) if part.strip()]
    return parts or ([beat] if beat.strip() else [])


_DECISION = re.compile(
    r"("
    r"\bthese are the beats\b|"
    r"\bthose are the beats\b|"
    r"\bno extra\b.{0,80}\b(lock|locks|stunt)\b|"
    r"\bbefore generation\b|"
    r"\bstunt locks?\b|"
    r"\b(beats|stunts) are (approved|locked|right)\b"
    r")",
    re.I,
)

_NOTE = re.compile(
    r"("
    r"\b(in the screenplay|in the script|in the treatment|in the shot list)\b|"
    r"\bthe documents say\b|"
    r"\bit is an?\b.+\bnot an?\b|"
    r"^(note|aside|continuity)\s*:"
    r")",
    re.I | re.S,
)

_YES_NO = re.compile(r"^(yes|no|yep|nope|approved|approve|lock|locked|keep)\b", re.I)


def is_decision_sentence(sentence: str) -> bool:
    """A confirmation or a decision about the beats. Not an action."""
    text = " ".join(str(sentence).split())
    if not text:
        return True
    from movie_swarm.treatment_doc import confirms_draft

    if confirms_draft(text):
        return True
    if _DECISION.search(text):
        return True
    if _YES_NO.match(text) and re.search(r"\b(beats?|locks?|generation|stunt)\b", text, re.I):
        return True
    return False


def is_note_sentence(sentence: str) -> bool:
    """A continuity note or a classification. Not a movement to stage."""
    text = " ".join(str(sentence).split())
    if not text or is_decision_sentence(text):
        return False
    return _NOTE.search(text) is not None


def split_beat(beat: str) -> tuple[list[str], list[str]]:
    """Action sentences become shots. Decisions are dropped. Notes stay notes."""
    actions = []
    notes = []
    for sentence in _sentences(beat):
        if is_decision_sentence(sentence):
            continue
        if is_note_sentence(sentence):
            notes.append(sentence)
            continue
        actions.append(sentence)
    return actions, notes


def action_content(answer: str) -> str:
    """The action in an answer. A confirmation or a decision is left out."""
    actions, _notes = split_beat(str(answer or ""))
    return " ".join(actions).strip()


def _from_model(llm, offline: dict, beats: list[str]) -> dict | None:
    if llm is None:
        return None
    source = source_blob(beats)
    drafted = try_model_json(
        llm,
        role="stunt-coordinator",
        purpose="breakdown",
        system=system_prompt(
            "You are the Stunt and Action Coordinator. Break the given beats into shots. "
            "Keep each source string exactly. Mark plausible false only when the beat is not physically possible."
        ),
        user=source,
    )
    if not drafted:
        return None
    drafted["production_id"] = offline["production_id"]
    drafted["safety_policy"] = SAFETY
    drafted["draft_method"] = "model"
    drafted["model"] = offline["model"]
    drafted["created_at"] = offline["created_at"]
    for beat in drafted.get("beats") or []:
        if not isinstance(beat, dict) or not grounded(str(beat.get("source") or ""), source):
            return None
    errors = validate_data(drafted, load_schema("action-breakdown"))
    if errors:
        return None
    return drafted


def _markdown(document: dict) -> str:
    lines = [
        "# Action breakdown",
        "",
        document["safety_policy"],
        "",
    ]
    for beat in document["beats"]:
        lines.append(f"## {beat['beat_id']}")
        lines.append("")
        lines.append(beat["source"])
        lines.append("")
        for shot in beat["shots"]:
            word = "plausible" if shot["plausible"] else "not plausible"
            lines.append(f"- {shot['shot_id']} ({word}): {shot['action']}")
        for note in beat.get("notes") or []:
            lines.append(f"- Note: {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
