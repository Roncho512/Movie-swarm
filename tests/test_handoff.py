"""Handoff reads and writes fail loudly when the JSON does not match."""

from __future__ import annotations

import json

import pytest

from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.paths import repo_root


ROOT = repo_root()


def _shot(production_id: str = "demo") -> dict:
    return {
        "production_id": production_id,
        "version": "1.0.0",
        "total_shots": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "shots": [
            {
                "shot_id": "s01-sh01",
                "scene_number": 1,
                "shot_number": 1,
                "shot_type": "wide",
                "description": "Desert.",
                "generation_prompt": "Wide desert.",
                "target_duration_seconds": 4,
                "tool_routing": {"primary_tool": "seedance-2.0", "rationale": "Test."},
            }
        ],
    }


def test_round_trip(tmp_path):
    path = tmp_path / "shot-list.json"
    write_handoff(path, _shot())
    loaded = read_handoff(path)
    assert loaded["production_id"] == "demo"
    assert loaded["total_shots"] == 1


def test_invalid_write_does_not_create_the_file(tmp_path):
    path = tmp_path / "shot-list.json"
    with pytest.raises(HandoffError) as caught:
        write_handoff(path, {"production_id": "demo"})
    message = str(caught.value)
    assert "Invalid handoff" in message
    assert "shot-list.schema.json" in message
    assert "total_shots" in message
    assert "was not accepted" in message
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


def test_invalid_read_names_the_problem(tmp_path):
    path = tmp_path / "audio-manifest.json"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(HandoffError) as caught:
        read_handoff(path)
    assert "layers" in str(caught.value)
    assert caught.value.errors


def test_existing_audio_manifest_is_rejected():
    path = ROOT / "productions/the-last-marker/audio/audio-manifest.json"
    with pytest.raises(HandoffError) as caught:
        read_handoff(path)
    assert "audio-manifest.schema.json" in str(caught.value)
    assert any("layers" in error for error in caught.value.errors)


def test_broken_json(tmp_path):
    path = tmp_path / "shot-list.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(HandoffError) as caught:
        read_handoff(path)
    assert "not valid JSON" in str(caught.value)


def test_explicit_schema_name(tmp_path):
    path = tmp_path / "notes.json"
    write_handoff(path, _shot(), schema="shot-list")
    loaded = read_handoff(path, schema="shot-list")
    assert loaded["version"] == "1.0.0"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["shots"][0]["shot_id"] == "s01-sh01"
