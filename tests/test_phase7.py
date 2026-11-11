"""Phase 7 studio: grade the locked picture and mix the stems.

The proof is Harbor Night, a synthetic production, plus tiny pictures and
tones made in these tests when ffmpeg is installed. Nothing here grades or
mixes The Last Marker. No provider is called. Spent stays $0.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from movie_swarm.color_mix import ColorMixError, grade_production, mix_production, write_grade, write_mix
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.line_producer import LineProducer
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.sound import spot_production, write_sound
from movie_swarm.treatment_doc import proposed_split
from movie_swarm.validate import validate_file
from tests.test_phase5 import _cut, _harbor, _shot, _write_sources


def _prepare(tmp_path: Path, shots) -> Path:
    production = _harbor(tmp_path)
    total = sum(shot["duration"] for shot in shots)
    _write_sources(production, shots, target=total, tolerance=1)
    edl = _cut(production)
    assert (production / "edit" / "picture-lock.json").is_file(), edl.get("blockers")
    sheet = spot_production(production, picture_lock_approved=True)
    write_sound(sheet, production)
    return production


def _open(production: Path, *, edit: bool = True, sound: bool = True) -> LineProducer:
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate(
        "treatment",
        "approved",
        "ron",
        stage_split=proposed_split(500),
    )
    producer.approve_gate("previs", "approved", "ron")
    if edit:
        producer.approve_gate("edit", "approved", "ron", note="Picture lock.")
    if sound:
        producer.approve_gate("sound", "approved", "ron", note="The cue sheet can go to color and mix.")
    return producer


def _paint(production: Path, shots, pictures) -> None:
    """Replace the stills with tiny synthetic video. ``testsrc`` is a pattern; other words are colors."""
    if shutil.which("ffmpeg") is None:
        return
    report_path = production / "dailies" / "dailies-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for shot, picture in zip(shots, pictures):
        dest = production / "frames" / f"{shot['shot_id']}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if picture == "testsrc":
            spec = f"testsrc=size=160x90:rate=24:duration={shot['duration']}"
        else:
            spec = f"color=c={picture}:size=160x90:rate=24:duration={shot['duration']}"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                spec,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "ultrafast",
                str(dest),
            ],
            check=True,
            capture_output=True,
        )
        png = production / "frames" / f"{shot['shot_id']}.png"
        if png.exists():
            png.unlink()
        for row in report["shots"]:
            if row["shot_id"] == shot["shot_id"]:
                row["takes"][0]["file"] = f"frames/{shot['shot_id']}.mp4"
    report_path.write_text(json.dumps(report), encoding="utf-8")


def _loud_stems(production: Path, seconds: float) -> None:
    stems = production / "sound" / "stems"
    stems.mkdir(parents=True, exist_ok=True)
    for name, frequency in (("dialogue", 440), ("effects", 220), ("music", 110)):
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=44100:duration={seconds}",
                str(stems / f"{name}.wav"),
            ],
            check=True,
            capture_output=True,
        )


def test_color_and_mix_refuse_without_edit_and_sound_gates(tmp_path):
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s01-sh02", duration=1, description="Ada steps onto the dock."),
    ]
    production = _prepare(tmp_path, shots)
    with pytest.raises(ColorMixError) as both:
        grade_production(production, picture_lock_approved=False, sound_approved=False)
    text = str(both.value).casefold()
    assert "edit gate" in text
    assert "sound gate" in text

    with pytest.raises(ColorMixError) as sound_closed:
        mix_production(production, picture_lock_approved=True, sound_approved=False)
    assert "sound gate" in str(sound_closed.value).casefold()
    assert "edit gate" not in str(sound_closed.value).casefold()

    _open(production, edit=False, sound=False)
    for agent, command in (("colorist", "grade"), ("mixer", "mix")):
        paused = Director(production).dispatch(
            CrewCall(agent=agent, command=command, estimated_cost_usd=0, note=command),
            "run-1",
        )
        assert paused.status == "paused", paused.message
        assert "edit" in paused.message
        assert "picture lock" in paused.message
    assert not (production / "color" / "grade-plan.json").exists()
    assert not (production / "color" / "mix-plan.json").exists()

    LineProducer.open(production, "run-1").approve_gate("edit", "approved", "ron", note="Picture lock.")
    still = Director(production).dispatch(
        CrewCall(agent="mixer", command="mix", estimated_cost_usd=0, note="mix"),
        "run-1",
    )
    assert still.status == "paused", still.message
    assert "sound gate" in still.message
    assert not (production / "color" / "mix-plan.json").exists()
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_grade_plan_comes_from_the_look_and_is_stated_once_per_scene(tmp_path):
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s01-sh02", duration=1, description="Ada steps onto the dock."),
        _shot("s02-sh01", scene_id="s02", duration=1, description="Ada looks back at the dock."),
    ]
    production = _prepare(tmp_path, shots)
    _open(production)
    graded = Director(production).dispatch(
        CrewCall(agent="colorist", command="grade", estimated_cost_usd=0, note="grade"),
        "run-1",
    )
    assert graded.status == "ran", graded.message
    result = validate_file(production / "color" / "grade-plan.json")
    assert result.ok, result.errors
    assert result.schema_name == "grade-plan.schema.json"
    plan = json.loads((production / "color" / "grade-plan.json").read_text(encoding="utf-8"))
    look = json.loads((production / "look" / "look.json").read_text(encoding="utf-8"))
    assert plan["base"]["contrast"] == pytest.approx(look["grade"]["contrast"])
    assert plan["base"]["saturation"] == pytest.approx(look["grade"]["saturation"])
    assert plan["base"]["warmth"] == pytest.approx(look["grade"]["warmth"])
    assert plan["base"]["brightness"] == pytest.approx(look["grade"]["brightness"])
    assert plan["base"]["time_of_day"] == look["grade"]["time_of_day"]
    assert plan["base"]["source"] == "look/look.json"
    assert plan["look_reference"]["look_name"] == look["look_name"]
    assert plan["color_mix_approved"] is False
    assert plan["spent_usd"] == 0
    assert plan["budget"]["estimated_usd"] is None
    assert plan["budget"]["rate_status"] == "unknown"

    scenes = [item for item in plan["adjustments"] if item["scope"] == "scene"]
    assert len(scenes) == 1
    assert scenes[0]["adjustment_id"] == "scene-s01"
    assert scenes[0]["scene_id"] == "s01"
    assert scenes[0]["shot_ids"] == ["s01-sh01", "s01-sh02"]
    assert scenes[0]["contrast"] == pytest.approx(1.12)
    assert scenes[0]["warmth"] == pytest.approx(-0.28)
    applied = {item["shot_id"]: item for item in plan["applied"]}
    assert applied["s01-sh01"]["adjustment_id"] == "scene-s01"
    assert applied["s01-sh02"]["adjustment_id"] == "scene-s01"
    assert applied["s01-sh01"]["contrast"] == pytest.approx(applied["s01-sh02"]["contrast"])
    assert applied["s02-sh01"]["adjustment_id"] == "base"
    assert applied["s02-sh01"]["contrast"] == pytest.approx(plan["base"]["contrast"])

    saved = LineProducer.open(production, "run-1")
    assert saved.run.data["stage"] == "color-mix"
    assert saved.gate_decision("color-mix") != "approved"
    assert "color-mix gate" in saved.status_text()
    assert "final delivery" in saved.status_text()
    saved.approve_gate("color-mix", "approved", "ron", note="Final delivery can start.")
    approved = LineProducer.open(production, "run-1")
    assert approved.gate_decision("color-mix") == "approved"
    assert "color-mix gate" not in approved.status_text()
    still = json.loads((production / "color" / "grade-plan.json").read_text(encoding="utf-8"))
    assert still["color_mix_approved"] is False
    assert approved.run.data["cost_usd"] == 0


def test_mix_plan_ducks_under_dialogue_and_fades_at_scene_changes(tmp_path):
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s02-sh01", scene_id="s02", duration=1, description="Ada looks back at the dock."),
    ]
    production = _prepare(tmp_path, shots)
    _open(production)
    mixed = Director(production).dispatch(
        CrewCall(agent="mixer", command="mix", estimated_cost_usd=0, note="mix"),
        "run-1",
    )
    assert mixed.status == "ran", mixed.message
    result = validate_file(production / "color" / "mix-plan.json")
    assert result.ok, result.errors
    assert result.schema_name == "mix-plan.schema.json"
    plan = json.loads((production / "color" / "mix-plan.json").read_text(encoding="utf-8"))
    assert plan["spent_usd"] == 0
    assert plan["color_mix_approved"] is False
    assert plan["budget"]["rate_status"] == "unknown"
    assert plan["budget"]["estimated_usd"] is None
    assert plan["budget"]["stage"] == "sound-designer"
    assert plan["loudness"]["standard"] == "EBU R128"
    assert plan["loudness"]["integrated_lufs"] == -23
    assert plan["loudness"]["true_peak_dbtp"] == -1
    assert "EBU R128" in plan["loudness"]["citation"]
    assert "https://tech.ebu.ch/docs/r/r128.pdf" in plan["loudness"]["citation"]
    assert any(level["priority"] == "dialogue" and level["stem"] == "dialogue" for level in plan["levels"])
    assert plan["ducking"]
    assert {item["stem"] for item in plan["ducking"]} >= {"music", "effects"}
    assert all(item["under"] == "dialogue" for item in plan["ducking"])
    assert all(item["duck_db"] < 0 for item in plan["ducking"])
    assert plan["fades"]
    assert plan["fades"][0]["kind"] == "scene-change"
    assert plan["fades"][0]["scene_id"] == "s02"
    assert plan["fades"][0]["time_seconds"] > 0
    assert "dialogue" in (production / "color" / "mix-plan.md").read_text(encoding="utf-8").casefold()
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_adjacent_shots_in_one_scene_are_flagged_when_color_drifts(tmp_path):
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s01-sh02", duration=1, description="Ada steps onto the dock."),
    ]
    production = _harbor(tmp_path)
    _write_sources(production, shots, target=2, tolerance=1)
    _paint(production, shots, ["black", "white"])
    edl = _cut(production)
    assert edl["ready_for_picture_lock"] is True
    sheet = spot_production(production, picture_lock_approved=True)
    write_sound(sheet, production)
    plan = grade_production(production, picture_lock_approved=True, sound_approved=True)
    fails = [item for item in plan["consistency"]["checks"] if item["status"] == "fail"]
    assert fails, plan["consistency"]
    assert fails[0]["scene_id"] == "s01"
    assert fails[0]["kind"] in {"brightness", "color", "both"}
    assert fails[0]["previous_shot_id"] == "s01-sh01"
    assert fails[0]["shot_id"] == "s01-sh02"
    assert plan["ready_for_color_mix_approval"] is False
    assert plan["render"]["status"] == "rendered", plan["render"]["note"]
    assert plan["spent_usd"] == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_loudness_outside_the_target_is_flagged(tmp_path):
    shots = [
        _shot("s01-sh01", duration=2),
        _shot("s01-sh02", duration=2, description="Ada steps onto the dock."),
    ]
    production = _prepare(tmp_path, shots)
    _loud_stems(production, 4)
    plan = mix_production(production, picture_lock_approved=True, sound_approved=True)
    assert plan["render"]["status"] == "rendered", plan["render"]["note"]
    assert plan["measurement"]["status"] == "measured", plan["measurement"]["note"]
    assert plan["measurement"]["meter"] in {"ebur128", "loudnorm"}
    assert plan["measurement"]["within_target"] is False
    assert plan["measurement"]["flags"]
    assert plan["ready_for_color_mix_approval"] is False
    kinds = {item["kind"] for item in plan["measurement"]["flags"]}
    assert kinds & {"integrated-loudness", "true-peak"}
    assert plan["spent_usd"] == 0
    assert plan["budget"]["estimated_usd"] is None


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_ffmpeg_grades_mixes_and_marries_a_low_res_preview(tmp_path):
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s02-sh01", scene_id="s02", duration=1, description="Ada looks back at the dock."),
    ]
    production = _harbor(tmp_path)
    _write_sources(production, shots, target=2, tolerance=1)
    _paint(production, shots, ["testsrc", "gray"])
    edl = _cut(production)
    assert edl["ready_for_picture_lock"] is True
    write_sound(spot_production(production, picture_lock_approved=True), production)
    _open(production)
    graded = Director(production).dispatch(
        CrewCall(agent="colorist", command="grade", estimated_cost_usd=0, note="grade"),
        "run-1",
    )
    assert graded.status == "ran", graded.message
    mixed = Director(production).dispatch(
        CrewCall(agent="mixer", command="mix", estimated_cost_usd=0, note="mix"),
        "run-1",
    )
    assert mixed.status == "ran", mixed.message
    preview = production / "color" / "graded-preview.mp4"
    mix = production / "color" / "mix.wav"
    married = production / "color" / "married-preview.mp4"
    assert preview.is_file() and preview.stat().st_size > 0
    assert mix.is_file() and mix.stat().st_size > 0
    assert married.is_file() and married.stat().st_size > 0
    grade_plan = json.loads((production / "color" / "grade-plan.json").read_text(encoding="utf-8"))
    mix_plan = json.loads((production / "color" / "mix-plan.json").read_text(encoding="utf-8"))
    assert grade_plan["render"]["status"] == "rendered"
    assert "eq" in grade_plan["render"]["note"]
    assert grade_plan["render"]["married"] == "color/married-preview.mp4"
    assert mix_plan["render"]["married"] == "color/married-preview.mp4"
    assert grade_plan["spent_usd"] == 0
    if shutil.which("ffprobe"):
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(married),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        kinds = {line.strip() for line in completed.stdout.splitlines() if line.strip()}
        assert "video" in kinds
        assert "audio" in kinds
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_ffmpeg_paths_are_skipped_when_it_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.color_mix.shutil.which", lambda _name: None)
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s01-sh02", duration=1, description="Ada steps onto the dock."),
    ]
    production = _prepare(tmp_path, shots)
    grade = grade_production(production, picture_lock_approved=True, sound_approved=True)
    mix = mix_production(production, picture_lock_approved=True, sound_approved=True)
    write_grade(grade, production)
    write_mix(mix, production)
    assert grade["render"]["status"] == "skipped"
    assert "not installed" in grade["render"]["note"]
    assert grade["render"]["preview"] is None
    assert grade["consistency"]["checks"]
    assert all(item["status"] == "skipped" for item in grade["consistency"]["checks"])
    assert mix["render"]["status"] == "skipped"
    assert "not installed" in mix["render"]["note"]
    assert mix["render"]["mix"] is None
    assert mix["measurement"]["status"] == "skipped"
    assert mix["measurement"]["within_target"] is None
    assert mix["ducking"]
    assert (production / "color" / "grade-plan.json").is_file()
    assert (production / "color" / "mix-plan.json").is_file()
    assert not (production / "color" / "graded-preview.mp4").exists()
    assert not (production / "color" / "mix.wav").exists()
    assert grade["spent_usd"] == 0
    assert mix["spent_usd"] == 0
    assert grade["budget"]["rate_status"] == "unknown"
    assert mix["budget"]["estimated_usd"] is None


def test_color_and_mix_use_the_cheap_admin_model():
    assert resolve_model("colorist")["model"] == "claude-haiku-5-5"
    assert resolve_model("colorist", purpose="grade")["model"] == "claude-haiku-5-5"
    assert resolve_model("colorist", purpose="notes")["model"] == "claude-haiku-5-5"
    assert resolve_model("mixer", purpose="mix")["model"] == "ffmpeg"
    assert resolve_model("mixer", purpose="notes")["model"] == "claude-haiku-5-5"


def test_color_and_mix_code_does_not_name_the_sample_film():
    banned = ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967")
    paths = [
        repo_root() / "movie_swarm" / "color_mix.py",
        repo_root() / "schemas" / "grade.schema.json",
        repo_root() / "schemas" / "grade-plan.schema.json",
        repo_root() / "schemas" / "mix-plan.schema.json",
        repo_root() / "schemas" / "mix-targets.schema.json",
        repo_root() / "schemas" / "look.schema.json",
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
