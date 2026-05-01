"""
Tests for the Sound Designer agent pipeline logic.

Run with: python3 -m pytest tests/ -v
(from the agents/06-sound-designer directory)

Tests validate shot list loading, SFX library structure, and asset
assignments without making any ElevenLabs API calls.
"""

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import (
    SoundDesignPipeline,
    load_sound_plan,
    LAST_MARKER_SFX_LIBRARY,
    LAST_MARKER_DIALOGUE,
    LAST_MARKER_MUSIC,
    AudioAsset,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SHOT_LIST = {
    "production_id": "test",
    "shots": [
        {
            "shot_id": "s01-sh01",
            "scene_number": 1,
            "shot_number": 1,
            "sequence_position": 1,
            "generation_prompt": "Wide desert shot.",
            "target_duration_seconds": 7,
            "sound_notes": "Silence for 4 seconds. Desert wind. Then distant engine.",
            "color_notes": "Full amber.",
        },
        {
            "shot_id": "s02-sh01",
            "scene_number": 2,
            "shot_number": 1,
            "sequence_position": 6,
            "generation_prompt": "Engine dies.",
            "target_duration_seconds": 8,
            "sound_notes": "Engine skipping. Hard cough. Dies. SILENCE.",
            "color_notes": "Amber to bronze.",
        },
    ],
}


def _write_shot_list(tmp_dir: Path) -> Path:
    p = tmp_dir / "shot-list.json"
    p.write_text(json.dumps(SAMPLE_SHOT_LIST, indent=2))
    return p


# ---------------------------------------------------------------------------
# Tests: Sound plan loading
# ---------------------------------------------------------------------------


def test_load_sound_plan():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_shot_list(Path(tmp))
        plans = load_sound_plan(path)

    assert len(plans) == 2
    assert plans[0].shot_id == "s01-sh01"
    assert "desert wind" in plans[0].sound_notes.lower()
    assert plans[1].shot_id == "s02-sh01"
    assert "SILENCE" in plans[1].sound_notes.upper()


# ---------------------------------------------------------------------------
# Tests: SFX library structure
# ---------------------------------------------------------------------------


def test_sfx_library_has_all_engine_states():
    engine_ids = [a.asset_id for a in LAST_MARKER_SFX_LIBRARY if "engine" in a.asset_id]
    assert "engine-healthy" in engine_ids
    assert "engine-skip" in engine_ids
    assert "engine-death" in engine_ids
    assert "engine-kick-fail" in engine_ids
    assert "engine-kick-catch" in engine_ids
    assert "engine-rough-idle" in engine_ids


def test_sfx_library_has_ambient():
    ambient_ids = [a.asset_id for a in LAST_MARKER_SFX_LIBRARY
                   if "desert" in a.asset_id or "silence" in a.asset_id]
    assert len(ambient_ids) >= 2


def test_sfx_library_has_foley():
    foley_ids = [a.asset_id for a in LAST_MARKER_SFX_LIBRARY
                 if a.asset_id in ("tire-hardpan", "pebble-spray", "boot-on-lever", "cooling-metal")]
    assert len(foley_ids) == 4


def test_all_sfx_have_assigned_shots():
    for asset in LAST_MARKER_SFX_LIBRARY:
        assert len(asset.assigned_shots) > 0, f"{asset.asset_id} has no assigned shots"


def test_all_sfx_have_prompts():
    for asset in LAST_MARKER_SFX_LIBRARY:
        assert len(asset.prompt) > 20, f"{asset.asset_id} has too short a prompt"


def test_all_sfx_have_durations():
    for asset in LAST_MARKER_SFX_LIBRARY:
        assert asset.duration is not None, f"{asset.asset_id} has no duration"
        assert 0.5 <= asset.duration <= 30, f"{asset.asset_id} duration out of range"


# ---------------------------------------------------------------------------
# Tests: Dialogue
# ---------------------------------------------------------------------------


def test_dialogue_has_one_line():
    assert len(LAST_MARKER_DIALOGUE) == 1
    assert LAST_MARKER_DIALOGUE[0].text == "Primero llegas. Despues compites."
    assert LAST_MARKER_DIALOGUE[0].asset_type == "dialogue"


# ---------------------------------------------------------------------------
# Tests: Music
# ---------------------------------------------------------------------------


def test_music_has_closing_guitar():
    assert len(LAST_MARKER_MUSIC) == 1
    assert LAST_MARKER_MUSIC[0].asset_id == "closing-guitar"
    assert "nylon" in LAST_MARKER_MUSIC[0].prompt.lower()


# ---------------------------------------------------------------------------
# Tests: Pipeline dry run
# ---------------------------------------------------------------------------


def test_pipeline_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        shot_list = _write_shot_list(Path(tmp))
        output = Path(tmp) / "audio"

        pipeline = SoundDesignPipeline(shot_list, output)
        results = pipeline.generate_sfx_library(dry_run=True)

        # Should return all assets without generating
        assert len(results) == len(LAST_MARKER_SFX_LIBRARY)
        assert all(not a.generated for a in results)


def test_pipeline_writes_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        shot_list = _write_shot_list(Path(tmp))
        output = Path(tmp) / "audio"

        pipeline = SoundDesignPipeline(shot_list, output)
        pipeline.generate_sfx_library(dry_run=True)
        pipeline.write_audio_manifest()

        manifest_path = output / "audio-manifest.json"
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text())
        assert "assets" in manifest
        assert "shot_assignments" in manifest
        assert len(manifest["assets"]) > 0


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
