"""Phase 2 package: props, continuity, camera, boards, and stunts.

Film facts stay in the production folder. These tests use The Last Marker
and a second fixture, Harbor Night, so a different prop and look need no code change.
"""

from __future__ import annotations

import json
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path

from movie_swarm.camera import build_package
from movie_swarm.llm import LLMClient
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.line_producer import LineProducer
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.stunts import build_breakdown
from tests.test_line_producer import _treatment


class FakeImages:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"offline://board/{len(self.prompts)}"


class Scripted:
    def __init__(self, reply: str):
        self.reply = reply
        self.models = []

    def complete(self, *, model, system, user, max_tokens):
        self.models.append(model)
        return self.reply


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    source = repo_root() / "tests" / "fixtures" / name
    dest = tmp_path / name
    shutil.copytree(source, dest)
    return dest


def _copy_last_marker_inputs(tmp_path: Path) -> Path:
    source = repo_root() / "productions" / "the-last-marker"
    dest = tmp_path / "the-last-marker"
    dest.mkdir()
    for relative in (
        "production-brief.json",
        "treatment/treatment.json",
        "props/prop-definitions.json",
        "look/look.json",
        "screenplay/Pilot_-_the_last_marker_screenplay.md",
    ):
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source / relative, target)
    return dest


def test_ron_approved_the_storyboard_previs_gate():
    root = repo_root() / "productions" / "the-last-marker"
    record = json.loads((root / "runs" / "phase-1" / "line-producer.json").read_text(encoding="utf-8"))
    decision = [item for item in record["gate_decisions"] if item["stage"] == "previs"][-1]
    assert decision["decision"] == "approved"
    assert decision["by"] == "ron"
    assert decision["note"] == "Approve the storyboard previs gate."
    assert record["schedule"]["previs"] == "approved"
    board = json.loads((root / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))
    assert board["status"] == "approved"
    assert board["approval"]["state"] == "approved"
    assert board["approval"]["by"] == "ron"
    assert board["approval"]["note"] == "Approve the storyboard previs gate."
    assert board["image_generation"] == "not-run"


def test_engine_source_does_not_name_the_sample_film():
    banned = ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967")
    roots = [
        repo_root() / "movie_swarm",
        repo_root() / "schemas",
        repo_root() / "config",
        repo_root() / "agents" / "04-cinematographer" / "src",
        repo_root() / "agents" / "10-script-supervisor",
        repo_root() / "agents" / "11-prop-master",
        repo_root() / "agents" / "12-stunt-coordinator",
        repo_root() / "agents" / "06-sound-designer" / "src",
    ]
    offenders = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".json", ".md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            for word in banned:
                if word in text:
                    offenders.append(f"{path.relative_to(repo_root())}: {word}")
    assert offenders == []


def test_last_marker_package_comes_from_its_files(tmp_path):
    production = _copy_last_marker_inputs(tmp_path)
    look = json.loads((production / "look" / "look.json").read_text(encoding="utf-8"))
    definitions = json.loads((production / "props" / "prop-definitions.json").read_text(encoding="utf-8"))
    locked = lock_props(production)
    package = build_package(production)
    boards = build_boards(production)
    check = check_continuity(production)
    breakdown = build_breakdown(production)

    assert locked["status"] == "locked"
    assert locked["props"] == definitions["props"]
    assert locked["facts"] == definitions["facts"]
    assert package["look_name"] == look["look_name"]
    assert package["lenses"] == look["lenses"]
    assert package["lighting"] == look["lighting"]
    assert package["source"] == "look/look.json"
    assert boards["image_generation"] == "not-run"
    assert all(frame["image_ref"] is None for frame in boards["frames"])
    assert boards["featured_placements"]
    assert boards["featured_placements"][0]["product"] == "Breitling Top Time"
    _assert_distinct_actions(boards)
    _assert_complete_sentences(boards)
    scene_3 = [frame["what_we_see"].casefold() for frame in boards["frames"] if frame["scene_id"] == "s03"]
    assert any("canteen" in text for text in scene_3)
    assert any("buzzards circle" in text for text in scene_3)
    assert any("hard cut" in text for text in scene_3)
    assert check["verdict"] == "clear"
    assert breakdown["beats"]
    assert breakdown["beats"][0]["source"] == json.loads(
        (production / "treatment" / "treatment.json").read_text(encoding="utf-8")
    )["action_and_stunt_beats"][0]

    shot_list = json.loads((production / "storyboard" / "shot-list.json").read_text(encoding="utf-8"))
    shot_list["shots"].append(
        {
            "shot_id": "s99-sh01",
            "scene_number": 99,
            "shot_number": 1,
            "shot_type": "close",
            "description": "The motorcycle exhaust is on the left, and the watch is on the right wrist.",
            "generation_prompt": "Triumph exhaust on the left. Breitling on the right wrist. The exhaust vanished.",
            "tool_routing": {"primary_tool": "veo-3.1-lite", "rationale": "Bad fixture."},
            "target_duration_seconds": 1,
            "props_in_shot": [{"prop_id": "breitling-top-time"}],
            "vehicles_in_shot": ["triumph-tr6sc"],
        }
    )
    shot_list["total_shots"] = len(shot_list["shots"])
    (production / "storyboard" / "shot-list.json").write_text(json.dumps(shot_list), encoding="utf-8")
    drifted = check_continuity(production)
    assert drifted["verdict"] == "drift"
    observed = " ".join(item.get("observed", "") for item in drifted["findings"]).casefold()
    assert "exhaust on the left" in observed
    assert "right wrist" in observed
    assert "exhaust vanished" in observed


