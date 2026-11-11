"""Phase 8 studio: package a locked cut and prove the offline pipeline.

The proof is Harbor Night, a synthetic production, plus tiny pictures and
tones made in these tests when ffmpeg is installed. Nothing here delivers
The Last Marker. No provider is called. Spent stays $0.

auto_approve on run_studio is the test harness. The command line does not set it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from movie_swarm.color_mix import grade_production, mix_production, write_grade, write_mix
from movie_swarm.delivery import DeliveryError, build_qc_report, deliver_production
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.line_producer import LineProducer
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.sound import spot_production, write_sound
from movie_swarm.studio import TEST_AUTO_APPROVE_ACTOR, run_studio
from movie_swarm.validate import validate_file
from tests.test_phase5 import _cut, _harbor, _write_sources
from tests.test_phase7 import _open, _paint, _prepare, _shot


def _deliver(production: Path, *, color_mix: bool = True):
    if color_mix:
        LineProducer.open(production, "run-1").approve_gate(
            "color-mix",
            "approved",
            "ron",
            note="Final delivery can start.",
        )
    return Director(production).dispatch(
        CrewCall(agent="post-supervisor", command="deliver", estimated_cost_usd=0, note="deliver"),
        "run-1",
    )


def test_delivery_refuses_without_the_color_mix_gate(tmp_path):
    shots = [_shot("s01-sh01", duration=1), _shot("s01-sh02", duration=1, description="Ada steps onto the dock.")]
    production = _prepare(tmp_path, shots)
    _open(production)
    with pytest.raises(DeliveryError) as caught:
        deliver_production(production, color_mix_approved=False)
    assert "color-mix" in str(caught.value).casefold()

    paused = Director(production).dispatch(
        CrewCall(agent="post-supervisor", command="deliver", estimated_cost_usd=0, note="deliver"),
        "run-1",
    )
    assert paused.status == "paused", paused.message
    assert "color-mix" in paused.message
    assert not (production / "delivery" / "delivery-manifest.json").exists()
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_delivery_spec_is_read_from_the_production(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.delivery.shutil.which", lambda _name: None)
    shots = [_shot("s01-sh01", duration=1)]
    production = _prepare(tmp_path, shots)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    plan = json.loads((production / "delivery" / "delivery-plan.json").read_text(encoding="utf-8"))
    assert plan["spec_source"] == "delivery/delivery-spec.json"
    assert plan["master"]["width"] == 320
    assert plan["master"]["height"] == 180
    assert plan["master"]["codec"] == "h264"
    assert plan["master"]["frame_rate"] == 24
    assert "master.width" not in plan["defaults_used"]
    social = next(item for item in plan["variants"] if item["id"] == "social-9x16")
    assert social["crop"] == "center"
    assert social["width"] == 90
    assert social["height"] == 160
    assert "EBU R95" in social["safe"]["citation"]
    assert "center-crop" in social["safe"]["guidance"].casefold()
    web = next(item for item in plan["variants"] if item["id"] == "web-16x9")
    assert web["crop"] == "scale"
    assert "ITU-T H.264" in plan["master"]["citation"] or "H.264" in plan["master"]["citation"]

    spec_path = production / "delivery" / "delivery-spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["master"]["width"] = 640
    spec["master"]["height"] = 360
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    again = deliver_production(production, color_mix_approved=True)
    assert again["plan"]["master"]["width"] == 640
    assert again["plan"]["master"]["height"] == 360

    spec.pop("master")
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    bare = deliver_production(production, color_mix_approved=True)
    assert bare["plan"]["master"]["width"] == 1920
    assert bare["plan"]["master"]["height"] == 1080
    assert "master.width" in bare["plan"]["defaults_used"]
    assert "BT.709" in bare["plan"]["master"]["citation"]
    assert bare["plan"]["spent_usd"] == 0
    assert bare["plan"]["budget"]["estimated_usd"] is None
    assert bare["plan"]["budget"]["rate_status"] == "unknown"


def test_captions_follow_the_dialogue_cues(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.delivery.shutil.which", lambda _name: None)
    shots = [_shot("s01-sh01", duration=1), _shot("s01-sh02", duration=1, description="Ada steps onto the dock.")]
    production = _prepare(tmp_path, shots)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    sheet = json.loads((production / "sound" / "cue-sheet.json").read_text(encoding="utf-8"))
    dialogue = [cue for cue in sheet["cues"] if cue["type"] == "dialogue"]
    assert dialogue
    srt = (production / "delivery" / "captions.srt").read_text(encoding="utf-8")
    vtt = (production / "delivery" / "captions.vtt").read_text(encoding="utf-8")
    assert vtt.startswith("WEBVTT")
    for cue in dialogue:
        assert cue["description"] in srt
        assert cue["description"] in vtt
        start = _clock(cue["start_seconds"], ",")
        end = _clock(cue["end_seconds"], ",")
        assert f"{start} --> {end}" in srt
        assert f"{_clock(cue['start_seconds'], '.')} --> {_clock(cue['end_seconds'], '.')}" in vtt
        assert cue["end_seconds"] <= sheet["cut_runtime_seconds"] + 0.001
    plan = json.loads((production / "delivery" / "delivery-plan.json").read_text(encoding="utf-8"))
    assert plan["captions"]["mode"] == "sidecar"
    assert plan["captions"]["cues"]
    assert plan["captions"]["cues"][0]["text"] == dialogue[0]["description"]


def test_qc_passes_caption_timing_when_picture_is_not_rendered(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.delivery.shutil.which", lambda _name: None)
    shots = [_shot("s01-sh01", duration=1)]
    production = _prepare(tmp_path, shots)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    report_path = production / "delivery" / "qc-report.json"
    result = validate_file(report_path)
    assert result.ok, result.errors
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "pass"
    assert report["spent_usd"] == 0
    captions = next(item for item in report["checks"] if item["kind"] == "captions")
    assert captions["status"] == "pass"
    skipped = [item for item in report["checks"] if item["status"] == "skipped"]
    assert skipped
    assert any(item["kind"] == "file" for item in skipped)
    text = (production / "delivery" / "qc-report.md").read_text(encoding="utf-8")
    assert "Verdict: pass." in text


def test_qc_fails_when_a_caption_runs_past_the_cut(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.delivery.shutil.which", lambda _name: None)
    shots = [_shot("s01-sh01", duration=1)]
    production = _prepare(tmp_path, shots)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    plan = json.loads((production / "delivery" / "delivery-plan.json").read_text(encoding="utf-8"))
    assert plan["captions"]["cues"]
    plan["captions"]["cues"][0]["end_seconds"] = plan["cut_runtime_seconds"] + 4
    package = production / "delivery"
    cue = plan["captions"]["cues"][0]
    (package / "captions.srt").write_text(
        f"1\n{_clock(cue['start_seconds'], ',')} --> {_clock(cue['end_seconds'], ',')}\n{cue['text']}\n",
        encoding="utf-8",
    )
    (package / "captions.vtt").write_text(
        "WEBVTT\n\n1\n"
        f"{_clock(cue['start_seconds'], '.')} --> {_clock(cue['end_seconds'], '.')}\n{cue['text']}\n",
        encoding="utf-8",
    )
    report = build_qc_report(production.name, plan, package)
    assert report["verdict"] == "fail"
    failed = [item for item in report["checks"] if item["kind"] == "captions"]
    assert failed and failed[0]["status"] == "fail"
    assert "cut" in failed[0]["detail"].casefold()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_qc_fails_a_black_stretch(tmp_path):
    package = tmp_path / "delivery"
    package.mkdir()
    master = package / "master.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:size=320x180:rate=24:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(master),
        ],
        check=True,
        capture_output=True,
    )
    plan = {
        "cut_runtime_seconds": 1,
        "location": {"relative": "delivery"},
        "qc_tolerances": {
            "duration_tolerance_seconds": 0.75,
            "frame_rate_tolerance": 0.1,
            "black_max_seconds": 0.5,
            "freeze_max_seconds": 0.5,
            "loudness_tolerance_lufs": 2,
        },
        "master": {"filename": "master.mp4", "width": 320, "height": 180, "frame_rate": 24},
        "variants": [],
        "poster": {},
        "captions": {"cues": [], "formats": [], "files": []},
        "loudness": {"integrated_lufs": -23, "true_peak_dbtp": -1, "tolerance_lufs": 2},
    }
    report = build_qc_report("demo", plan, package)
    assert report["verdict"] == "fail"
    black = next(item for item in report["checks"] if item["kind"] == "black")
    assert black["status"] == "fail"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_qc_passes_a_rendered_master(tmp_path):
    shots = [
        _shot("s01-sh01", duration=2),
        _shot("s01-sh02", duration=2, description="Ada steps onto the dock."),
    ]
    production = _harbor(tmp_path)
    _write_sources(production, shots, target=4, tolerance=1)
    _paint(production, shots, ["testsrc", "testsrc"])
    edl = _cut(production)
    assert edl["ready_for_picture_lock"] is True
    write_sound(spot_production(production, picture_lock_approved=True), production)
    grade = grade_production(production, picture_lock_approved=True, sound_approved=True)
    write_grade(grade, production)
    mixed = mix_production(production, picture_lock_approved=True, sound_approved=True)
    write_mix(mixed, production)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    master = production / "delivery" / "master.mp4"
    assert master.is_file() and master.stat().st_size > 0
    assert (production / "delivery" / "variants" / "web-16x9.mp4").is_file()
    assert (production / "delivery" / "variants" / "social-9x16.mp4").is_file()
    assert (production / "delivery" / "poster.png").is_file()
    report = json.loads((production / "delivery" / "qc-report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "pass", report["checks"]
    resolution = [item for item in report["checks"] if item["kind"] == "resolution" and item["status"] == "fail"]
    assert resolution == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_manifest_records_checksums_spend_and_gates(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.delivery.shutil.which", lambda _name: None)
    shots = [_shot("s01-sh01", duration=1)]
    production = _prepare(tmp_path, shots)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    path = production / "delivery" / "delivery-manifest.json"
    result = validate_file(path)
    assert result.ok, result.errors
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["spent_usd"] == 0
    assert manifest["delivery_approved"] is False
    assert manifest["delivered"] is False
    assert manifest["spend"]["spent_usd"] == 0
    assert manifest["spend"]["budget_cap_usd"] == 500
    assert manifest["spend"]["within_cap"] is True
    assert manifest["spend"]["rate_status"] == "unknown"
    assert manifest["budget"]["estimated_usd"] is None
    assert "editor" in manifest["spend"]["stage_split"]
    assert manifest["spend"]["stage_spent"]["editor"] == 0
    captions = next(item for item in manifest["files"] if item["path"].endswith("captions.srt"))
    assert captions["status"] == "present"
    digest = hashlib.sha256((production / "delivery" / "captions.srt").read_bytes()).hexdigest()
    assert captions["sha256"] == digest
    assert captions["bytes"] == (production / "delivery" / "captions.srt").stat().st_size
    master = next(item for item in manifest["files"] if item["role"] == "master" and item["path"].endswith("master.mp4"))
    assert master["status"] == "not-rendered"
    assert master["sha256"] is None
    gates = {item["stage"]: item for item in manifest["gates"]}
    assert gates["color-mix"]["decision"] == "approved"
    assert gates["color-mix"]["by"] == "ron"
    assert gates["color-mix"]["decided_at"]
    assert gates["color-mix"]["note"]
    assert gates["delivery"]["decision"] == "pending"
    assert gates["generation"]["decision"] == "pending"
    assert "FIPS" in manifest["checksum"] or "SHA-256" in manifest["checksum"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_the_delivery_gate_marks_the_film_delivered(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.delivery.shutil.which", lambda _name: None)
    shots = [_shot("s01-sh01", duration=1)]
    production = _prepare(tmp_path, shots)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    waiting = LineProducer.open(production, "run-1")
    assert waiting.gate_decision("delivery") != "approved"
    assert "delivery gate" in waiting.status_text()
    before = json.loads((production / "delivery" / "delivery-manifest.json").read_text(encoding="utf-8"))
    assert before["delivered"] is False
    message = waiting.approve_gate("delivery", "approved", "ron", note="The film is delivered.")
    assert "delivered" in message.casefold()
    saved = LineProducer.open(production, "run-1")
    assert saved.gate_decision("delivery") == "approved"
    assert saved.run.data["status"] == "completed"
    assert saved.run.data["cost_usd"] == 0
    assert "delivery gate" not in saved.status_text()
    manifest = json.loads((production / "delivery" / "delivery-manifest.json").read_text(encoding="utf-8"))
    result = validate_file(production / "delivery" / "delivery-manifest.json")
    assert result.ok, result.errors
    assert manifest["delivery_approved"] is True
    assert manifest["delivered"] is True
    assert manifest["approved_by"] == "ron"
    assert manifest["approval_note"] == "The film is delivered."
    delivery_rows = [item for item in manifest["gates"] if item["stage"] == "delivery"]
    assert any(item["decision"] == "approved" and item["by"] == "ron" for item in delivery_rows)


def test_the_delivery_folder_follows_the_asset_root(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.delivery.shutil.which", lambda _name: None)
    drive = tmp_path / "stick"
    monkeypatch.setenv("MOVIE_SWARM_ASSET_ROOT", str(drive))
    shots = [_shot("s01-sh01", duration=1)]
    production = _prepare(tmp_path, shots)
    _open(production)
    ran = _deliver(production)
    assert ran.status == "ran", ran.message
    package = drive / production.name / "delivery"
    assert (package / "captions.srt").is_file()
    assert (package / "delivery-manifest.json").is_file()
    assert not (production / "delivery" / "captions.srt").exists()
    pointer = json.loads((production / "delivery" / "location.json").read_text(encoding="utf-8"))
    assert pointer["setting"] == "MOVIE_SWARM_ASSET_ROOT"
    assert pointer["relative"] == "delivery"
    assert Path(pointer["resolved"]) == package.resolve()
    manifest = json.loads((package / "delivery-manifest.json").read_text(encoding="utf-8"))
    assert manifest["location"]["setting"] == "MOVIE_SWARM_ASSET_ROOT"


def test_studio_stops_at_each_gate_and_the_test_harness_finishes(tmp_path):
    production = _harbor(tmp_path)
    first = run_studio(production, run_id="studio-1")
    assert first["status"] == "stopped"
    assert first["stopped_at"] == "treatment"
    assert first["auto_approve"] is False
    assert first["completed"] == []
    assert first["spent_usd"] == 0
    assert first["generation_gate"] == "closed"
    assert not (production / "storyboard" / "storyboard.json").exists()

    LineProducer.open(production, "studio-1").approve_gate(
        "treatment",
        "approved",
        "ron",
        note="The treatment can go forward.",
    )
    second = run_studio(production, run_id="studio-1")
    assert second["status"] == "stopped", second["message"]
    assert second["stopped_at"] == "previs"
    assert "previs" in second["completed"]
    assert (production / "storyboard" / "storyboard.json").is_file()
    assert not (production / "dailies" / "dailies-report.json").exists()

    producer = LineProducer.open(production, "studio-1")
    producer.approve_gate("previs", "approved", "ron", note="The package can go forward.")
    producer.approve_gate("production", "approved", "ron", note="A quote can be written.")
    third = run_studio(production, run_id="studio-1")
    assert third["status"] == "stopped", third["message"]
    assert third["stopped_at"] == "dailies"
    assert "dailies" in third["completed"]
    assert "edit" not in third["completed"]
    assert (production / "dailies" / "dailies-report.json").is_file()
    assert not (production / "edit" / "picture-lock.json").exists()
    assert LineProducer.open(production, "studio-1").run.data["cost_usd"] == 0

    finish = tmp_path / "finish"
    finish.mkdir()
    other = _harbor(finish)
    finished = run_studio(other, run_id="studio-1", auto_approve=True)
    assert finished["status"] == "complete", finished["message"]
    assert finished["stopped_at"] is None
    assert finished["generation_gate"] == "closed"
    assert finished["spent_usd"] == 0
    assert finished["auto_approve"] is True
    assert "delivery" in finished["completed"]
    saved = LineProducer.open(other, "studio-1")
    assert saved.run.data["cost_usd"] == 0
    assert saved.run.data["status"] == "completed"
    assert saved.gate_decision("generation") != "approved"
    assert saved.gate_decision("delivery") == "approved"
    for item in saved.record["gate_decisions"]:
        assert item["by"] == TEST_AUTO_APPROVE_ACTOR
        assert item["by"] != "ron"
    manifest_path = other / "delivery" / "delivery-manifest.json"
    if not manifest_path.is_file():
        pointer = json.loads((other / "delivery" / "location.json").read_text(encoding="utf-8"))
        manifest_path = Path(pointer["resolved"]) / "delivery-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = validate_file(manifest_path)
    assert result.ok, result.errors
    assert manifest["delivered"] is True
    assert manifest["approved_by"] == TEST_AUTO_APPROVE_ACTOR
    assert manifest["spend"]["spent_usd"] == 0
    assert manifest["qc_verdict"] == "pass"
    script = (repo_root() / "scripts" / "studio.py").read_text(encoding="utf-8")
    command = (repo_root() / "movie_swarm" / "cli_director.py").read_text(encoding="utf-8")
    assert "auto_approve=True" not in script
    assert "auto_approve=True" not in command


def test_post_supervisor_uses_the_cheap_admin_model():
    assert resolve_model("post-supervisor")["model"] == "claude-haiku-5-5"
    assert resolve_model("post-supervisor", purpose="package")["model"] == "claude-haiku-5-5"
    assert resolve_model("post-supervisor", purpose="notes")["model"] == "claude-haiku-5-5"
    assert resolve_model("post-supervisor", purpose="render")["model"] == "ffmpeg"


def test_delivery_code_does_not_name_the_sample_film():
    banned = ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967")
    paths = [
        repo_root() / "movie_swarm" / "delivery.py",
        repo_root() / "movie_swarm" / "studio.py",
        repo_root() / "schemas" / "delivery-spec.schema.json",
        repo_root() / "schemas" / "delivery-plan.schema.json",
        repo_root() / "schemas" / "qc-report.schema.json",
        repo_root() / "schemas" / "delivery-manifest.schema.json",
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


def _clock(seconds: float, separator: str) -> str:
    millis = int(round(max(seconds, 0) * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"
