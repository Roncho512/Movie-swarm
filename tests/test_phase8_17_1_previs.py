"""Phase 8.17.1. Absence stays absent in the continuity check, and a rider is not missed.

Harbor Night and synthetic shots. No paid call. The engine stays generic.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.costume import lock_costumes
from movie_swarm.handoff import write_handoff
from movie_swarm.makeup import lock_makeup
from movie_swarm.mentions import load_absence_phrases, load_kind_nouns, prop_frame_state
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.treatment_doc import load_treatment, treatment_json_path


def _harbor(tmp_path: Path) -> Path:
    dest = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", dest)
    return dest


def _save(production: Path, treatment: dict) -> None:
    write_handoff(treatment_json_path(production), treatment, schema="treatment")


def _scene(production: Path, what: str, *, characters: list[dict] | None = None, heading: str = "EXT. YARD - DAY") -> None:
    treatment = load_treatment(production)
    treatment["hero_props"] = []
    treatment["characters"] = characters or [
        {"name": "Mina Cole", "role": "protagonist", "look": "Short hair. A dark coat."}
    ]
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": heading,
            "what_happens": what,
            "emotional_purpose": "A test beat.",
            "approximate_duration_seconds": 8,
            "coverage_intent": "",
        }
    ]
    treatment["deliverables"]["length"] = "8 seconds"
    _save(production, treatment)


def _vehicle(production: Path, *, aliases: list[str] | None = None) -> None:
    (production / "props" / "prop-definitions.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": production.name,
                "status": "draft",
                "props": [
                    {
                        "prop_id": "dusty-bike",
                        "name": "Dusty machine",
                        "kind": "vehicle",
                        "aliases": aliases if aliases is not None else ["machine", "bike", "the bike"],
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
                ],
            }
        ),
        encoding="utf-8",
    )


def _wardrobe(production: Path) -> None:
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
                        "character_id": "mina-cole",
                        "name": "Mina Cole",
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


def _shots(production: Path) -> list[dict]:
    return json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]


def _by_text(shots: list[dict], snippet: str) -> dict:
    matches = [shot for shot in shots if snippet in shot["description"].casefold()]
    assert len(matches) == 1, snippet
    return matches[0]


def _prop() -> dict:
    return {
        "prop_id": "dusty-bike",
        "name": "Dusty machine",
        "kind": "vehicle",
        "aliases": ["machine", "bike", "the bike"],
    }


def test_perfect_tense_absence_is_clear_even_when_the_alias_includes_the_article():
    prop = _prop()
    props = [prop]
    kind = load_kind_nouns()
    absence = load_absence_phrases()
    clear = [
        "She has left the bike.",
        "He had left the bike.",
        "She has abandoned the bike.",
        "He had abandoned his bike.",
        "They have left the bike.",
    ]
    for line in clear:
        assert prop_frame_state(prop, line, props, kind, absence) == "absent", line
    assert prop_frame_state(prop, "She has left the bike in the lane.", props, kind, absence) == "ambiguous"
    assert prop_frame_state(prop, "He left the bike running.", props, kind, absence) == "ambiguous"
    assert prop_frame_state(prop, "His bike waits.", props, kind, absence) == "in-frame"


def test_an_absence_alias_is_not_a_continuity_finding(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(production, "She has left the bike.")
    lock_props(production)
    boards = build_boards(production)
    shot = _shots(production)[0]
    assert "vehicles_in_shot" not in shot
    assert "props_in_shot" not in shot
    assert "pipe on the right" not in shot["generation_prompt"].casefold()
    assert not any(item["kind"] == "needs-review" and "prop" in item["detail"].casefold() for item in boards["tag_notes"])
    check = check_continuity(production)
    assert check["verdict"] == "clear", check["findings"]
    assert not any(item.get("shot_id") == shot["shot_id"] for item in check["findings"])

    shown = _harbor(tmp_path / "shown")
    _vehicle(shown)
    _scene(shown, "The bike waits by the wall.")
    lock_props(shown)
    build_boards(shown)
    listed = json.loads((shown / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))
    waiting_shot = listed["shots"][0]
    waiting_shot.pop("vehicles_in_shot", None)
    waiting_shot.pop("props_in_shot", None)
    waiting_shot["generation_prompt"] = waiting_shot["description"]
    waiting_shot["continuity_notes"] = ""
    (shown / "storyboard" / "shot-list.json").write_text(json.dumps(listed), encoding="utf-8")
    waiting = check_continuity(shown)
    assert any(item["kind"] == "unstated" and item.get("prop_id") == "dusty-bike" for item in waiting["findings"])


def test_a_passing_shot_uses_ride_language_from_earlier_in_the_scene(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _wardrobe(production)
    _scene(
        production,
        "Mina Cole on a 1965 dusty machine. Cole rides in a low crouch. "
        "She has been riding for hours.\n\n"
        "LOW ANGLE. The machine passes camera.",
    )
    lock_props(production)
    lock_costumes(production)
    lock_makeup(production)
    boards = build_boards(production)
    passing = _by_text(_shots(production), "passes camera")
    assert passing["characters_in_shot"] == ["Mina Cole"]
    assert passing.get("vehicles_in_shot") == ["dusty-bike"]
    assert "dark coat" in passing["generation_prompt"].casefold()
    notes = [item for item in boards["tag_notes"] if item["shot_id"] == passing["shot_id"]]
    assert notes and notes[0]["kind"] == "inherited-character"
    assert "needs review" not in notes[0]["detail"].casefold()


def test_ride_language_in_the_scene_description_tags_the_passing_shot(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _wardrobe(production)
    _scene(production, "Mina Cole rides the machine for hours. She has been riding.", heading="EXT. YARD - DAY")
    screenplay = production / "screenplay" / "yard.md"
    screenplay.write_text("EXT. YARD - DAY\n\nLOW ANGLE. The machine passes camera.\n", encoding="utf-8")
    brief = {
        "production_id": production.name,
        "title": "Harbor Night",
        "screenplay_path": "screenplay/yard.md",
    }
    (production / "production-brief.json").write_text(json.dumps(brief), encoding="utf-8")
    lock_props(production)
    lock_costumes(production)
    lock_makeup(production)
    boards = build_boards(production)
    shots = _shots(production)
    assert len(shots) == 1
    passing = shots[0]
    assert "passes camera" in passing["description"].casefold()
    assert passing["characters_in_shot"] == ["Mina Cole"]
    assert passing.get("vehicles_in_shot") == ["dusty-bike"]
    assert "dark coat" in passing["generation_prompt"].casefold()
    assert not any(
        item["shot_id"] == passing["shot_id"] and "needs review" in item["detail"].casefold()
        for item in boards["tag_notes"]
    )


def test_a_passing_vehicle_with_no_clear_rider_is_flagged(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(production, "LOW ANGLE. The machine passes camera.")
    lock_props(production)
    boards = build_boards(production)
    shot = _shots(production)[0]
    assert "characters_in_shot" not in shot
    review = [item for item in boards["tag_notes"] if item["shot_id"] == shot["shot_id"]]
    assert review and "needs review" in review[0]["detail"].casefold()
    assert "rider" in review[0]["detail"].casefold()

    both = _harbor(tmp_path / "both")
    _vehicle(both)
    _scene(
        both,
        "Mina Cole rides the machine.\n\nJonah Pell rides the machine.\n\nLOW ANGLE. The machine passes camera.",
        characters=[
            {"name": "Mina Cole", "role": "protagonist", "look": "A dark coat."},
            {"name": "Jonah Pell", "role": "support", "look": "A grey cap."},
        ],
    )
    lock_props(both)
    boards = build_boards(both)
    passing = _by_text(_shots(both), "passes camera")
    assert "characters_in_shot" not in passing
    review = [item for item in boards["tag_notes"] if item["shot_id"] == passing["shot_id"]]
    assert review and "needs review" in review[0]["detail"].casefold()
