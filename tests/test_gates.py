"""Review gates and the budget cap are config, not code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from movie_swarm.gates import budget_cap_usd, is_stage_gated, load_gate_config, would_exceed_budget
from movie_swarm.paths import repo_root


def test_shipped_config_gates_every_stage_and_caps_at_500():
    config = load_gate_config()
    assert config["budget_cap_usd"] == 500
    assert config["currency"] == "USD"
    assert config["gates"]
    assert all(config["gates"].values())
    assert budget_cap_usd() == 500
    for stage in config["gates"]:
        assert is_stage_gated(stage) is True


def test_turning_a_gate_off_is_a_config_edit(tmp_path):
    source = json.loads((repo_root() / "config" / "gates.json").read_text(encoding="utf-8"))
    source["gates"]["qa"] = False
    source["budget_cap_usd"] = 100
    path = tmp_path / "gates.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    assert is_stage_gated("QA", config_path=path) is False
    assert is_stage_gated("sound_designer", config_path=path) is True
    assert budget_cap_usd(path) == 100
    assert would_exceed_budget(100, config_path=path) is False
    assert would_exceed_budget(100.01, config_path=path) is True


def test_unknown_stage_is_an_error():
    with pytest.raises(ValueError) as caught:
        is_stage_gated("colorist")
    assert "colorist" in str(caught.value)
    assert "config/gates.json" in str(caught.value)


def test_exact_cap_is_allowed_and_over_is_not():
    assert would_exceed_budget(500, spent_usd=0, cap_usd=500) is False
    assert would_exceed_budget(0, spent_usd=500, cap_usd=500) is False
    assert would_exceed_budget(1, spent_usd=499.5, cap_usd=500) is True


def test_negative_spend_is_refused():
    with pytest.raises(ValueError):
        would_exceed_budget(-1)


def test_shipped_file_is_the_one_the_function_reads():
    path = repo_root() / "config" / "gates.json"
    assert Path(path).is_file()
    assert load_gate_config(path)["budget_cap_usd"] == 500
