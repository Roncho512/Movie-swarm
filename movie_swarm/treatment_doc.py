"""Build, check, and render a treatment.

The offline path fills a valid draft from the screenplay and the production
brief. It does not call a model. A model draft, when one is used, is checked
against the same schema. Status stays ``draft`` until the Line Producer
records Ron's approval.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.money import as_money, money_number
from movie_swarm.paths import repo_root
from movie_swarm.script_intake import ParsedSource
from movie_swarm.validate import load_schema, validate_data


SKILL_FILES = (
    "agents/02-screenwriter/skill.md",
    "agents/03-art-director/skill.md",
)

# Dollars for a $500 film. The last entry keeps the sum exact when the cap changes.
_SPLIT_WEIGHTS = (
    ("director", 20),
    ("line-producer", 5),
    ("screenwriter", 5),
    ("art-director", 25),
    ("cinematographer", 10),
    ("production", 270),
    ("sound-designer", 55),
    ("editor", 15),
    ("qa", 45),
    ("fix-loop", 50),
    ("treatment", 0),
)

_QUESTION_ORDER = (
    "intent",
    "tone",
    "references",
    "character-arcs",
    "withheld",
    "action-beats",
    "hero-props",
    "budget-split",
)


def treatment_dir(production_dir: str | Path) -> Path:
    return Path(production_dir) / "treatment"


def treatment_json_path(production_dir: str | Path) -> Path:
    return treatment_dir(production_dir) / "treatment.json"


def treatment_markdown_path(production_dir: str | Path) -> Path:
    return treatment_dir(production_dir) / "treatment.md"


def questions_path(production_dir: str | Path) -> Path:
    return treatment_dir(production_dir) / "questions.json"


def skill_note() -> str:
    """Say whether the Screenwriter and Art Director skills were available to read."""
    missing = [rel for rel in SKILL_FILES if not (repo_root() / rel).is_file()]
    if missing:
        return "Skill files were missing: " + ", ".join(missing) + "."
    return (
        "Read the Screenwriter and Art Director skill files as context. "
        "Each scene is written so a later agent can work without the screenplay."
    )


def skill_excerpt() -> str:
    chunks = []
    for rel in SKILL_FILES:
        path = repo_root() / rel
        if path.is_file():
            chunks.append(f"--- {rel} ---\n{path.read_text(encoding='utf-8')[:3500]}")
    return "\n\n".join(chunks)


def proposed_split(cap_usd: float) -> dict[str, float]:
    """A full split of ``cap_usd``. At $500 the weights are used as written."""
    weights = dict(_SPLIT_WEIGHTS)
    total = sum(weights.values())
    cap = as_money(cap_usd)
    if cap == as_money(total):
        return {name: float(amount) for name, amount in _SPLIT_WEIGHTS}
    allocated = []
    running = as_money(0)
    names = list(weights)
    for name in names[:-1]:
        share = as_money(cap * as_money(weights[name]) / as_money(total))
        allocated.append((name, money_number(share)))
        running += share
    allocated.append((names[-1], money_number(cap - running)))
    return dict(allocated)


def parse_stage_split(text: str) -> dict[str, float] | None:
    """Read ``production=270, qa=45`` or a JSON object. Return None when it is not a split."""
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and data:
            try:
                return {str(key): money_number(value) for key, value in data.items()}
            except (TypeError, ValueError):
                return None
    pairs = re.findall(
        r"([a-z][a-z0-9-]*)\s*[=:]\s*\$?\s*(\d+(?:\.\d+)?)",
        stripped.lower(),
    )
    if len(pairs) < 1:
        return None
    if len(pairs) == 1 and not re.search(r"\d", stripped):
        return None
    # A single pair is only a split when the line is mostly that pair.
    if len(pairs) == 1 and len(stripped) > 40:
        return None
    return {name: money_number(amount) for name, amount in pairs}


def _plain_words(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.strip().lower())).strip()


def confirms_draft(text: str) -> bool:
    """Ron is keeping the draft, not replacing it. 'Lock.' and 'Lock it.' are a yes.

    The whole answer has to be the confirmation. A sentence that merely
    contains one of these words is a new instruction.
    """
    return _plain_words(strip_answer_lead_in(text)) in {
        "lock",
        "lock it",
        "lock them",
        "lock this",
        "locked",
        "yes",
        "y",
        "ok",
        "okay",
        "approved",
        "approve",
        "keep",
        "keep it",
        "looks right",
        "use the proposal",
        "yes those beats",
    }


def strip_answer_lead_in(text: str) -> str:
    """Drop a conversational prefix such as ``That's all:``.

    The words after the colon are the decision. The prefix is not part of
    the treatment.
    """
    cleaned = str(text or "").strip()
    match = re.match(
        r"(?i)^(?:that(?:'s|’s|s| is) all|that is all|note|answer)\s*:\s*",
        cleaned,
    )
    if not match:
        return cleaned
    return cleaned[match.end():].strip()


def note_locked(treatment: dict, label: str) -> None:
    """Say that Ron kept a drafted field. The field text stays as it was."""
    sentence = f"Locked the drafted {label}."
    note = treatment.get("draft_note") or ""
    if sentence in note:
        return
    treatment["draft_note"] = (note + " " + sentence).strip()


def approves_proposal(text: str) -> bool:
    """Ron is keeping the proposed dollar split. A reply that names new amounts is not this."""
    if parse_stage_split(text):
        return False
    cleaned = re.sub(r"[.!?]", "", text.strip().lower())
    if cleaned.startswith("approve") or "approve" in cleaned:
        return True
    return confirms_draft(text) or _plain_words(text) in {
        "looks good",
    }


def treatment_schema_instructions() -> str:
    """Required treatment keys and formats, read from the schema, for a model prompt."""
    schema = load_schema("treatment")
    properties = schema.get("properties") or {}
    required = [str(key) for key in schema.get("required") or []]
    lines = [
        "Required top-level keys: " + ", ".join(required) + ".",
        "Use these names. Do not rename them.",
    ]
    for key in required:
        lines.append(_schema_field_line(key, properties.get(key) or {}))
    lines.append(
        "theme and emotional_intent belong inside theme_and_emotional_intent. "
        "tone and genre belong inside tone_and_genre. "
        "Do not put those four names at the top level."
    )
    lines.append(
        "deliverables.aspect_ratio, deliverables.resolution, and deliverables.length "
        "are strings. Never null."
    )
    pattern = (properties.get("version") or {}).get("pattern")
    if pattern:
        lines.append(f"version matches {pattern}. A draft uses 0.1.0.")
    lines.append(
        "Do not raise open questions about items already locked in the creative inputs "
        "or the prop facts. Follow those locks. Do not re-ask them."
    )
    return "\n".join(lines)


def conform_treatment(data: dict, *, fallback: dict | None = None) -> dict:
    """Map common model names onto the schema, then drop keys the schema does not know.

    ``fallback`` is an offline draft or a brief-shaped treatment. Blank
    deliverable strings are filled from it. A version that is not semver
    becomes ``0.1.0``.
    """
    mapped = _map_treatment_aliases(dict(data))
    cleaned = _conform(mapped, load_schema("treatment"))
    _normalise_version(cleaned)
    _fill_blank_deliverables(cleaned, fallback)
    return cleaned


def merge_missing_required(drafted: dict, offline: dict) -> dict:
    """Fill required keys the model left blank. Keep every value the model did supply."""
    if not isinstance(drafted, dict):
        return drafted
    merged = copy.deepcopy(drafted)
    source = offline if isinstance(offline, dict) else {}
    schema = load_schema("treatment")
    properties = schema.get("properties") or {}
    for key in schema.get("required") or []:
        prop = properties.get(key) or {}
        backup = source.get(key)
        if prop.get("type") == "object":
            if not isinstance(merged.get(key), dict):
                if isinstance(backup, dict):
                    merged[key] = copy.deepcopy(backup)
                continue
            if isinstance(backup, dict):
                _fill_required_object(merged[key], backup, prop)
            continue
        if _blank_leaf(merged.get(key), prop) and not _blank_leaf(backup, prop):
            merged[key] = copy.deepcopy(backup)
    return merged


def force_draft(treatment: dict) -> dict:
    """The Director never writes an approval. Ron's yes is recorded by the Line Producer."""
    treatment["status"] = "draft"
    treatment["approval"] = {
        "state": "pending",
        "by": None,
        "at": None,
        "note": "The Director cannot approve. Ron approves through the Line Producer.",
    }
    if treatment.get("version") in (None, "", "1.0.0"):
        treatment["version"] = "0.1.0"
    return treatment