def test_harbor_night_uses_a_different_prop_and_look(tmp_path):
    production = _copy_fixture(tmp_path, "harbor-night")
    locked = lock_props(production)
    package = build_package(production)
    boards = build_boards(production)
    check = check_continuity(production)
    breakdown = build_breakdown(production)
    blob = json.dumps({"locked": locked, "package": package, "boards": boards, "breakdown": breakdown}).casefold()

    assert locked["props"][0]["name"] == "Red scarf"
    assert locked["props"][0]["attributes"][0]["value"] == "right"
    assert package["look_name"] == "modern documentary"
    assert "fluorescent" in package["summary"].casefold()
    assert package["lenses"][0]["name"] == "standard handheld"
    assert "leone" not in blob
    assert "triumph" not in blob
    assert "spaghetti" not in blob
    assert check["verdict"] == "clear"
    assert any("scarf on the right shoulder" in frame["board_prompt"] for frame in boards["frames"])
    lamp = next(frame for frame in boards["frames"] if "fluorescent" in frame["what_we_see"].casefold())
    assert "scarf on the right shoulder" not in lamp["board_prompt"].casefold()
    _assert_distinct_actions(boards)
    _assert_complete_sentences(boards)
    summary = boards["look"]["summary"]
    assert boards["frames"]
    assert sum(frame["board_prompt"].casefold().count(summary.casefold()) for frame in boards["frames"]) == 0
    assert breakdown["beats"][0]["source"].startswith("She ties the scarf")
    assert breakdown["beats"][0]["shots"][0]["plausible"] is True

    bad = {
        "production_id": "harbor-night",
        "version": "1.0.0",
        "total_shots": 2,
        "created_at": "2026-01-01T00:00:00Z",
        "shots": [
            {
                "shot_id": "s01-sh09",
                "scene_number": 1,
                "shot_number": 9,
                "shot_type": "close",
                "description": "The scarf on the left shoulder.",
                "generation_prompt": "A red scarf on the left shoulder.",
                "tool_routing": {"primary_tool": "veo-3.1-lite", "rationale": "Bad fixture."},
                "target_duration_seconds": 1,
                "props_in_shot": [{"prop_id": "red-scarf"}],
            },
            {
                "shot_id": "s01-sh10",
                "scene_number": 1,
                "shot_number": 10,
                "shot_type": "close",
                "description": "A red scarf.",
                "generation_prompt": "Ada wears a red scarf.",
                "tool_routing": {"primary_tool": "veo-3.1-lite", "rationale": "Missing lock."},
                "target_duration_seconds": 1,
                "props_in_shot": [{"prop_id": "red-scarf"}],
            },
        ],
    }
    path = production / "storyboard" / "shot-list.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    drifted = check_continuity(production)
    kinds = {(item["kind"], item["observed"]) for item in drifted["findings"]}
    assert ("contradiction", "scarf on the left shoulder") in kinds
    assert ("unstated", "not stated") in kinds


def test_a_model_cannot_replace_the_production_look(tmp_path):
    production = _copy_fixture(tmp_path, "harbor-night")
    invented = {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "look_name": "Sergio Leone spaghetti western",
        "summary": "Harsh sun and dusty vistas.",
        "lenses": [{"lens_id": "vista", "name": "extreme wide", "use": "Vistas."}],
        "framing": [{"id": "wide", "description": "Extreme wide vistas."}],
        "lighting": [{"id": "sun", "description": "Harsh sun."}],
        "source": "look/look.json",
    }
    scripted = Scripted(json.dumps(invented))
    package = build_package(production, llm=LLMClient(scripted))
    assert package["draft_method"] == "offline-deterministic"
    assert package["look_name"] == "modern documentary"
    assert scripted.models == ["claude-sonnet-5-5"]


