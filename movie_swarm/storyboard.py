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
    generic_nouns_for,
    has_personal_pronoun,
    joined_to_trace,
    load_absence_phrases,
    load_kind_nouns,
    mentioned,
    named_characters,
    named_phrase,
    no_visible_action,
    prop_frame_state,
    prop_labels,
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
    absence = load_absence_phrases(production_dir)
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
        absence,
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
    absence,
):
    shots = []
    frames = []
    placements = []
    tag_notes = []
    order = 1
    scenes = treatment.get("scenes") or []
    plan = str(treatment.get("color_and_light_plan") or "")
    used_script = set()
    catalog = character_catalog(treatment, character_locks)
    prepared = []
    for index, scene in enumerate(scenes, start=1):
        scene_id = str(scene.get("scene_id") or f"s{index:02d}")
        source = _scene_text(scene, script_scenes, used_script)
        beats = _beats(source, str(scene.get("coverage_intent") or ""))
        durations, budget, held = _durations(beats, scene.get("approximate_duration_seconds"))
        shot_ids = [f"{_scene_slug(scene_id, index)}-sh{number:02d}" for number in range(1, len(beats) + 1)]
        durations, notes = _pace(shot_ids, durations, held, budget, minimum, maximum)
        described = str(scene.get("what_happens") or "").strip()
        boarded = source.strip()
        scene_text = described if boarded == described else " ".join(part for part in (described, boarded) if part)
        prepared.append({
            "index": index,
            "scene_id": scene_id,
            "beats": beats,
            "durations": durations,
            "held": held,
            "budget": budget,
            "shot_ids": shot_ids,
            "notes": notes,
            "light": _scene_light(plan, index),
            "heading": str(scene.get("heading") or ""),
            "scene_text": scene_text,
        })
    _absorb_across_scenes(prepared, minimum, maximum)
    for item in prepared:
        index = item["index"]
        scene_id = item["scene_id"]
        beats = item["beats"]
        durations = item["durations"]
        shot_ids = item["shot_ids"]
        light = item["light"]
        heading = item["heading"]
        actions = [beat["text"] for beat in beats]
        shot_types = [beat["shot_type"] for beat in beats]
        resolved_people = resolve_scene_characters(actions, catalog, heading)
        resolved_props = _props_for_scene(actions, props, kind_nouns, shot_types, absence)
        _tag_vehicle_riders(
            actions,
            resolved_people,
            resolved_props,
            props,
            kind_nouns,
            catalog,
            item.get("scene_text") or "",
            absence,
        )
        for shot_number, beat in enumerate(beats, start=1):
            shot_id = shot_ids[shot_number - 1]
            shot_type = beat["shot_type"]
            action = _finish(beat["text"])
            shown = f"{heading} {action}"
            people_row = resolved_people[shot_number - 1]
            prop_row = resolved_props[shot_number - 1]
            people = people_row["names"]
            in_frame = prop_row["props"]
            if people_row.get("via") == "rider" and people:
                tag_notes.append(
                    {
                        "shot_id": shot_id,
                        "kind": "inherited-character",
                        "detail": (
                            f"{people[0]} rides the vehicle in this scene, "
                            "and the vehicle is in motion, so this shot includes them."
                        ),
                    }
                )
            elif people_row["inherited"] and people:
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
    pacing = _pacing_report(minimum, maximum, prepared, treatment)
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


