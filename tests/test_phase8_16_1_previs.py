"""Phase 8.16.1. The storyboard must name people with the people matcher.

A locked character who is not already on the shot used to call ``mentioned``
after Phase 8.16 dropped that import. Harbor Night only ever resolved the
one person who was in the shot, so the suite never took that branch.

This run is the offline studio previs. No paid call. Nothing from The Last Marker.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.line_producer import LineProducer
from movie_swarm.mentions import advertising_phrases, previs_advertising_hits
from movie_swarm.paths import repo_root
from movie_swarm.studio import run_studio
from movie_swarm.treatment_doc import load_treatment


def _harbor(tmp_path: Path) -> Path:
    dest = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", dest)
    return dest


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _character(name: str, character_id: str, *, garment: str, phrase: str, forbidden: str) -> dict:
    return {
        "character_id": character_id,
        "name": name,
        "aliases": [],
        "locked_spec": phrase,
        "garment": garment,
        "color": "not named",
        "condition": "worn",
        "changes": [],
        "attributes": [
            {
                "attribute_id": garment,
                "label": garment,
                "value": phrase,
                "must_be_stated_when_visible": True,
                "required_phrases": [phrase],
                "forbidden_phrases": [forbidden],
            }
        ],
    }


def _makeup(name: str, character_id: str, phrase: str, forbidden: str) -> dict:
    return {
        "character_id": character_id,
        "name": name,
        "aliases": [],
        "locked_spec": phrase,
        "makeup": "none named",
        "hair": phrase,
        "effects": [],
        "changes": [],
        "attributes": [
            {
                "attribute_id": "hair",
                "label": "hair",
                "value": phrase,
                "must_be_stated_when_visible": True,
                "required_phrases": [phrase],
                "forbidden_phrases": [forbidden],
            }
        ],
    }


def _yard(production: Path) -> None:
    """One vehicle, two locked people, pronoun shots, a kind noun, and a continuation."""
    treatment = load_treatment(production)
    treatment["characters"] = [
        {"name": "Mina Cole", "role": "protagonist", "look": "Short hair. A dark coat."},
        {"name": "Jonah Pell", "role": "support", "look": "A grey cap."},
    ]
    treatment["hero_props"] = [
        {
            "name": "Dusty machine",
            "locked_spec": "One pipe on the right. A kickstand.",
            "sidedness": "pipe on the right",
        }
    ]
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. YARD - DAY",
            "what_happens": (
                "Mina Cole stands under the lamp.\n\n"
                "He checks his cuff.\n\n"
                "His bike waits by the wall.\n\n"
                "He kicks again."
            ),
            "emotional_purpose": "The day is ordinary.",
            "approximate_duration_seconds": 12,
            "coverage_intent": "",
        }
    ]
    treatment["action_and_stunt_beats"] = [
        "He kicks the stand.",
        "She steps back from the wall.",
    ]
    treatment["color_and_light_plan"] = "Flat daylight. No sun in the lens."
    _write(production / "treatment" / "treatment.json", treatment)
    definitions = json.loads((production / "props" / "prop-definitions.json").read_text(encoding="utf-8"))
    definitions["props"] = [
        {
            "prop_id": "dusty-bike",
            "name": "Dusty machine",
            "kind": "vehicle",
            "aliases": ["machine"],
            "parts": ["kickstand"],
            "locked_spec": "One pipe on the right. A kickstand.",
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
    _write(production / "props" / "prop-definitions.json", definitions)
    _write(
        production / "wardrobe" / "costume-definitions.json",
        {
            "version": "1.0.0",
            "production_id": production.name,
            "status": "draft",
            "characters": [
                _character(
                    "Mina Cole",
                    "mina-cole",
                    garment="coat",
                    phrase="dark coat",
                    forbidden="light coat",
                ),
                _character(
                    "Jonah Pell",
                    "jonah-pell",
                    garment="cap",
                    phrase="grey cap",
                    forbidden="no cap",
                ),
            ],
        },
    )
    _write(
        production / "makeup" / "makeup-definitions.json",
        {
            "version": "1.0.0",
            "production_id": production.name,
            "status": "draft",
            "characters": [
                _makeup("Mina Cole", "mina-cole", "short hair", "long hair"),
                _makeup("Jonah Pell", "jonah-pell", "cropped hair", "long hair"),
            ],
        },
    )


def _approve_treatment(production: Path, run_id: str) -> None:
    first = run_studio(production, run_id=run_id)
    assert first["stopped_at"] == "treatment"
    LineProducer.open(production, run_id).approve_gate(
        "treatment", "approved", "ron", note="The treatment can go forward."
    )


def test_offline_previs_tags_pronouns_a_kind_noun_a_continuation_and_every_stunt(tmp_path):
    production = _harbor(tmp_path)
    _yard(production)
    _approve_treatment(production, "previs-1")
    result = run_studio(production, run_id="previs-1", redo="previs")
    assert result["status"] == "stopped"
    assert result["stopped_at"] == "previs"
    assert result["spent_usd"] == 0
    assert "nothing was spent" in result["message"].casefold()
    producer = LineProducer.open(production, "previs-1")
    assert producer.gate_decision("previs") != "approved"
    assert producer.gate_decision("generation") != "approved"

    board_path = production / "storyboard" / "storyboard.json"
    list_path = production / "storyboard" / "shot-list.json"
    assert board_path.is_file()
    assert (production / "storyboard" / "storyboard.md").is_file()
    assert list_path.is_file()
    boards = json.loads(board_path.read_text(encoding="utf-8"))
    shots = json.loads(list_path.read_text(encoding="utf-8"))["shots"]
    by_text = {shot["description"].casefold(): shot for shot in shots}

    pronouns = [by_text[key] for key in ("he checks his cuff.", "his bike waits by the wall.", "he kicks again.")]
    for shot in pronouns:
        assert shot["characters_in_shot"] == ["Mina Cole"]
        prompt = shot["generation_prompt"].casefold()
        assert "dark coat" in prompt
        assert "short hair" in prompt
        assert "grey cap" not in prompt
        assert "jonah" not in prompt

    bike = by_text["his bike waits by the wall."]
    assert bike["vehicles_in_shot"] == ["dusty-bike"]
    assert "pipe on the right" in bike["generation_prompt"].casefold()

    again = by_text["he kicks again."]
    assert again["vehicles_in_shot"] == ["dusty-bike"]
    carried = [item for item in boards["tag_notes"] if item["kind"] == "carried-prop"]
    assert carried and carried[0]["shot_id"] == again["shot_id"]
    assert "dusty machine" in carried[0]["detail"].casefold()

    locked = json.loads((production / "props" / "hero-props.json").read_text(encoding="utf-8"))
    vehicle = next(prop for prop in locked["props"] if prop["prop_id"] == "dusty-bike")
    assert vehicle["kind"] == "vehicle"
    assert vehicle["parts"] == ["kickstand"]

    breakdown = json.loads((production / "stunts" / "action-breakdown.json").read_text(encoding="utf-8"))
    schedule = json.loads((production / "schedule" / "shooting-schedule.json").read_text(encoding="utf-8"))
    beat_ids = {item["beat_id"] for item in breakdown["beats"]}
    safety_ids = {item["beat_id"] for item in schedule["safety"]}
    assert beat_ids
    assert beat_ids <= safety_ids
    markdown = (production / "schedule" / "shooting-schedule.md").read_text(encoding="utf-8")
    for beat_id in beat_ids:
        assert beat_id in markdown

    generated = (production / "storyboard" / "storyboard.md").read_text(encoding="utf-8")
    generated += " ".join(shot["generation_prompt"] for shot in shots)
    assert advertising_phrases(generated) == []
    assert previs_advertising_hits(production) == []


def test_the_harbor_night_fixture_previs_still_runs(tmp_path):
    production = _harbor(tmp_path)
    _approve_treatment(production, "harbor-1")
    result = run_studio(production, run_id="harbor-1", redo="previs")
    assert result["status"] == "stopped"
    assert result["stopped_at"] == "previs"
    assert result["spent_usd"] == 0
    shots = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]
    assert shots
    assert any("ada" in " ".join(shot.get("characters_in_shot") or []).casefold() for shot in shots)
    assert (production / "schedule" / "shooting-schedule.json").is_file()
    assert previs_advertising_hits(production) == []
    assert LineProducer.open(production, "harbor-1").gate_decision("previs") != "approved"
