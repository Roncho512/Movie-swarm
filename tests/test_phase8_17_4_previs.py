"""Phase 8.17.4. A trace does not stop a prop carrying within a continuous beat.

Harbor Night and synthetic shots. No paid call. The engine stays generic.
The frame classifier, the storyboard review, and the continuity check share
prop_frame_state. A trace is unnamed. Carry is a storyboard tag. The check
follows that tag.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.handoff import write_handoff
from movie_swarm.mentions import load_absence_phrases, load_kind_nouns, prop_frame_state, prop_shown
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


def _scene(production: Path, what: str) -> None:
    treatment = load_treatment(production)
    treatment["hero_props"] = []
    treatment["characters"] = [
        {"name": "Mina Cole", "role": "protagonist", "look": "Short hair. A dark coat."}
    ]
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. YARD - DAY",
            "what_happens": what,
            "emotional_purpose": "A test beat.",
            "approximate_duration_seconds": 12,
            "coverage_intent": "",
        }
    ]
    treatment["deliverables"]["length"] = "12 seconds"
    _save(production, treatment)


def _vehicle(production: Path) -> None:
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
                        "aliases": ["machine", "bike", "the bike"],
                        "parts": ["throttle", "tire"],
                        "locked_spec": "One pipe on the right.",
                        "reference_images": ["props/dusty-bike/side.png"],
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


def _shots(production: Path) -> list[dict]:
    return json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]


def _frames(production: Path) -> list[dict]:
    return json.loads((production / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))["frames"]


def _by_text(shots: list[dict], snippet: str) -> dict:
    matches = [shot for shot in shots if snippet in shot["description"].casefold()]
    assert len(matches) == 1, snippet
    return matches[0]


def _locked(production: Path) -> dict:
    return json.loads((production / "props" / "hero-props.json").read_text(encoding="utf-8"))["props"][0]


def _state(prop: dict, line: str) -> str:
    return prop_frame_state(prop, line, [prop], load_kind_nouns(), load_absence_phrases())


def _carried(notes: list[dict], shot_id: str) -> list[dict]:
    return [item for item in notes if item["shot_id"] == shot_id and item["kind"] == "carried-prop"]


def _prop_review(notes: list[dict], shot_id: str) -> list[dict]:
    return [
        item
        for item in notes
        if item["shot_id"] == shot_id
        and item["kind"] == "needs-review"
        and "prop" in item["detail"].casefold()
    ]


def test_a_trace_in_a_continuous_beat_carries_the_prop(tmp_path):
    """Shot A rolls the throttle. Shot B looks down the road at tire tracks."""
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(
        production,
        "He rolls the throttle.\n\nHe looks toward the open road. The tire tracks lead south.",
    )
    lock_props(production)
    prop = _locked(production)
    boards = build_boards(production)
    shots = _shots(production)
    throttle = _by_text(shots, "rolls the throttle")
    look = _by_text(shots, "tire tracks lead south")
    assert look["shot_type"] == "medium"
    assert "he looks toward the open road" in look["description"].casefold()
    assert throttle.get("vehicles_in_shot") == ["dusty-bike"]
    assert _carried(boards["tag_notes"], throttle["shot_id"]) == []
    assert _state(prop, throttle["description"]) == "in-frame"

    assert _state(prop, look["description"]) == "unnamed"
    assert look.get("vehicles_in_shot") == ["dusty-bike"]
    assert "pipe on the right" in look["generation_prompt"].casefold()
    assert "props/dusty-bike/side.png" in (look.get("reference_images") or [])
    frame = next(item for item in _frames(production) if item["shot_id"] == look["shot_id"])
    assert any("Dusty machine" in item for item in frame["props_in_frame"])
    carried = _carried(boards["tag_notes"], look["shot_id"])
    assert len(carried) == 1
    assert "dusty machine" in carried[0]["detail"].casefold()
    assert _prop_review(boards["tag_notes"], look["shot_id"]) == []
    assert prop_shown(
        prop,
        look["description"],
        look.get("vehicles_in_shot") or [],
        [prop],
        load_kind_nouns(),
        load_absence_phrases(),
    )
    assert not prop_shown(prop, look["description"], [], [prop], load_kind_nouns(), load_absence_phrases())

    check = check_continuity(production)
    assert check["verdict"] == "clear", check["findings"]
    assert any(item["kind"] == "carried" and item["shot_id"] == look["shot_id"] for item in check["reviews"])
    assert not any(item.get("shot_id") == look["shot_id"] for item in check["findings"])


def test_a_trace_that_opens_the_shot_does_not_block_carry(tmp_path):
    """The first word is the part inside the trace. That is not a new subject."""
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(production, "He rolls the throttle.\n\nThe tire tracks lead south.")
    lock_props(production)
    prop = _locked(production)
    boards = build_boards(production)
    tracks = _by_text(_shots(production), "tire tracks lead south")
    assert _state(prop, tracks["description"]) == "unnamed"
    assert tracks.get("vehicles_in_shot") == ["dusty-bike"]
    assert _carried(boards["tag_notes"], tracks["shot_id"])
    assert _prop_review(boards["tag_notes"], tracks["shot_id"]) == []
    check = check_continuity(production)
    assert any(item["kind"] == "carried" and item["shot_id"] == tracks["shot_id"] for item in check["reviews"])
    assert not any(item.get("shot_id") == tracks["shot_id"] for item in check["findings"])


def test_a_trace_after_a_clear_absence_stays_untagged(tmp_path):
    """He has left the bike. A later tire-tracks shot does not bring it back."""
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(
        production,
        "He rolls the throttle.\n\n"
        "He has left the bike.\n\n"
        "He walks along the fence.\n\n"
        "The tire tracks lead south.",
    )
    lock_props(production)
    prop = _locked(production)
    boards = build_boards(production)
    shots = _shots(production)
    gone = _by_text(shots, "has left the bike")
    walked = _by_text(shots, "walks along the fence")
    tracks = _by_text(shots, "tire tracks lead south")
    assert _state(prop, gone["description"]) == "absent"
    assert _state(prop, tracks["description"]) == "unnamed"
    for shot in (gone, walked, tracks):
        assert "vehicles_in_shot" not in shot
        assert "props_in_shot" not in shot
        assert "pipe on the right" not in shot["generation_prompt"].casefold()
        assert "props/dusty-bike/side.png" not in (shot.get("reference_images") or [])
        assert _carried(boards["tag_notes"], shot["shot_id"]) == []
        assert _prop_review(boards["tag_notes"], shot["shot_id"]) == []
        assert not prop_shown(
            prop,
            shot["description"],
            shot.get("vehicles_in_shot") or [],
            [prop],
            load_kind_nouns(),
            load_absence_phrases(),
        )
    check = check_continuity(production)
    assert check["verdict"] == "clear", check["findings"]
    assert not any(
        item["shot_id"] in {gone["shot_id"], walked["shot_id"], tracks["shot_id"]}
        and "prop" in item["detail"].casefold()
        for item in check["reviews"]
    )
    assert not any(
        item.get("shot_id") in {gone["shot_id"], tracks["shot_id"]} for item in check["findings"]
    )


def test_a_trace_in_a_close_up_of_another_object_does_not_carry(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(
        production,
        "He rolls the throttle.\n\nClose on the lantern. The tire tracks cross the dusty glass.",
    )
    lock_props(production)
    prop = _locked(production)
    boards = build_boards(production)
    shots = _shots(production)
    close = _by_text(shots, "close on the lantern")
    assert "tire tracks" in close["description"].casefold()
    assert close["shot_type"] == "close"
    assert _state(prop, close["description"]) == "unnamed"
    assert "vehicles_in_shot" not in close
    assert "props_in_shot" not in close
    assert "pipe on the right" not in close["generation_prompt"].casefold()
    assert "props/dusty-bike/side.png" not in (close.get("reference_images") or [])
    assert _carried(boards["tag_notes"], close["shot_id"]) == []
    assert _by_text(shots, "rolls the throttle").get("vehicles_in_shot") == ["dusty-bike"]
    assert not prop_shown(
        prop,
        close["description"],
        [],
        [prop],
        load_kind_nouns(),
        load_absence_phrases(),
    )
    check = check_continuity(production)
    assert not any(item["shot_id"] == close["shot_id"] and item["kind"] == "carried" for item in check["reviews"])
    assert not any(item.get("shot_id") == close["shot_id"] for item in check["findings"])
