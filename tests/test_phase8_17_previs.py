"""Phase 8.17. Absence, carry, riders, and a remainder that another scene can hold.

Harbor Night and synthetic shots. No paid call. The engine stays generic.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.costume import lock_costumes
from movie_swarm.handoff import write_handoff
from movie_swarm.makeup import lock_makeup
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


def _scene(production: Path, what: str, *, seconds: float = 8, characters: list[dict] | None = None) -> None:
    treatment = load_treatment(production)
    treatment["hero_props"] = []
    treatment["characters"] = characters or [
        {"name": "Mina Cole", "role": "protagonist", "look": "Short hair. A dark coat."}
    ]
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. YARD - DAY",
            "what_happens": what,
            "emotional_purpose": "A test beat.",
            "approximate_duration_seconds": seconds,
            "coverage_intent": "",
        }
    ]
    treatment["deliverables"]["length"] = f"{seconds:g} seconds"
    _save(production, treatment)


def _vehicle(production: Path, *, images: list[str] | None = None) -> None:
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
                        "aliases": ["machine"],
                        "locked_spec": "One pipe on the right.",
                        "reference_images": images or [],
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


def test_absence_phrases_do_not_put_the_prop_in_frame(tmp_path):
    lines = [
        "He has left the bike.",
        "She leaves the bike behind.",
        "He walks away from the bike.",
        "Without the bike, he walks on.",
        "He looks back at the bike from a distance.",
    ]
    for line in lines:
        production = _harbor(tmp_path / line[:12].replace(" ", "-"))
        _vehicle(production)
        _scene(production, line.replace("He ", "Mina Cole ").replace("She ", "Mina Cole "))
        lock_props(production)
        boards = build_boards(production)
        shot = _shots(production)[0]
        assert "vehicles_in_shot" not in shot, line
        assert "pipe on the right" not in shot["generation_prompt"].casefold(), line
        assert not any(
            item["kind"] == "needs-review" and "prop" in item["detail"].casefold() for item in boards["tag_notes"]
        ), line

    present = _harbor(tmp_path / "present")
    _vehicle(present)
    _scene(present, "His bike waits by the wall.")
    lock_props(present)
    build_boards(present)
    waiting = _shots(present)[0]
    assert waiting.get("vehicles_in_shot") == ["dusty-bike"]


def test_an_ambiguous_absence_is_not_guessed_and_is_listed_for_review(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(production, "He left the bike in the lane.")
    lock_props(production)
    boards = build_boards(production)
    shot = _shots(production)[0]
    assert "vehicles_in_shot" not in shot
    review = [
        item
        for item in boards["tag_notes"]
        if item["kind"] == "needs-review" and "prop" in item["detail"].casefold()
    ]
    assert review and "needs review" in review[0]["detail"].casefold()
    check = check_continuity(production)
    listed = [
        item
        for item in check["reviews"]
        if item["shot_id"] == shot["shot_id"] and "prop" in item["detail"].casefold()
    ]
    assert listed and "needs review" in listed[0]["detail"].casefold()
    assert check["verdict"] == "clear"


def test_a_film_can_replace_the_absence_list(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(production, "He steps off the bike.")
    lock_props(production)
    build_boards(production)
    assert _shots(production)[0].get("vehicles_in_shot") == ["dusty-bike"]

    (production / "props" / "absence-phrases.json").write_text(
        json.dumps({"phrases": ["steps off the {prop}"]}),
        encoding="utf-8",
    )
    build_boards(production)
    assert "vehicles_in_shot" not in _shots(production)[0]


def test_a_close_up_of_another_object_does_not_inherit_the_vehicle(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production, images=["props/dusty-bike/side.png"])
    _scene(
        production,
        "He starts the bike.\n\nClose on the lantern. The glass is still.\n\nThe lantern sits on the step again.",
    )
    lock_props(production)
    boards = build_boards(production)
    shots = _shots(production)
    close = _by_text(shots, "close on the lantern")
    other = _by_text(shots, "lantern sits")
    for shot in (close, other):
        assert "vehicles_in_shot" not in shot
        assert "reference_images" not in shot
        assert "pipe on the right" not in shot["generation_prompt"].casefold()
    assert not any(item["kind"] == "carried-prop" and item["shot_id"] == close["shot_id"] for item in boards["tag_notes"])
    assert _by_text(shots, "starts the bike").get("vehicles_in_shot") == ["dusty-bike"]


def test_an_absence_leaves_nothing_for_the_next_shot_to_carry(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production, images=["props/dusty-bike/side.png"])
    _scene(production, "He starts the bike.\n\nHe has left the bike.\n\nHe kicks again.")
    lock_props(production)
    build_boards(production)
    shots = _shots(production)
    assert "vehicles_in_shot" not in _by_text(shots, "has left the bike")
    kicked = _by_text(shots, "kicks again")
    assert "vehicles_in_shot" not in kicked
    assert "pipe on the right" not in kicked["generation_prompt"].casefold()
    assert "props/dusty-bike/side.png" not in (kicked.get("reference_images") or [])


def test_a_fade_or_hold_does_not_carry_a_prop_and_is_listed_for_review(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production, images=["props/dusty-bike/side.png"])
    _scene(
        production,
        "He starts the bike.\n\nThe lantern fades again. Silence. Hold for three seconds.",
    )
    lock_props(production)
    boards = build_boards(production)
    shots = _shots(production)
    fade = _by_text(shots, "fades again")
    assert "vehicles_in_shot" not in fade
    assert "pipe on the right" not in fade["generation_prompt"].casefold()
    assert "props/dusty-bike/side.png" not in (fade.get("reference_images") or [])
    notes = [item for item in boards["tag_notes"] if item["shot_id"] == fade["shot_id"]]
    assert notes and notes[0]["kind"] == "needs-review"
    assert "needs review" in notes[0]["detail"].casefold()
    check = check_continuity(production)
    assert any(
        item["shot_id"] == fade["shot_id"] and "needs review" in item["detail"].casefold()
        for item in check["reviews"]
    )


def test_one_rider_is_tagged_when_the_vehicle_passes(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _wardrobe(production)
    _scene(production, "Mina Cole rides the bike down the lane.\n\nThe bike passes camera.")
    lock_props(production)
    lock_costumes(production)
    lock_makeup(production)
    boards = build_boards(production)
    passing = _by_text(_shots(production), "passes camera")
    assert passing["characters_in_shot"] == ["Mina Cole"]
    assert passing.get("vehicles_in_shot") == ["dusty-bike"]
    assert "dark coat" in passing["generation_prompt"].casefold()
    assert "pipe on the right" in passing["generation_prompt"].casefold()
    notes = [item for item in boards["tag_notes"] if item["shot_id"] == passing["shot_id"]]
    assert notes and notes[0]["kind"] == "inherited-character"
    assert "needs review" not in notes[0]["detail"].casefold()


def test_an_ambiguous_rider_is_not_guessed_and_is_listed_for_review(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production)
    _scene(
        production,
        "Mina Cole rides the bike.\n\nJonah Pell rides the bike.\n\nThe bike passes camera.",
        characters=[
            {"name": "Mina Cole", "role": "protagonist", "look": "A dark coat."},
            {"name": "Jonah Pell", "role": "support", "look": "A grey cap."},
        ],
    )
    lock_props(production)
    boards = build_boards(production)
    passing = _by_text(_shots(production), "passes camera")
    assert "characters_in_shot" not in passing
    review = [item for item in boards["tag_notes"] if item["shot_id"] == passing["shot_id"]]
    assert review and "needs review" in review[0]["detail"].casefold()
    assert "rider" in review[0]["detail"].casefold()
    check = check_continuity(production)
    listed = [item for item in check["reviews"] if item["shot_id"] == passing["shot_id"]]
    assert listed and listed[0]["kind"] == "rider"
    assert "needs review" in listed[0]["detail"].casefold()


def test_a_scene_remainder_lands_in_another_scene_that_has_room(tmp_path):
    production = _harbor(tmp_path)
    treatment = load_treatment(production)
    treatment["scenes"] = [
        {
            "scene_id": "s01",
            "heading": "EXT. YARD - DAY",
            "what_happens": "\n\n".join(f"A worker crosses the yard on pass {index}." for index in range(4)),
            "emotional_purpose": "Room to spare.",
            "approximate_duration_seconds": 12,
            "coverage_intent": "",
        },
        {
            "scene_id": "s02",
            "heading": "EXT. LAMP - DAY",
            "what_happens": (
                "A gull crosses the lamp on the first pass.\n\n"
                "A gull crosses the lamp on the second pass."
            ),
            "emotional_purpose": "No room in this scene.",
            "approximate_duration_seconds": 30,
            "coverage_intent": "",
        },
    ]
    treatment["deliverables"]["length"] = "42 seconds"
    _save(production, treatment)
    (production / "storyboard").mkdir(exist_ok=True)
    (production / "storyboard" / "pacing-limits.json").write_text(
        json.dumps({"min_shot_seconds": 1, "max_shot_seconds": 12}),
        encoding="utf-8",
    )
    boards = build_boards(production)
    durations = [frame["duration_seconds"] for frame in boards["frames"]]
    assert abs(sum(durations) - 42) < 0.05
    by_scene: dict[str, float] = {}
    for frame in boards["frames"]:
        by_scene[frame["scene_id"]] = round(by_scene.get(frame["scene_id"], 0) + frame["duration_seconds"], 3)
    assert by_scene["s02"] == 24
    assert abs(by_scene["s01"] - 18) < 0.05
    note = boards["pacing"]["note"].casefold()
    assert "scene s01 absorbed" in note or "it absorbed" in note
    assert "s02" in note and "absorbed" in note
    assert "no room" not in note

    tight = _harbor(tmp_path / "tight")
    treatment = load_treatment(tight)
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
    _save(tight, treatment)
    (tight / "storyboard").mkdir(exist_ok=True)
    (tight / "storyboard" / "pacing-limits.json").write_text(
        json.dumps({"min_shot_seconds": 1, "max_shot_seconds": 12}),
        encoding="utf-8",
    )
    blocked = build_boards(tight)
    assert "no room" in blocked["pacing"]["note"].casefold()
    assert abs(sum(frame["duration_seconds"] for frame in blocked["frames"]) - 16) < 0.05
