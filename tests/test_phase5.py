"""Phase 5 studio: edit circled takes into a rough cut.

The proof is Harbor Night, a synthetic production, plus tiny frames and clips
made in these tests. Nothing here cuts The Last Marker. No provider is called.
Spent stays $0.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.edit import EditError, assemble_production, write_edit
from movie_swarm.line_producer import LineProducer
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.validate import validate_file
from tests.test_line_producer import _treatment


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


def _harbor(tmp_path: Path) -> Path:
    source = repo_root() / "tests" / "fixtures" / "harbor-night"
    production = tmp_path / "harbor-night"
    shutil.copytree(source, production)
    return production


def _shot(
    shot_id: str,
    *,
    scene_id: str = "s01",
    duration: float = 4,
    description: str = "Ada stands on the dock.",
    props=None,
    transition: str = "cut",
    verdict: str = "circle",
):
    return {
        "shot_id": shot_id,
        "scene_id": scene_id,
        "duration": duration,
        "description": description,
        "props": list(props or []),
        "transition": transition,
        "verdict": verdict,
    }


def _write_sources(production: Path, shots: list[dict], *, order=None, target=None, tolerance=None) -> None:
    frames = []
    for index, shot in enumerate(reversed(shots), start=1):
        frames.append(
            {
                "order": index,
                "shot_id": shot["shot_id"],
                "scene_id": shot["scene_id"],
                "what_we_see": shot["description"],
                "board_prompt": shot["description"],
                "transition": shot["transition"],
                "duration_seconds": shot["duration"],
                "props_in_frame": shot["props"],
                "image_status": "not-generated",
                "image_ref": None,
            }
        )
    animatic = order or [shot["shot_id"] for shot in shots]
    board = {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "frames": frames,
        "animatic": {"total_duration_seconds": sum(shot["duration"] for shot in shots), "order": animatic},
        "image_generation": "not-run",
    }
    storyboard = production / "storyboard"
    storyboard.mkdir(exist_ok=True)
    (storyboard / "storyboard.json").write_text(json.dumps(board), encoding="utf-8")
    listed = []
    for shot in reversed(shots):
        listed.append(
            {
                "shot_id": shot["shot_id"],
                "scene_id": shot["scene_id"],
                "description": "Listed in a different order.",
                "target_duration_seconds": 9,
                "props_in_shot": shot["props"],
            }
        )
    shot_lists = production / "shot-lists"
    shot_lists.mkdir(exist_ok=True)
    (shot_lists / "shot-list.json").write_text(json.dumps({"shots": listed}), encoding="utf-8")
    if target is not None:
        (production / "production-brief.json").write_text(
            json.dumps({"target_runtime_seconds": target}),
            encoding="utf-8",
        )
    if tolerance is not None:
        edit = production / "edit"
        edit.mkdir(exist_ok=True)
        (edit / "editing-style.json").write_text(
            json.dumps({"runtime_tolerance_seconds": tolerance, "default_transition": "cut"}),
            encoding="utf-8",
        )
    _write_dailies(production, shots)


def _write_dailies(production: Path, shots: list[dict]) -> None:
    rows = []
    for shot in shots:
        take_id = f"{shot['shot_id']}-t01"
        file_name = f"frames/{shot['shot_id']}.png"
        if shot["verdict"] == "circle":
            path = production / file_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_PNG)
        checks = {
            "technical": {"status": "pass", "detail": "The file is on disk."},
            "continuity": {"status": "pass", "detail": "The picture description matches the locked phrases."},
            "shot_match": {"status": "pass", "detail": "The take matches the shot list."},
            "look_match": {"status": "pass", "detail": "The description matches the look."},
        }
        reason = "Circled. The take matches the shot list." if shot["verdict"] == "circle" else "Needs another take."
        rows.append(
            {
                "shot_id": shot["shot_id"],
                "verdict": shot["verdict"],
                "best_take": take_id,
                "reasons": [reason],
                "takes": [
                    {
                        "take_id": take_id,
                        "file": file_name,
                        "verdict": shot["verdict"],
                        "reasons": [reason],
                        "description_source": "client",
                        "checks": checks,
                    }
                ],
            }
        )
    report = {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "reviewed_at": "2026-01-01T00:00:00Z",
        "spent_usd": 0,
        "fix_loop_reserve_usd": 50,
        "retake_estimate_usd": 0,
        "within_fix_loop": True,
        "shots": rows,
        "retakes": [],
    }
    folder = production / "dailies"
    folder.mkdir(exist_ok=True)
    (folder / "dailies-report.json").write_text(json.dumps(report), encoding="utf-8")


def _cut(production: Path):
    edl = assemble_production(production, dailies_approved=True)
    write_edit(edl, production)
    return edl


def test_the_editor_refuses_without_dailies_approval(tmp_path):
    production = _harbor(tmp_path)
    _write_sources(production, [_shot("s01-sh01")], target=4)
    with pytest.raises(EditError) as caught:
        assemble_production(production, dailies_approved=False)
    assert "dailies" in str(caught.value).casefold()

    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    producer.approve_gate("editor", "approved", "ron")
    call = CrewCall(agent="editor", command="assemble", estimated_cost_usd=0, note="cut")
    paused = Director(production).dispatch(call, "run-1")
    assert paused.status == "paused"
    assert "dailies" in paused.message
    assert not (production / "edit" / "rough-cut.json").exists()
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    LineProducer.open(production, "run-1").approve_gate(
        "dailies", "approved", "ron", note="Circled takes can be cut."
    )
    allowed = Director(production).dispatch(call, "run-1")
    assert allowed.status == "ran", allowed.message
    saved = LineProducer.open(production, "run-1")
    assert saved.run.data["cost_usd"] == 0
    assert saved.run.data["stage"] == "edit"
    assert saved.gate_decision("edit") != "approved"
    assert "edit gate" in saved.status_text()
    assert any(item["role"] == "Editor" for item in saved.record["credits"])
    assert (production / "edit" / "rough-cut.json").is_file()


def test_shot_order_follows_the_storyboard(tmp_path):
    production = _harbor(tmp_path)
    shots = [
        _shot("s01-sh02", description="Ada stands on the dock."),
        _shot("s01-sh01", description="Ada ties the coat."),
        _shot("s02-sh01", scene_id="s02", description="Ada steps onto the dock."),
    ]
    _write_sources(
        production,
        shots,
        order=["s01-sh02", "s01-sh01", "s02-sh01"],
        target=12,
    )
    edl = _cut(production)

    assert edl["order_source"] == "storyboard/storyboard.json"
    assert [event["shot_id"] for event in edl["events"]] == ["s01-sh02", "s01-sh01", "s02-sh01"]
    assert [event["duration_seconds"] for event in edl["events"]] == [4, 4, 4]
    assert edl["events"][0]["take_id"] == "s01-sh02-t01"
    assert edl["events"][0]["source_in"] == 0
    assert edl["events"][0]["source_out"] == 4
    assert edl["events"][0]["transition"] == "cut"
    markers = edl["scene_markers"]
    assert markers[0]["scene_id"] == "s01"
    assert markers[0]["record_in"] == 0
    assert markers[0]["label"] == "EXT. HARBOR DOCK - NIGHT"
    assert markers[1]["scene_id"] == "s02"
    assert markers[1]["record_in"] == 8
    assert markers[1]["label"] == "s02"
    assert edl["blockers"] == []
    assert edl["ready_for_picture_lock"] is True
    assert edl["picture_lock"] is False
    assert edl["spent_usd"] == 0
    cmx = (production / "edit" / "assembly.edl").read_text(encoding="utf-8")
    assert "TITLE: HARBOR NIGHT" in cmx
    assert "FCM: NON-DROP FRAME" in cmx
    assert cmx.index("s01-sh02-t01") < cmx.index("s01-sh01-t01") < cmx.index("s02-sh01-t01")
    locked = json.loads((production / "edit" / "picture-lock.json").read_text(encoding="utf-8"))
    assert locked["kind"] == "picture-lock"
    assert locked["picture_lock"] is False


def test_a_shot_with_no_circled_take_is_a_blocker(tmp_path):
    production = _harbor(tmp_path)
    shots = [
        _shot("s01-sh01"),
        _shot("s01-sh02", verdict="retake"),
        _shot("s01-sh03"),
    ]
    _write_sources(production, shots, target=8)
    edl = _cut(production)

    assert [event["shot_id"] for event in edl["events"]] == ["s01-sh01", "s01-sh03"]
    assert "s01-sh02" not in {event["shot_id"] for event in edl["events"]}
    blocker = edl["blockers"][0]
    assert blocker["shot_id"] == "s01-sh02"
    assert blocker["kind"] == "missing-coverage"
    assert blocker["routed_to"] == "generation"
    assert "dailies" in blocker["detail"]
    assert "invent" in blocker["detail"]
    assert edl["ready_for_picture_lock"] is False
    assert not (production / "edit" / "picture-lock.json").exists()
    assert edl["spent_usd"] == 0


def test_runtime_trims_to_the_brief_within_tolerance(tmp_path):
    production = _harbor(tmp_path)
    shots = [_shot("s01-sh01"), _shot("s01-sh02", description="Ada ties the coat.")]
    _write_sources(production, shots, target=6, tolerance=0.25)
    edl = _cut(production)

    assert edl["sources"]["runtime"] == "production-brief.json"
    assert edl["target_runtime_seconds"] == 6
    assert edl["tolerance_seconds"] == 0.25
    assert edl["runtime_seconds"] == pytest.approx(6, abs=0.05)
    assert abs(edl["runtime_delta_seconds"]) <= 0.25
    assert edl["within_tolerance"] is True
    assert "inside the tolerance" in edl["runtime_note"]
    assert [event["shot_id"] for event in edl["events"]] == ["s01-sh01", "s01-sh02"]
    assert all(event["duration_seconds"] < 4 for event in edl["events"])
    assert sum(event["duration_seconds"] for event in edl["events"]) == pytest.approx(edl["runtime_seconds"], abs=0.001)
    assert edl["spent_usd"] == 0


def test_the_edit_decision_list_matches_its_schema(tmp_path):
    production = _harbor(tmp_path)
    _write_sources(production, [_shot("s01-sh01"), _shot("s01-sh02")], target=8)
    _cut(production)
    result = validate_file(production / "edit" / "rough-cut.json")
    assert result.ok, result.errors
    assert result.schema_name == "edit-decision-list.schema.json"
    locked = validate_file(production / "edit" / "picture-lock.json")
    assert locked.ok, locked.errors


def test_a_locked_prop_is_flagged_across_adjacent_cuts(tmp_path):
    production = _harbor(tmp_path)
    shots = [
        _shot(
            "s01-sh01",
            description="Ada stands on the dock. The scarf on the right shoulder.",
            props=["red-scarf"],
        ),
        _shot(
            "s01-sh02",
            description="Ada stands on the dock. The scarf on the left shoulder.",
            props=["red-scarf"],
        ),
    ]
    _write_sources(production, shots, target=8)
    edl = _cut(production)

    assert [event["shot_id"] for event in edl["events"]] == ["s01-sh01", "s01-sh02"]
    pair = edl["continuity"][0]
    assert pair["from_shot_id"] == "s01-sh01"
    assert pair["to_shot_id"] == "s01-sh02"
    assert pair["status"] == "fail"
    assert "scarf on the left shoulder" in pair["detail"]
    assert edl["ready_for_picture_lock"] is False
    assert not (production / "edit" / "picture-lock.json").exists()
    assert edl["spent_usd"] == 0
    text = (production / "edit" / "rough-cut.md").read_text(encoding="utf-8")
    assert "s01-sh01 to s01-sh02: fail" in text


def test_picture_lock_blocks_sound_until_ron_approves(tmp_path):
    production = tmp_path / "demo"
    _treatment(production)
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    producer.approve_gate("sound-designer", "approved", "ron")
    shot_list = production / "shot-lists" / "shot-list.json"
    shot_list.parent.mkdir(parents=True)
    shot_list.write_text(
        json.dumps({"production_id": "demo", "shots": [{"shot_id": "s01-sh01"}]}),
        encoding="utf-8",
    )
    call = CrewCall(
        agent="sound-designer",
        command="dry-run",
        estimated_cost_usd=0,
        shot_list=str(shot_list),
        output_dir=str(production / "audio-out"),
    )
    paused = Director(production).dispatch(call, "run-1")
    assert paused.status == "paused"
    assert "picture lock" in paused.message
    assert "edit" in paused.message
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    LineProducer.open(production, "run-1").approve_gate("edit", "approved", "ron", note="Picture lock.")
    allowed = Director(production).dispatch(call, "run-1")
    assert allowed.status == "ran", allowed.message
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_preview_is_skipped_when_ffmpeg_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.edit.shutil.which", lambda _name: None)
    production = _harbor(tmp_path)
    _write_sources(production, [_shot("s01-sh01"), _shot("s01-sh02")], target=8)
    edl = _cut(production)
    assert edl["render"]["status"] == "skipped"
    assert edl["render"]["path"] is None
    assert "not installed" in edl["render"]["note"]
    assert (production / "edit" / "rough-cut.json").is_file()
    assert (production / "edit" / "assembly.edl").is_file()
    assert not (production / "edit" / "rough-cut.mp4").exists()
    assert edl["spent_usd"] == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_ffmpeg_renders_a_low_res_preview(tmp_path):
    production = _harbor(tmp_path)
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s01-sh02", duration=1, description="Ada ties the coat.", transition="dissolve"),
    ]
    _write_sources(production, shots, target=2, tolerance=0.5)
    for shot in shots:
        path = production / "clips" / f"{shot['shot_id']}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=160x90:rate=24:duration=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
    report = json.loads((production / "dailies" / "dailies-report.json").read_text(encoding="utf-8"))
    for row, shot in zip(report["shots"], shots):
        row["takes"][0]["file"] = f"clips/{shot['shot_id']}.mp4"
    (production / "dailies" / "dailies-report.json").write_text(json.dumps(report), encoding="utf-8")

    edl = _cut(production)
    assert edl["events"][1]["transition"] == "dissolve"
    assert edl["render"]["status"] == "rendered", edl["render"]["note"]
    preview = production / "edit" / "rough-cut.mp4"
    assert preview.is_file()
    assert preview.stat().st_size > 0
    assert edl["spent_usd"] == 0
    if shutil.which("ffprobe"):
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(preview),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        duration = float(completed.stdout.strip())
        assert duration == pytest.approx(edl["runtime_seconds"], abs=0.2)


def test_the_editor_stays_on_the_cheap_local_tool():
    assert resolve_model("editor")["model"] == "ffmpeg"
    assert resolve_model("editor", purpose="assemble")["model"] == "ffmpeg"
    assert resolve_model("editor", purpose="notes")["model"] == "claude-haiku-5-5"


def test_edit_code_does_not_name_the_sample_film():
    banned = ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967")
    paths = [
        repo_root() / "movie_swarm" / "edit.py",
        repo_root() / "schemas" / "edit-decision-list.schema.json",
        repo_root() / "config" / "gates.json",
        repo_root() / "config" / "model-routing.json",
    ]
    offenders = []
    for path in paths:
        text = path.read_text(encoding="utf-8").casefold()
        for word in banned:
            if word in text:
                offenders.append(f"{path.relative_to(repo_root())}: {word}")
    assert offenders == []
