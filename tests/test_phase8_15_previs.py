"""Phase 8.15 previs fixes. Harbor Night and synthetic data. No paid call.

The engine stays generic. Nothing here names a real film's props as code.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.assistant_director import build_schedule
from movie_swarm.camera import build_package
from movie_swarm.costume import lock_costumes
from movie_swarm.director import Director, _reconform_note
from movie_swarm.gaffer import build_lighting_plan
from movie_swarm.generation import generate_shots, load_shots
from movie_swarm.graphics import write_research
from movie_swarm.handoff import write_handoff
from movie_swarm.line_producer import LineProducer
from movie_swarm.makeup import lock_makeup
from movie_swarm.mentions import advertising_phrases
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.studio import StudioError, run_studio
from movie_swarm.stunts import action_content, build_breakdown
from movie_swarm.treatment_doc import load_treatment, treatment_json_path


def _harbor(tmp_path: Path) -> Path:
    dest = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", dest)
    return dest


def _save_treatment(production: Path, treatment: dict) -> None:
    write_handoff(treatment_json_path(production), treatment, schema="treatment")


def _shot(shot_id: str, description: str, **extra) -> dict:
    item = {
        "shot_id": shot_id,
        "scene_number": 1,
        "shot_number": 1,
        "shot_type": "close",
        "description": description,
        "generation_prompt": description,
        "tool_routing": {"primary_tool": "veo-3.1-lite", "rationale": "Fixture."},
        "target_duration_seconds": 2,
    }
    item.update(extra)
    return item


def _write_shots(production: Path, shots: list[dict]) -> None:
    folder = production / "storyboard"
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "production_id": production.name,
        "version": "1.0.0",
        "total_shots": len(shots),
        "shots": shots,
        "created_at": "2026-11-12T00:00:00Z",
    }
    (folder / "shot-list.json").write_text(json.dumps(payload), encoding="utf-8")


class _Recorder:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return {"status": "not-sent", "detail": "fake"}


def test_character_aliases_and_storyboard_tags(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["characters"][0]["name"] = "Mina Cole"
    treatment["scenes"][0]["what_happens"] = (
        "Cole stands under a fluorescent lamp.\n\n"
        "MINA ties the red scarf on her right shoulder.\n\n"
        "MC nods once beside the lamp."
    )
    _save_treatment(production, treatment)
    costume = json.loads((production / "wardrobe" / "costume-definitions.json").read_text(encoding="utf-8"))
    costume["characters"][0]["character_id"] = "mina-cole"
    costume["characters"][0]["name"] = "Mina Cole"
    costume["characters"][0]["aliases"] = ["MC"]
    (production / "wardrobe" / "costume-definitions.json").write_text(json.dumps(costume), encoding="utf-8")
    makeup = json.loads((production / "makeup" / "makeup-definitions.json").read_text(encoding="utf-8"))
    makeup["characters"][0]["name"] = "Mina Cole"
    makeup["characters"][0]["character_id"] = "mina-cole"
    (production / "makeup" / "makeup-definitions.json").write_text(json.dumps(makeup), encoding="utf-8")

    lock_props(production)
    lock_costumes(production)
    lock_makeup(production)
    boards = build_boards(production)
    tagged = [frame["shot_id"] for frame in boards["frames"]]
    shot_list = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))
    by_text = {shot["description"]: shot for shot in shot_list["shots"]}
    for snippet in ("Cole stands", "MINA ties", "MC nods"):
        match = next(shot for text, shot in by_text.items() if snippet in text)
        assert match["characters_in_shot"] == ["Mina Cole"], snippet
        assert match["shot_id"] in tagged

    _write_shots(
        production,
        [
            _shot("s01-sh01", "Cole wears a light coat.", characters_in_shot=["Cole"]),
            _shot("s01-sh02", "Mina waits.", characters_in_shot=["Mina"]),
        ],
    )
    drifted = check_continuity(production)
    observed = " ".join(item.get("observed", "") for item in drifted["findings"]).casefold()
    assert "light coat" in observed
    assert {item.get("costume_id") for item in drifted["findings"] if item.get("costume_id")} == {"mina-cole"}


def test_prop_parts_tag_the_prop_and_enforce_sidedness(tmp_path):
    production = _harbor(tmp_path)
    definitions = json.loads((production / "props" / "prop-definitions.json").read_text(encoding="utf-8"))
    definitions["props"][0]["parts"] = ["knot", "fringe"]
    definitions["props"][0]["reference_images"] = ["refs/scarf-side.png"]
    (production / "props" / "prop-definitions.json").write_text(json.dumps(definitions), encoding="utf-8")
    treatment = load_treatment(production)
    treatment["scenes"][0]["what_happens"] = "The knot turns in the lamp light. The fringe moves once."
    _save_treatment(production, treatment)
    locked = lock_props(production)
    assert locked["props"][0]["parts"] == ["knot", "fringe"]
    boards = build_boards(production)
    shot_list = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))
    for shot in shot_list["shots"]:
        ids = [item["prop_id"] for item in shot.get("props_in_shot") or []]
        assert "red-scarf" in ids
        assert "Wool, red, worn on the right shoulder." in shot["generation_prompt"]
        assert "scarf on the right shoulder" in shot["generation_prompt"].casefold()
        assert shot["reference_images"] == ["refs/scarf-side.png"]
        assert "platinum" not in shot["generation_prompt"].casefold()
        assert "No locked prop is in this frame." not in shot["continuity_notes"]
        assert "Red scarf is in this frame." in shot["continuity_notes"]
    assert boards["frames"][0]["reference_images"] == ["refs/scarf-side.png"]

    _write_shots(production, [_shot("s01-sh09", "The knot is loose.")])
    drifted = check_continuity(production)
    assert any(item["kind"] == "unstated" and item.get("prop_id") == "red-scarf" for item in drifted["findings"])
    _write_shots(
        production,
        [_shot("s01-sh09", "The fringe shows the scarf on the left shoulder.")],
    )
    contradicted = check_continuity(production)
    assert any(
        item["kind"] == "contradiction" and "left shoulder" in item.get("observed", "")
        for item in contradicted["findings"]
    )


def test_wardrobe_accepts_key_facts_or_a_lock_reference_and_keeps_contradictions(tmp_path):
    production = _harbor(tmp_path)
    costume = json.loads((production / "wardrobe" / "costume-definitions.json").read_text(encoding="utf-8"))
    person = costume["characters"][0]
    person["character_id"] = "mina-cole"
    person["name"] = "Mina Cole"
    long = "She wears a white cotton shirt, a brown leather vest, and khaki pants."
    person["locked_spec"] = long
    person["garment"] = long
    person["attributes"] = [
        {
            "attribute_id": "wardrobe",
            "label": "wardrobe",
            "value": long,
            "must_be_stated_when_visible": True,
            "required_phrases": [long],
            "forbidden_phrases": ["light coat"],
        }
    ]
    (production / "wardrobe" / "costume-definitions.json").write_text(json.dumps(costume), encoding="utf-8")
    lock_props(production)
    lock_costumes(production)
    facts = "Mina wears a white cotton shirt, a brown leather vest, and khaki pants."
    _write_shots(production, [_shot("s01-sh01", facts, characters_in_shot=["Mina"])])
    clear = check_continuity(production)
    assert clear["verdict"] == "clear", clear["findings"]

    _write_shots(
        production,
        [_shot("s01-sh01", "Mina stands. Wardrobe lock: mina-cole.", characters_in_shot=["Mina Cole"])],
    )
    referenced = check_continuity(production)
    assert referenced["verdict"] == "clear", referenced["findings"]

    _write_shots(
        production,
        [
            _shot(
                "s01-sh01",
                "Mina stands. Wardrobe lock: mina-cole. She wears a light coat.",
                characters_in_shot=["Mina"],
            )
        ],
    )
    contradicted = check_continuity(production)
    assert any(item["kind"] == "contradiction" and item.get("observed") == "light coat" for item in contradicted["findings"])
    assert not any(item["kind"] == "unstated" for item in contradicted["findings"])


def test_storyboard_docs_use_hero_prop_moments_not_advertising_words(tmp_path):
    production = _harbor(tmp_path)
    lock_props(production)
    (production / "production-brief.json").write_text(
        json.dumps(
            {
                "featured_product": {
                    "product": "Red scarf",
                    "also_known_as": ["scarf"],
                    "placement_intent": "It is already part of the night.",
                    "rules": ["The scarf stays readable in a close view."],
                    "moments": [
                        {
                            "when": "red scarf",
                            "why": "The scarf is already on her shoulder in this moment.",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    build_boards(production)
    markdown = (production / "storyboard" / "storyboard.md").read_text(encoding="utf-8")
    prompts = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))
    blob = markdown + "\n" + " ".join(shot["generation_prompt"] for shot in prompts["shots"])
    assert "## Hero prop moments" in markdown
    assert "Featured product" not in markdown
    assert advertising_phrases(blob) == []


def test_prompts_carry_the_locked_spec_and_reference_images(tmp_path):
    production = _harbor(tmp_path)
    definitions = json.loads((production / "props" / "prop-definitions.json").read_text(encoding="utf-8"))
    definitions["props"][0]["reference_images"] = ["refs/scarf-side.png"]
    (production / "props" / "prop-definitions.json").write_text(json.dumps(definitions), encoding="utf-8")
    lock_props(production)
    build_boards(production)
    recorder = _Recorder()
    result = generate_shots(production, client=recorder, gate_open=True)
    assert result["called"] is True
    matched = [request for request in recorder.requests if "refs/scarf-side.png" in request.get("reference_images", [])]
    assert matched
    assert "Wool, red, worn on the right shoulder." in matched[0]["prompt"]
    assert "platinum clasp" not in matched[0]["prompt"].casefold()


def test_confirmation_answers_do_not_become_stunt_beats_or_shots(tmp_path):
    assert action_content("Yes, these are the beats. No extra stunt locks before generation.") == ""
    assert action_content("It is a field fix, not a repair.") == ""
    kept = action_content("She ties the scarf and steps onto the dock. The knot is on the right in the screenplay.")
    assert kept == "She ties the scarf and steps onto the dock."

    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["action_and_stunt_beats"] = [
        "She ties the scarf and steps onto the dock. The knot is on the right in the screenplay.",
        "Yes, these are the beats. No extra stunt locks before generation.",
        "It is a field fix, not a repair.",
    ]
    _save_treatment(production, treatment)
    breakdown = build_breakdown(production)
    assert len(breakdown["beats"]) == 1
    actions = [shot["action"] for shot in breakdown["beats"][0]["shots"]]
    assert actions == ["She ties the scarf and steps onto the dock."]
    assert any("screenplay" in note for note in breakdown["beats"][0]["notes"])
    blob = json.dumps(breakdown)
    assert "these are the beats" not in blob
    assert "field fix" not in blob


def test_lighting_reads_the_heading_and_does_not_repeat_the_sun_as_a_practical(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. YARD - LATE AFTERNOON",
            "what_happens": "A worker crosses the yard.",
            "emotional_purpose": "The day is still warm.",
            "approximate_duration_seconds": 4,
        },
        {
            "scene_id": "s02",
            "heading": "EXT. YARD - MOMENTS LATER",
            "what_happens": "The worker stops.",
            "emotional_purpose": "The same light.",
            "approximate_duration_seconds": 4,
        },
        {
            "scene_id": "s03",
            "heading": "EXT. GATE - CONTINUOUS",
            "what_happens": "The worker waits.",
            "emotional_purpose": "The same light.",
            "approximate_duration_seconds": 4,
        },
    ]
    _save_treatment(production, treatment)
    look = json.loads((production / "look" / "look.json").read_text(encoding="utf-8"))
    look["lighting"] = [{"id": "sun", "description": "The sun is low."}]
    (production / "look" / "look.json").write_text(json.dumps(look), encoding="utf-8")
    build_boards(production)
    plan = build_lighting_plan(production)
    assert [scene["time_of_day"] for scene in plan["scenes"]] == [
        "LATE AFTERNOON",
        "LATE AFTERNOON",
        "LATE AFTERNOON",
    ]
    for scene in plan["scenes"]:
        assert scene["practicals"] == "not named"
        assert "sun" in scene["key"].casefold()
        assert scene["practicals"].casefold() not in scene["prompt_note"].casefold() or scene["practicals"] == "not named"


def test_an_older_shot_list_is_superseded_and_not_checked_or_generated(tmp_path):
    production = _harbor(tmp_path)
    lock_props(production)
    build_boards(production)
    older = production / "shot-lists"
    older.mkdir(parents=True, exist_ok=True)
    bad = {
        "production_id": "harbor-night",
        "version": "1.0.0",
        "total_shots": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "shots": [
            _shot(
                "s01-sh99",
                "The scarf on the left shoulder.",
                props_in_shot=[{"prop_id": "red-scarf"}],
            )
        ],
    }
    (older / "shot-list.json").write_text(json.dumps(bad), encoding="utf-8")
    check = check_continuity(production)
    stored = json.loads((older / "shot-list.json").read_text(encoding="utf-8"))
    assert stored["superseded"] is True
    assert stored["superseded_by"] == "storyboard/shot-list.json"
    assert check["verdict"] == "clear"
    assert any(item["path"] == "shot-lists/shot-list.json" for item in check["skipped_sources"])
    assert "not checked for drift" in check["summary"].casefold()
    assert "not sent to generation" in check["summary"].casefold()
    assert (older / "shot-list.json").is_file()

    (production / "storyboard" / "storyboard.json").unlink()
    shots, source = load_shots(production)
    assert source == "storyboard/shot-list.json"
    assert all(shot["shot_id"] != "s01-sh99" for shot in shots)
    (production / "storyboard" / "shot-list.json").unlink()
    assert load_shots(production) == ([], "")


def test_shot_lengths_stay_in_range_unless_the_screenplay_names_a_hold(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    long = " ".join(["The worker crosses the yard"] * 12).strip() + "."
    short = "A small bell rings once now."
    treatment["scenes"][0]["what_happens"] = f"Hold for 14 seconds.\n\n{long}\n\n{short}"
    treatment["scenes"][0]["approximate_duration_seconds"] = 20
    treatment["deliverables"]["length"] = "20 seconds"
    _save_treatment(production, treatment)
    (production / "storyboard").mkdir(exist_ok=True)
    (production / "storyboard" / "pacing-limits.json").write_text(
        json.dumps({"min_shot_seconds": 1.0, "max_shot_seconds": 12}),
        encoding="utf-8",
    )
    boards = build_boards(production)
    durations = {frame["shot_id"]: frame["duration_seconds"] for frame in boards["frames"]}
    assert 14 in durations.values()
    for shot_id, duration in durations.items():
        if duration == 14:
            continue
        assert 1.0 <= duration <= 12.0, shot_id
    note = boards["pacing"]["note"]
    assert "1s and 12s" in note or "1.0s and 12s" in note or "between 1" in note
    assert any("screenplay names a hold" in line for line in boards["pacing"]["adjustments"])
    assert any("was " in line and "is " in line for line in boards["pacing"]["adjustments"])
    assert "20" in note


def test_graphics_research_reads_the_year_from_the_logline_and_the_world(tmp_path):
    plain = _harbor(tmp_path / "plain")
    unnamed = write_research(plain)
    unnamed_text = " ".join(item["text"] for item in unnamed["items"])
    assert "or a year" in unnamed_text

    production = _harbor(tmp_path / "dated")
    treatment = load_treatment(production)
    treatment["logline"] = "A night worker in 1984 ties a red scarf."
    treatment["world_and_period"] = "A harbor city in 1984."
    _save_treatment(production, treatment)
    research = write_research(production)
    years = [item for item in research["items"] if item["item_id"].startswith("period-year")]
    fields = {item["source_field"] for item in years}
    assert fields == {"logline", "world_and_period"}
    assert {item["text"] for item in years} == {"Year: 1984."}
    text = " ".join(item["text"] for item in research["items"])
    assert "or a year" not in text
    assert "do not name a year" not in text.casefold()


def test_the_schedule_lists_hero_props_and_writes_safety_in_full_sentences(tmp_path):
    production = _harbor(tmp_path)
    lock_props(production)
    lock_costumes(production)
    lock_makeup(production)
    build_package(production)
    build_boards(production)
    build_lighting_plan(production)
    build_breakdown(production)
    schedule = build_schedule(production)
    props = [prop for day in schedule["days"] for setup in day["setups"] for prop in setup["props"]]
    assert "Red scarf" in props
    markdown = (production / "schedule" / "shooting-schedule.md").read_text(encoding="utf-8")
    assert " Safety." not in markdown
    shot_lines = [line for line in markdown.splitlines() if line.startswith("- ") and "s01-sh03" in line]
    assert shot_lines
    assert any("real fall" in line for line in shot_lines)
    assert all(line.rstrip()[-1] in ".!?" for line in shot_lines)


def test_reconform_replaces_the_stale_final_pass_failure(tmp_path):
    production = _harbor(tmp_path)
    stale = (
        "Offline draft. The final model pass failed (Expecting value: line 1 column 1 (char 0)). "
        "The earlier draft was kept."
    )
    treatment = load_treatment(production)
    treatment["status"] = "draft"
    treatment["approval"] = {"state": "pending", "by": None, "at": None, "note": ""}
    treatment["draft_note"] = stale
    _save_treatment(production, treatment)
    note = _reconform_note(stale, "abc" * 8, [], final=True, repaired=True)
    assert "final model pass failed" not in note.casefold()
    assert "earlier draft was kept" not in note.casefold()
    assert "Nothing new was booked." in note
    assert "Repaired from a truncated paid reply" in note

    revised = json.loads(json.dumps(load_treatment(production)))
    revised["logline"] = "A night worker ties a red scarf and stays on the dock."
    request_hash = "d" * 64
    cache = production / "runs" / "run-1" / "provider-cache.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {
                "calls": {
                    request_hash: {
                        "status": "settled",
                        "purpose": "final",
                        "text": json.dumps(revised),
                        "stop_reason": "end_turn",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    result = Director(production).reconform(request_hash, run_id="run-1")
    saved = load_treatment(production)
    assert "final model pass failed" not in saved["draft_note"].casefold()
    assert "earlier draft was kept" not in saved["draft_note"].casefold()
    assert "Nothing new was booked." in result["draft_note"]
    assert saved["logline"] == revised["logline"]
    assert saved["status"] == "draft"


def test_redo_previs_is_offline_and_does_not_touch_an_approved_gate(tmp_path):
    production = _harbor(tmp_path)
    try:
        run_studio(production, run_id="first-film-1", redo="previs", live=True)
    except StudioError as exc:
        assert "offline only" in str(exc).casefold()
    else:
        raise AssertionError("A live redo was allowed.")

    first = run_studio(production, run_id="first-film-1")
    assert first["stopped_at"] == "treatment"
    LineProducer.open(production, "first-film-1").approve_gate(
        "treatment", "approved", "ron", note="The treatment can go forward."
    )
    redone = run_studio(production, run_id="first-film-1", redo="previs")
    assert redone["status"] == "stopped"
    assert redone["stopped_at"] == "previs"
    assert redone["spent_usd"] == 0
    assert (production / "storyboard" / "shot-list.json").is_file()
    assert (production / "continuity" / "continuity-check.json").is_file()
    producer = LineProducer.open(production, "first-film-1")
    assert producer.gate_decision("previs") != "approved"
    assert producer.gate_decision("generation") != "approved"

    producer.approve_gate("previs", "approved", "ron", note="The package can go forward.")
    before = (production / "storyboard" / "storyboard.json").read_text(encoding="utf-8")
    try:
        run_studio(production, run_id="first-film-1", redo="previs")
    except StudioError as exc:
        assert "already approved" in str(exc).casefold()
    else:
        raise AssertionError("Redo changed an approved previs gate.")
    assert (production / "storyboard" / "storyboard.json").read_text(encoding="utf-8") == before
    assert LineProducer.open(production, "first-film-1").gate_decision("previs") == "approved"
