"""Gaffer: a lighting plan from the camera package and the look.

Key, fill, practicals, time of day, color temperature, and contrast ratio
are copied from the production. A number the production did not write is
left as not named. The prompt note is those same words, ready to attach to
a shot. Shots in one scene that name a different time of day are flagged.
"""

from __future__ import annotations

import re
from pathlib import Path

from movie_swarm.camera import package_path
from movie_swarm.prep_inputs import load_scenes, load_shots, scene_for_shot
from movie_swarm.previs_common import (
    approved_treatment,
    load_optional,
    model_name,
    now,
    save_pair,
    source_blob,
    system_prompt,
    try_model_json,
)


_KELVIN = re.compile(r"\b(\d{3,5})\s*k\b", re.I)
_RATIO = re.compile(r"\b\d+(?:\.\d+)?\s*:\s*\d+\b")
_PRACTICAL = (
    "practical",
    "lamp",
    "fluorescent",
    "window",
    "neon",
    "candle",
    "fire",
    "available light",
)
_SUN = ("sun", "sunlight", "moon", "moonlight", "daylight")
_TIME_FAMILIES = {
    "dawn": "dawn",
    "sunrise": "dawn",
    "morning": "morning",
    "dusk": "dusk",
    "sunset": "dusk",
    "evening": "dusk",
    "night": "night",
    "midnight": "night",
    "nighttime": "night",
    "day": "day",
    "daytime": "day",
    "noon": "day",
    "afternoon": "day",
}

# A bare "day" inside "minutes of day left" is not a time-of-day statement.
_EXPLICIT_TIME = (
    re.compile(
        r"\bat\s+(dawn|dusk|sunrise|sunset|night|midnight|noon|morning|evening)\b",
        re.I,
    ),
    re.compile(
        r"\b(dawn|dusk|sunrise|sunset|night|morning|evening)\s+(?:falls|breaks|comes|arrives|settles|fell|broke)\b",
        re.I,
    ),
    re.compile(r"\b(night|dawn|dusk)\s+falls\b", re.I),
    re.compile(
        r"\bit(?:'s| is)\s+(dawn|dusk|night|morning|evening|noon|midnight|daytime|nighttime)\b",
        re.I,
    ),
    re.compile(r"\b(?:by|before|after|until)\s+(dawn|dusk|night|morning|evening|noon)\b", re.I),
    re.compile(r"\b(daytime|nighttime)\b", re.I),
    re.compile(
        r"\b(?:INT|EXT|I/E)\.?\s+[^\n.]{0,80}-\s*(DAWN|DUSK|NIGHT|DAY|MORNING|EVENING|NOON)\b",
        re.I,
    ),
)


def plan_path(production_dir: Path) -> Path:
    return production_dir / "lighting" / "lighting-plan.json"


def build_lighting_plan(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    package = load_optional(package_path(production_dir), "camera-package")
    look = load_optional(production_dir / "look" / "look.json", "look")
    shots, shot_source = load_shots(production_dir)
    scenes, scene_source = load_scenes(production_dir, treatment)
    offline = _offline(production_dir, treatment, package, look, shots, shot_source, scenes, scene_source)
    drafted = _from_model(llm, offline, package, look)
    document = drafted or offline
    save_pair(plan_path(production_dir), document, "lighting-plan", _markdown(document))
    return document


def _offline(production_dir, treatment, package, look, shots, shot_source, scenes, scene_source) -> dict:
    grouped: dict[str, dict] = {}
    for shot in shots:
        scene = scene_for_shot(shot, scenes)
        scene_id = shot["scene_id"] or (scene["scene_id"] if scene else "unassigned")
        bucket = grouped.setdefault(scene_id, {"scene": scene, "shots": []})
        if bucket["scene"] is None and scene is not None:
            bucket["scene"] = scene
        bucket["shots"].append(shot)
    if not grouped and scenes:
        for scene in scenes:
            grouped.setdefault(scene["scene_id"], {"scene": scene, "shots": []})
    rows = []
    for scene_id, bucket in grouped.items():
        rows.append(_scene_plan(scene_id, bucket["scene"], bucket["shots"], package, look, treatment))
    rows.sort(key=lambda item: item["scene_id"])
    findings = [item for row in rows for item in row["continuity"]["findings"]]
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "source": {
            "camera": "camera/camera-package.json" if package else None,
            "look": "look/look.json" if look else None,
            "shots": shot_source,
            "scenes": scene_source,
        },
        "continuity": "drift" if findings else "clear",
        "scenes": rows,
        "draft_method": "offline-deterministic",
        "model": model_name("gaffer", "plan"),
        "note": "Lighting words are copied from the camera plan and the look. No source was invented.",
        "created_at": now(),
    }