def ensure_treatment_markdown(production_dir: str | Path) -> Path | None:
    """Write treatment.md from treatment.json when the markdown is missing.

    This does not approve the gate and does not change the JSON. Intake already
    writes both files. A film that only has the JSON gets the readable copy
    before Ron is asked to approve.
    """
    json_path = treatment_json_path(production_dir)
    md_path = treatment_markdown_path(production_dir)
    if not json_path.is_file() or md_path.is_file():
        return md_path if md_path.is_file() else None
    try:
        document = load_treatment(production_dir)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(document), encoding="utf-8")
    except (OSError, KeyError, TypeError, HandoffError):
        return None
    return md_path


def write_treatment_files(production_dir: str | Path, treatment: dict) -> tuple[Path, Path]:
    """Check the treatment, write JSON, and write the readable Markdown beside it."""
    document = conform_treatment(treatment)
    json_path = treatment_json_path(production_dir)
    write_handoff(json_path, document, schema="treatment")
    md_path = treatment_markdown_path(production_dir)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(document), encoding="utf-8")
    return json_path, md_path


def write_questions(production_dir: str | Path, questions: dict) -> Path:
    path = questions_path(production_dir)
    return write_handoff(path, questions, schema="director-questions")


def load_treatment(production_dir: str | Path) -> dict:
    return read_handoff(treatment_json_path(production_dir), schema="treatment")


def load_questions(production_dir: str | Path) -> dict:
    return read_handoff(questions_path(production_dir), schema="director-questions")


def draft_offline(
    *,
    production_id: str,
    script: ParsedSource | None,
    brief: dict | None,
    cap_usd: float,
) -> dict:
    """A valid draft from the files on disk. No model call."""
    script_text = script.text if script else ""
    title = _first(
        (brief or {}).get("title"),
        script.title if script else "",
        production_id,
    )
    logline = _logline(script_text, brief)
    theme, intent = _theme_and_intent(script_text, brief)
    tone, genre = _tone_and_genre(brief, script_text)
    characters = _characters(script_text, brief)
    scenes = _scenes(script, script_text)
    deliverables = _deliverables(script_text, brief)
    split = proposed_split(cap_usd)
    treatment = {
        "version": "0.1.0",
        "status": "draft",
        "approval": {
            "state": "pending",
            "by": None,
            "at": None,
            "note": "The Director cannot approve. Ron approves through the Line Producer.",
        },
        "production_id": production_id,
        "title": title,
        "logline": logline,
        "theme_and_emotional_intent": {"theme": theme, "emotional_intent": intent},
        "tone_and_genre": {"tone": tone, "genre": genre},
        "characters": characters,
        "scenes": scenes,
        "deliverables": deliverables,
        "open_questions": [],
        "world_and_period": _world(script_text, brief),
        "camera_lens_film_stock": _camera(brief, script_text),
        "hero_props": _hero_props(script_text, brief),
        "sound_and_music_intent": _sound(script_text, brief),
        "color_and_light_plan": _section(script_text, "COLOR PROGRESSION") or _palette(brief),
        "pacing_and_runtime_target": _section(script_text, "EDITORIAL RHYTHM")
        or f"Target length {deliverables['length']}.",
        "action_and_stunt_beats": _action_beats(script_text),
        "reference_lookbook": _lookbook(brief),
        "audience_feeling_per_act": _feelings(script_text),
        "constraints_and_budget": {
            "budget_cap_usd": money_number(cap_usd),
            "notes": (
                "Proposed split of the film cap. Retakes come out of the same stage "
                "allocations and the same cap. Not locked until Ron approves the treatment."
            ),
            "stage_split": split,
        },
        "draft_method": "offline-deterministic",
        "draft_note": (
            "Offline draft. No model was called, because this path does not use an API key. "
            + skill_note()
        ),
    }
    _merge_partial(treatment, script.partial if script else None)
    return force_draft(_drop_empty(treatment))


def merge_sources(draft: dict, partial: dict | None) -> dict:
    """Ron's partial treatment wins where he already wrote a value."""
    if partial:
        _merge_partial(draft, partial)
    return draft


