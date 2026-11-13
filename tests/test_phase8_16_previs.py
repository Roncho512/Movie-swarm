"""Phase 8.16 previs follow-ups. Harbor Night and synthetic shots. No paid call.

The engine stays generic. A film's names and props are data, not code.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.assistant_director import build_schedule
from movie_swarm.director import Director
from movie_swarm.gaffer import build_lighting_plan
from movie_swarm.handoff import write_handoff
from movie_swarm.line_producer import LineProducer
from movie_swarm.mentions import advertising_phrases, previs_advertising_hits
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.stunts import build_breakdown
from movie_swarm.treatment_doc import load_treatment, treatment_json_path


def _harbor(tmp_path: Path) -> Path:
    dest = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", dest)
    return dest


def _save_treatment(production: Path, treatment: dict) -> None:
    write_handoff(treatment_json_path(production), treatment, schema="treatment")


def _wardrobe(production: Path, name: str = "Mina Cole", character_id: str = "mina-cole") -> None:
    folder = production / "wardrobe"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "costume-definitions.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": production.name,
                "status": "draft",
                "characters": [
                    {
                        "character_id": character_id,
                        "name": name,
                        "aliases": [],
                        "locked_spec": "A dark coat, worn.",
                        "garment": "coat",
                        "color": "dark",
                        "condition": "worn",
                        "changes": [],
                        "attributes": [
                            {
                                "attribute_id": "coat",
                                "label": "coat",
                                "value": "dark coat",
                                "must_be_stated_when_visible": True,
                                "required_phrases": ["dark coat"],
                                "forbidden_phrases": ["light coat"],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _makeup(production: Path, name: str = "Mina Cole", character_id: str = "mina-cole") -> None:
    folder = production / "makeup"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "makeup-definitions.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": production.name,
                "status": "draft",
                "characters": [
                    {
                        "character_id": character_id,
                        "name": name,
                        "aliases": [],
                        "locked_spec": "Short hair. No added effect.",
                        "makeup": "none named",
                        "hair": "short",
                        "effects": [],
                        "changes": [],
                        "attributes": [
                            {
                                "attribute_id": "hair",
                                "label": "hair",
                                "value": "short",
                                "must_be_stated_when_visible": True,
                                "required_phrases": ["short hair"],
                                "forbidden_phrases": ["long hair"],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _vehicle(production: Path, *, nouns: list[str] | None = None, second: bool = False) -> None:
    props = [
        {
            "prop_id": "dusty-bike",
            "name": "Dusty machine",
            "kind": "vehicle",
            "aliases": ["machine"],
            "locked_spec": "One pipe on the right.",
            "reference_images": [],
            "attributes": [
                {
                    "attribute_id": "pipe",
                    "label": "pipe",
                    "value": "right",
                    "must_be_stated_when_visible": True,
                    "required_phrases": ["pipe on the right"],
                    "forbidden_phrases": ["pipe on the left"],
                }
            ],
        }
    ]
    if nouns is not None:
        props[0]["generic_nouns"] = nouns
    if second:
        props.append(
            {
                "prop_id": "second-bike",
                "name": "Second machine",
                "kind": "vehicle",
                "aliases": ["second machine"],
                "locked_spec": "A second pipe on the right.",
                "reference_images": [],
                "attributes": [
                    {
                        "attribute_id": "pipe",
                        "label": "pipe",
                        "value": "right",
                        "must_be_stated_when_visible": True,
                        "required_phrases": ["pipe on the right"],
                        "forbidden_phrases": [],
                    }
                ],
            }
        )
    (production / "props" / "prop-definitions.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": production.name,
                "status": "draft",
                "props": props,
            }
        ),
        encoding="utf-8",
    )


def test_a_pronoun_inherits_the_only_character_and_wardrobe_follows(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["characters"] = [
        {"name": "Mina Cole", "role": "protagonist", "look": "Short hair. A dark coat."}
    ]
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. DOCK - NIGHT",
            "what_happens": (
                "Mina Cole stands under the lamp.\n\n"
                "He checks his cuff.\n\n"
                "His glove stays on."
            ),
            "emotional_purpose": "The night is ordinary.",
            "approximate_duration_seconds": 9,
            "coverage_intent": "",
        }
    ]
    _save_treatment(production, treatment)
    _wardrobe(production)
    _makeup(production)
    from movie_swarm.costume import lock_costumes
    from movie_swarm.makeup import lock_makeup

    lock_costumes(production)
    lock_makeup(production)
    boards = build_boards(production)
    shots = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    inherited = [shot for shot in shots if shot["shot_id"] in {"s01-sh02", "s01-sh03"}]
    assert inherited
    for shot in inherited:
        assert shot["characters_in_shot"] == ["Mina Cole"]
        assert "dark coat" in shot["generation_prompt"].casefold()
        assert "short hair" in shot["generation_prompt"].casefold()
    notes = [item for item in boards["tag_notes"] if item["kind"] == "inherited-character"]
    assert {item["shot_id"] for item in notes} >= {"s01-sh02", "s01-sh03"}
    assert "needs review" not in json.dumps(boards["tag_notes"]).casefold()


def test_an_ambiguous_pronoun_is_not_guessed_and_is_listed_for_review(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["characters"] = [
        {"name": "Mina Cole", "role": "protagonist", "look": "A dark coat."},
        {"name": "Jonah Pell", "role": "support", "look": "A grey cap."},
    ]
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. DOCK - NIGHT",
            "what_happens": "Mina Cole and Jonah Pell wait by the lamp.\n\nHe looks at the water.",
            "emotional_purpose": "Two people.",
            "approximate_duration_seconds": 8,
            "coverage_intent": "",
        }
    ]
    _save_treatment(production, treatment)
    lock_props(production)
    boards = build_boards(production)
    shots = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    third = next(shot for shot in shots if shot["shot_id"] == "s01-sh02")
    assert "characters_in_shot" not in third
    review = [item for item in boards["tag_notes"] if item["shot_id"] == "s01-sh02"]
    assert review and "needs review" in review[0]["detail"].casefold()
    check = check_continuity(production)
    listed = [item for item in check["reviews"] if item["shot_id"] == "s01-sh02"]
    assert listed
    assert "needs review" in listed[0]["detail"].casefold()
    assert check["verdict"] == "clear"


def test_one_vehicle_matches_a_kind_noun_and_two_vehicles_do_not(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    treatment = load_treatment(production)
    treatment["hero_props"] = []
    treatment["scenes"][0]["heading"] = "EXT. YARD - DAY"
    treatment["scenes"][0]["what_happens"] = "His bike waits. The motorcycle is still."
    _save_treatment(production, treatment)
    lock_props(production)
    build_boards(production)
    shots = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    for shot in shots:
        assert "dusty-bike" in shot.get("vehicles_in_shot") or []
        assert "pipe on the right" in shot["generation_prompt"].casefold()

    other = _harbor(tmp_path / "two")
    _vehicle(other, second=True)
    treatment = load_treatment(other)
    treatment["hero_props"] = []
    treatment["scenes"][0]["heading"] = "EXT. YARD - DAY"
    treatment["scenes"][0]["what_happens"] = "His bike waits in the yard for a moment."
    _save_treatment(other, treatment)
    lock_props(other)
    build_boards(other)
    shots = json.loads((other / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    assert all(not shot.get("vehicles_in_shot") for shot in shots)

    claimed = _harbor(tmp_path / "claimed")
    _vehicle(claimed, nouns=["bike"], second=True)
    treatment = load_treatment(claimed)
    treatment["hero_props"] = []
    treatment["scenes"][0]["heading"] = "EXT. YARD - DAY"
    treatment["scenes"][0]["what_happens"] = "His bike waits in the yard for a moment."
    _save_treatment(claimed, treatment)
    locked = lock_props(claimed)
    assert locked["props"][0]["generic_nouns"] == ["bike"]
    build_boards(claimed)
    shots = json.loads((claimed / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    assert any(shot.get("vehicles_in_shot") == ["dusty-bike"] for shot in shots)


def test_a_repeated_action_carries_one_prop_and_reports_it(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    treatment = load_treatment(production)
    treatment["hero_props"] = []
    treatment["scenes"][0]["heading"] = "EXT. YARD - DAY"
    treatment["scenes"][0]["what_happens"] = (
        "He starts the bike.\n\nHe kicks again. A cough. Nothing."
    )
    _save_treatment(production, treatment)
    lock_props(production)
    boards = build_boards(production)
    shots = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    second = next(shot for shot in shots if "kicks again" in shot["description"].casefold())
    assert second.get("vehicles_in_shot") == ["dusty-bike"]
    assert "pipe on the right" in second["generation_prompt"].casefold()
    carried = [item for item in boards["tag_notes"] if item["kind"] == "carried-prop"]
    assert carried and carried[0]["shot_id"] == second["shot_id"]
    check = check_continuity(production)
    assert any(item["kind"] == "carried" and item["shot_id"] == second["shot_id"] for item in check["reviews"])

    crowded = _harbor(tmp_path / "crowded")
    definitions = json.loads((crowded / "props" / "prop-definitions.json").read_text(encoding="utf-8"))
    _vehicle(crowded)
    extra = definitions["props"][0]
    (crowded / "props").mkdir(exist_ok=True)
    current = json.loads((crowded / "props" / "prop-definitions.json").read_text(encoding="utf-8"))
    current["props"].append(extra)
    (crowded / "props" / "prop-definitions.json").write_text(json.dumps(current), encoding="utf-8")
    treatment = load_treatment(crowded)
    treatment["hero_props"] = [{"name": "Red scarf", "locked_spec": "Wool, red.", "sidedness": "not locked"}]
    treatment["scenes"][0]["heading"] = "EXT. YARD - DAY"
    treatment["scenes"][0]["what_happens"] = (
        "The bike and the red scarf are both in frame.\n\nHe kicks again."
    )
    _save_treatment(crowded, treatment)
    lock_props(crowded)
    boards = build_boards(crowded)
    assert any(item["kind"] == "needs-review" and "more than one" in item["detail"] for item in boards["tag_notes"])


def test_placement_copy_drops_banned_phrases_including_negations(tmp_path):
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
                            "why": "The scarf is on her shoulder, not a product shot.",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    boards = build_boards(production)
    why = boards["featured_placements"][0]["why"]
    assert advertising_phrases(why) == []
    assert "product shot" not in why.casefold()
    assert "story" in why.casefold()
    blob = (production / "storyboard" / "storyboard.md").read_text(encoding="utf-8")
    prompts = " ".join(
        shot["generation_prompt"]
        for shot in json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    )
    assert advertising_phrases(blob + prompts) == []
    assert "hero shot of the product" not in (blob + prompts).casefold()
    close = [
        frame
        for frame in boards["frames"]
        if frame["shot_type"] in {"close", "detail", "extreme-close", "medium-close"}
        and "scarf" in frame["what_we_see"].casefold()
    ]
    if close:
        assert "the detail stays readable" in close[0]["camera"].casefold()

    quiet = _harbor(tmp_path / "quiet")
    lock_props(quiet)
    (quiet / "production-brief.json").write_text(
        json.dumps(
            {
                "featured_product": {
                    "product": "Red scarf",
                    "also_known_as": ["scarf"],
                    "rules": ["Keep the scarf in the story."],
                    "moments": [{"when": "red scarf", "why": "The scarf is already on her shoulder."}],
                }
            }
        ),
        encoding="utf-8",
    )
    quiet_boards = build_boards(quiet)
    assert all("the detail stays readable" not in frame["camera"].casefold() for frame in quiet_boards["frames"])

    planted = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))
    planted["shots"][0]["generation_prompt"] += " This is a product shot."
    (production / "storyboard" / "shot-list.json").write_text(json.dumps(planted), encoding="utf-8")
    check = check_continuity(production)
    assert check["verdict"] == "drift"
    assert any(item["kind"] == "banned-phrase" and item["observed"] == "product shot" for item in check["findings"])
    assert previs_advertising_hits(production)


def test_remaining_daylight_is_not_a_time_of_day_change(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["color_and_light_plan"] = "Low sun."
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. WASH - PRE-DUSK",
            "what_happens": "He has fifteen minutes of day left. Maybe less.",
            "emotional_purpose": "The light is leaving.",
            "approximate_duration_seconds": 4,
            "coverage_intent": "",
        }
    ]
    _save_treatment(production, treatment)
    build_boards(production)
    plan = build_lighting_plan(production)
    assert plan["scenes"][0]["continuity"]["verdict"] == "clear"
    assert plan["continuity"] == "clear"

    treatment["scenes"][0]["what_happens"] = "Night falls on the wash."
    _save_treatment(production, treatment)
    build_boards(production)
    changed = build_lighting_plan(production)
    assert changed["scenes"][0]["continuity"]["verdict"] == "drift"
    assert any("night" in item["detail"].casefold() for item in changed["scenes"][0]["continuity"]["findings"])


def test_every_stunt_beat_is_on_the_safety_list(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["scenes"][0]["heading"] = "EXT. YARD - DAY"
    treatment["scenes"][0]["what_happens"] = "He kicks again. A cough. Nothing."
    treatment["action_and_stunt_beats"] = [
        "Three kicks on the stand.",
        "She ties the scarf and steps onto the dock.",
    ]
    _save_treatment(production, treatment)
    lock_props(production)
    build_boards(production)
    build_breakdown(production)
    schedule = build_schedule(production)
    beats = {item["beat_id"] for item in schedule["safety"]}
    assert beats >= {"beat-001", "beat-002"}
    for item in schedule["safety"]:
        assert "real fall" in item["note"] or "no special safety needs, per stunt rules" in item["note"].casefold()
        assert item["note"].rstrip()[-1] in ".!?"
    markdown = (production / "schedule" / "shooting-schedule.md").read_text(encoding="utf-8")
    assert "beat-001" in markdown
    assert "beat-002" in markdown
    assert " Safety." not in markdown


def test_leftover_scene_time_fills_shots_that_still_have_room(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    hold = "Hold this frame for four seconds. The yard is empty."
    named = "It takes three full seconds for the bell to show."
    others = "\n\n".join(f"A worker crosses the yard on pass {index}." for index in range(4))
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. YARD - DAY",
            "what_happens": f"{hold}\n\n{named}\n\n{others}",
            "emotional_purpose": "Time to spare.",
            "approximate_duration_seconds": 45,
            "coverage_intent": "",
        }
    ]
    treatment["deliverables"]["length"] = "45 seconds"
    _save_treatment(production, treatment)
    (production / "storyboard").mkdir(exist_ok=True)
    (production / "storyboard" / "pacing-limits.json").write_text(
        json.dumps({"min_shot_seconds": 1, "max_shot_seconds": 12}),
        encoding="utf-8",
    )
    boards = build_boards(production)
    durations = [frame["duration_seconds"] for frame in boards["frames"]]
    assert 4 in durations
    assert 3 in durations
    assert abs(sum(durations) - 45) < 0.05
    for duration in durations:
        if duration in {3, 4}:
            continue
        assert 1 <= duration <= 12

    short = _harbor(tmp_path / "short")
    treatment = load_treatment(short)
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. YARD - DAY",
            "what_happens": "Hold this frame for four seconds. The yard is empty.\n\nA worker crosses once.",
            "emotional_purpose": "Not enough room.",
            "approximate_duration_seconds": 45,
            "coverage_intent": "",
        }
    ]
    treatment["deliverables"]["length"] = "45 seconds"
    _save_treatment(short, treatment)
    (short / "storyboard").mkdir(exist_ok=True)
    (short / "storyboard" / "pacing-limits.json").write_text(
        json.dumps({"min_shot_seconds": 1, "max_shot_seconds": 12}),
        encoding="utf-8",
    )
    tight = build_boards(short)
    assert "no room" in tight["pacing"]["note"].casefold()
    assert abs(sum(frame["duration_seconds"] for frame in tight["frames"]) - 16) < 0.05


def test_reconform_clears_a_stale_note_on_an_approved_treatment(tmp_path):
    production = _harbor(tmp_path)
    producer = LineProducer.start(production, run_id="run-1", stage="treatment")
    producer.approve_gate("treatment", "approved", "ron", note="The treatment can go forward.")
    treatment = load_treatment(production)
    stale = (
        "Offline draft. The final model pass failed (Expecting value: line 1 column 1 (char 0)). "
        "The earlier draft was kept."
    )
    treatment["draft_note"] = stale
    kept_logline = treatment["logline"]
    kept_approval = json.loads(json.dumps(treatment["approval"]))
    kept_scenes = json.loads(json.dumps(treatment["scenes"]))
    _save_treatment(production, treatment)
    request_hash = "e" * 64
    cache = production / "runs" / "run-1" / "provider-cache.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cached = json.loads(json.dumps(load_treatment(production)))
    cached["logline"] = "A different line that must not replace the approved one."
    cache.write_text(
        json.dumps({"calls": {request_hash: {"status": "settled", "purpose": "final", "text": json.dumps(cached)}}}),
        encoding="utf-8",
    )
    result = Director(production).reconform(request_hash, run_id="run-1")
    saved = load_treatment(production)
    assert saved["status"] == "approved"
    assert saved["approval"] == kept_approval
    assert saved["logline"] == kept_logline
    assert saved["scenes"] == kept_scenes
    assert "final model pass failed" not in saved["draft_note"].casefold()
    assert "earlier draft was kept" not in saved["draft_note"].casefold()
    assert "nothing new was booked" in result["draft_note"].casefold()
    assert result["status"] == "approved"
    assert LineProducer.open(production, "run-1").gate_decision("treatment") == "approved"
    markdown = (production / "treatment" / "treatment.md").read_text(encoding="utf-8")
    assert "final model pass failed" not in markdown.casefold()
    assert "Status: approved." in markdown
