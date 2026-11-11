"""
Tests for the Production agent pipeline logic.

Run with: python -m pytest tests/ -v
(from the agents/05-production directory)

These tests validate endpoint selection, payload construction, and cost
estimation without making any fal.ai API calls.
"""

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    Endpoint, Resolution, ShotSpec, Tier, estimate_cost
)
from src.pipeline import (
    ProductionPipeline,
    build_payload, load_shot_list, select_endpoint, _endpoint_type
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SHOT_LIST = {
    "production_id": "test-production",
    "version": "1.0.0",
    "total_shots": 3,
    "shots": [
        {
            "shot_id": "s01-sh01",
            "scene_number": 1,
            "shot_number": 1,
            "sequence_position": 1,
            "generation_prompt": "Wide shot of desert landscape at sunset.",
            "target_duration_seconds": 8,
            "aspect_ratio": "16:9",
            "tool_routing": {"primary_tool": "seedance-2.0"},
            "reference_assets": [
                {
                    "asset_type": "environment-ref",
                    "asset_id": "env-amber",
                    "path": "visual-assets/environment-refs/baja-desert-amber.png",
                    "usage_note": "Match landscape."
                }
            ],
        },
        {
            "shot_id": "s01-sh02",
            "scene_number": 1,
            "shot_number": 2,
            "sequence_position": 2,
            "generation_prompt": "@Image1 rides a motorcycle down a dusty road.",
            "target_duration_seconds": 10,
            "aspect_ratio": "16:9",
            "tool_routing": {"primary_tool": "seedance-2.0"},
            "reference_assets": [
                {
                    "asset_type": "character-ref",
                    "asset_id": "mv-riding",
                    "path": "https://example.com/miguel-front.png",
                    "usage_note": "Match rider."
                },
                {
                    "asset_type": "vehicle-ref",
                    "asset_id": "tr6-side",
                    "path": "https://example.com/triumph-side.png",
                    "usage_note": "Match motorcycle."
                }
            ],
        },
        {
            "shot_id": "s02-sh01",
            "scene_number": 2,
            "shot_number": 1,
            "sequence_position": 3,
            "generation_prompt": "Camera pans across rocky terrain.",
            "target_duration_seconds": 6,
            "aspect_ratio": "16:9",
            "tool_routing": {"primary_tool": "seedance-2.0"},
            "reference_assets": [],
        },
    ],
}


def _write_shot_list(tmp_dir: Path) -> Path:
    """Write sample shot list to a temp file and return the path."""
    p = tmp_dir / "shot-list.json"
    p.write_text(json.dumps(SAMPLE_SHOT_LIST, indent=2))
    return p


# ---------------------------------------------------------------------------
# Tests: Shot list loading
# ---------------------------------------------------------------------------


def test_load_shot_list():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_shot_list(Path(tmp))
        shots = load_shot_list(path)

    assert len(shots) == 3
    assert shots[0].shot_id == "s01-sh01"
    assert shots[1].generation_prompt.startswith("@Image1")
    assert shots[2].target_duration_seconds == 6
    # s01-sh01 has one environment ref
    assert len(shots[0].environment_ref_urls) == 1
    # s01-sh02 has character + vehicle ref merged into character_ref_urls
    assert len(shots[1].character_ref_urls) == 2
    # s02-sh01 has no refs at all
    assert len(shots[2].character_ref_urls) == 0


def test_shots_sorted_by_sequence_position():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_shot_list(Path(tmp))
        shots = load_shot_list(path)

    positions = [s.sequence_position for s in shots]
    assert positions == sorted(positions)


# ---------------------------------------------------------------------------
# Tests: Endpoint selection
# ---------------------------------------------------------------------------


def test_text_only_shot_selects_text_to_video():
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="Desert wide shot.",
        target_duration_seconds=8,
    )
    assert select_endpoint(shot, Tier.STANDARD) == Endpoint.TEXT_TO_VIDEO
    assert select_endpoint(shot, Tier.FAST) == Endpoint.FAST_TEXT_TO_VIDEO


def test_character_refs_selects_reference_to_video():
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="@Image1 walks forward.",
        target_duration_seconds=8,
        character_ref_urls=["https://example.com/ref.png"],
    )
    assert select_endpoint(shot, Tier.STANDARD) == Endpoint.REFERENCE_TO_VIDEO
    assert select_endpoint(shot, Tier.FAST) == Endpoint.FAST_REFERENCE_TO_VIDEO


def test_text_only_no_refs_selects_text_to_video():
    """Shot with empty reference_assets array → text-to-video."""
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="Desert wide shot.",
        target_duration_seconds=8,
    )
    assert select_endpoint(shot, Tier.STANDARD) == Endpoint.TEXT_TO_VIDEO