def build_questions(treatment: dict, script_text: str = "") -> dict:
    """One short question per gap Ron still needs to lock."""
    cap = treatment.get("constraints_and_budget", {}).get("budget_cap_usd", 500)
    split = treatment.get("constraints_and_budget", {}).get("stage_split") or {}
    theme = treatment["theme_and_emotional_intent"]
    tone = treatment["tone_and_genre"]
    character = treatment["characters"][0]
    lookbook = treatment.get("reference_lookbook") or []
    look_text = "; ".join(
        f"{item['reference']} ({item['take']})" for item in lookbook
    ) or "none yet"
    beats = treatment.get("action_and_stunt_beats") or []
    beat_text = " ".join(beats) if beats else "None are listed yet."
    props = treatment.get("hero_props") or []
    prop_text = _prop_question(props, script_text)
    split_text = ", ".join(f"{name} ${amount:g}" for name, amount in split.items()) or "none"
    split_sum = money_number(sum(as_money(value) for value in split.values())) if split else 0
    arc = character.get("arc") or ""
    arc_question = (
        f"{character['name']} is the {character['role']}. "
        + (
            f"The draft arc is: {arc} Lock it, or replace it?"
            if arc
            else "The draft does not lock an arc yet. What does he want, and what is different in him by the last shot? If he only chooses and does not change, say that."
        )
    )
    questions = [
        {
            "id": "q-intent",
            "topic": "intent",
            "required": True,
            "why": "The Director will not invent the film's intent.",
            "question": (
                f"The draft theme is \"{theme['theme'].strip().rstrip('.')}\". "
                f"The feeling it aims for is \"{theme['emotional_intent'].strip().rstrip('.')}\". "
                "Lock that, or replace it?"
            ),
            "answer": None,
        },
        {
            "id": "q-tone",
            "topic": "tone",
            "required": True,
            "why": "Tone drives the look, the pace, and the performances.",
            "question": (
                f"The draft calls the tone \"{tone['tone'].strip().rstrip('.')}\" and the genre \"{tone['genre'].strip().rstrip('.')}\". "
                "Lock this, or tell me what to change?"
            ),
            "answer": None,
        },
        {
            "id": "q-references",
            "topic": "references",
            "required": True,
            "why": "A reference is useful only if we name what to take from it.",
            "question": (
                f"The lookbook currently takes: {look_text}. "
                "Is each 'what to take' right? Add or cut references in your answer."
            ),
            "answer": None,
        },
        {
            "id": "q-arcs",
            "topic": "character-arcs",
            "required": True,
            "why": "The character's change, or the choice not to change, has to be explicit.",
            "question": arc_question,
            "answer": None,
        },
        {
            "id": "q-withheld",
            "topic": "withheld",
            "required": True,
            "why": "What we hide is a directing choice, not a guess from the screenplay.",
            "question": (
                "What should the audience not know yet? "
                "Name it. The answer is saved once, on the last scene."
            ),
            "answer": None,
        },
        {
            "id": "q-action",
            "topic": "action-beats",
            "required": True,
            "why": "Stunt beats have to be named before anyone generates them.",
            "question": (
                f"Action beats in the draft: {beat_text} "
                "Are these the beats you want? Is there anything a stunt pass must lock before generation?"
            ),
            "answer": None,
        },
        {
            "id": "q-props",
            "topic": "hero-props",
            "required": True,
            "why": "A hero prop drifts if its side or placement is not locked.",
            "question": prop_text,
            "answer": None,
        },
        {
            "id": "q-budget",
            "topic": "budget-split",
            "required": True,
            "why": "The Line Producer cannot enforce a split until you approve one.",
            "question": (
                f"The film cap is ${money_number(cap):g}. "
                f"The draft proposes: {split_text}. "
                f"Those numbers add up to ${split_sum:g}. "
                "Retakes spend from the same buckets and the same cap. "
                "Approve the split, or send new numbers as stage=amount, separated by commas."
            ),
            "answer": None,
        },
    ]
    by_topic = {item["topic"]: item for item in questions}
    ordered = [by_topic[topic] for topic in _QUESTION_ORDER]
    return {
        "production_id": treatment["production_id"],
        "round": 1,
        "status": "open",
        "drafted_by": "offline-deterministic",
        "model": None,
        "note": "Answer in the answer field, or send a separate answers file. Leave a field null if you are not ready.",
        "questions": ordered,
    }


def apply_answers(treatment: dict, questions: dict, incoming: dict[str, str]) -> tuple[dict, dict]:
    """Copy Ron's answers onto the treatment. Unanswered required questions stay open."""
    for item in questions["questions"]:
        if item["id"] in incoming and str(incoming[item["id"]]).strip():
            item["answer"] = str(incoming[item["id"]]).strip()
            _apply_one(treatment, item["topic"], item["answer"])
    pending = [
        item for item in questions["questions"]
        if item.get("required", True) and not str(item.get("answer") or "").strip()
    ]
    questions["status"] = "closed" if not pending else "open"
    treatment["open_questions"] = [item["question"] for item in pending]
    return treatment, questions


def unanswered_required(questions: dict) -> list[dict]:
    return [
        item for item in questions.get("questions", [])
        if item.get("required", True) and not str(item.get("answer") or "").strip()
    ]


