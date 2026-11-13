"""Storyboards and an animatic plan from the approved treatment.

Each shot is one beat of the scene. The look is stated once. A locked prop
is named only on a shot whose beat already puts that prop in frame.

An animatic is the boards in order, with a duration on each one. Image
generation runs only when a caller passes a client.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from movie_swarm.handoff import write_handoff
from movie_swarm.mentions import (
    action_continues,
    advertising_phrases,
    character_aliases,
    character_catalog,
    character_prompt_line,
    faithful_spec,
    load_kind_nouns,
    prop_mentioned,
    resolve_scene_characters,
    story_purpose_line,
)
from movie_swarm.prep_inputs import mark_superseded_shot_list
from movie_swarm.previs_common import approved_treatment, model_name, now, read_brief, save_pair
from movie_swarm.costume import load_locked as load_costumes
from movie_swarm.makeup import load_locked as load_makeup
from movie_swarm.prop_master import locked_path
from movie_swarm.script_intake import load_source


# A shot shorter than this, or longer, is padding unless the screenplay names a hold.
DEFAULT_MIN_SHOT_SECONDS = 1.0
DEFAULT_MAX_SHOT_SECONDS = 12.0


_SHOT_WORDS = (
    ("extreme wide", "extreme-wide"),
    ("extreme close", "extreme-close"),
    ("medium close", "medium-close"),
    ("medium wide", "medium-wide"),
    ("medium tracking", "tracking"),
    ("low angle", "low-angle"),
    ("high angle", "high-angle"),
    ("over the shoulder", "over-shoulder"),
    ("detail shot", "detail"),
    ("wide shot", "wide"),
    ("tracking", "tracking"),
    ("detail", "detail"),
    ("pov", "pov"),
    ("close", "close"),
    ("wide", "wide"),
)

_MOVE = {
    "extreme-wide": "static",
    "wide": "static",
    "tracking": "moves with the subject",
    "detail": "static",
    "close": "slow push-in",
    "extreme-close": "static",
    "medium-close": "slow push-in",
    "medium": "static",
    "medium-wide": "static",
    "low-angle": "static",
    "high-angle": "static",
    "pov": "static",
    "over-shoulder": "static",
}

_FRAMING = {
    "extreme-wide": "The place fills the frame. A person, if any, is small.",
    "wide": "The person and the place share the frame.",
    "medium-wide": "The person is clear, with the place still visible.",
    "medium": "The person is clear, with room around them.",
    "medium-close": "Head and shoulders.",
    "tracking": "The subject stays in frame while the ground moves.",
    "detail": "One object fills the frame.",
    "close": "The face, or the one object that matters, fills the frame.",
    "extreme-close": "A fragment of the face or the object.",
    "low-angle": "The camera is near the ground.",
    "high-angle": "The camera looks down.",
    "pov": "We see what the character sees.",
    "over-shoulder": "Past the near shoulder, toward what they face.",
}


def _existing_board(production_dir: Path) -> dict:
    path = storyboard_path(production_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def storyboard_path(production_dir: Path) -> Path:
    return production_dir / "storyboard" / "storyboard.json"


def shot_list_path(production_dir: Path) -> Path:
    return production_dir / "storyboard" / "shot-list.json"


def build_boards(production_dir: Path, llm=None, image_client=None) -> dict:
    production_dir = Path(production_dir)
    treatment = approved_treatment(production_dir)
    brief = read_brief(production_dir)
    package = _package(production_dir)
    props = _props(production_dir)
    character_locks = [lock for lock in (load_costumes(production_dir), load_makeup(production_dir)) if lock]
    featured = brief.get("featured_product") if isinstance(brief.get("featured_product"), dict) else None
    script_scenes = _script_scenes(production_dir, brief)
    model = model_name("cinematographer", "boards")
    minimum, maximum = _shot_limits(production_dir)
    kind_nouns = load_kind_nouns(production_dir)
    shots, frames, placements, pacing, tag_notes = _frames(
        treatment,
        package,
        props,
        character_locks,
        featured,
        script_scenes,
        image_client,
        minimum,
        maximum,
        kind_nouns,
    )
    created = now()
    shot_list = {
        "production_id": production_dir.name,
        "version": "1.0.0",
        "total_shots": len(shots),
        "shots": shots,
        "created_at": created,
    }
    write_handoff(shot_list_path(production_dir), shot_list, schema="shot-list")
    mark_superseded_shot_list(production_dir)
    total = round(sum(frame["duration_seconds"] for frame in frames), 3)
    prior = _existing_board(production_dir)
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "shot_list_path": "storyboard/shot-list.json",
        "look": _look_block(package),
        "featured_placements": placements,
        "tag_notes": tag_notes,
        "pacing": pacing,
        "frames": frames,
        "animatic": {
            "total_duration_seconds": total,
            "order": [frame["shot_id"] for frame in frames],
            "note": "Play the boards in this order. Each duration belongs to that beat.",
        },
        "image_generation": "fake-client" if image_client is not None else "not-run",
        "draft_method": "offline-deterministic",
        "model": model,
        "created_at": created,
    }
    if prior.get("status") == "approved" and isinstance(prior.get("approval"), dict):
        document["status"] = "approved"
        document["approval"] = prior["approval"]
    if llm is not None:
        document["animatic"]["note"] += (
            " A model was available. The beats stayed offline so a shot cannot be copied from its neighbor."
        )
    save_pair(storyboard_path(production_dir), document, "storyboard", _markdown(document, treatment))
    return document


def _package(production_dir: Path) -> dict:
    path = production_dir / "camera" / "camera-package.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _props(production_dir: Path) -> list[dict]:
    if not locked_path(production_dir).is_file():
        return []
    try:
        data = json.loads(locked_path(production_dir).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return list(data.get("props") or [])


def _script_scenes(production_dir: Path, brief: dict) -> list[dict]:
    relative = brief.get("screenplay_path")
    if not relative:
        return []
    path = production_dir / str(relative)
    if not path.is_file():
        return []
    try:
        return list(load_source(path).scenes)
    except (OSError, ValueError):
        return []


def _frames(
    treatment,
    package,
    props,
    character_locks,
    featured,
    script_scenes,
    image_client,
    minimum,
    maximum,
    kind_nouns,
):
    shots = []
    frames = []
    placements = []
    pacing_notes = []
    scene_notes = []
    tag_notes = []
    order = 1
    scenes = treatment.get("scenes") or []
    plan = str(treatment.get("color_and_light_plan") or "")
    used_script = set()
    catalog = character_catalog(treatment, character_locks)
    for index, scene in enumerate(scenes, start=1):
        scene_id = str(scene.get("scene_id") or f"s{index:02d}")
        source = _scene_text(scene, script_scenes, used_script)
        beats = _beats(source, str(scene.get("coverage_intent") or ""))
        durations, budget, held = _durations(beats, scene.get("approximate_duration_seconds"))
        shot_ids = [f"{_scene_slug(scene_id, index)}-sh{number:02d}" for number in range(1, len(beats) + 1)]
        durations, notes = _pace(shot_ids, durations, held, budget, minimum, maximum)
        pacing_notes.extend(notes)
        scene_notes.append((scene_id, budget, round(sum(durations), 3)))
        light = _scene_light(plan, index)
        heading = str(scene.get("heading") or "")
        actions = [beat["text"] for beat in beats]
        resolved_people = resolve_scene_characters(actions, catalog, heading)
        resolved_props = _props_for_scene(actions, props, kind_nouns)
        for shot_number, beat in enumerate(beats, start=1):
            shot_id = shot_ids[shot_number - 1]
            shot_type = beat["shot_type"]
            action = _finish(beat["text"])
            shown = f"{heading} {action}"
            people_row = resolved_people[shot_number - 1]
            prop_row = resolved_props[shot_number - 1]
            people = people_row["names"]
            in_frame = prop_row["props"]
            if people_row["inherited"] and people:
                tag_notes.append(
                    {
                        "shot_id": shot_id,
                        "kind": "inherited-character",
                        "detail": (
                            f"Pronouns in this shot use {people[0]}. "
                            "One locked character is in the scene, so the shot was not left blank."
                        ),
                    }
                )
            if people_row["review"]:
                tag_notes.append(
                    {"shot_id": shot_id, "kind": "needs-review", "detail": people_row["review"]}
                )
            if prop_row["carried"]:
                carried_name = prop_row["props"][0]["name"] if prop_row["props"] else "the prop"
                tag_notes.append(
                    {
                        "shot_id": shot_id,
                        "kind": "carried-prop",
                        "detail": (
                            f"Carried {carried_name} from the previous shot in {scene_id}. "
                            "The action continues and this shot does not name a different prop."
                        ),
                    }
                )
            if prop_row["review"]:
                tag_notes.append(
                    {"shot_id": shot_id, "kind": "needs-review", "detail": prop_row["review"]}
                )
            if featured and _mentions_product(action, featured) and _wants_legible(featured):
                if shot_type not in {"detail", "close", "extreme-close", "medium-close"}:
                    shot_type = "close"
            duration = durations[shot_number - 1]
            transition_in = "fade-in" if order == 1 else "cut"
            if re.search(r"\bhard cut\b", action, re.I):
                transition_out = "cut"
            else:
                transition_out = "hold" if beat.get("hold_out") else "cut"
            lens = _lens_for(package, shot_type)
            camera = _camera_line(shot_type, lens, light)
            spec_line = _spec_line(in_frame, action)
            character_line = _character_line(people, character_locks, f"{action} {spec_line}")
            prompt = _prompt(action, camera, " ".join(part for part in (spec_line, character_line) if part))
            if featured and _mentions_product(action, featured):
                why = _placement_why(featured, action, shot_type)
                placements.append({"shot_id": shot_id, "product": featured["product"], "why": why})
                focus = _detail_focus(featured, in_frame)
                if focus and shot_type in {"close", "extreme-close", "detail", "medium-close"}:
                    if focus.casefold() not in camera.casefold():
                        camera = f"{camera} {focus}"
                    prompt = _prompt(action, camera, " ".join(part for part in (spec_line, character_line) if part))
            images = _reference_images(in_frame)
            note = _frame_note(in_frame, character_line)
            shot = {
                "shot_id": shot_id,
                "scene_number": _scene_number(scene_id, index),
                "shot_number": shot_number,
                "sequence_position": order,
                "shot_type": shot_type,
                "description": action,
                "camera_movement": _MOVE.get(shot_type, "static"),
                "framing_notes": _FRAMING.get(shot_type, "The subject of this beat."),
                "generation_prompt": prompt,
                "negative_prompt": _negative(in_frame, people, character_locks, shown),
                "tool_routing": {
                    "primary_tool": "veo-3.1-lite",
                    "rationale": "Storyboard pass. A prompt for this beat, not a finished picture.",
                    "iteration_first": True,
                    "requires_native_audio": False,
                },
                "target_duration_seconds": duration,
                "transition_in": transition_in,
                "transition_out": transition_out,
                "continuity_notes": note,
                "color_notes": light or "Light stays with the package.",
            }
            if people:
                shot["characters_in_shot"] = people
            prop_refs, vehicle_refs = _shot_refs(in_frame)
            if prop_refs:
                shot["props_in_shot"] = prop_refs
            if vehicle_refs:
                shot["vehicles_in_shot"] = vehicle_refs
            if images:
                shot["reference_images"] = images
                assets = _reference_assets(in_frame)
                if assets:
                    shot["reference_assets"] = assets
            shots.append(shot)
            image_ref = None
            image_status = "not-generated"
            if image_client is not None:
                image_ref = str(image_client.generate(prompt))
                image_status = "fake-client"
            frame = {
                "order": order,
                "shot_id": shot_id,
                "scene_id": scene_id,
                "shot_type": shot_type,
                "what_we_see": action,
                "camera": camera,
                "transition": f"{transition_in} / {transition_out}",
                "props_in_frame": [
                    item["name"] + (f" — {item['line']}" if item.get("line") else "") for item in in_frame
                ],
                "board_prompt": prompt,
                "duration_seconds": duration,
                "image_status": image_status,
                "image_ref": image_ref,
            }
            if images:
                frame["reference_images"] = images
            frames.append(frame)
            order += 1
    if not frames:
        raise ValueError("The approved treatment has no scenes to board.")
    pacing = _pacing_report(minimum, maximum, pacing_notes, scene_notes, treatment)
    return shots, frames, placements, pacing, tag_notes


def _scene_text(scene: dict, script_scenes: list[dict], used: set[int]) -> str:
    """Use the next unused screenplay scene with the same heading.

    Two treatment scenes can share a heading. The first match must not be reused.
    """
    heading = _norm(str(scene.get("heading") or ""))
    for index, item in enumerate(script_scenes):
        if index in used:
            continue
        other = _norm(str(item.get("heading") or ""))
        if heading and other and (heading in other or other in heading):
            body = str(item.get("body") or "").strip()
            if body:
                used.add(index)
                return body
    return str(scene.get("what_happens") or "")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _beats(text: str, coverage: str) -> list[dict]:
    paragraphs = _paragraphs(text)
    if len(paragraphs) <= 1:
        paragraphs = _split_sentences(paragraphs[0] if paragraphs else text)
    if not paragraphs:
        paragraphs = ["The scene does not say what happens."]
    raw = []
    for paragraph in paragraphs:
        if _is_hold_note(paragraph) and raw:
            raw[-1] = (raw[-1] + " " + paragraph).strip()
            continue
        cleaned = re.sub(r"^(cut to\s+(a|an)?\s*)", "", paragraph, flags=re.I).strip()
        if cleaned:
            raw.append(cleaned)
    found_types = []
    for paragraph in raw:
        found = _type_in_text(paragraph)
        if not found and re.search(r"\b(face|eyes)\b", paragraph[:80], re.I):
            found = "close"
        if not found and "of the frame" in paragraph.casefold():
            found = "extreme-wide"
        found_types.append(found)
    fallback = _shot_types(coverage)
    use_coverage = not any(found_types)
    beats = []
    for index, paragraph in enumerate(raw):
        if found_types[index]:
            shot_type = found_types[index]
        elif use_coverage and index < len(fallback):
            shot_type = fallback[index]
        else:
            shot_type = "medium"
        beats.append({
            "text": _tidy(paragraph),
            "shot_type": shot_type,
            "hold_out": bool(re.search(r"\bhold\b", paragraph, re.I)),
        })
    return beats or [{"text": "The scene does not say what happens.", "shot_type": "wide", "hold_out": False}]


def _paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", text)
    kept = []
    for chunk in chunks:
        lines = []
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped or stripped in {"---", "***"}:
                continue
            if stripped.startswith("*[") or stripped.startswith("["):
                seconds = _explicit_seconds(stripped)
                if seconds and kept and "visibility" in stripped.casefold():
                    unit = "second" if seconds == 1 else "seconds"
                    kept[-1] = kept[-1] + f" Hold for {seconds:g} {unit}."
                continue
            upper = stripped.upper().rstrip(".")
            if upper in {"FADE IN", "CUT TO", "CUT TO:"} or upper.startswith("TITLE CARD"):
                continue
            if stripped.startswith("#") or stripped.startswith("*("):
                continue
            if re.fullmatch(r"\*\*[^*]+\*\*", stripped):
                continue
            lines.append(stripped.strip("*").strip())
        if lines:
            kept.append(_tidy(" ".join(lines)))
    return kept


def _split_sentences(text: str) -> list[str]:
    """Split a single block into beats. Short sentences stay with a neighbor."""
    cleaned = text.replace("…", ". ").replace("---", " ")
    parts = [_tidy(part) for part in re.split(r"(?<=[.!?])\s+", cleaned) if _tidy(part)]
    beats = []
    bucket = ""
    for part in parts:
        if not bucket:
            bucket = part
            continue
        if len(bucket.split()) >= 6 and len(part.split()) >= 6:
            beats.append(bucket)
            bucket = part
        else:
            bucket = f"{bucket} {part}".strip()
    if bucket:
        beats.append(bucket)
    return beats


def _is_hold_note(text: str) -> bool:
    return bool(re.match(r"^(hold|then:)\b", text.strip(), re.I))


def _type_in_text(text: str) -> str | None:
    head = text[:80].casefold()
    for phrase, shot_type in _SHOT_WORDS:
        if phrase in head:
            return shot_type
    return None


def _shot_types(coverage: str) -> list[str]:
    lowered = coverage.casefold()
    found = []
    cursor = lowered
    while cursor:
        matched = False
        for phrase, shot_type in _SHOT_WORDS:
            if phrase in cursor:
                if shot_type not in found:
                    found.append(shot_type)
                cursor = cursor.replace(phrase, " ", 1)
                matched = True
                break
        if not matched:
            break
    return found


def _durations(beats: list[dict], scene_seconds) -> tuple[list[float], float, list[bool]]:
    try:
        budget = float(scene_seconds)
    except (TypeError, ValueError):
        budget = 0.0
    explicit = [_explicit_seconds(beat["text"]) for beat in beats]
    # A named length stays put. The word "hold" by itself only sets the transition.
    held = [value is not None for value in explicit]
    named = [value for value in explicit if value]
    if budget <= 0:
        budget = sum(named) + (3.0 * (len(beats) - len(named)) or 4.0)
    remainder = max(budget - sum(named), 0.0)
    weights = [max(len(beat["text"].split()), 1) for beat, value in zip(beats, explicit) if not value]
    weight_sum = sum(weights) or 1
    durations = []
    weight_index = 0
    for value in explicit:
        if value:
            durations.append(round(max(value, 0.5), 3))
            continue
        share = remainder * (weights[weight_index] / weight_sum) if remainder else 3.0
        weight_index += 1
        durations.append(round(max(share, 0.5), 3))
    return durations, round(budget, 3), held


def _shot_limits(production_dir: Path) -> tuple[float, float]:
    """Minimum and maximum shot length. A production file can set both."""
    path = Path(production_dir) / "storyboard" / "pacing-limits.json"
    data = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            data = loaded

    def number(key: str, default: float) -> float:
        try:
            value = float(data.get(key, default))
        except (TypeError, ValueError):
            return default
        if value <= 0:
            return default
        return value

    minimum = number("min_shot_seconds", DEFAULT_MIN_SHOT_SECONDS)
    maximum = number("max_shot_seconds", DEFAULT_MAX_SHOT_SECONDS)
    if maximum < minimum:
        return DEFAULT_MIN_SHOT_SECONDS, DEFAULT_MAX_SHOT_SECONDS
    return minimum, maximum


def _pace(shot_ids, durations, held, budget, minimum, maximum):
    """Clamp unlocked shots, then move time so the scene still hits its target."""
    original = [float(value) for value in durations]
    current = []
    for duration, locked in zip(original, held):
        if locked:
            current.append(duration)
        else:
            current.append(min(maximum, max(minimum, duration)))
    current = _redistribute(current, held, budget, minimum, maximum)
    notes = []
    for shot_id, before, after, locked in zip(shot_ids, original, current, held):
        if locked and (after < minimum or after > maximum):
            notes.append(f"{shot_id} stays {after:g}s because the screenplay names a hold.")
        elif not locked and abs(after - before) >= 0.05:
            notes.append(
                f"{shot_id} was {before:g}s and is {after:g}s "
                f"so the shot stays between {minimum:g}s and {maximum:g}s."
            )
    return current, notes


def _millis(value: float) -> int:
    return int(round(float(value) * 1000))


def _redistribute(current, held, budget, minimum, maximum):
    """Move leftover time onto shots that still have room inside the limits.

    Work in milliseconds so a rounding leftover is not dropped when the last
    shot cannot take the whole remainder.
    """
    current = [_millis(value) for value in current]
    budget_ms = _millis(budget)
    minimum_ms = _millis(minimum)
    maximum_ms = _millis(maximum)
    for _ in range(len(current) + 4):
        delta = budget_ms - sum(current)
        if delta == 0:
            break
        if delta > 0:
            room = [index for index, locked in enumerate(held) if not locked and current[index] < maximum_ms]
            capacity = sum(maximum_ms - current[index] for index in room)
        else:
            room = [index for index, locked in enumerate(held) if not locked and current[index] > minimum_ms]
            capacity = sum(current[index] - minimum_ms for index in room)
        if not room or capacity <= 0:
            break
        step = min(abs(delta), capacity)
        assigned = 0
        for position, index in enumerate(room):
            if delta > 0:
                space = maximum_ms - current[index]
            else:
                space = current[index] - minimum_ms
            if position == len(room) - 1:
                give = step - assigned
            else:
                give = int(step * (space / capacity))
            give = max(0, min(give, space, step - assigned))
            if delta > 0:
                current[index] += give
            else:
                current[index] -= give
            assigned += give
        left = step - assigned
        for index in room:
            if left <= 0:
                break
            if delta > 0:
                space = maximum_ms - current[index]
                give = min(space, left)
                current[index] += give
            else:
                space = current[index] - minimum_ms
                give = min(space, left)
                current[index] -= give
            left -= give
    return [round(value / 1000, 3) for value in current]


def _pacing_report(minimum, maximum, notes, scene_notes, treatment) -> dict:
    sentences = [
        f"Shot lengths stay between {minimum:g}s and {maximum:g}s unless the screenplay names a hold."
    ]
    for scene_id, target, total in scene_notes:
        if abs(total - target) >= 0.05:
            sentences.append(
                f"Scene {scene_id} targets {target:g}s and the boards total {total:g}s. "
                "The shot limits left no room to place the remainder."
            )
        else:
            sentences.append(f"Scene {scene_id} targets {target:g}s and the boards total {total:g}s.")
    runtime = _runtime_seconds(treatment)
    boarded = round(sum(total for _, _, total in scene_notes), 3)
    targets = round(sum(target for _, target, _ in scene_notes), 3)
    if abs(boarded - targets) >= 0.05:
        sentences.append(
            f"The scene targets add up to {targets:g}s and the boards total {boarded:g}s."
        )
    if runtime is not None:
        if abs(runtime - boarded) < 0.05:
            sentences.append(
                f"The deliverable names {runtime:g}s. The boards total {boarded:g}s, within rounding."
            )
        else:
            sentences.append(
                f"The deliverable names {runtime:g}s. The boards total {boarded:g}s."
            )
    return {
        "minimum_seconds": minimum,
        "maximum_seconds": maximum,
        "adjustments": notes,
        "note": " ".join(sentences),
    }


def _runtime_seconds(treatment: dict) -> float | None:
    text = str((treatment.get("deliverables") or {}).get("length") or "")
    minutes = re.search(r"(\d+(?:\.\d+)?)\s*minutes?", text, re.I)
    if minutes:
        return float(minutes.group(1)) * 60
    seconds = re.search(r"(\d+(?:\.\d+)?)\s*seconds?", text, re.I)
    if seconds:
        return float(seconds.group(1))
    return None


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _explicit_seconds(text: str) -> float | None:
    match = re.search(
        r"(?:for|visibility:?)\s*(\d+(?:\.\d+)?)\s*(?:full\s+)?seconds?",
        text,
        re.I,
    )
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)\s+full\s+seconds?", text, re.I)
    if match:
        return float(match.group(1))
    word = re.search(
        r"(?:for\s+)?(" + "|".join(_NUMBER_WORDS) + r")\s+(?:full\s+)?seconds?",
        text,
        re.I,
    )
    if word:
        return float(_NUMBER_WORDS[word.group(1).casefold()])
    return None


def _scene_light(plan: str, index: int) -> str:
    match = re.search(
        rf"Scene\s+{index}\s*:\s*(.+?)(?=Scene\s+\d+\s*:|$)",
        plan,
        re.I | re.S,
    )
    if not match:
        return ""
    return _finish(_tidy(match.group(1).strip(" *")))


def _lens_for(package: dict, shot_type: str) -> dict | None:
    lenses = package.get("lenses") or []
    if not lenses:
        return None
    wide = shot_type in {"extreme-wide", "wide", "medium-wide"}
    close = shot_type in {"close", "extreme-close", "detail", "medium-close"}
    for lens in lenses:
        blob = f"{lens.get('name', '')} {lens.get('use', '')}".casefold()
        if wide and "wide" in blob:
            return lens
        if close and any(word in blob for word in ("close", "tight", "long")):
            return lens
    return None


def _camera_line(shot_type: str, lens: dict | None, light: str) -> str:
    parts = []
    if lens and lens.get("name"):
        parts.append(f"Lens: {lens['name']}")
    parts.append("Move: " + _MOVE.get(shot_type, "static"))
    parts.append(_FRAMING.get(shot_type, "The subject of this beat."))
    if light:
        parts.append("Light: " + light)
    return " ".join(parts)


def _props_for_scene(actions: list[str], props: list[dict], kind_nouns: dict) -> list[dict]:
    """Tag props in each shot, then carry one prop when the action continues."""
    rows = []
    previous = []
    previous_text = ""
    for text in actions:
        direct = _props_for_beat(props, text, kind_nouns)
        carried = []
        review = ""
        if not direct and previous and action_continues(previous_text, text):
            if len(previous) == 1:
                item = previous[0]
                carried = [
                    {
                        "prop": item["prop"],
                        "name": item["name"],
                        "line": _missing_phrase(item["prop"], text),
                    }
                ]
            else:
                review = (
                    "The action may continue a prop from the previous shot, "
                    "but that shot has more than one. Needs review."
                )
        chosen = direct or carried
        rows.append({"props": chosen, "carried": bool(carried), "review": review})
        previous = chosen
        previous_text = text
    return rows


def _props_for_beat(props: list[dict], text: str, kind_nouns: dict | None = None) -> list[dict]:
    found = []
    for prop in props:
        if not prop_mentioned(prop, text, props, kind_nouns):
            continue
        missing = _missing_phrase(prop, text)
        found.append({"prop": prop, "name": prop.get("name") or "Prop", "line": missing})
    return found


def _spec_line(in_frame: list[dict], action: str) -> str:
    """Locked spec for each hero prop in frame, plus a sidedness phrase the action omitted.

    The spec is copied. A prompt does not add a fact the lock did not state.
    """
    parts = []
    for item in in_frame:
        spec = faithful_spec(str(item["prop"].get("locked_spec") or ""))
        if spec and spec.casefold() not in action.casefold() and spec not in parts:
            if spec[-1] not in ".!?":
                spec += "."
            parts.append(spec)
        missing = _missing_phrase(item["prop"], action + " " + " ".join(parts))
        if missing and missing not in parts:
            parts.append(missing)
    return " ".join(parts)


def _frame_note(in_frame: list[dict], character_line: str) -> str:
    """List the locks this frame actually shows. The same match that tagged the shot."""
    bits = []
    for item in in_frame:
        spec = faithful_spec(str(item["prop"].get("locked_spec") or ""))
        if spec and spec[-1] not in ".!?":
            spec += "."
        bits.append(f"{item['name']} is in this frame. {spec}".strip())
    if character_line:
        bits.append(character_line)
    if bits:
        return " ".join(bits)
    return "No locked prop is in this frame."


def _reference_images(in_frame: list[dict]) -> list[str]:
    images = []
    for item in in_frame:
        for path in item["prop"].get("reference_images") or []:
            text = str(path).strip()
            if text and text not in images:
                images.append(text)
    return images


def _reference_assets(in_frame: list[dict]) -> list[dict]:
    assets = []
    seen = set()
    for item in in_frame:
        prop_id = str(item["prop"].get("prop_id") or item["name"])
        for path in item["prop"].get("reference_images") or []:
            text = str(path).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            assets.append(
                {
                    "asset_type": "prop-ref",
                    "asset_id": prop_id,
                    "path": text,
                    "usage_note": "Locked prop reference for this frame.",
                }
            )
    return assets


def _missing_phrase(prop: dict, text: str) -> str:
    haystack = text.casefold()
    phrases = [
        phrase.strip()
        for attribute in prop.get("attributes") or []
        for phrase in attribute.get("required_phrases") or []
        if phrase.strip()
    ]
    if any(phrase.casefold() in haystack for phrase in phrases):
        return ""
    if not phrases:
        return ""
    return phrases[0].rstrip(".") + "."


def _prompt(action: str, camera: str, lock_line: str) -> str:
    parts = [action, camera]
    if lock_line:
        parts.append(lock_line)
    return " ".join(part for part in parts if part)


def _character_line(people: list[str], locks: list[dict], text: str) -> str:
    lines = []
    for lock in locks:
        for character in lock.get("characters") or []:
            if not isinstance(character, dict) or not _person_in_shot(character, people, text):
                continue
            missing = character_prompt_line(
                character,
                text,
                allow_key_facts="garment" in character,
            )
            if missing and missing not in lines:
                lines.append(missing)
    return " ".join(lines)


def _person_in_shot(character: dict, people: list[str], text: str) -> bool:
    names = character_aliases(character)
    if character.get("character_id"):
        names = [*names, str(character["character_id"])]
    folded_people = {person.casefold() for person in people}
    for name in names:
        if len(name) >= 2 and (name.casefold() in folded_people or mentioned(text, [name])):
            return True
    return False


def _negative(in_frame: list[dict], people: list[str] | None = None, locks: list[dict] | None = None, text: str = "") -> str:
    phrases = []
    for item in in_frame:
        for attribute in item["prop"].get("attributes") or []:
            for phrase in attribute.get("forbidden_phrases") or []:
                if phrase not in phrases:
                    phrases.append(phrase)
    for lock in locks or []:
        for character in lock.get("characters") or []:
            if not isinstance(character, dict) or not _person_in_shot(character, people or [], text):
                continue
            for attribute in character.get("attributes") or []:
                for phrase in attribute.get("forbidden_phrases") or []:
                    if phrase not in phrases:
                        phrases.append(phrase)
    if not phrases:
        return "Do not add a prop that this beat does not show."
    return "Do not show: " + "; ".join(phrases) + "."


def _mentions_product(text: str, featured: dict) -> bool:
    names = [str(featured.get("product") or "")]
    names.extend(str(name) for name in featured.get("also_known_as") or [])
    haystack = text.casefold()
    return any(len(name) >= 3 and name.casefold() in haystack for name in names)


def _placement_why(featured: dict, action: str, shot_type: str) -> str:
    """One plain sentence about the story. A brief line is kept only when it does not sell."""
    del shot_type
    haystack = action.casefold()
    best = None
    for moment in featured.get("moments") or []:
        if not isinstance(moment, dict):
            continue
        when = str(moment.get("when") or "").strip()
        why = str(moment.get("why") or "").strip()
        if len(when) >= 3 and when.casefold() in haystack and why:
            if best is None or len(when) > len(str(best.get("when") or "")):
                best = moment
    if best is not None and not advertising_phrases(str(best["why"])):
        return _finish(str(best["why"]))
    product = str(featured.get("product") or "").strip()
    return _finish(story_purpose_line(product))


def _detail_focus(featured: dict, in_frame: list[dict]) -> str:
    """A focus line when the brief asks the detail to be legible.

    A short sentence already on the lock is copied. Otherwise this is a camera
    instruction. It does not say the frame is or is not an advertisement.
    """
    if not _wants_legible(featured):
        return ""
    for item in in_frame:
        spec = faithful_spec(str(item["prop"].get("locked_spec") or ""))
        for sentence in re.split(r"(?<=[.!?])\s+", spec):
            if not re.search(r"\b(legible|readable)\b", sentence, re.I):
                continue
            if advertising_phrases(sentence):
                continue
            if len(sentence.split()) > 18:
                continue
            return _finish(sentence)
    return "The detail stays readable."


def _wants_legible(featured: dict) -> bool:
    blob = " ".join(featured.get("rules") or []).casefold()
    return "legible" in blob or "readable" in blob


def _shot_refs(in_frame: list[dict]) -> tuple[list[dict], list[str]]:
    prop_refs = []
    vehicles = []
    for item in in_frame:
        prop = item["prop"]
        if str(prop.get("kind") or "").casefold() == "vehicle":
            vehicles.append(prop["prop_id"])
        else:
            note = item["line"] or prop.get("name") or ""
            prop_refs.append({"prop_id": prop["prop_id"], "visibility_note": note})
    return prop_refs, vehicles


def _look_block(package: dict) -> dict:
    block = {
        "look_name": str(package.get("look_name") or "The treatment's look"),
        "summary": str(package.get("summary") or ""),
        "lenses": [_lens_line(lens) for lens in package.get("lenses") or []],
        "framing": [str(item.get("description") or "") for item in package.get("framing") or [] if item.get("description")],
        "lighting": [str(item.get("description") or "") for item in package.get("lighting") or [] if item.get("description")],
        "palette": [str(color) for color in package.get("palette") or []],
    }
    return block


def _lens_line(lens: dict) -> str:
    name = str(lens.get("name") or "Lens")
    if lens.get("focal_length"):
        name = f"{name} ({lens['focal_length']})"
    if lens.get("use"):
        return f"{name}: {lens['use']}"
    return name


def _finish(text: str) -> str:
    """Keep the whole line. End on a complete sentence. Never cut a word off."""
    cleaned = _tidy(text)
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _markdown(document: dict, treatment: dict) -> str:
    look = document.get("look") or {}
    lines = [
        "# Storyboard",
        "",
    ]
    if document.get("status") == "approved":
        note = str((document.get("approval") or {}).get("note") or "").strip()
        who = str((document.get("approval") or {}).get("by") or "Ron")
        lines.append(f"Status: approved by {who}.")
        if note:
            lines.append(note)
        lines.append("")
    lines.extend([
        "The look is stated once. Each shot below is one beat. It lists only its own frame.",
        "",
        f"## Look: {look.get('look_name') or 'Unnamed'}",
        "",
        look.get("summary") or "The production has not named a look.",
        "",
    ])
    if look.get("lenses"):
        lines.append("Lenses: " + "; ".join(look["lenses"]))
        lines.append("")
    if look.get("framing"):
        lines.append("Framing: " + " ".join(look["framing"]))
        lines.append("")
    if look.get("lighting"):
        lines.append("Lighting: " + " ".join(look["lighting"]))
        lines.append("")
    if look.get("palette"):
        lines.append("Palette: " + ", ".join(look["palette"]))
        lines.append("")
    lines.append(f"Images: {document['image_generation']}. Animatic: {document['animatic']['total_duration_seconds']} seconds.")
    lines.append("")
    pacing = document.get("pacing") or {}
    if pacing.get("note"):
        lines.append("## Shot lengths")
        lines.append("")
        lines.append(pacing["note"])
        lines.append("")
        for item in pacing.get("adjustments") or []:
            lines.append(f"- {item}")
        lines.append("")
    notes = document.get("tag_notes") or []
    if notes:
        lines.append("## Tags")
        lines.append("")
        for item in notes:
            lines.append(f"- {item['shot_id']}: {item['detail']}")
        lines.append("")
    placements = document.get("featured_placements") or []
    lines.append("## Hero prop moments")
    lines.append("")
    if not placements:
        lines.append("No shot names a hero prop from the brief.")
        lines.append("")
    else:
        for item in placements:
            lines.append(f"- {item['shot_id']} — {item['product']}: {item['why']}")
        lines.append("")
    scenes = {str(scene.get("scene_id") or f"s{index:02d}"): scene for index, scene in enumerate(treatment.get("scenes") or [], start=1)}
    current = None
    for frame in document["frames"]:
        if frame["scene_id"] != current:
            current = frame["scene_id"]
            scene = scenes.get(current) or {}
            lines.append(f"## {current}. {scene.get('heading') or 'Scene'}")
            lines.append("")
        props = ", ".join(frame.get("props_in_frame") or []) or "none"
        lines.extend([
            f"### {frame['order']}. {frame['shot_id']} — {frame.get('shot_type', '').replace('-', ' ')} — {frame['duration_seconds']}s — {frame.get('transition', 'cut')}",
            "",
            f"What we see: {frame.get('what_we_see') or frame['board_prompt']}",
            "",
            f"Camera: {frame.get('camera') or 'See the look.'}",
            "",
            f"Props in frame: {props}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _scene_slug(scene_id: str, index: int) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in scene_id.casefold()).strip("-")
    if cleaned and cleaned[0].isalpha():
        return cleaned
    return f"s{index:02d}"


def _scene_number(scene_id: str, index: int) -> int:
    digits = "".join(ch for ch in scene_id if ch.isdigit())
    if digits:
        return int(digits[:4])
    return index


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
