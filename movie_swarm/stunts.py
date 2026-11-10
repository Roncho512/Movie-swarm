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
    if not beats:
        raise PrevisError(
            "The approved treatment has no action beats. There is nothing for the stunt pass to break down."
        )
    offline = _offline(production_dir, beats)
    drafted = _from_model(llm, offline, beats)
    document = drafted or offline
    save_pair(breakdown_path(production_dir), document, "action-breakdown", _markdown(document))
    return document


def _offline(production_dir: Path, beats: list[str]) -> dict:
    items = []
    for index, beat in enumerate(beats, start=1):
        sentences = _sentences(beat)
        shots = []
        for shot_index, sentence in enumerate(sentences, start=1):
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
        items.append({"beat_id": f"beat-{index:03d}", "source": beat, "shots": shots})
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
    return parts or [beat]


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
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