def render_markdown(treatment: dict) -> str:
    """A readable draft. The JSON file remains the one the pipeline checks."""
    method = treatment.get("draft_method")
    if method == "offline-deterministic":
        how = (
            "This draft was written offline, without a model, because no API key was used. "
            "The label on the draft is offline-deterministic."
        )
    elif method == "model":
        how = "This draft was written with a model. It is still a draft."
    else:
        how = "This is a draft."
    lines = [
        f"# {treatment['title']} — treatment",
        "",
        "**Status: draft. Not approved.**" if treatment.get("status") != "approved"
        else "**Status: approved.**",
        "",
        how,
        "Ron approves this through the Line Producer. The Director cannot approve it.",
        "",
    ]
    if treatment.get("draft_note"):
        lines.extend([treatment["draft_note"], ""])
    lines.extend([
        "## Logline",
        "",
        treatment["logline"],
        "",
        "## Theme and emotional intent",
        "",
        f"Theme: {treatment['theme_and_emotional_intent']['theme']}",
        "",
        f"Emotional intent: {treatment['theme_and_emotional_intent']['emotional_intent']}",
        "",
        "## Tone and genre",
        "",
        f"Tone: {treatment['tone_and_genre']['tone']}",
        "",
        f"Genre: {treatment['tone_and_genre']['genre']}",
        "",
        "## Characters",
        "",
    ])
    for person in treatment["characters"]:
        lines.append(f"### {person['name']}")
        lines.append("")
        lines.append(f"Role: {person['role']}")
        lines.append("")
        lines.append(f"Look: {person['look']}")
        lines.append("")
        for key, label in (
            ("wardrobe", "Wardrobe"),
            ("arc", "Arc"),
            ("continuity_specs", "Continuity"),
        ):
            if person.get(key):
                lines.append(f"{label}: {person[key]}")
                lines.append("")
    lines.extend(["## Scenes", ""])
    for scene in treatment["scenes"]:
        heading = scene.get("heading") or scene.get("scene_id") or "Scene"
        lines.append(f"### {heading}")
        lines.append("")
        lines.append(scene["what_happens"])
        lines.append("")
        lines.append(f"Emotional purpose: {scene['emotional_purpose']}")
        lines.append("")
        for key, label in (
            ("point_of_view", "Point of view"),
            ("withheld", "Withheld"),
            ("coverage_intent", "Coverage"),
        ):
            if scene.get(key):
                lines.append(f"{label}: {scene[key]}")
                lines.append("")
        if scene.get("approximate_duration_seconds"):
            lines.append(f"Approximate duration: {scene['approximate_duration_seconds']:g} seconds")
            lines.append("")
    deliverables = treatment["deliverables"]
    lines.extend([
        "## Deliverables",
        "",
        f"Aspect ratio: {deliverables['aspect_ratio']}",
        "",
        f"Resolution: {deliverables['resolution']}",
        "",
        f"Length: {deliverables['length']}",
        "",
    ])
    _md_section(lines, "World and period", treatment.get("world_and_period"))
    _md_section(lines, "Camera, lens, and film stock", treatment.get("camera_lens_film_stock"))
    if treatment.get("hero_props"):
        lines.extend(["## Hero props", ""])
        for prop in treatment["hero_props"]:
            lines.append(f"### {prop['name']}")
            lines.append("")
            if prop.get("locked_spec"):
                lines.append(prop["locked_spec"])
                lines.append("")
            if prop.get("sidedness"):
                lines.append(f"Sidedness: {prop['sidedness']}")
                lines.append("")
            images = prop.get("reference_images") or []
            lines.append(
                "Reference images: " + (", ".join(images) if images else "(slot empty — add multi-angle refs when they exist)")
            )
            lines.append("")
    if treatment.get("reference_lookbook"):
        lines.extend(["## Reference lookbook", ""])
        for item in treatment["reference_lookbook"]:
            lines.append(f"- **{item['reference']}.** Take: {item['take']}")
        lines.append("")
    if treatment.get("action_and_stunt_beats"):
        lines.extend(["## Action and stunt beats", ""])
        for beat in treatment["action_and_stunt_beats"]:
            lines.append(f"- {beat}")
        lines.append("")
    _md_section(lines, "Sound and music", treatment.get("sound_and_music_intent"))
    _md_section(lines, "Color and light", treatment.get("color_and_light_plan"))
    _md_section(lines, "Pacing and runtime", treatment.get("pacing_and_runtime_target"))
    if treatment.get("audience_feeling_per_act"):
        lines.extend(["## Audience feeling", ""])
        for act in treatment["audience_feeling_per_act"]:
            lines.append(f"- **{act['act']}.** {act['feeling']}")
        lines.append("")
    budget = treatment.get("constraints_and_budget")
    if budget:
        lines.extend(["## Constraints and budget", ""])
        lines.append(f"Film cap: ${budget['budget_cap_usd']:g}")
        lines.append("")
        if budget.get("notes"):
            lines.append(budget["notes"])
            lines.append("")
        if budget.get("stage_split"):
            lines.append("Proposed stage split:")
            lines.append("")
            for name, amount in budget["stage_split"].items():
                lines.append(f"- {name}: ${amount:g}")
            lines.append("")
    lines.extend(["## Open questions", ""])
    if treatment.get("open_questions"):
        for question in treatment["open_questions"]:
            lines.append(f"- {question}")
    else:
        lines.append("None in the treatment file. See the questions file if a round is still open.")
    lines.append("")
    return "\n".join(lines)


def extract_json_object(text: str) -> dict:
    """Pull one JSON object out of a model reply. Fences are allowed."""
    cleaned = _json_slice(text, through_end=False)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The model did not return JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("The model did not return a JSON object.")
    return data


def repair_truncated_json(text: str) -> tuple[dict, list[str]]:
    """Read a JSON object that was cut off at the end.

    A complete object is returned with nothing dropped. A reply that stops
    inside a string, a key, or a value closes the open arrays and objects
    and drops that unfinished key or value. Nothing is sent to a model.
    """
    body = _json_slice(text, through_end=True)
    if body.rstrip().endswith("}"):
        try:
            return extract_json_object(text), []
        except ValueError:
            pass
    if not body.startswith("{"):
        raise ValueError("The model did not return JSON. No object was found.")
    value, _index, dropped = _parse_value(body, 0)
    if value is _DROP or not isinstance(value, dict):
        raise ValueError("The model did not return a JSON object.")
    return value, dropped


def reply_was_repaired(text: str, dropped: list[str]) -> bool:
    """True when the reply was not already one complete JSON object.

    A nested ``}`` is not enough. The whole text has to parse. A reply that
    only needed its containers closed still counts, even when no field was dropped.
    """
    if dropped:
        return True
    try:
        extract_json_object(text)
    except ValueError:
        return True
    return False


def merge_treatment_patch(base: dict, patch: dict) -> dict:
    """Keep the current draft and overlay the fields a reply actually sent.

    A final pass may return the whole treatment or only the fields it changed.
    A blank value does not wipe a drafted one. Nested objects merge key by key
    so a cut-off budget note does not erase the rest of that object.
    """
    if not isinstance(base, dict):
        return copy.deepcopy(patch) if isinstance(patch, dict) else {}
    merged = copy.deepcopy(base)
    if isinstance(patch, dict):
        _deep_merge(merged, patch)
    return merged


def _json_slice(text: str, *, through_end: bool) -> str:
    """The object text. A complete reply stops at the last brace.

    A truncated reply has to keep everything after that brace, because the
    last brace may close a nested object while the root is still open.
    """
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*)", cleaned, re.DOTALL)
    if fenced:
        body = fenced.group(1)
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]
    else:
        start = cleaned.find("{")
        body = cleaned[start:] if start >= 0 else cleaned
    body = body.strip()
    if through_end:
        return body
    end = body.rfind("}")
    if end > 0:
        return body[: end + 1]
    return body


class _DropType:
    pass


_DROP = _DropType()