def _absorb_across_scenes(prepared, minimum, maximum) -> None:
    """Place a scene's leftover time on shots in other scenes that still have room.

    Each scene stays as close to its own target as the limits allow. A shot
    whose length the screenplay named does not grow.
    """
    del minimum
    maximum_ms = _millis(maximum)
    for item in prepared:
        item["duration_ms"] = [_millis(value) for value in item["durations"]]
        item["target_ms"] = _millis(item["budget"])
        item["absorbed_ms"] = 0
        item["absorbed_from"] = []
        item["absorbed_by"] = []
        item["shortfall_ms"] = 0
        item["placed_elsewhere_ms"] = 0
        item["before_absorb"] = list(item["durations"])

    def total(item) -> int:
        return sum(item["duration_ms"])

    def capacity(item) -> int:
        room = 0
        for duration, locked in zip(item["duration_ms"], item["held"]):
            if not locked and duration < maximum_ms:
                room += maximum_ms - duration
        return room

    short = []
    for item in prepared:
        gap = item["target_ms"] - total(item)
        if gap >= 50:
            item["shortfall_ms"] = gap
            short.append(item)
    remaining = {id(item): item["shortfall_ms"] for item in short}
    need = sum(remaining.values())
    for _ in range(100000):
        if need < 1:
            break
        candidates = [item for item in prepared if capacity(item) > 0]
        if not candidates:
            break
        candidates.sort(key=lambda item: (total(item) - item["target_ms"], item["index"]))
        best = candidates[0]
        if len(candidates) == 1:
            give = min(need, capacity(best))
        else:
            nxt = candidates[1]
            until_tie = (total(nxt) - nxt["target_ms"]) - (total(best) - best["target_ms"])
            if until_tie <= 0:
                share = max(1, need // len(candidates))
                give = min(need, capacity(best), share)
            else:
                give = min(need, capacity(best), until_tie)
        poured = _pour(best, give, maximum_ms)
        if poured <= 0:
            break
        left = poured
        for item in short:
            if left <= 0:
                break
            slot = remaining[id(item)]
            if slot <= 0:
                continue
            take = min(slot, left)
            remaining[id(item)] -= take
            left -= take
            if item["scene_id"] not in best["absorbed_from"]:
                best["absorbed_from"].append(item["scene_id"])
            if best["scene_id"] not in item["absorbed_by"]:
                item["absorbed_by"].append(best["scene_id"])
        best["absorbed_ms"] += poured
        need -= poured
    for item in short:
        item["placed_elsewhere_ms"] = item["shortfall_ms"] - remaining[id(item)]
    for item in prepared:
        item["durations"] = [round(value / 1000, 3) for value in item["duration_ms"]]
        if not item["absorbed_ms"]:
            continue
        sources = _scene_phrase(item["absorbed_from"], lower=True)
        for shot_id, before, after in zip(item["shot_ids"], item["before_absorb"], item["durations"]):
            if abs(after - before) >= 0.05:
                item["notes"].append(
                    f"{shot_id} was {before:g}s and is {after:g}s "
                    f"so a remainder from {sources} could be placed."
                )


def _pour(item, give: int, maximum_ms: int) -> int:
    room = [
        index
        for index, (duration, locked) in enumerate(zip(item["duration_ms"], item["held"]))
        if not locked and duration < maximum_ms
    ]
    if not room or give <= 0:
        return 0
    capacity = sum(maximum_ms - item["duration_ms"][index] for index in room)
    step = min(int(give), capacity)
    assigned = 0
    for position, index in enumerate(room):
        space = maximum_ms - item["duration_ms"][index]
        if position == len(room) - 1:
            portion = step - assigned
        else:
            portion = int(step * (space / capacity)) if capacity else 0
        portion = max(0, min(portion, space, step - assigned))
        item["duration_ms"][index] += portion
        assigned += portion
    left = step - assigned
    for index in room:
        if left <= 0:
            break
        space = maximum_ms - item["duration_ms"][index]
        portion = min(space, left)
        item["duration_ms"][index] += portion
        left -= portion
    return step - left


def _scene_phrase(scene_ids: list[str], *, lower: bool = False) -> str:
    single = "scene" if lower else "Scene"
    plural = "scenes" if lower else "Scenes"
    if len(scene_ids) == 1:
        return f"{single} {scene_ids[0]}"
    if len(scene_ids) == 2:
        return f"{plural} {scene_ids[0]} and {scene_ids[1]}"
    if not scene_ids:
        return "another scene"
    head = ", ".join(scene_ids[:-1])
    return f"{plural} {head}, and {scene_ids[-1]}"


def _scene_pacing_sentences(item: dict) -> list[str]:
    scene_id = item["scene_id"]
    target = item["budget"]
    total = round(sum(item["durations"]), 3)
    placed = round(item.get("placed_elsewhere_ms", 0) / 1000, 3)
    absorbed = round(item.get("absorbed_ms", 0) / 1000, 3)
    if placed >= 0.05:
        who = _scene_phrase(item.get("absorbed_by") or [])
        still = round(item.get("shortfall_ms", 0) / 1000 - placed, 3)
        if still < 0.05:
            return [
                f"Scene {scene_id} targets {target:g}s and the boards total {total:g}s. "
                f"{who} absorbed the {placed:g}s this scene could not place."
            ]
        return [
            f"Scene {scene_id} targets {target:g}s and the boards total {total:g}s. "
            f"{who} absorbed {placed:g}s. "
            "The shot limits left no room to place the rest."
        ]
    if absorbed >= 0.05:
        sources = _scene_phrase(item.get("absorbed_from") or [], lower=True)
        return [
            f"Scene {scene_id} targets {target:g}s and the boards total {total:g}s. "
            f"It absorbed {absorbed:g}s from {sources} so the film total could hit its target."
        ]
    if abs(total - target) >= 0.05:
        return [
            f"Scene {scene_id} targets {target:g}s and the boards total {total:g}s. "
            "The shot limits left no room to place the remainder."
        ]
    return [f"Scene {scene_id} targets {target:g}s and the boards total {total:g}s."]


def _pacing_report(minimum, maximum, prepared, treatment) -> dict:
    notes = []
    for item in prepared:
        notes.extend(item.get("notes") or [])
    sentences = [
        f"Shot lengths stay between {minimum:g}s and {maximum:g}s unless the screenplay names a hold."
    ]
    for item in prepared:
        sentences.extend(_scene_pacing_sentences(item))
    runtime = _runtime_seconds(treatment)
    boarded = round(sum(sum(item["durations"]) for item in prepared), 3)
    targets = round(sum(item["budget"] for item in prepared), 3)
    if abs(boarded - targets) >= 0.05 or any(item.get("absorbed_ms") for item in prepared):
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


def _props_for_scene(
    actions: list[str],
    props: list[dict],
    kind_nouns: dict,
    shot_types: list[str] | None = None,
    absence: dict | None = None,
) -> list[dict]:
    """Tag props that are in frame, then carry one prop when the action continues.

    An absence phrase does not put the prop in frame, so the next shot has
    nothing to carry from it. A close view of some other object, a different
    subject, or a line with no picture does not inherit the previous prop.
    """
    rows = []
    previous = []
    previous_text = ""
    types = shot_types or ["medium"] * len(actions)
    for text, shot_type in zip(actions, types):
        direct, beat_review, blocked = _props_for_beat(props, text, kind_nouns, absence)
        available = [item for item in previous if _prop_key(item["prop"]) not in blocked]
        carried = []
        carry_review = ""
        if not direct and available and action_continues(previous_text, text):
            carried, carry_review = _carry_forward(
                text, shot_type, available, props, kind_nouns, absence
            )
        chosen = direct or carried
        review = " ".join(part for part in (beat_review, carry_review) if part)
        rows.append({"props": chosen, "carried": bool(carried), "review": review})
        previous = chosen
        previous_text = text
    return rows


def _props_for_beat(
    props: list[dict],
    text: str,
    kind_nouns: dict | None = None,
    absence: dict | None = None,
) -> tuple[list[dict], str, set[str]]:
    found = []
    reviews = []
    blocked = set()
    for prop in props:
        state = prop_frame_state(prop, text, props, kind_nouns, absence)
        if state == "unnamed":
            continue
        key = _prop_key(prop)
        if state == "absent":
            blocked.add(key)
            continue
        if state == "ambiguous":
            # The same prop_frame_state decision as the absence classifier.
            # A perfect-tense line with nothing after the object is "absent"
            # and does not reach this review.
            blocked.add(key)
            name = prop.get("name") or "A prop"
            reviews.append(
                f"{name} is named, and the phrase does not say whether that prop is in frame. Needs review."
            )
            continue
        missing = _missing_phrase(prop, text)
        found.append({"prop": prop, "name": prop.get("name") or "Prop", "line": missing})
    return found, " ".join(reviews), blocked


def _prop_key(prop: dict) -> str:
    return str(prop.get("prop_id") or prop.get("name") or "").casefold()


def _carry_forward(text, shot_type, available, props, kind_nouns, absence=None) -> tuple[list[dict], str]:
    """One continued prop, or a review, or nothing when the shot is about something else."""
    if no_visible_action(text):
        return [], (
            "This shot is sound, a fade, a hold, black, or a title, and it shows no visible action. "
            "A prop was not carried. Needs review."
        )
    blocks = [
        _carry_block(shot_type, text, item["prop"], props, kind_nouns, absence) for item in available
    ]
    open_items = [item for item, block in zip(available, blocks) if block == ""]
    unsure = [item for item, block in zip(available, blocks) if block == "review"]
    if len(open_items) == 1 and not unsure:
        item = open_items[0]
        return [
            {
                "prop": item["prop"],
                "name": item["name"],
                "line": _missing_phrase(item["prop"], text),
            }
        ], ""
    if len(open_items) > 1:
        return [], (
            "The action may continue a prop from the previous shot, "
            "but that shot has more than one. Needs review."
        )
    if unsure:
        return [], (
            "This close view does not name the prop from the previous shot. "
            "It was not carried. Needs review."
        )
    return [], ""


def _carry_block(shot_type: str, text: str, prop: dict, props: list[dict], kind_nouns: dict, absence=None) -> str:
    """'stop' when the shot is about something else, 'review' when a tight shot is unclear, else ''."""
    if _is_tight(shot_type, text) and not prop_mentioned(prop, text, props, kind_nouns, absence):
        if _other_object_words(text):
            return "stop"
        return "review"
    if _different_subject(text, prop, props, kind_nouns, absence):
        return "stop"
    return ""


_LEAD_SKIP = {
    "a",
    "an",
    "the",
    "close",
    "closer",
    "insert",
    "ecu",
    "detail",
    "extreme",
    "wide",
    "shot",
    "on",
    "of",
    "cut",
    "to",
    "again",
    "another",
    "still",
}

_OBJECT_SKIP = _LEAD_SKIP | {
    "and",
    "or",
    "but",
    "from",
    "with",
    "into",
    "onto",
    "over",
    "under",
    "for",
    "this",
    "that",
    "then",
    "than",
    "when",
    "while",
    "where",
    "camera",
    "frame",
    "lens",
    "hold",
    "holds",
    "fade",
    "fades",
    "fading",
    "silence",
    "silent",
    "black",
    "title",
    "titles",
    "credits",
    "credit",
    "nothing",
}

# Generic English. Not a film's vehicles or people.
_MOTION_WORDS = (
    "pass",
    "passes",
    "passing",
    "roll",
    "rolls",
    "rolling",
    "ride",
    "rides",
    "riding",
    "rode",
    "drive",
    "drives",
    "driving",
    "drove",
    "speed",
    "speeds",
    "speeding",
    "move",
    "moves",
    "moving",
    "approach",
    "approaches",
    "approaching",
    "race",
    "races",
    "racing",
    "cruise",
    "cruises",
    "cruising",
    "sweep",
    "sweeps",
    "sweeping",
    "roar",
    "roars",
    "roaring",
    "thunder",
    "thunders",
    "crest",
    "crests",
    "crested",
)

_RIDE_WORDS = (
    "ride",
    "rides",
    "riding",
    "rode",
    "drive",
    "drives",
    "driving",
    "drove",
    "mount",
    "mounts",
    "mounted",
    "mounting",
    "steer",
    "steers",
    "steering",
    "steered",
    "pedal",
    "pedals",
    "pedaling",
    "pedalling",
    "astride",
)


def _is_tight(shot_type: str, text: str) -> bool:
    if shot_type in {"close", "extreme-close", "detail"}:
        return True
    return bool(re.search(r"\b(insert|close-up|close up|extreme close|ecu)\b", text[:80], re.I))


def _content_words(text: str) -> list[str]:
    sentence = re.split(r"[.!?]", str(text).strip(), maxsplit=1)[0]
    words = re.findall(r"[A-Za-z']+", sentence)
    kept = []
    for word in words:
        if not kept and word.casefold() in _LEAD_SKIP:
            continue
        kept.append(word)
    return kept


def _different_subject(text: str, prop: dict, props: list[dict], kind_nouns: dict, absence=None) -> bool:
    words = _content_words(text)
    if not words or has_personal_pronoun(words[0]):
        return False
    if prop_mentioned(prop, " ".join(words[:4]), props, kind_nouns, absence):
        return False
    head = words[0].casefold()
    if len(head) < 3 or head in _OBJECT_SKIP:
        return False
    return True


def _other_object_words(text: str) -> list[str]:
    found = []
    for word in re.findall(r"[A-Za-z']+", text):
        folded = word.casefold()
        if folded in _OBJECT_SKIP or len(folded) < 3 or has_personal_pronoun(folded):
            continue
        verbish = folded.endswith("ing") or folded.endswith("ed") or (
            folded.endswith("s") and not folded.endswith("ss") and len(folded) > 3
        )
        if verbish:
            continue
        found.append(folded)
    return found


def _tag_vehicle_riders(
    actions, people_rows, prop_rows, props, kind_nouns, catalog, scene_text="", absence=None
) -> None:
    """When one person rides the vehicle that passes, tag that person.

    Ride and drive language can sit in an earlier shot or in the scene
    description. The passing shot itself may not name anyone. A shot-size
    line such as "LOW ANGLE." is not the subject. More than one rider, or
    none, is a review. A passing vehicle is never left untagged and unflagged.
    """
    vehicles = [prop for prop in props if str(prop.get("kind") or "").casefold() == "vehicle"]
    if not vehicles:
        return
    for text, people, prop_row in zip(actions, people_rows, prop_rows):
        if people.get("names") or has_personal_pronoun(text) or named_characters(text, catalog):
            continue
        moving = _moving_vehicles(text, prop_row, vehicles, props, kind_nouns, absence)
        if len(moving) == 1:
            riders = _riders_of(
                actions, people_rows, moving[0], props, kind_nouns, catalog, scene_text, absence
            )
            if len(riders) == 1:
                people["names"] = [riders[0]]
                people["inherited"] = True
                people["via"] = "rider"
            else:
                people["review"] = _append_review(
                    people.get("review") or "",
                    "A ridden vehicle is in motion and the rider is not one clear person. Needs review.",
                )
        elif _in_motion(text) and _subject_could_be_vehicle(text, vehicles, props, kind_nouns, absence):
            people["review"] = _append_review(
                people.get("review") or "",
                "A ridden vehicle is in motion and the rider is not one clear person. Needs review.",
            )


def _append_review(existing: str, detail: str) -> str:
    if not existing:
        return detail
    if detail in existing:
        return existing
    return f"{existing} {detail}"


def _in_motion(text: str) -> bool:
    return mentioned(text, list(_MOTION_WORDS))


def _moving_vehicles(text, prop_row, vehicles, props, kind_nouns, absence=None) -> list[dict]:
    if not _in_motion(text):
        return []
    tagged = {
        _prop_key(item["prop"])
        for item in prop_row.get("props") or []
        if str(item["prop"].get("kind") or "").casefold() == "vehicle"
    }
    moving = []
    for vehicle in vehicles:
        if tagged and _prop_key(vehicle) not in tagged:
            continue
        if not _subject_is_prop(text, vehicle, props, kind_nouns, absence):
            continue
        moving.append(vehicle)
    return moving


# A leading sentence that only names the camera. "LOW ANGLE." is not the subject.
_SHOT_LABEL = re.compile(
    r"^(?:cut\s+to\s+)?(?:a\s+|an\s+)?"
    r"(?:extreme|medium|med|low|high|wide|tight|close|detail|tracking|insert|ecu|pov|static|handheld)"
    r"(?:\s+(?:extreme|medium|med|low|high|wide|tight|close|detail|tracking|insert|ecu|pov|static|handheld|angle|shot|close-up|closeup|view))*"
    r"$",
    re.I,
)


def _picture_text(text: str) -> str:
    """Drop a leading shot-size sentence so the action can be the subject."""
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text).strip()) if part.strip()]
    kept = []
    skipping = True
    for part in parts:
        words = " ".join(re.findall(r"[A-Za-z0-9']+", part))
        if skipping and words and _SHOT_LABEL.match(words):
            continue
        skipping = False
        kept.append(part)
    return " ".join(kept) if kept else str(text).strip()


