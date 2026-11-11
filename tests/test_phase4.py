"""Phase 4 studio: dailies review before the edit.

The proof is Harbor Night, a synthetic production, plus tiny frames and clips
made in these tests. Nothing here reviews or generates The Last Marker.
No provider is called. Spent stays $0.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from movie_swarm.dailies import review_production, write_report
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.line_producer import LineProducer
from movie_swarm.paths import repo_root
from movie_swarm.treatment_doc import proposed_split
from movie_swarm.validate import validate_file
from tests.test_line_producer import _treatment


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)
_CLEAN = (
    "A wide view of Ada on the dock. "
    "The scarf on the right shoulder. "
    "Available fluorescent light. Cool gray."
)


class FakeVision:
    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def describe(self, *, path, shot_id):
        self.calls.append(shot_id)
        return self.text


def _harbor(tmp_path: Path) -> Path:
    source = repo_root() / "tests" / "fixtures" / "harbor-night"
    production = tmp_path / "harbor-night"
    shutil.copytree(source, production)
    return production


def _prepare(
    production: Path,
    *,
    kind: str = "frame",
    file_name: str = "frames/s01-sh01.png",
    write_file: bool = True,
    duration: float = 4,
    camera_movement: str = "static",
) -> Path:
    shot = {
        "shot_id": "s01-sh01",
        "scene_number": 1,
        "shot_number": 1,
        "shot_type": "wide",
        "description": "Ada stands on the dock.",
        "camera_movement": camera_movement,
        "generation_prompt": "Ada stands on the dock.",
        "target_duration_seconds": duration,
        "props_in_shot": ["red-scarf"],
    }
    board = production / "storyboard"
    board.mkdir(exist_ok=True)
    (board / "shot-list.json").write_text(json.dumps({"shots": [shot]}), encoding="utf-8")
    path = production / file_name
    if write_file and kind == "frame":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_PNG)
    manifest = {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "takes": [
            {
                "take_id": "s01-sh01-t01",
                "shot_id": "s01-sh01",
                "file": file_name,
                "kind": kind,
            }
        ],
    }
    takes = production / "takes"
    takes.mkdir(exist_ok=True)
    (takes / "takes-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _review(production: Path, text: str, allocations=None):
    vision = FakeVision(text)
    report = review_production(
        production,
        vision=vision,
        allocations=allocations if allocations is not None else proposed_split(500),
    )
    write_report(report, production)
    return report, vision


def test_a_clean_take_is_circled(tmp_path):
    production = _harbor(tmp_path)
    _prepare(production)
    report, vision = _review(production, _CLEAN)

    shot = report["shots"][0]
    assert shot["verdict"] == "circle"
    assert shot["best_take"] == "s01-sh01-t01"
    assert shot["takes"][0]["checks"]["continuity"]["status"] == "pass"
    assert shot["takes"][0]["checks"]["shot_match"]["status"] == "pass"
    assert shot["takes"][0]["checks"]["look_match"]["status"] == "pass"
    assert shot["takes"][0]["checks"]["technical"]["status"] == "pass"
    assert report["retakes"] == []
    assert report["spent_usd"] == 0
    assert report["within_fix_loop"] is True
    assert vision.calls == ["s01-sh01"]
    text = (production / "dailies" / "dailies-report.md").read_text(encoding="utf-8")
    assert "| s01-sh01 | s01-sh01-t01 | circle |" in text
    assert "No money was spent" in text


def test_a_forbidden_prop_phrase_is_a_retake(tmp_path):
    production = _harbor(tmp_path)
    _prepare(production)
    drifted = (
        "A wide view of Ada on the dock. "
        "The scarf on the left shoulder. "
        "Available fluorescent light. Cool gray."
    )
    report, _vision = _review(production, drifted)

    shot = report["shots"][0]
    assert shot["verdict"] == "retake"
    assert "scarf on the left shoulder" in " ".join(shot["reasons"])
    retake = report["retakes"][0]
    assert retake["shot_id"] == "s01-sh01"
    assert retake["routed_to"] == "production generate"
    assert "scarf on the left shoulder" in retake["prompt_fix"]
    assert "scarf on the right shoulder" in retake["prompt_fix"]
    assert retake["estimate_usd"] == 0.28
    assert report["retake_estimate_usd"] == 0.28
    assert report["fix_loop_reserve_usd"] == 50
    assert report["within_fix_loop"] is True
    assert report["spent_usd"] == 0


def test_a_missing_file_is_rejected(tmp_path):
    production = _harbor(tmp_path)
    _prepare(production, file_name="frames/missing.png", write_file=False)
    report, vision = _review(production, _CLEAN)

    shot = report["shots"][0]
    assert shot["verdict"] == "reject"
    assert "not on disk" in " ".join(shot["reasons"])
    assert shot["takes"][0]["checks"]["technical"]["status"] == "fail"
    assert shot["takes"][0]["checks"]["continuity"]["status"] == "skipped"
    assert report["retakes"] == []
    assert vision.calls == []
    assert report["spent_usd"] == 0


def test_a_shot_list_mismatch_is_flagged(tmp_path):
    production = _harbor(tmp_path)
    _prepare(production)
    mismatched = (
        "A close view of an empty street. "
        "The scarf on the right shoulder. "
        "Available fluorescent light. Cool gray."
    )
    report, _vision = _review(production, mismatched)

    shot = report["shots"][0]
    reasons = " ".join(shot["reasons"])
    assert shot["verdict"] == "retake"
    assert "Framing does not match the shot list" in reasons
    assert "wide" in reasons
    assert "subject does not match the shot list" in reasons
    assert report["retakes"][0]["prompt_fix"]
    assert "Match the shot list framing: wide." in report["retakes"][0]["prompt_fix"]
    assert report["spent_usd"] == 0


def test_the_report_matches_its_schema(tmp_path):
    production = _harbor(tmp_path)
    _prepare(production)
    _review(production, _CLEAN)
    result = validate_file(production / "dailies" / "dailies-report.json")
    assert result.ok, result.errors
    assert result.schema_name == "dailies-report.schema.json"
    manifest = validate_file(production / "takes" / "takes-manifest.json")
    assert manifest.ok, manifest.errors


def test_the_dailies_gate_blocks_editing_until_ron_approves(tmp_path):
    production = tmp_path / "demo"
    _treatment(production)
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    producer.approve_gate("editor", "approved", "ron")
    director = Director(production)
    call = CrewCall(agent="editor", command="dry-run", estimated_cost_usd=0, note="cut")

    paused = director.dispatch(call, "run-1")
    assert paused.status == "paused"
    assert "dailies" in paused.message
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    producer = LineProducer.open(production, "run-1")
    producer.approve_gate("dailies", "approved", "ron", note="Circled takes can be cut.")
    allowed = director.dispatch(call, "run-1")
    assert allowed.status == "ran", allowed.message
    assert "editor" in allowed.output
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_dispatch_writes_a_report_and_holds_the_edit(tmp_path):
    production = _harbor(tmp_path)
    _prepare(production)
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", stage_split=proposed_split(500))
    producer.approve_gate("previs", "approved", "ron")
    producer.approve_gate("editor", "approved", "ron")
    result = Director(production).dispatch(
        CrewCall(
            agent="dailies",
            command="review",
            estimated_cost_usd=0,
            client=FakeVision(_CLEAN),
            note="review the takes",
        ),
        "run-1",
    )
    assert result.status == "ran", result.message
    report = json.loads((production / "dailies" / "dailies-report.json").read_text(encoding="utf-8"))
    assert report["shots"][0]["verdict"] == "circle"
    assert report["spent_usd"] == 0
    saved = LineProducer.open(production, "run-1")
    assert saved.run.data["cost_usd"] == 0
    assert saved.run.data["stage"] == "dailies"
    assert saved.gate_decision("dailies") != "approved"
    assert any(item["role"] == "Dailies Reviewer" for item in saved.record["credits"])
    assert "dailies gate" in saved.status_text()

    paused = Director(production).dispatch(
        CrewCall(agent="editor", command="dry-run", estimated_cost_usd=0),
        "run-1",
    )
    assert paused.status == "paused"
    assert "dailies" in paused.message


def test_a_retake_over_the_fix_loop_line_is_not_spent(tmp_path):
    production = _harbor(tmp_path)
    _prepare(production)
    drifted = (
        "A wide view of Ada on the dock. "
        "The scarf on the left shoulder. "
        "Available fluorescent light. Cool gray."
    )
    report, _vision = _review(production, drifted, allocations={"fix-loop": 0.01})
    assert report["shots"][0]["verdict"] == "retake"
    assert report["within_fix_loop"] is False
    assert "not cleared to spend" in report["fix_loop_note"]
    assert report["spent_usd"] == 0
    assert report["retakes"]


def test_technical_checks_skip_when_the_tools_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.dailies.shutil.which", lambda _name: None)
    production = _harbor(tmp_path)
    _prepare(production)
    report, _vision = _review(production, _CLEAN)
    technical = report["shots"][0]["takes"][0]["checks"]["technical"]
    assert report["shots"][0]["verdict"] == "circle"
    assert technical["status"] == "pass"
    assert "not installed" in technical["detail"]


def test_a_sidecar_description_circles_without_a_client(tmp_path):
    production = _harbor(tmp_path)
    path = _prepare(production)
    Path(str(path) + ".txt").write_text(_CLEAN, encoding="utf-8")
    report = review_production(production, allocations=proposed_split(500))
    assert report["draft_method"] == "offline-deterministic"
    assert report["shots"][0]["verdict"] == "circle"
    assert report["shots"][0]["takes"][0]["description_source"] == "sidecar"
    assert report["spent_usd"] == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg is not installed")
def test_a_black_clip_is_a_retake(tmp_path):
    production = _harbor(tmp_path)
    path = _prepare(production, kind="clip", file_name="clips/s01-sh01.mp4", write_file=False, duration=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x90:r=24:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        capture_output=True,
    )
    report, _vision = _review(production, _CLEAN)
    reasons = " ".join(report["shots"][0]["reasons"])
    assert report["shots"][0]["verdict"] == "retake"
    assert "black stretch" in reasons
    assert report["spent_usd"] == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_a_frozen_moving_shot_is_a_retake(tmp_path):
    production = _harbor(tmp_path)
    path = _prepare(
        production,
        kind="clip",
        file_name="clips/s01-sh01.mp4",
        write_file=False,
        duration=1,
        camera_movement="push in",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=24:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        capture_output=True,
    )
    report, _vision = _review(production, _CLEAN)
    reasons = " ".join(report["shots"][0]["reasons"])
    assert report["shots"][0]["verdict"] == "retake"
    assert "frozen" in reasons
    assert report["spent_usd"] == 0


def test_dailies_code_does_not_name_the_sample_film():
    banned = ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967")
    paths = [
        repo_root() / "movie_swarm" / "dailies.py",
        repo_root() / "movie_swarm" / "continuity.py",
        repo_root() / "schemas" / "dailies-report.schema.json",
        repo_root() / "schemas" / "takes-manifest.schema.json",
        repo_root() / "config" / "gates.json",
        repo_root() / "config" / "model-routing.json",
        repo_root() / "config" / "generation-rates.json",
    ]
    offenders = []
    for path in paths:
        text = path.read_text(encoding="utf-8").casefold()
        for word in banned:
            if word in text:
                offenders.append(f"{path.relative_to(repo_root())}: {word}")
    assert offenders == []