def _parse_value(text: str, index: int) -> tuple[object, int, list[str]]:
    index = _skip_ws(text, index)
    if index >= len(text):
        return _DROP, index, []
    char = text[index]
    if char == "{":
        return _parse_object(text, index)
    if char == "[":
        return _parse_array(text, index)
    if char == '"':
        value, index, closed = _parse_string(text, index)
        if not closed:
            return _DROP, index, []
        return value, index, []
    if char in "-0123456789":
        return _parse_number(text, index)
    for word in ("true", "false", "null"):
        if text.startswith(word, index):
            return {"true": True, "false": False, "null": None}[word], index + len(word), []
        if word.startswith(text[index:]) and index + len(word) > len(text):
            return _DROP, len(text), []
    return _DROP, index, []


def _parse_object(text: str, index: int) -> tuple[object, int, list[str]]:
    index += 1
    found: dict = {}
    dropped: list[str] = []
    while True:
        index = _skip_ws(text, index)
        if index >= len(text):
            return found, index, dropped
        if text[index] == "}":
            return found, index + 1, dropped
        if text[index] == ",":
            index += 1
            continue
        if text[index] != '"':
            return found, index, dropped
        key, index, closed = _parse_string(text, index)
        if not closed:
            dropped.append(key or "(incomplete key)")
            return found, index, dropped
        index = _skip_ws(text, index)
        if index >= len(text) or text[index] != ":":
            dropped.append(key)
            return found, index, dropped
        index += 1
        value, index, nested = _parse_value(text, index)
        if value is _DROP:
            dropped.append(key)
            return found, index, dropped
        found[key] = value
        for item in nested:
            dropped.append(f"{key}.{item}")
        index = _skip_ws(text, index)
        if index >= len(text):
            return found, index, dropped
        if text[index] not in {",", "}"}:
            return found, index, dropped


def _parse_array(text: str, index: int) -> tuple[object, int, list[str]]:
    index += 1
    items: list = []
    dropped: list[str] = []
    while True:
        index = _skip_ws(text, index)
        if index >= len(text):
            return items, index, dropped
        if text[index] == "]":
            return items, index + 1, dropped
        if text[index] == ",":
            index += 1
            continue
        value, index, nested = _parse_value(text, index)
        if value is _DROP:
            dropped.append(str(len(items)))
            return items, index, dropped
        items.append(value)
        for item in nested:
            dropped.append(f"{len(items) - 1}.{item}")
        index = _skip_ws(text, index)
        if index >= len(text):
            return items, index, dropped
        if text[index] not in {",", "]"}:
            return items, index, dropped


