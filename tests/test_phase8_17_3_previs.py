"""Phase 8.17.3. A trace a part leaves behind is not the prop.

Harbor Night and synthetic shots. No paid call. The engine stays generic.
The review flag, the frame classifier, and the continuity check read one phrase file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.handoff import write_handoff
from movie_swarm.mentions import load_absence_phrases, load_kind_nouns, prop_frame_state, prop_mentioned
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.treatment_doc import load_treatment, treatment_json_path
from movie_swarm.validate import validate_file


_SHARED_TRACE_NOUNS = [
    "tracks",
    "track",
    "marks",
    "prints",
    "footprints",
    "ruts",
    "skid marks",
    "tread marks",
    "trail",
    "imprint",
]


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


def _vehicle(
    production: Path,
    *,
    aliases: list[str],
    parts: list[str] | None = None,
    prop_id: str = "dusty-bike",
    name: str = "Dusty machine",
) -> None:
    prop = {
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
    if parts:
        prop["parts"] = parts
    (production / "props" / "prop-definitions.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": production.name,
                "status": "draft",
                "props": [prop],
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


def _hauler(parts: list[str], aliases: list[str] | None = None) -> dict:
    return {
        "prop_id": "yard-hauler",
        "name": "Yard hauler",
        "kind": "vehicle",
        "aliases": aliases or ["hauler"],
        "parts": parts,
    }


def _state(prop: dict, line: str, absence: dict | None = None) -> str:
    kind = load_kind_nouns()
    loaded = absence if absence is not None else load_absence_phrases()
    return prop_frame_state(prop, line, [prop], kind, loaded)


def _named(prop: dict, line: str, absence: dict | None = None) -> bool:
    kind = load_kind_nouns()
    loaded = absence if absence is not None else load_absence_phrases()
    return prop_mentioned(prop, line, [prop], kind, loaded)


def test_the_shared_trace_nouns_match_the_schema():
    result = validate_file(repo_root() / "config" / "absence-phrases.json")
    assert result.ok, result.errors
    loaded = load_absence_phrases()
    assert loaded["trace_nouns"] == _SHARED_TRACE_NOUNS


def test_a_part_followed_by_a_trace_noun_is_not_the_prop():
    tire = _hauler(["tire", "front tire"])
    skid = _hauler(["skid"])
    tread = _hauler(["tread"])
    hub = _hauler(["hub"])
    unnamed = [
        (tire, "following the faint tire tracks of riders who came through here before her"),
        (tire, "the faint tire-tracks of riders"),
        (tire, "tire - tracks in the dust"),
        (skid, "skid marks on the road"),
        (skid, "skid-marks on the road"),
        (tread, "tread marks"),
        (hub, "hub skid marks on the lane"),
        (hub, "hub tread marks"),
    ]
    for prop, line in unnamed:
        assert _named(prop, line) is False, line
        assert _state(prop, line) == "unnamed", line


def test_a_real_part_mention_stays_named():
    prop = _hauler(["tire", "front tire"])
    for line in ("the front tire spins", "he kicks the tire", "the tire is flat"):
        assert _named(prop, line) is True, line
        assert _state(prop, line) == "in-frame", line
    mixed = "He has left the hauler. The front tire spins."
    both = _hauler(["tire", "front tire"], ["hauler", "the hauler"])
    assert _state(both, mixed) == "ambiguous"


def test_a_departure_then_a_part_trace_is_not_a_review(tmp_path):
    """The s03-sh01 shape: a perfect absence, then a part-word trace, in one shot."""
    production = _harbor(tmp_path)
    _vehicle(production, aliases=["machine", "bike", "the bike"], parts=["tire"])
    _scene(
        production,
        "Mina walks. She has left the bike. She carries nothing. Her boots crunch on the yard stones. "
        "She is walking in the direction she was riding, following the faint tire tracks of riders who came "
        "through here before her. Looking for something. Any sign of the path. Any marker.\n\n"
        "A lantern sits on the step.",
    )
    lock_props(production)
    locked = json.loads((production / "props" / "hero-props.json").read_text(encoding="utf-8"))["props"][0]
    assert locked["parts"] == ["tire"]
    boards = build_boards(production)
    shot = _by_text(_shots(production), "has left the bike")
    assert "tire tracks" in shot["description"].casefold()
    assert "vehicles_in_shot" not in shot
    assert "props_in_shot" not in shot
    assert "pipe on the right" not in shot["generation_prompt"].casefold()
    assert _state(locked, shot["description"]) == "absent"
    assert _prop_review(boards["tag_notes"], shot["shot_id"]) == []
    check = check_continuity(production)
    assert check["verdict"] == "clear", check["findings"]
    assert not any(
        item["shot_id"] == shot["shot_id"] and "prop" in item["detail"].casefold()
        for item in check["reviews"]
    )


def test_a_spinning_part_is_still_tagged(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production, aliases=["hauler"], parts=["tire", "front tire"])
    _scene(production, "The front tire spins.")
    lock_props(production)
    boards = build_boards(production)
    shot = _shots(production)[0]
    assert shot.get("vehicles_in_shot") == ["dusty-bike"]
    assert _prop_review(boards["tag_notes"], shot["shot_id"]) == []
    check = check_continuity(production)
    assert not any(item["shot_id"] == shot["shot_id"] and "prop" in item["detail"].casefold() for item in check["reviews"])


def test_a_film_trace_list_extends_the_shared_nouns(tmp_path):
    production = _harbor(tmp_path)
    _vehicle(production, aliases=["hauler", "the hauler"], parts=["tire"])
    (production / "props" / "absence-phrases.json").write_text(
        json.dumps({"trace_nouns": ["furrows", "tracks"]}),
        encoding="utf-8",
    )
    absence = load_absence_phrases(production)
    assert absence["trace_nouns"][: len(_SHARED_TRACE_NOUNS)] == _SHARED_TRACE_NOUNS
    assert "furrows" in absence["trace_nouns"]
    assert absence["trace_nouns"].count("tracks") == 1
    prop = _hauler(["tire"], ["hauler", "the hauler"])
    line = "She has left the hauler. She follows the faint tire furrows."
    assert _state(prop, line, absence) == "absent"
    assert _state(prop, "the faint tire tracks", absence) == "unnamed"
    assert _state(prop, line, load_absence_phrases()) == "ambiguous"

    (production / "props" / "absence-phrases.json").write_text(
        json.dumps({"trace_nouns": []}),
        encoding="utf-8",
    )
    cleared = load_absence_phrases(production)
    assert cleared["trace_nouns"] == _SHARED_TRACE_NOUNS
    assert _state(prop, "the faint tire tracks", cleared) == "unnamed"

    (production / "props" / "absence-phrases.json").write_text(
        json.dumps({"trace_nouns": ["furrows"]}),
        encoding="utf-8",
    )
    _scene(
        production,
        "Mina walks. She has left the hauler. She carries nothing. Her boots crunch on the yard stones. "
        "She is walking in the direction she was riding, following the faint tire furrows of riders who came "
        "through here before her. Looking for something. Any sign of the path. Any marker.\n\n"
        "A lantern sits on the step.",
    )
    lock_props(production)
    boards = build_boards(production)
    shot = _by_text(_shots(production), "has left the hauler")
    assert "tire furrows" in shot["description"].casefold()
    assert "vehicles_in_shot" not in shot
    assert "props_in_shot" not in shot
    assert _prop_review(boards["tag_notes"], shot["shot_id"]) == []
    check = check_continuity(production)
    assert check["verdict"] == "clear", check["findings"]
    assert not any(
        item["shot_id"] == shot["shot_id"] and "prop" in item["detail"].casefold()
        for item in check["reviews"]
    )
