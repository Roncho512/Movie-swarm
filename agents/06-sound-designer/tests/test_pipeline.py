"""
Tests for the Sound Designer agent pipeline logic.

Run with: python3 -m pytest tests/ -v
(from the agents/06-sound-designer directory)

Tests validate shot list loading, a production sound library, and asset
assignments without making any ElevenLabs API calls.
"""

import json
import tempfile
from pathlib import Path

import pytest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import (
    SoundDesignPipeline,
    load_sound_plan,
    load_sound_library,
    AudioAsset,
)


LIBRARY = (
    Path(__file__).resolve().parents[3]
    / "productions"
    / "the-last-marker"
    / "audio"
    / "sound-prompts.json"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SHOT_LIST = {
    "production_id": "dock-test",
    "shots": [
        {
            "shot_id": "s01-sh01",
            "scene_number": 1,
            "shot_number": 1,
            "sequence_position": 1,
            "generation_prompt": "Wide dock shot.",
            "target_duration_seconds": 7,
            "sound_notes": "Silence for 4 seconds. Dock water. Then a distant bell.",
            "color_notes": "Cool blue.",
        },
        {
            "shot_id": "s02-sh01",
            "scene_number": 2,
            "shot_number": 1,
            "sequence_position": 6,
            "generation_prompt": "A bell stops.",
            "target_duration_seconds": 8,
            "sound_notes": "Bell fading. Then SILENCE.",
            "color_notes": "Blue to grey.",
        },
    ],
}


def _write_shot_list(tmp_dir: Path) -> Path:
    p = tmp_dir / "shot-list.json"
    p.write_text(json.dumps(SAMPLE_SHOT_LIST, indent=2))
    return p


def _write_library(tmp_dir: Path) -> Path:
    path = tmp_dir / "audio" / "sound-prompts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "production_id": "dock-test",
        "sfx": [{
            "asset_id": "rope",
            "asset_type": "sfx",
            "prompt": "A rope hitting a wooden dock.",
            "dest_path": "sfx/rope.mp3",
            "duration": 2,
            "assigned_shots": ["s01-sh01"],
            "layer_notes": "One hit.",
        }],
        "dialogue": [],
        "music": [],
    }))
    return path


def _moved_library() -> dict:
    return load_sound_library(LIBRARY)


# ---------------------------------------------------------------------------
# Tests: Sound plan loading
# ---------------------------------------------------------------------------


def test_load_sound_plan():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_shot_list(Path(tmp))
        plans = load_sound_plan(path)

    assert len(plans) == 2
    assert plans[0].shot_id == "s01-sh01"
    assert "dock water" in plans[0].sound_notes.lower()
    assert plans[1].shot_id == "s02-sh01"
    assert "SILENCE" in plans[1].sound_notes.upper()


# ---------------------------------------------------------------------------
# Tests: the moved pilot library, and a generic one
# ---------------------------------------------------------------------------


def test_program_does_not_keep_a_film_library():
    source = (Path(__file__).resolve().parents[1] / "src" / "pipeline.py").read_text(encoding="utf-8")
    assert "LAST_MARKER" not in source
    assert "the-last-marker" not in source
    assert "Primero llegas" not in source


def test_moved_library_still_has_the_pilot_prompts():
    loaded = _moved_library()
    sfx = loaded["sfx"]
    engine_ids = [asset.asset_id for asset in sfx if "engine" in asset.asset_id]
    assert "engine-healthy" in engine_ids
    assert "engine-skip" in engine_ids
    assert "engine-death" in engine_ids
    assert "engine-kick-fail" in engine_ids
    assert "engine-kick-catch" in engine_ids
    assert "engine-rough-idle" in engine_ids
    ambient = [asset.asset_id for asset in sfx if "desert" in asset.asset_id or "silence" in asset.asset_id]
    assert len(ambient) >= 2
    foley = [asset.asset_id for asset in sfx if asset.asset_id in ("tire-hardpan", "pebble-spray", "boot-on-lever", "cooling-metal")]
    assert len(foley) == 4
    for asset in sfx:
        assert asset.assigned_shots, asset.asset_id
        assert len(asset.prompt) > 20, asset.asset_id
        assert asset.duration is not None
        assert 0.5 <= asset.duration <= 30
    assert len(loaded["dialogue"]) == 1
    assert loaded["dialogue"][0].text == "Primero llegas. Despues compites."
    assert loaded["music"][0].asset_id == "closing-guitar"
    assert loaded["production_id"] == "the-last-marker"


def test_generic_library_is_what_the_pipeline_loads():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shot_list = _write_shot_list(root)
        _write_library(root)
        pipeline = SoundDesignPipeline(shot_list, root / "out")
    assert pipeline.production_id == "dock-test"
    assert [asset.asset_id for asset in pipeline.sfx_assets] == ["rope"]
    assert pipeline.dialogue_assets == []


# ---------------------------------------------------------------------------
# Tests: Pipeline dry run
# ---------------------------------------------------------------------------


def test_pipeline_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shot_list = _write_shot_list(root)
        _write_library(root)
        pipeline = SoundDesignPipeline(shot_list, root / "audio-out")
        results = pipeline.generate_sfx_library(dry_run=True)

        assert len(results) == 1
        assert all(not asset.generated for asset in results)


def test_paid_audio_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shot_list = _write_shot_list(root)
        _write_library(root)
        pipeline = SoundDesignPipeline(shot_list, root / "audio-out")
        with pytest.raises(RuntimeError, match="generation gate"):
            pipeline.generate_sfx_library(dry_run=False)


def test_pipeline_writes_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shot_list = _write_shot_list(root)
        _write_library(root)
        output = root / "audio-out"
        pipeline = SoundDesignPipeline(shot_list, output)
        pipeline.generate_sfx_library(dry_run=True)
        pipeline.write_audio_manifest()

        manifest = json.loads((output / "audio-manifest.json").read_text())
        assert manifest["production_id"] == "dock-test"
        assert manifest["assets"][0]["asset_id"] == "rope"


def test_audio_asset_can_be_built():
    asset = AudioAsset(asset_id="bell", asset_type="sfx", prompt="A bell.", dest_path="sfx/bell.mp3")
    assert asset.generated is False


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