def _parse_string(text: str, index: int) -> tuple[str, int, bool]:
    index += 1
    chars: list[str] = []
    while index < len(text):
        char = text[index]
        if char == "\\":
            if index + 1 >= len(text):
                return "".join(chars), len(text), False
            nxt = text[index + 1]
            chars.append({"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
            index += 2
            continue
        if char == '"':
            return "".join(chars), index + 1, True
        chars.append(char)
        index += 1
    return "".join(chars), index, False


def _parse_number(text: str, index: int) -> tuple[object, int, list[str]]:
    end = index + 1
    while end < len(text) and text[end] in "0123456789.eE+-":
        end += 1
    token = text[index:end]
    try:
        if any(mark in token for mark in (".", "e", "E")):
            return float(token), end, []
        return int(token), end, []
    except ValueError:
        return _DROP, end, []


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _deep_merge(dest: dict, patch: dict) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(dest.get(key), dict):
            _deep_merge(dest[key], value)
            continue
        if _empty_patch(value) and key in dest:
            continue
        dest[key] = copy.deepcopy(value)


def _empty_patch(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False


def treatment_errors(treatment: dict) -> list[str]:
    return validate_data(conform_treatment(treatment), load_schema("treatment"))


def _apply_withheld(treatment: dict, answer: str) -> None:
    """Record one withheld fact, on the last scene.

    A confirmation keeps the drafted text. The answer is not copied onto
    every scene that shares a word with it, and it is not pasted into
    what happens in the scene.
    """
    text = strip_answer_lead_in(answer)
    if not text:
        return
    if confirms_draft(text):
        note_locked(treatment, "withheld fact")
        return
    scenes = [scene for scene in treatment.get("scenes") or [] if isinstance(scene, dict)]
    if not scenes:
        note = treatment.get("draft_note") or ""
        sentence = f"Withheld: {text}"
        if sentence not in note:
            treatment["draft_note"] = (note + " " + sentence).strip()
        return
    for scene in scenes[:-1]:
        if scene.get("withheld") in {text, answer, answer.strip()}:
            scene.pop("withheld", None)
    scenes[-1]["withheld"] = text


def _apply_hero_props(treatment: dict, answer: str) -> None:
    """Lock a prop when Ron's answer names it. The prop names come from the treatment."""
    props = treatment.get("hero_props") or []
    if not props:
        return
    if confirms_draft(answer):
        note_locked(treatment, "hero props")
        return
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", answer.strip()) if part.strip()]
    if not sentences:
        sentences = [answer.strip()]
    matched = False
    for prop in props:
        tokens = [token for token in re.findall(r"[A-Za-z0-9]+", prop.get("name") or "") if len(token) > 3]
        hit = ""
        for sentence in sentences:
            if any(token.casefold() in sentence.casefold() for token in tokens):
                hit = sentence.strip()
                break
        if not hit:
            continue
        matched = True
        prop["sidedness"] = hit.rstrip(".")
        spec = prop.get("locked_spec") or prop.get("name") or ""
        if hit.casefold() not in spec.casefold():
            prop["locked_spec"] = spec.rstrip(".") + ". " + hit
    if not matched:
        for prop in props:
            prop["sidedness"] = answer.strip()
            prop["locked_spec"] = answer.strip()


def _apply_one(treatment: dict, topic: str, answer: str) -> None:
    answer = strip_answer_lead_in(answer)
    if topic == "intent":
        if confirms_draft(answer):
            note_locked(treatment, "emotional intent")
        else:
            treatment["theme_and_emotional_intent"]["emotional_intent"] = answer
    elif topic == "tone":
        if confirms_draft(answer):
            note_locked(treatment, "tone")
        else:
            treatment["tone_and_genre"]["tone"] = answer
    elif topic == "references":
        if confirms_draft(answer):
            note_locked(treatment, "references")
        else:
            treatment.setdefault("reference_lookbook", []).append(
                {"reference": "From Ron", "take": answer}
            )
    elif topic == "character-arcs":
        if confirms_draft(answer):
            note_locked(treatment, "character arc")
        elif treatment.get("characters"):
            treatment["characters"][0]["arc"] = answer
    elif topic == "withheld":
        _apply_withheld(treatment, answer)
    elif topic == "action-beats":
        if confirms_draft(answer):
            note_locked(treatment, "action beats")
        else:
            treatment.setdefault("action_and_stunt_beats", []).append(answer)
    elif topic == "hero-props":
        _apply_hero_props(treatment, answer)
    elif topic == "budget-split":
        budget = treatment.setdefault("constraints_and_budget", {"budget_cap_usd": 500})
        parsed = parse_stage_split(answer)
        if parsed:
            budget["stage_split"] = parsed
            total = sum(as_money(value) for value in parsed.values())
            cap = as_money(budget.get("budget_cap_usd", 500))
            if total > cap:
                budget["notes"] = (
                    f"Ron's split adds up to ${money_number(total):g}, over the ${money_number(cap):g} cap. "
                    "The Line Producer will not lock it until it fits."
                )
            return
        if approves_proposal(answer) and budget.get("stage_split"):
            budget["notes"] = (
                "Ron approved this split in his answer. Retakes come out of the same "
                "stage allocations and the same cap. The Line Producer locks the split "
                "when Ron approves the treatment gate."
            )
            return
        budget["notes"] = ((budget.get("notes") or "") + " Ron's budget note: " + answer).strip()


def _merge_partial(draft: dict, partial: dict | None) -> None:
    if not partial:
        return
    for key in (
        "title",
        "logline",
        "world_and_period",
        "camera_lens_film_stock",
        "sound_and_music_intent",
        "color_and_light_plan",
        "pacing_and_runtime_target",
    ):
        if _filled(partial.get(key)):
            draft[key] = partial[key]
    for key in ("theme_and_emotional_intent", "tone_and_genre", "deliverables", "constraints_and_budget"):
        if isinstance(partial.get(key), dict):
            current = draft.get(key) or {}
            for sub, value in partial[key].items():
                if _filled(value):
                    current[sub] = value
            draft[key] = current
    if partial.get("characters"):
        draft["characters"] = partial["characters"]
    if partial.get("scenes"):
        draft["scenes"] = partial["scenes"]
    for key in (
        "hero_props",
        "reference_lookbook",
        "action_and_stunt_beats",
        "audience_feeling_per_act",
        "open_questions",
    ):
        if partial.get(key):
            draft[key] = partial[key]


def _characters(script_text: str, brief: dict | None) -> list[dict]:
    people = []
    for person in (brief or {}).get("characters") or []:
        description = person.get("description") or ""
        look, wardrobe = _split_look(description)
        item = {
            "name": person.get("name") or "Unnamed",
            "role": "protagonist" if len((brief or {}).get("characters") or []) == 1 else "character",
            "look": look or "Look is not described yet.",
        }
        if wardrobe:
            item["wardrobe"] = wardrobe
        props = person.get("props") or []
        if props:
            item["continuity_specs"] = " ".join(
                f"{prop.get('name', 'Prop')}: {prop.get('description', '')}".strip()
                for prop in props
            )
        people.append(item)
    if people:
        return people
    match = re.search(r"\*\*CHARACTER:\*\*\s*(.+?)(?:\n\s*\n|\*\*[A-Z])", script_text, re.S)
    paragraph = re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
    if not paragraph:
        return [{"name": "Unnamed", "role": "protagonist", "look": "Look is not described yet."}]
    name_match = re.match(r"([A-Z][A-Za-z' -]+?)(?:,|\.)", paragraph)
    name = name_match.group(1).title() if name_match else "Unnamed"
    look, wardrobe = _split_look(paragraph)
    item = {"name": name, "role": "protagonist", "look": look or paragraph}
    if wardrobe:
        item["wardrobe"] = wardrobe
    return [item]


def _scenes(script: ParsedSource | None, script_text: str) -> list[dict]:
    durations = {}
    for match in re.finditer(r"Scene\s+(\d+)\s*\((\d+)\s*sec\)", script_text, re.I):
        durations[int(match.group(1))] = float(match.group(2))
    raw_scenes = script.scenes if script else []
    if not raw_scenes:
        return [{
            "scene_id": "s01",
            "what_happens": "The screenplay has not been broken into scenes yet.",
            "emotional_purpose": "The feeling of this scene is still open.",
        }]
    built = []
    for index, raw in enumerate(raw_scenes, start=1):
        body = raw.get("body") or ""
        item = {
            "scene_id": f"s{index:02d}",
            "heading": raw.get("heading") or f"Scene {index}",
            "what_happens": _what_happens(body),
            "emotional_purpose": _emotional_purpose(body),
        }
        if durations.get(index):
            item["approximate_duration_seconds"] = durations[index]
        if re.search(r"\bPOV\b", body):
            item["point_of_view"] = "The character, for the shot marked POV. The rest of the scene is observed."
        coverage = _coverage(body)
        if coverage:
            item["coverage_intent"] = coverage
        built.append(item)
    return built


def _what_happens(body: str) -> str:
    kept = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if stripped.startswith("*[") or stripped.startswith("["):
            continue
        if upper in {"FADE IN.", "CUT TO:", "CUT TO"} or upper.startswith("CUT TO"):
            continue
        if stripped.startswith("#"):
            continue
        kept.append(stripped)
    text = re.sub(r"\s+", " ", " ".join(kept)).strip()
    return _shorten(text, 900) or "What happens in this scene is not described yet."


def _emotional_purpose(body: str) -> str:
    thesis = re.search(r"central visual thesis of the film:\s*([^.\]]+)", body, re.I)
    if thesis:
        sentence = thesis.group(1).strip().rstrip(".")
        return sentence[:1].upper() + sentence[1:] + "."
    color = re.search(r"\[COLOR:\s*([^\]]+)\]", body)
    if color:
        return "The light carries the feeling. " + _shorten(re.sub(r"\s+", " ", color.group(1)).strip(), 240)
    return "The feeling of this scene is still open."


def _coverage(body: str) -> str:
    found = re.findall(
        r"\b(EXTREME WIDE|WIDE SHOT|MEDIUM TRACKING SHOT|MEDIUM|DETAIL SHOT|CLOSE|LOW ANGLE|POV)\b",
        body,
        re.I,
    )
    unique = []
    for item in found:
        label = item.upper()
        if label not in unique:
            unique.append(label)
    if not unique:
        return ""
    return "Coverage named in the screenplay: " + ", ".join(unique[:8]) + "."


def _logline(script_text: str, brief: dict | None) -> str:
    concept = (brief or {}).get("concept")
    if concept:
        return _shorten(re.sub(r"\s+", " ", concept).strip(), 500)
    match = re.search(r"\*\*CONCEPT:\*\*\s*(.+?)(?:\n\s*\n|\*\*[A-Z])", script_text, re.S)
    if match:
        return _shorten(re.sub(r"\s+", " ", match.group(1)).strip(), 500)
    return "Logline still open."


def _theme_and_intent(script_text: str, brief: dict | None) -> tuple[str, str]:
    del script_text
    concept = (brief or {}).get("concept") or ""
    return (
        "The theme is still open.",
        _shorten(concept, 240) or "The feeling the audience should leave with is still open.",
    )


def _tone_and_genre(brief: dict | None, script_text: str) -> tuple[str, str]:
    tone = (brief or {}).get("tone") or ""
    genre = (brief or {}).get("genre") or ""
    if not genre:
        match = re.search(
            r"\b(western|comedy|drama|documentary|horror|thriller)\b",
            script_text,
            re.I,
        )
        if match:
            genre = match.group(1).casefold()
    return tone or "Tone is still open.", genre or "drama"


def _deliverables(script_text: str, brief: dict | None) -> dict:
    aspect = (brief or {}).get("aspect_ratio") or ""
    if not aspect:
        match = re.search(r"Aspect Ratio:\s*([0-9.]+:[0-9.]+)", script_text, re.I)
        aspect = match.group(1) if match else "16:9"
    seconds = (brief or {}).get("target_runtime_seconds")
    if not seconds:
        match = re.search(r"(\d+)\s*minutes", script_text, re.I)
        seconds = int(match.group(1)) * 60 if match else None
    if seconds and int(seconds) % 60 == 0:
        length = f"{int(seconds) // 60} minutes"
    elif seconds:
        length = f"{int(seconds)} seconds"
    else:
        length = "Length is still open."
    return {
        "aspect_ratio": aspect,
        "resolution": "1920x1080, framed in the delivery aspect ratio",
        "length": length,
    }


def _world(script_text: str, brief: dict | None) -> str:
    setting = (brief or {}).get("setting") or {}
    if setting.get("place") or setting.get("year"):
        place = setting.get("place") or "Place not set"
        year = setting.get("year") or "year not set"
        note = setting.get("notes") or ""
        text = f"{place}, {year}."
        return (text + " " + note).strip()
    year = re.search(r"\bin (\d{4})\b", script_text)
    heading = re.search(r"\b(?:EXT|INT)\.\s+([^-\n]+)", script_text)
    if heading or year:
        place = heading.group(1).strip(" .") if heading else "Place not set"
        return place + ", " + (year.group(1) if year else "year not set") + "."
    return "World and period are still open."


def _camera(brief: dict | None, script_text: str) -> str:
    style = (brief or {}).get("visual_style") or {}
    if style.get("description"):
        return style["description"]
    match = re.search(r"Visual Style:\s*(.+)", script_text)
    if match:
        return match.group(1).strip()
    return "Camera and film stock are still open."


def _hero_props(script_text: str, brief: dict | None) -> list[dict]:
    props = []
    for prop in (brief or {}).get("hero_props") or []:
        item = {
            "name": prop["name"],
            "locked_spec": prop.get("description") or "Spec not locked.",
            "sidedness": prop.get("sidedness") or ("locked" if prop.get("locked") else "not locked"),
            "reference_images": [],
        }
        props.append(item)
    return props


def _sound(script_text: str, brief: dict | None) -> str:
    sound = (brief or {}).get("sound_design") or {}
    parts = [sound.get("description") or "", sound.get("music_approach") or ""]
    text = " ".join(part for part in parts if part).strip()
    if text:
        return text
    return _section(script_text, "SOUND DESIGN") or "Sound and music intent are still open."


def _palette(brief: dict | None) -> str:
    colors = ((brief or {}).get("visual_style") or {}).get("color_palette") or []
    if colors:
        return "Palette: " + ", ".join(colors) + "."
    return ""


def _lookbook(brief: dict | None) -> list[dict]:
    style = (brief or {}).get("visual_style") or {}
    items = []
    for film in style.get("reference_films") or []:
        items.append({
            "reference": film,
            "take": style.get("description") or "Use the reference for framing and pace, not as a copy.",
        })
    music = ((brief or {}).get("sound_design") or {}).get("music_approach") or ""
    if music.strip():
        items.append({
            "reference": "Score approach",
            "take": music.strip(),
        })
    return items


def _feelings(script_text: str) -> list[dict]:
    section = _section(script_text, "EDITORIAL RHYTHM")
    if not section:
        return []
    return [{"act": "Whole film", "feeling": _shorten(section, 400)}]


def _action_beats(script_text: str) -> list[str]:
    """Quote action sentences from the screenplay. Do not invent a beat."""
    beats = []
    pattern = re.compile(r"\b(kicks?|falls?|jumps?|punches|stumbles|crashes|fights)\b", re.I)
    for sentence in re.split(r"(?<=[.!?])\s+", script_text):
        cleaned = _shorten(sentence, 280)
        if pattern.search(cleaned) and cleaned not in beats:
            beats.append(cleaned)
        if len(beats) >= 6:
            break
    return beats


def _prop_question(props: list[dict], script_text: str) -> str:
    del script_text
    if not props:
        return (
            "Name the hero props, if this film has any. "
            "For each one, lock the attribute that must not drift. Name the prop in your answer."
        )
    described = []
    for prop in props:
        side = prop.get("sidedness") or "not locked"
        described.append(f"{prop['name']} ({side})")
    return (
        "Hero props: " + "; ".join(described) + ". "
        "Lock each one. Name the prop and the attribute you are locking."
    )


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"###\s+{re.escape(heading)}\s*(.+?)(?:\n###|\n---|\Z)",
        text,
        re.S | re.I,
    )
    if not match:
        return ""
    body = re.sub(r"\s+", " ", match.group(1)).strip()
    return _shorten(body, 700)


def _split_look(description: str) -> tuple[str, str]:
    match = re.search(r"\b(He wears|She wears|They wear|Wardrobe:)\b", description)
    if not match:
        return _shorten(description.strip(), 500), ""
    look = description[: match.start()].strip()
    wardrobe = description[match.start() :].strip()
    biography = re.search(r"\b(?:He|She) is a\b", wardrobe)
    if biography:
        wardrobe = wardrobe[: biography.start()].strip()
    return _shorten(look, 500) or "Look is not described yet.", _shorten(wardrobe, 400)


def _shorten(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _first(*values: str) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _drop_empty(treatment: dict) -> dict:
    """Omit optional strings that are empty so the file stays readable."""
    for key in (
        "world_and_period",
        "camera_lens_film_stock",
        "sound_and_music_intent",
        "color_and_light_plan",
        "pacing_and_runtime_target",
        "draft_note",
    ):
        if key in treatment and not str(treatment[key]).strip():
            del treatment[key]
    for key in ("action_and_stunt_beats", "reference_lookbook", "audience_feeling_per_act", "hero_props"):
        if key in treatment and not treatment[key]:
            del treatment[key]
    return treatment


def _md_section(lines: list[str], title: str, body: str | None) -> None:
    if not body:
        return
    lines.extend([f"## {title}", "", body, ""])


def _schema_field_line(key: str, prop: dict) -> str:
    kind = prop.get("type") or "value"
    if isinstance(kind, list):
        kind = " or ".join(str(item) for item in kind)
    parts = [f"{key} is a {kind}"]
    if prop.get("pattern"):
        parts.append(f"matching {prop['pattern']}")
    if prop.get("enum"):
        parts.append("one of " + ", ".join(str(item) for item in prop["enum"]))
    if prop.get("minLength"):
        parts.append(f"at least {prop['minLength']} characters")
    if kind == "object":
        required = prop.get("required") or []
        if required:
            details = []
            for sub in required:
                subprop = (prop.get("properties") or {}).get(sub) or {}
                details.append(f"{sub} ({subprop.get('type') or 'value'})")
            parts.append("with " + ", ".join(details))
    if kind == "array":
        item = prop.get("items") or {}
        if item.get("type") == "object" and item.get("required"):
            parts.append("each item requires " + ", ".join(item["required"]))
        elif item.get("type"):
            parts.append(f"items are {item['type']}")
        if prop.get("minItems"):
            parts.append(f"at least {prop['minItems']} item(s)")
    return "- " + "; ".join(parts) + "."


def _map_treatment_aliases(data: dict) -> dict:
    """Fold theme/tone name variants into the schema's object keys."""
    if not isinstance(data, dict):
        return data
    mapped = dict(data)
    _fold_pair(mapped, "theme_and_emotional_intent", "theme", "emotional_intent")
    _fold_pair(mapped, "tone_and_genre", "tone", "genre")
    return mapped


def _fold_pair(mapped: dict, target: str, left: str, right: str) -> None:
    built = {}
    current = mapped.get(target)
    if isinstance(current, dict):
        if _plain_text(current.get(left)):
            built[left] = current[left]
        if _plain_text(current.get(right)):
            built[right] = current[right]
    for key in (left, right):
        raw = mapped.get(key)
        if isinstance(raw, dict):
            if _plain_text(raw.get(left)) and left not in built:
                built[left] = raw[left]
            if _plain_text(raw.get(right)) and right not in built:
                built[right] = raw[right]
        elif key == left and _plain_text(raw) and left not in built:
            built[left] = raw
        elif key == right and _plain_text(raw) and right not in built:
            built[right] = raw
    if built:
        mapped[target] = built


def _plain_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _normalise_version(treatment: dict) -> None:
    treatment["version"] = _semver(treatment.get("version"))


def _semver(value) -> str:
    if not isinstance(value, str):
        return "0.1.0"
    text = value.strip()
    if _SEMVER.fullmatch(text):
        return text
    pair = re.fullmatch(r"(\d+)\.(\d+)", text)
    if pair:
        return f"{pair.group(1)}.{pair.group(2)}.0"
    single = re.fullmatch(r"(\d+)", text)
    if single:
        return f"{single.group(1)}.0.0"
    return "0.1.0"


_DELIVERABLE_FIELDS = ("aspect_ratio", "resolution", "length")


def _fill_blank_deliverables(treatment: dict, fallback: dict | None) -> None:
    source = {}
    if isinstance(fallback, dict) and isinstance(fallback.get("deliverables"), dict):
        source = fallback["deliverables"]
    current = treatment.get("deliverables")
    if not isinstance(current, dict):
        filled = {
            key: source[key] for key in _DELIVERABLE_FIELDS if _plain_text(source.get(key))
        }
        if filled:
            treatment["deliverables"] = filled
        return
    for key in _DELIVERABLE_FIELDS:
        if not _plain_text(current.get(key)) and _plain_text(source.get(key)):
            current[key] = source[key]


def _fill_required_object(current: dict, backup: dict, schema: dict) -> None:
    for key in schema.get("required") or []:
        sub = (schema.get("properties") or {}).get(key) or {}
        if _blank_leaf(current.get(key), sub) and not _blank_leaf(backup.get(key), sub):
            current[key] = copy.deepcopy(backup[key])


def _blank_leaf(value, schema: dict) -> bool:
    """True when a required value is missing, the wrong type, or outside the schema."""
    expected = schema.get("type")
    if isinstance(expected, list):
        expected = next((item for item in expected if item != "null"), None)
    if value is None:
        return True
    if expected == "string":
        if not isinstance(value, str) or not value.strip():
            return True
        minimum = schema.get("minLength") or 0
        if len(value.strip()) < minimum:
            return True
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            return True
        allowed = schema.get("enum")
        if allowed is not None and value not in allowed:
            return True
        return False
    if expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return True
        exclusive = schema.get("exclusiveMinimum")
        if exclusive is not None and not (value > exclusive):
            return True
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            return True
        return False
    if expected == "array":
        if not isinstance(value, list):
            return True
        minimum = schema.get("minItems") or 0
        return len(value) < minimum
    if expected == "object":
        return not isinstance(value, dict)
    return False


def _conform(data, schema: dict):
    schema_type = schema.get("type")
    if schema_type == "object" and isinstance(data, dict):
        props = schema.get("properties") or {}
        additional = schema.get("additionalProperties", True)
        cleaned = {}
        for key, value in data.items():
            if key in props:
                cleaned[key] = _conform(value, props[key])
            elif isinstance(additional, dict):
                cleaned[key] = _conform(value, additional)
        return cleaned
    if schema_type == "array" and isinstance(data, list):
        item_schema = schema.get("items") or {}
        return [_conform(item, item_schema) for item in data]
    return data