def test_audio_refs_selects_reference_to_video():
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="Lip sync dialogue.",
        target_duration_seconds=10,
        audio_ref_urls=["https://example.com/dialogue.wav"],
    )
    assert select_endpoint(shot, Tier.STANDARD) == Endpoint.REFERENCE_TO_VIDEO


# ---------------------------------------------------------------------------
# Tests: Payload construction
# ---------------------------------------------------------------------------


def test_text_to_video_payload():
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="Desert wide shot.",
        target_duration_seconds=8,
    )
    payload = build_payload(shot, Endpoint.TEXT_TO_VIDEO, Resolution.P720)

    assert payload["prompt"] == "Desert wide shot."
    assert payload["resolution"] == "720p"
    assert payload["duration"] == "8"
    assert payload["aspect_ratio"] == "16:9"
    assert payload["generate_audio"] is True
    assert "image_url" not in payload
    assert "image_urls" not in payload


def test_reference_to_video_payload_includes_image_urls():
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="@Image1 walks forward.",
        target_duration_seconds=8,
        character_ref_urls=["https://example.com/a.png", "https://example.com/b.png"],
        environment_ref_urls=["https://example.com/env.png"],
    )
    payload = build_payload(shot, Endpoint.REFERENCE_TO_VIDEO, Resolution.P720)

    assert "image_urls" in payload
    assert len(payload["image_urls"]) == 3
    assert "image_url" not in payload  # that's for image-to-video


def test_image_to_video_payload_includes_image_url():
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="Animate.",
        target_duration_seconds=6,
        start_frame_url="https://example.com/frame.png",
    )
    payload = build_payload(shot, Endpoint.IMAGE_TO_VIDEO, Resolution.P480)

    assert payload["image_url"] == "https://example.com/frame.png"
    assert payload["resolution"] == "480p"


def test_reference_caps_at_9_images():
    shot = ShotSpec(
        shot_id="test", scene_number=1, shot_number=1,
        sequence_position=1, generation_prompt="Crowd scene.",
        target_duration_seconds=10,
        character_ref_urls=[f"https://example.com/{i}.png" for i in range(12)],
    )
    payload = build_payload(shot, Endpoint.REFERENCE_TO_VIDEO, Resolution.P720)
    assert len(payload["image_urls"]) == 9  # capped at Seedance max


# ---------------------------------------------------------------------------
# Tests: Cost estimation
# ---------------------------------------------------------------------------


def test_standard_720p_text_to_video_cost():
    cost = estimate_cost(Tier.STANDARD, Resolution.P720, "text-to-video", 10)
    assert abs(cost - 3.034) < 0.01


def test_fast_720p_cost_is_cheaper():
    standard = estimate_cost(Tier.STANDARD, Resolution.P720, "text-to-video", 10)
    fast = estimate_cost(Tier.FAST, Resolution.P720, "text-to-video", 10)
    assert fast < standard


def test_video_input_multiplier():
    without = estimate_cost(Tier.STANDARD, Resolution.P720, "reference-to-video", 10)
    with_vid = estimate_cost(Tier.STANDARD, Resolution.P720, "reference-to-video", 10, has_video_inputs=True)
    assert abs(with_vid - without * 0.6) < 0.01


# ---------------------------------------------------------------------------
# Tests: Load real shot list
# ---------------------------------------------------------------------------


def test_load_real_shot_list():
    """Verify loader handles the actual The Last Marker shot list."""
    real_path = Path(__file__).parent.parent.parent.parent.parent / \
        "productions" / "the-last-marker" / "shot-lists" / "shot-list.json"
    if not real_path.exists():
        # Skip if running outside the full repo
        return
    shots = load_shot_list(real_path)
    assert len(shots) == 22
    # s01-sh01 has one environment ref
    assert len(shots[0].environment_ref_urls) >= 1
    # s01-sh02 has character + vehicle refs
    assert len(shots[1].character_ref_urls) >= 2
    # All shots sorted by sequence position
    positions = [s.sequence_position for s in shots]
    assert positions == sorted(positions)


def test_paid_run_is_refused_before_the_provider(tmp_path, monkeypatch):
    import pytest

    called = []
    monkeypatch.setattr("src.pipeline.generate_shot", lambda *args, **kwargs: called.append(True))
    shot_list = tmp_path / "shot-list.json"
    shot_list.write_text(json.dumps({
        "shots": [{
            "shot_id": "s01-sh01",
            "scene_number": 1,
            "shot_number": 1,
            "sequence_position": 1,
            "generation_prompt": "A dock at night.",
            "target_duration_seconds": 4,
        }]
    }), encoding="utf-8")
    pipeline = ProductionPipeline(shot_list, tmp_path / "out")
    with pytest.raises(RuntimeError, match="generation gate"):
        pipeline.run(dry_run=False)
    assert called == []


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