def test_images_run_only_through_the_client(tmp_path):
    production = _copy_fixture(tmp_path, "harbor-night")
    lock_props(production)
    build_package(production)
    plain = build_boards(production)
    assert plain["image_generation"] == "not-run"
    client = FakeImages()
    pictured = build_boards(production, image_client=client)
    assert pictured["image_generation"] == "fake-client"
    assert client.prompts
    assert pictured["frames"][0]["image_ref"] == "offline://board/1"
    assert "http" not in pictured["frames"][0]["image_ref"]


def test_impossible_beat_is_marked(tmp_path):
    production = _copy_fixture(tmp_path, "harbor-night")
    treatment_path = production / "treatment" / "treatment.json"
    treatment = json.loads(treatment_path.read_text(encoding="utf-8"))
    treatment["action_and_stunt_beats"] = ["She teleports across the dock."]
    treatment_path.write_text(json.dumps(treatment), encoding="utf-8")
    breakdown = build_breakdown(production)
    assert breakdown["beats"][0]["shots"][0]["plausible"] is False


def test_phase2_dispatch_uses_the_locked_split_and_the_previs_gate(tmp_path):
    production = tmp_path / "demo"
    _treatment(production)
    producer = LineProducer.start(production, run_id="run-1")
    director = Director(production)
    paused = director.dispatch(
        CrewCall(agent="prop-master", command="lock", estimated_cost_usd=0),
        "run-1",
    )
    assert paused.status == "paused"
    assert "treatment" in paused.message

    producer.approve_gate("treatment", "approved", "ron")
    over = director.dispatch(
        CrewCall(agent="prop-master", command="lock", estimated_cost_usd=30, note="too much art"),
        "run-1",
    )
    assert over.status == "paused"
    assert "art-director" in over.message
    assert "allocation" in over.message

    locked = director.dispatch(
        CrewCall(agent="prop-master", command="lock", estimated_cost_usd=0),
        "run-1",
    )
    assert locked.status == "ran", locked.message
    assert (production / "props" / "hero-props.json").is_file()
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert LineProducer.open(production, "run-1").record["schedule"]["previs"] == "waiting-for-review"

    producer.approve_gate("production", "approved", "ron")
    picture = director.dispatch(
        CrewCall(agent="production", command="estimate", estimated_cost_usd=0),
        "run-1",
        handler=lambda call: "no",
    )
    assert picture.status == "paused"
    assert "previs" in picture.message


def _assert_distinct_actions(boards: dict) -> None:
    """Shots in one scene must not repeat the same action, or a near copy of it."""
    grouped: dict[str, list[str]] = {}
    for frame in boards["frames"]:
        grouped.setdefault(frame["scene_id"], []).append(_action_key(frame.get("what_we_see") or ""))
    for scene_id, actions in grouped.items():
        assert len(actions) == len(set(actions)), f"{scene_id} repeats an action"
        for left_index, left in enumerate(actions):
            for right in actions[left_index + 1 :]:
                if len(left) > 40 and (left in right or right in left):
                    raise AssertionError(f"{scene_id} has a near-duplicate action")
                if len(left) > 40 and len(right) > 40 and SequenceMatcher(None, left, right).ratio() >= 0.85:
                    raise AssertionError(f"{scene_id} has a near-duplicate action")


def _action_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


_DANGLING_END = re.compile(r"\b(a|an|the|and|or|to|of|his|her|its)\.$", re.I)


def _assert_complete_sentences(boards: dict) -> None:
    """A description ends on a finished sentence. It is not cut off mid-phrase."""
    texts = [frame.get("what_we_see") or "" for frame in boards["frames"]]
    texts.extend(item.get("why") or "" for item in boards.get("featured_placements") or [])
    for text in texts:
        cleaned = text.strip()
        assert cleaned, "a shot description is empty"
        assert cleaned[-1] in ".!?", cleaned
        assert _DANGLING_END.search(cleaned) is None, cleaned
    for item in boards.get("featured_placements") or []:
        why = item["why"]
        assert "Intent:" not in why
        assert "because the beat already shows it" not in why
        assert why.count(".") + why.count("!") + why.count("?") == 1