def _scene_plan(scene_id, scene, shots, package, look, treatment) -> dict:
    heading_time = (scene or {}).get("time_of_day") or "not named"
    grade_time = ""
    if look and isinstance(look.get("grade"), dict):
        grade_time = str(look["grade"].get("time_of_day") or "")
    time_of_day = heading_time if heading_time != "not named" else (grade_time or "not named")
    lines = _lighting_lines(package, look, treatment)
    sources = _sources(lines)
    blob = " ".join(lines)
    temperature = _temperature(blob)
    ratio = _ratio(blob)
    prompt = _prompt(time_of_day, sources, temperature, ratio, lines)
    findings = _continuity(scene_id, time_of_day, shots)
    return {
        "scene_id": scene_id,
        "location": (scene or {}).get("location") or "not named",
        "time_of_day": time_of_day,
        "key": sources["key"],
        "fill": sources["fill"],
        "practicals": sources["practicals"],
        "color_temperature": temperature,
        "contrast_ratio": ratio,
        "prompt_note": prompt,
        "shot_ids": [shot["shot_id"] for shot in shots],
        "continuity": {
            "verdict": "drift" if findings else "clear",
            "findings": findings,
        },
    }


def _lighting_lines(package, look, treatment) -> list[str]:
    lines = []
    for source in (package, look):
        if not source:
            continue
        for item in source.get("lighting") or []:
            if isinstance(item, dict) and item.get("description"):
                text = str(item["description"]).strip()
                if text and text not in lines:
                    lines.append(text)
            elif isinstance(item, str) and item.strip() and item.strip() not in lines:
                lines.append(item.strip())
    plan = str(treatment.get("color_and_light_plan") or "").strip()
    if plan and plan not in lines and not lines:
        lines.append(plan)
    return lines


def _sources(lines: list[str]) -> dict:
    practicals = []
    fills = []
    keys = []
    for line in lines:
        folded = line.casefold()
        if "fill" in folded:
            fills.append(line)
        if "key" in folded:
            keys.append(line)
        if any(word in folded for word in _PRACTICAL):
            practicals.append(line)
    practical = " ".join(practicals) if practicals else "not named"
    fill = " ".join(fills) if fills else "not named"
    if keys:
        key = " ".join(keys)
    elif practical != "not named":
        key = practical
    elif lines:
        key = lines[0]
    else:
        key = "not named"
    # Daylight is the key, not a practical. Do not copy a sun line into both.
    if _sun_line(practical) or (_sun_line(key) and practical == key):
        practical = "not named"
    return {"key": key, "fill": fill, "practicals": practical}


def _sun_line(text: str) -> bool:
    folded = str(text or "").casefold()
    if folded in {"", "not named"}:
        return False
    if not any(re.search(rf"\b{word}\b", folded) for word in _SUN):
        return False
    return not any(word in folded for word in _PRACTICAL)


def _temperature(text: str) -> str:
    match = _KELVIN.search(text or "")
    if not match:
        return "not named"
    return f"{match.group(1)}K"


def _ratio(text: str) -> str:
    match = _RATIO.search(text or "")
    if not match:
        return "not named"
    return re.sub(r"\s+", "", match.group(0))