def _subject_words(text: str) -> list[str]:
    return _content_words(_picture_text(text))


def _subject_is_prop(text, prop, props, kind_nouns, absence=None) -> bool:
    words = _subject_words(text)
    if not words or has_personal_pronoun(words[0]):
        return False
    return prop_mentioned(prop, " ".join(words[:6]), props, kind_nouns, absence)


def _subject_could_be_vehicle(text, vehicles, props, kind_nouns, absence=None) -> bool:
    words = _subject_words(text)
    if not words or has_personal_pronoun(words[0]):
        return False
    phrase = " ".join(words[:6])
    for vehicle in vehicles:
        if prop_mentioned(vehicle, phrase, props, kind_nouns, absence):
            return True
    kind_words = list((kind_nouns or {}).get("vehicle") or [])
    if "vehicle" not in {word.casefold() for word in kind_words}:
        kind_words.append("vehicle")
    return named_phrase(phrase, kind_words, absence)


def _riders_of(actions, people_rows, vehicle, props, kind_nouns, catalog, scene_text="", absence=None) -> list[str]:
    found = []

    def add(names) -> None:
        for name in names:
            if name and name not in found:
                found.append(name)

    for text, people in zip(actions, people_rows):
        add(_people_riding(text, vehicle, props, kind_nouns, catalog, people.get("names") or [], absence))
    if scene_text:
        named = []
        for row in people_rows:
            for name in row.get("names") or []:
                if name not in named:
                    named.append(name)
        add(
            _people_riding(
                scene_text,
                vehicle,
                props,
                kind_nouns,
                catalog,
                named if len(named) == 1 else [],
                absence,
            )
        )
    return found


