"""Phase 8.17.2. A perfect-tense absence with nothing after the object is clear.

Harbor Night and synthetic shots. No paid call. The engine stays generic.
The review flag and the frame classifier read the same phrase file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.handoff import write_handoff
from movie_swarm.mentions import load_absence_phrases, load_kind_nouns, prop_frame_state
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.treatment_doc import load_treatment, treatment_json_path
from movie_swarm.validate import validate_file


def _harbor(tmp_path: Path) -> Path:
    dest = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", dest)
    return dest


def _save(production: Path, treatment: dict) -> None:
    write_handoff(treatment_json_path(production), treatment, schema="treatment")


def _scene(production: Path, what: str, *, heading: str = "EXT. YARD - DAY") -> None:
    treatment = load_treatment(production)
    treatment["hero_props"] = []
    treatment["characters"] = [
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


def _vehicle(production: Path, *, aliases: list[str], prop_id: str = "dusty-bike", name: str = "Dusty machine") -> None:
    (production / "props" / "prop-definitions.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": production.name,
                "status": "draft",
                "props": [
                    {
                        "prop_id": prop_id,
                        "name": name,
                        "kind": "vehicle",
                        "aliases": aliases,
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


def _shots(production: Path) -> list[dict]:
    return json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))["shots"]


def _by_text(shots: list[dict], snippet: str) -> dict:
    matches = [shot for shot in shots if snippet in shot["description"].casefold()]
    assert len(matches) == 1, snippet
    return matches[0]


def _prop_review(notes: list[dict], shot_id: str) -> list[dict]:
    return [
        item
        for item in notes
        if item["shot_id"] == shot_id
        and item["kind"] == "needs-review"
        and "prop" in item["detail"].casefold()
    ]


def _bike() -> dict:
    return {
        "prop_id": "dusty-bike",
        "name": "Dusty machine",
        "kind": "vehicle",
        "aliases": ["machine", "bike", "the bike"],
    }


def _truck() -> dict:
    return {
        "prop_id": "yard-truck",
        "name": "Yard truck",
        "kind": "vehicle",
        "aliases": ["truck"],
    }


def test_the_shared_phrase_file_matches_its_schema():
    result = validate_file(repo_root() / "config" / "absence-phrases.json")
    assert result.ok, result.errors
    assert result.schema_name == "absence-phrases.schema.json"
    loaded = load_absence_phrases()
    assert loaded["conjunctions"] == ["and", "but", "or", "nor", "so", "yet"]


def test_a_perfect_tense_absence_with_nothing_after_the_object_is_clear():
    kind = load_kind_nouns()
    absence = load_absence_phrases()
    bike = _bike()
    truck = _truck()
    clear = [
        (bike, "He has left the bike."),
        (bike, "He has left the bike"),
        (bike, "He has left the bike, and he walks on."),
        (bike, "He has left the bike; she stays."),
        (truck, "She had left the truck"),
        (truck, "She had left the truck."),
        (truck, "They have left the truck, but the gate is shut."),
    ]
    for prop, line in clear:
        assert prop_frame_state(prop, line, [prop], kind, absence) == "absent", line
    flagged = [
        (bike, "He has left the bike running."),
        (bike, "He left the bike in the barn."),
        (bike, "He left the bike on its stand."),
        (bike, "He has left the bike there."),
        (truck, "She had left the truck in the yard."),
    ]
    for prop, line in flagged:
        assert prop_frame_state(prop, line, [prop], kind, absence) == "ambiguous", line


def test_the_review_flag_uses_the_same_phrase_rules(tmp_path):
    kind = load_kind_nouns()
    absence = load_absence_phrases()
    cases = [
        ("He has left the bike.", "absent", ["bike", "the bike"]),
        ("She had left the truck.", "absent", ["truck"]),
        ("He has left the bike running.", "ambiguous", ["bike", "the bike"]),
        ("He left the bike in the barn.", "ambiguous", ["bike", "the bike"]),
    ]
    for line, state, aliases in cases:
        folder = tmp_path / state / f"{abs(hash(line))}"
        folder.mkdir(parents=True)
        production = _harbor(folder)
        _vehicle(production, aliases=aliases, name="Hauler" if "truck" in line else "Dusty machine")
        _scene(production, line.replace("He ", "Mina Cole ").replace("She ", "Mina Cole "))
        lock_props(production)
        prop = json.loads((production / "props" / "hero-props.json").read_text(encoding="utf-8"))["props"][0]
        assert prop_frame_state(prop, line, [prop], kind, absence) == state
        boards = build_boards(production)
        shot = _shots(production)[0]
        assert "vehicles_in_shot" not in shot
        review = _prop_review(boards["tag_notes"], shot["shot_id"])
        check = check_continuity(production)
        listed = [
            item
            for item in check["reviews"]
            if item["shot_id"] == shot["shot_id"] and "prop" in item["detail"].casefold()
        ]
        if state == "absent":
            assert review == [], line
            assert listed == [], line
        else:
            assert review and "needs review" in review[0]["detail"].casefold()
            assert listed and listed[0]["detail"] == review[0]["detail"]
        assert check["verdict"] == "clear"


def test_a_walking_paragraph_with_later_in_and_on_is_not_a_review(tmp_path):
    """The s03-sh01 pattern: a perfect absence, then later words in and on, in one shot."""
    production = _harbor(tmp_path)
    _vehicle(production, aliases=["machine", "bike", "the bike"])
    _scene(
        production,
        "Mina walks. She has left the bike. She carries nothing. Her boots crunch on the yard stones. "
        "She is walking in the direction she was riding, following the faint tracks of people who came "
        "through here before her. Looking for something. Any sign of the path. Any marker.\n\n"
        "A lantern sits on the step.",
    )
    lock_props(production)
    boards = build_boards(production)
    shot = _by_text(_shots(production), "has left the bike")
    assert "on the yard" in shot["description"].casefold()
    assert "walking in the direction" in shot["description"].casefold()
    assert "vehicles_in_shot" not in shot
    assert "props_in_shot" not in shot
    assert "pipe on the right" not in shot["generation_prompt"].casefold()
    assert _prop_review(boards["tag_notes"], shot["shot_id"]) == []
    check = check_continuity(production)
    assert check["verdict"] == "clear", check["findings"]
    assert not any(
        item["shot_id"] == shot["shot_id"] and "prop" in item["detail"].casefold()
        for item in check["reviews"]
    )


def test_a_film_conjunction_list_is_shared_by_the_review_and_the_classifier(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production, aliases=["bike", "the bike"])
    _scene(production, "Mina Cole has left the bike and walks on.")
    lock_props(production)
    (production / "props" / "absence-phrases.json").write_text(
        json.dumps(
            {
                "ambiguous": ["left the {prop} and"],
                "closed_clause": {"conjunctions": ["and"]},
            }
        ),
        encoding="utf-8",
    )
    absence = load_absence_phrases(production)
    assert absence["conjunctions"] == ["and"]
    prop = json.loads((production / "props" / "hero-props.json").read_text(encoding="utf-8"))["props"][0]
    kind = load_kind_nouns(production)
    line = "Mina Cole has left the bike and walks on."
    assert prop_frame_state(prop, line, [prop], kind, absence) == "absent"
    boards = build_boards(production)
    shot = _shots(production)[0]
    assert _prop_review(boards["tag_notes"], shot["shot_id"]) == []

    (production / "props" / "absence-phrases.json").write_text(
        json.dumps(
            {
                "ambiguous": ["left the {prop} and"],
                "closed_clause": {"conjunctions": []},
            }
        ),
        encoding="utf-8",
    )
    absence = load_absence_phrases(production)
    assert absence["conjunctions"] == []
    assert prop_frame_state(prop, line, [prop], kind, absence) == "ambiguous"
    boards = build_boards(production)
    assert _prop_review(boards["tag_notes"], shot["shot_id"])
