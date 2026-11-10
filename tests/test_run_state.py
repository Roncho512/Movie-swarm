"""Run state can be written and read back."""

from __future__ import annotations

import json

import pytest

from movie_swarm.gates import would_exceed_budget
from movie_swarm.handoff import HandoffError
from movie_swarm.run_state import RunState


def test_create_update_and_reload(tmp_path):
    production = tmp_path / "the-last-marker"
    production.mkdir()
    state = RunState.create(production, run_id="run-1", budget_cap=500)
    assert state.path == production / "runs" / "run-1" / "run-state.json"
    assert state.data["stage"] == "screenwriter"
    assert state.data["status"] == "pending"
    assert state.data["cost_usd"] == 0
    assert state.data["budget_cap_usd"] == 500

    state.set_stage("production", status="running")
    state.add_artifact(
        "clip-metadata",
        "seedance-output/clip-metadata.json",
        schema="clip-metadata.schema.json",
    )
    total = state.add_cost("12.50")
    assert total == 12.5

    loaded = RunState.load(state.path)
    assert loaded.data["stage"] == "production"
    assert loaded.data["status"] == "running"
    assert loaded.data["cost_usd"] == 12.5
    assert loaded.data["artifacts"] == [
        {
            "name": "clip-metadata",
            "path": "seedance-output/clip-metadata.json",
            "schema": "clip-metadata.schema.json",
        }
    ]
    on_disk = json.loads(state.path.read_text(encoding="utf-8"))
    assert on_disk["run_id"] == "run-1"
    assert would_exceed_budget(
        "487.5",
        spent_usd=loaded.data["cost_usd"],
        cap_usd=loaded.data["budget_cap_usd"],
    ) is False
    assert would_exceed_budget(
        "487.5001",
        spent_usd=loaded.data["cost_usd"],
        cap_usd=loaded.data["budget_cap_usd"],
    ) is True


def test_invalid_status_is_not_written(tmp_path):
    production = tmp_path / "the-last-marker"
    production.mkdir()
    state = RunState.create(production, run_id="run-2")
    state.data["status"] = "almost"
    with pytest.raises(HandoffError) as caught:
        state.save()
    assert "status" in str(caught.value)
    reloaded = RunState.load(state.path)
    assert reloaded.data["status"] == "pending"


def test_negative_cost_is_refused(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    state = RunState.create(production, run_id="run-3", budget_cap=500)
    with pytest.raises(ValueError):
        state.add_cost(-1)
    assert RunState.load(state.path).data["cost_usd"] == 0


def test_run_id_cannot_escape_the_production_folder(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    with pytest.raises(ValueError):
        RunState.create(production, run_id="../other")