def _prompt(time_of_day, sources, temperature, ratio, lines) -> str:
    parts = [
        _labeled("Time of day", time_of_day),
        _labeled("Key", sources["key"]),
        _labeled("Fill", sources["fill"]),
        _labeled("Practicals", sources["practicals"]),
        _labeled("Color temperature", temperature),
        _labeled("Contrast ratio", ratio),
    ]
    if lines and sources["key"] == "not named":
        parts.append("Lighting text: " + " ".join(lines))
    return " ".join(parts)


def _labeled(label: str, value: str) -> str:
    text = str(value).strip().rstrip(".")
    return f"{label}: {text}."


def _continuity(scene_id: str, time_of_day: str, shots: list[dict]) -> list[dict]:
    findings = []
    notes = {}
    for shot in shots:
        note = (shot.get("color_notes") or "").strip()
        if note:
            notes.setdefault(note, []).append(shot["shot_id"])
        conflict = _time_conflict(time_of_day, shot.get("text") or "")
        if conflict:
            findings.append(
                {
                    "shot_id": shot["shot_id"],
                    "detail": (
                        f"{scene_id} is {time_of_day}. {shot['shot_id']} says \"{conflict}\"."
                    ),
                }
            )
    if len(notes) > 1:
        listed = "; ".join(f"{ids[0]} says {note}" for note, ids in notes.items())
        findings.append(
            {
                "shot_id": shots[0]["shot_id"],
                "detail": f"Shots in {scene_id} do not share one lighting note. {listed}.",
            }
        )
    return findings


def _scene_family(time_of_day: str) -> str:
    text = str(time_of_day or "")
    if re.search(r"\b(pre[\s-]?dusk|dusk|sunset|evening)\b", text, re.I):
        return "dusk"
    if re.search(r"\b(dawn|sunrise)\b", text, re.I):
        return "dawn"
    if re.search(r"\bmorning\b", text, re.I):
        return "morning"
    if re.search(r"\b(night|midnight|nighttime)\b", text, re.I):
        return "night"
    if re.search(r"\b(afternoon|daytime|noon|day)\b", text, re.I):
        return "day"
    return ""


def _explicit_times(text: str) -> list[str]:
    found = []
    for pattern in _EXPLICIT_TIME:
        for match in pattern.finditer(text or ""):
            word = match.group(1).casefold()
            family = _TIME_FAMILIES.get(word, word)
            if family not in found:
                found.append(family)
    return found


def _time_conflict(time_of_day: str, text: str) -> str:
    """A different time of day, and only when the shot states one outright.

    "Fifteen minutes of day left" is remaining daylight. It is not a change
    from a pre-dusk heading. "At dawn" and "night falls" are statements.
    """
    scene = _scene_family(time_of_day)
    if not scene:
        return ""
    for family in _explicit_times(text):
        if family != scene:
            return family
    return ""


def _from_model(llm, offline, package, look) -> dict | None:
    if llm is None:
        return None
    drafted = try_model_json(
        llm,
        role="gaffer",
        purpose="plan",
        system=system_prompt(
            "You are the Gaffer. Rewrite the note only. Do not change the lighting plan. "
            "Return {\"note\": \"...\"}."
        ),
        user=source_blob(offline.get("note"), package, look),
    )
    if not drafted:
        return None
    text = drafted.get("note")
    if not isinstance(text, str) or not text.strip():
        return None
    document = dict(offline)
    document["note"] = text.strip()
    document["draft_method"] = "model"
    return document


def _markdown(document: dict) -> str:
    lines = ["# Lighting plan", "", document.get("note") or "", ""]
    for scene in document.get("scenes") or []:
        lines.append(f"## {scene['scene_id']}")
        lines.append("")
        lines.append(scene["prompt_note"])
        lines.append("")
        verdict = scene["continuity"]["verdict"]
        lines.append(f"Continuity: {verdict}.")
        for finding in scene["continuity"]["findings"]:
            lines.append(f"- {finding['detail']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