def _people_riding(text, vehicle, props, kind_nouns, catalog, resolved=None, absence=None) -> list[str]:
    """People tied to this vehicle by a ride word or by "on a vehicle".

    The name and the ride can sit in different sentences of the same passage.
    A pronoun uses the one person already resolved for that passage.
    """
    if not _ride_relation(text, vehicle, props, kind_nouns, absence):
        return []
    resolved = [name for name in (resolved or []) if name]
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text).strip()) if part.strip()]
    if not sentences:
        sentences = [str(text).strip()]
    found = []
    for sentence in sentences:
        if not _ride_relation(sentence, vehicle, props, kind_nouns, absence):
            continue
        names = named_characters(sentence, catalog)
        if not names and len(resolved) == 1 and has_personal_pronoun(sentence):
            names = resolved
        for name in names:
            if name not in found:
                found.append(name)
    if found:
        return found
    pool = resolved or named_characters(text, catalog)
    if len(pool) == 1:
        return list(pool)
    return []


def _ride_relation(text, vehicle, props, kind_nouns, absence=None) -> bool:
    if not prop_mentioned(vehicle, text, props, kind_nouns, absence):
        return False
    if mentioned(text, list(_RIDE_WORDS)):
        return True
    labels = prop_labels(vehicle)
    for noun in generic_nouns_for(vehicle, props, kind_nouns):
        if noun.casefold() not in {item.casefold() for item in labels}:
            labels.append(noun)
    for label in labels:
        flexible = re.escape(" ".join(str(label).split())).replace(r"\ ", r"[\s-]+")
        # A year or a short modifier may sit between "a" and the vehicle name.
        pattern = (
            rf"\bon\s+(?:(?:the|his|her|their|a|an)\s+)?(?:[\w']+\s+){{0,3}}?{flexible}\b"
        )
        for found in re.finditer(pattern, text, re.I):
            if not joined_to_trace(text, found.end(), absence):
                return True
    return False


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
    """True when this lock is a person already resolved for the shot, or the shot names them.

    ``people`` comes from ``resolve_scene_characters``, so a pronoun that
    inherited one locked character is already a name. A name written in the
    shot uses the same word-boundary match as the catalog. Props use
    ``prop_mentioned`` instead, which also accepts a kind noun.
    """
    names = [name for name in character_aliases(character) if len(name) >= 2]
    character_id = str(character.get("character_id") or "").strip()
    if len(character_id) >= 2 and character_id.casefold() not in {name.casefold() for name in names}:
        names.append(character_id)
    folded_people = {person.casefold() for person in people}
    if any(name.casefold() in folded_people for name in names):
        return True
    return mentioned(text, names)


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
