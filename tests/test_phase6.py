"""Phase 6 studio: spot sound and score onto a picture-locked cut.

The proof is Harbor Night, a synthetic production, plus tiny tones made in
these tests when ffmpeg is installed. Nothing here spots The Last Marker.
No provider is called. Spent stays $0.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.line_producer import LineProducer
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.sound import SoundError, request_paid_sound, spot_production, write_sound
from movie_swarm.treatment_doc import proposed_split
from movie_swarm.validate import validate_file
from tests.test_phase5 import _cut, _harbor, _shot, _write_sources


def _prompts(sfx=None, dialogue=None, music=None, ambience=None, tolerance=0.5):
    return {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "sync_tolerance_seconds": tolerance,
        "sfx": list(sfx or []),
        "dialogue": list(dialogue or []),
        "music": list(music or []),
        "ambience": list(ambience or []),
    }


def _asset(asset_id, asset_type, prompt, shots, **extra):
    row = {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "prompt": prompt,
        "dest_path": f"{asset_type}/{asset_id}.wav",
        "assigned_shots": list(shots),
    }
    row.update(extra)
    return row


def _brief():
    return {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "tempo_bpm": 72,
        "instrumentation": ["piano"],
        "motifs": [
            {
                "motif_id": "hold",
                "description": "A held low note.",
                "shot_ids": ["s01-sh01"],
            }
        ],
        "silence": [{"shot_id": "s01-sh02", "reason": "Leave this shot quiet."}],
    }


def _ready(tmp_path: Path, shots, prompts=None, brief=None, prop_sound=None) -> Path:
    production = _harbor(tmp_path)
    total = sum(shot["duration"] for shot in shots)
    _write_sources(production, shots, target=total, tolerance=1)
    _cut(production)
    audio = production / "audio"
    audio.mkdir(exist_ok=True)
    if prompts is not None:
        (audio / "sound-prompts.json").write_text(json.dumps(prompts), encoding="utf-8")
    if brief is not None:
        (audio / "score-brief.json").write_text(json.dumps(brief), encoding="utf-8")
    if prop_sound is not None:
        path = production / "props" / "prop-definitions.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for prop in data["props"]:
            if prop["prop_id"] == prop_sound["prop_id"]:
                prop["sound"] = prop_sound["sound"]
        path.write_text(json.dumps(data), encoding="utf-8")
    return production


def _two_shots(first=None, second=None):
    first = dict(first or {})
    second = dict(second or {})
    first.setdefault("description", "Ada stands on the dock.")
    second.setdefault("description", "Ada steps onto the dock.")
    return [
        _shot("s01-sh01", duration=4, **first),
        _shot("s01-sh02", duration=4, **second),
    ]


def _happy_prompts():
    return _prompts(
        dialogue=[_asset("ada-line", "dialogue", "A short line.", ["s01-sh01"], text="Hold.")],
        sfx=[_asset("dock-water", "sfx", "Quiet water against wood.", ["s01-sh01"])],
        ambience=[_asset("room", "ambient", "A quiet room.", ["s01-sh01", "s01-sh02"])],
    )


def _open(production: Path, split=None) -> LineProducer:
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate(
        "treatment",
        "approved",
        "ron",
        stage_split=split if split is not None else proposed_split(500),
    )
    producer.approve_gate("previs", "approved", "ron")
    producer.approve_gate("sound-designer", "approved", "ron")
    producer.approve_gate("edit", "approved", "ron", note="Picture lock.")
    return producer


class _FakeAudio:
    def __init__(self):
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        return {"status": "not-sent", "cost_usd": 0, "cue_id": request.get("cue_id")}


def test_sound_refuses_without_picture_lock(tmp_path):
    production = _harbor(tmp_path)
    with pytest.raises(SoundError) as caught:
        spot_production(production, picture_lock_approved=False)
    assert "picture lock" in str(caught.value).casefold()

    _write_sources(production, [_shot("s01-sh01")], target=4)
    _cut(production)
    with pytest.raises(SoundError) as still_closed:
        spot_production(production, picture_lock_approved=False)
    assert "edit gate" in str(still_closed.value).casefold()

    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    producer.approve_gate("sound-designer", "approved", "ron")
    for agent in ("sound-designer", "composer"):
        paused = Director(production).dispatch(
            CrewCall(agent=agent, command="spot", estimated_cost_usd=0, note="spot"),
            "run-1",
        )
        assert paused.status == "paused", paused.message
        assert "picture lock" in paused.message
        assert "edit" in paused.message
    assert not (production / "sound" / "cue-sheet.json").exists()
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_cue_sheet_matches_schema_and_stays_inside_the_cut(tmp_path):
    shots = _two_shots(first={"props": ["red-scarf"], "description": "Ada stands on the dock."})
    production = _ready(tmp_path, shots, prompts=_happy_prompts(), brief=_brief())
    _open(production)
    spotted = Director(production).dispatch(
        CrewCall(agent="sound-designer", command="spot", estimated_cost_usd=0, note="spot"),
        "run-1",
    )
    assert spotted.status == "ran", spotted.message
    composed = Director(production).dispatch(
        CrewCall(agent="composer", command="spot", estimated_cost_usd=0, note="score"),
        "run-1",
    )
    assert composed.status == "ran", composed.message

    result = validate_file(production / "sound" / "cue-sheet.json")
    assert result.ok, result.errors
    assert result.schema_name == "cue-sheet.schema.json"
    sheet = json.loads((production / "sound" / "cue-sheet.json").read_text(encoding="utf-8"))
    runtime = sheet["cut_runtime_seconds"]
    assert runtime == pytest.approx(8, abs=0.05)
    assert sheet["cues"]
    assert sheet["sound_approved"] is False
    assert sheet["spent_usd"] == 0
    assert sheet["ready_for_sound_approval"] is True
    for cue in sheet["cues"]:
        assert 0 <= cue["start_seconds"] < cue["end_seconds"] <= runtime + 0.001
        assert set(cue["shot_ids"]).issubset({"s01-sh01", "s01-sh02"})
    by_id = {cue["cue_id"]: cue for cue in sheet["cues"]}
    music = by_id["motif-hold-s01-sh01"]
    assert music["type"] == "music"
    assert music["role"] == "composer"
    assert "72" in music["prompt"]
    assert "piano" in music["prompt"]
    assert "held low note" in music["prompt"]
    silence = by_id["silence-s01-sh02"]
    assert silence["source"] == "silence"
    assert silence["type"] == "music"
    assert by_id["ada-line-s01-sh01"]["type"] == "dialogue"
    assert by_id["dock-water-s01-sh01"]["type"] == "sfx"
    assert by_id["room-s01-sh01"]["type"] == "ambience"
    assert all(item["status"] == "pass" for item in sheet["sync"])
    saved = LineProducer.open(production, "run-1")
    assert saved.run.data["cost_usd"] == 0
    assert saved.run.data["stage"] == "sound"
    assert saved.gate_decision("sound") != "approved"
    assert "sound gate" in saved.status_text()
    assert "color and mix" in saved.status_text()
    roles = {item["role"] for item in saved.record["credits"]}
    assert "Sound Designer" in roles
    assert "Composer" in roles

    saved.approve_gate("sound", "approved", "ron", note="The cue sheet can go to color and mix.")
    approved = LineProducer.open(production, "run-1")
    assert approved.gate_decision("sound") == "approved"
    assert "sound gate" not in approved.status_text()
    assert approved.run.data["cost_usd"] == 0
    still = json.loads((production / "sound" / "cue-sheet.json").read_text(encoding="utf-8"))
    assert still["sound_approved"] is False


def test_sync_tolerance_and_a_missing_shot_are_flagged(tmp_path):
    production = _ready(
        tmp_path,
        _two_shots(),
        prompts=_prompts(
            sfx=[
                _asset(
                    "door",
                    "sfx",
                    "A door closes.",
                    ["s01-sh01"],
                    start_offset_seconds=1,
                    duration=4,
                ),
                _asset("ghost", "sfx", "A sound for a shot that was not cut.", ["s01-sh99"]),
            ]
        ),
    )
    sheet = spot_production(production, picture_lock_approved=True)
    door = next(cue for cue in sheet["cues"] if cue["cue_id"] == "door-s01-sh01")
    assert door["start_seconds"] == pytest.approx(1, abs=0.01)
    assert door["end_seconds"] == pytest.approx(5, abs=0.01)
    assert door["end_seconds"] <= sheet["cut_runtime_seconds"]
    late = next(item for item in sheet["sync"] if item["cue_id"] == "door-s01-sh01")
    assert late["status"] == "fail"
    assert late["kind"] == "tolerance"
    assert "tolerance" in late["detail"]
    missing = next(item for item in sheet["sync"] if item["cue_id"] == "ghost-s01-sh99")
    assert missing["status"] == "fail"
    assert missing["kind"] == "missing-shot"
    assert "s01-sh99" in missing["detail"]
    assert "not in the cut" in missing["detail"]
    assert "ghost-s01-sh99" not in {cue["cue_id"] for cue in sheet["cues"]}
    assert sheet["ready_for_sound_approval"] is False
    assert sheet["spent_usd"] == 0


def test_a_prop_sound_outside_the_frame_is_flagged(tmp_path):
    shots = _two_shots(
        first={"props": ["red-scarf"], "description": "Ada stands on the dock."},
        second={"props": [], "description": "Ada steps onto the dock."},
    )
    production = _ready(
        tmp_path,
        shots,
        prompts=_prompts(
            sfx=[
                _asset(
                    "scarf-rustle",
                    "sfx",
                    "The scarf rustles.",
                    ["s01-sh02"],
                    prop_id="red-scarf",
                )
            ]
        ),
        prop_sound={
            "prop_id": "red-scarf",
            "sound": {"prompt": "Soft wool moving.", "source": "generated"},
        },
    )
    sheet = spot_production(production, picture_lock_approved=True)
    foley = next(cue for cue in sheet["cues"] if cue["cue_id"] == "prop-red-scarf-s01-sh01")
    assert foley["type"] == "foley"
    assert foley["shot_ids"] == ["s01-sh01"]
    assert foley["prop_id"] == "red-scarf"
    foley_check = next(item for item in sheet["continuity"] if item["cue_id"] == foley["cue_id"])
    assert foley_check["status"] == "pass"
    bad = next(item for item in sheet["continuity"] if item["cue_id"] == "scarf-rustle-s01-sh02")
    assert bad["status"] == "fail"
    assert bad["kind"] == "prop-sound"
    assert "scarf" in bad["detail"].casefold()
    assert "s01-sh02" in bad["detail"]
    assert "frame" in bad["detail"]
    assert sheet["ready_for_sound_approval"] is False
    assert sheet["spent_usd"] == 0
    write_sound(sheet, production)
    checked = validate_file(production / "sound" / "cue-sheet.json")
    assert checked.ok, checked.errors
    text = (production / "sound" / "cue-sheet.md").read_text(encoding="utf-8")
    assert "scarf-rustle-s01-sh02: fail" in text


def test_a_paid_sound_call_is_refused_while_the_generation_gate_is_closed(tmp_path):
    client = _FakeAudio()
    paused = request_paid_sound(
        [{"cue_id": "line", "source": "generated", "type": "dialogue", "prompt": "Hold.", "model": "eleven_v3"}],
        client=client,
        gate_open=False,
    )
    assert paused["called"] is False
    assert paused["spent_usd"] == 0
    assert client.calls == []
    assert "generation" in paused["message"]

    production = _ready(tmp_path, _two_shots(), prompts=_happy_prompts(), brief=_brief())
    _open(production)
    dispatch_client = _FakeAudio()
    held = Director(production).dispatch(
        CrewCall(
            agent="sound-designer",
            command="generate",
            estimated_cost_usd=0,
            note="generate",
            client=dispatch_client,
        ),
        "run-1",
    )
    assert held.status == "paused", held.message
    assert "generation" in held.message
    assert dispatch_client.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    LineProducer.open(production, "run-1").approve_gate(
        "generation", "approved", "ron", note="A paid sound call may be prepared."
    )
    allowed = Director(production).dispatch(
        CrewCall(
            agent="composer",
            command="generate",
            estimated_cost_usd=0,
            note="generate score",
            client=dispatch_client,
        ),
        "run-1",
    )
    assert allowed.status == "ran", allowed.message
    assert dispatch_client.calls
    assert all(call.get("model") for call in dispatch_client.calls)
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_the_sound_plan_is_checked_against_the_sound_line(tmp_path):
    production = _ready(tmp_path, _two_shots(), prompts=_happy_prompts(), brief=_brief())
    _open(production, split=proposed_split(500))
    over = Director(production).dispatch(
        CrewCall(agent="sound-designer", command="spot", estimated_cost_usd=80, note="too much"),
        "run-1",
    )
    assert over.status == "paused", over.message
    assert "sound-designer" in over.message
    assert "55.00" in over.message
    assert "allocation" in over.message
    assert not (production / "sound" / "cue-sheet.json").exists()
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    allowed = Director(production).dispatch(
        CrewCall(agent="sound-designer", command="spot", estimated_cost_usd=0, note="spot"),
        "run-1",
    )
    assert allowed.status == "ran", allowed.message
    sheet = json.loads((production / "sound" / "cue-sheet.json").read_text(encoding="utf-8"))
    budget = sheet["budget"]
    assert budget["stage"] == "sound-designer"
    assert budget["locked_usd"] == 55
    assert budget["rate_status"] == "unknown"
    assert budget["estimated_usd"] is None
    assert budget["within_allocation"] is None
    assert budget["models_without_a_rate"]
    assert "unknown" in budget["note"]
    assert "not a price of zero" in budget["note"]
    assert "55.00" in budget["note"]
    assert sheet["spent_usd"] == 0
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    card = {
        "version": "1.0.0",
        "checked_on": "2026-11-11",
        "assumptions": [],
        "generators": [
            {
                "model": model,
                "label": model,
                "usd_per_second": "1",
                "source": "tests/test_phase6.py",
                "source_date": "2026-11-11",
                "quote": "A fixture rate used only to test the Sound line.",
            }
            for model in ("eleven_v3", "eleven_text_to_sound_v2", "elevenlabs-music-compose")
        ],
    }
    rates = tmp_path / "rates.json"
    rates.write_text(json.dumps(card), encoding="utf-8")
    priced = spot_production(
        production,
        picture_lock_approved=True,
        allocations={"sound-designer": 1},
        rates_path=rates,
    )
    assert priced["budget"]["rate_status"] == "priced"
    assert priced["budget"]["estimated_usd"] > 1
    assert priced["budget"]["within_allocation"] is False
    assert priced["budget"]["locked_usd"] == 1
    assert "tests/test_phase6.py" in priced["budget"]["note"]
    assert priced["spent_usd"] == 0
    fits = spot_production(
        production,
        picture_lock_approved=True,
        allocations={"sound-designer": 500},
        rates_path=rates,
    )
    assert fits["budget"]["within_allocation"] is True
    assert fits["budget"]["estimated_usd"] == priced["budget"]["estimated_usd"]
    assert fits["spent_usd"] == 0
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_stems_are_skipped_when_ffmpeg_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.sound.shutil.which", lambda _name: None)
    production = _ready(tmp_path, _two_shots(), prompts=_happy_prompts(), brief=_brief())
    sheet = spot_production(production, picture_lock_approved=True)
    write_sound(sheet, production)
    assert sheet["render"]["status"] == "skipped"
    assert sheet["render"]["dialogue"] is None
    assert "not installed" in sheet["render"]["note"]
    assert (production / "sound" / "cue-sheet.json").is_file()
    assert not (production / "sound" / "stems" / "dialogue.wav").exists()
    assert sheet["spent_usd"] == 0


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_ffmpeg_renders_placeholder_stems(tmp_path):
    shots = [
        _shot("s01-sh01", duration=1),
        _shot("s01-sh02", duration=1, description="Ada steps onto the dock."),
    ]
    production = _ready(
        tmp_path,
        shots,
        prompts=_prompts(
            dialogue=[_asset("ada-line", "dialogue", "A short line.", ["s01-sh01"])],
            sfx=[_asset("dock-water", "sfx", "Quiet water against wood.", ["s01-sh02"])],
        ),
        brief={
            "version": "1.0.0",
            "production_id": "harbor-night",
            "tempo_bpm": 60,
            "instrumentation": ["piano"],
            "motifs": [
                {"motif_id": "hold", "description": "A held low note.", "shot_ids": ["s01-sh01"]}
            ],
            "silence": [],
        },
    )
    sheet = spot_production(production, picture_lock_approved=True)
    assert sheet["render"]["status"] == "rendered", sheet["render"]["note"]
    stems = production / "sound" / "stems"
    for name in ("dialogue.wav", "effects.wav", "music.wav", "mix-preview.wav"):
        path = stems / name
        assert path.is_file(), name
        assert path.stat().st_size > 0
    assert sheet["spent_usd"] == 0
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
                str(stems / "mix-preview.wav"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        duration = float(completed.stdout.strip())
        assert duration == pytest.approx(sheet["cut_runtime_seconds"], abs=0.25)


def test_spotting_uses_the_cheap_admin_model():
    assert resolve_model("sound-designer", purpose="spot")["model"] == "claude-haiku-5-5"
    assert resolve_model("sound-designer", purpose="notes")["model"] == "claude-haiku-5-5"
    assert resolve_model("composer", purpose="spot")["model"] == "claude-haiku-5-5"
    assert resolve_model("composer")["model"] == "claude-haiku-5-5"
    assert resolve_model("sound-designer", purpose="dialogue")["model"] == "eleven_v3"
    assert resolve_model("sound-designer", purpose="sfx")["model"] == "eleven_text_to_sound_v2"
    assert resolve_model("sound-designer", purpose="score")["model"] == "elevenlabs-music-compose"


def test_sound_code_does_not_name_the_sample_film():
    banned = ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967")
    paths = [
        repo_root() / "movie_swarm" / "sound.py",
        repo_root() / "schemas" / "cue-sheet.schema.json",
        repo_root() / "schemas" / "score-brief.schema.json",
        repo_root() / "schemas" / "sound-prompts.schema.json",
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
