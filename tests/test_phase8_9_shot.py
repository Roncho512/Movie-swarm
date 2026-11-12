"""Phase 8.9: a test shot can name a wired model, and it prints the quote first.

Nothing here opens a socket. Harbor Night is the fixture.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from movie_swarm.budget import load_rate_card as load_budget_rates
from movie_swarm.budget import write_film_budget, proposed_document
from movie_swarm.http_retry import HttpResult
from movie_swarm.line_producer import LineProducer
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.providers import CallSettings, run_test_shot
from movie_swarm.shot_model import ShotModelError, resolve_shot_model, wired_model_ids
from movie_swarm.studio import run_studio
from movie_swarm.treatment_doc import proposed_split
from tests.test_phase8_5 import SECRET, Scripted, _ok_script, _settings


def _harbor(tmp_path: Path) -> Path:
    source = repo_root() / "tests" / "fixtures" / "harbor-night"
    production = tmp_path / "harbor-night"
    shutil.copytree(source, production)
    lock_props(production)
    frames = {
        "frames": [
            {
                "shot_id": "s01-sh01",
                "scene_id": "s01",
                "duration_seconds": 4,
                "board_prompt": "Ada wears a red scarf on the dock.",
                "props_in_frame": ["red-scarf"],
            }
        ]
    }
    board = production / "storyboard"
    board.mkdir(exist_ok=True)
    (board / "storyboard.json").write_text(json.dumps(frames), encoding="utf-8")
    return production


def _open(production: Path) -> LineProducer:
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", stage_split=proposed_split(500))
    producer.approve_gate("production", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    return producer


def test_picture_tiers_match_the_budget_rate_card():
    routing = resolve_model("production")
    card = load_budget_rates()
    picture = card["stages"]["production"]["tiers"]
    assert set(routing["tiers"]) == {"good", "better", "best"}
    for name, row in picture.items():
        assert routing["tiers"][name] == row["model"]
    assert routing["tiers"]["good"] == "gemini-omni-1.2-flash"
    assert routing["tiers"]["better"] == "seedance-2.0-fast"
    assert routing["tiers"]["best"] == "seedance-2.0"
    assert wired_model_ids() == ["seedance-2.0-fast", "seedance-2.0"]
    rates = json.loads((repo_root() / "config" / "generation-rates.json").read_text(encoding="utf-8"))
    gemini = next(row for row in rates["generators"] if row["model"] == "gemini-omni-1.2-flash")
    assert gemini.get("status") == "planned"
    assert "endpoint" not in gemini


def test_model_then_tier_then_budget_then_routing(tmp_path):
    production = _harbor(tmp_path)
    write_film_budget(
        production,
        proposed_document(500, trailer_on=False, contingency_percent=0, tiers={"production": "best"}),
    )
    by_model = resolve_shot_model(production, model="seedance-2.0-fast", tier="good", shot_id="s01-sh01")
    assert by_model["model"] == "seedance-2.0-fast"
    assert by_model["source"] == "model"
    assert by_model["tier"] == "better"
    assert "--model seedance-2.0-fast overrides --tier good." in by_model["note"]
    by_tier = resolve_shot_model(production, tier="better", shot_id="s01-sh01")
    assert by_tier["model"] == "seedance-2.0-fast"
    assert by_tier["source"] == "tier"
    by_budget = resolve_shot_model(production, shot_id="s01-sh01")
    assert by_budget["model"] == "seedance-2.0"
    assert by_budget["source"] == "budget"
    assert by_budget["tier"] == "best"
    bare = tmp_path / "no-budget"
    shutil.copytree(production, bare)
    (bare / "budget.json").unlink()
    routed = resolve_shot_model(bare, shot_id="s01-sh01")
    assert routed["model"] == "gemini-omni-1.2-flash"
    assert routed["source"] == "routing"
    assert routed["wired"] is False


def test_an_unknown_model_or_tier_is_rejected(tmp_path):
    production = _harbor(tmp_path)
    with pytest.raises(ShotModelError) as caught:
        resolve_shot_model(production, model="not-a-model")
    assert "not on the rate card" in str(caught.value)
    with pytest.raises(ShotModelError):
        resolve_shot_model(production, tier="luxury")


def test_dry_run_quotes_seedance_fast_and_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    transport = Scripted(_ok_script())
    spoken = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=False,
        settings=_settings(transport),
        model="seedance-2.0-fast",
        announce=spoken.append,
    )
    assert spoken == []
    assert transport.calls == []
    assert result["status"] == "offline"
    assert result["sent"] is False
    assert result["message"].startswith("Offline is the default.")
    assert "Nothing was sent." in result["message"]
    quote = (
        "Shot s01-sh01: model seedance-2.0-fast, tier better, provider fal.ai, "
        "resolution 720p, duration 4 seconds, estimated cost $0.9676.\n"
        "Production line remaining: $270.00. Film remaining: $500.00."
    )
    assert result["quote"] == quote
    assert quote in result["message"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert SECRET not in result["message"]


def test_an_unwired_model_is_refused_and_lists_the_wired_choices(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        tier="good",
    )
    assert result["status"] == "refused"
    assert "gemini-omni-1.2-flash" in result["message"]
    assert "endpoint" in result["message"]
    assert "seedance-2.0-fast" in result["message"]
    assert "--model seedance-2.0-fast" in result["message"]
    assert "--tier better" in result["message"]
    assert "seedance-2.0" in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_the_quote_is_printed_before_a_live_call(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    order = []

    class Watching(Scripted):
        def __call__(self, method, url, headers, body, timeout):
            order.append("call")
            return super().__call__(method, url, headers, body, timeout)

    def announce(text):
        order.append("quote")
        assert "seedance-2.0-fast" in text
        assert "estimated cost $0.9676" in text
        assert SECRET not in text

    transport = Watching(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="seedance-2.0-fast",
        announce=announce,
    )
    assert result["status"] == "generated", result["message"]
    assert order[0] == "quote"
    assert "call" in order
    assert transport.calls
    assert SECRET not in result["message"]


def test_the_guide_dry_run_quotes_the_boarded_harbor_shot(tmp_path):
    production = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", production)
    write_film_budget(
        production,
        proposed_document(500, trailer_on=False, contingency_percent=0),
    )
    LineProducer.start(production, run_id="guide-1")
    assert run_studio(production, run_id="guide-1")["stopped_at"] == "treatment"
    LineProducer.open(production, "guide-1").approve_gate(
        "treatment", "approved", "ron", note="The treatment can proceed."
    )
    assert run_studio(production, run_id="guide-1")["stopped_at"] == "previs"
    result = run_test_shot(
        LineProducer.open(production, "guide-1"),
        "s01-sh01",
        live=False,
        model="seedance-2.0-fast",
        announce=lambda _text: None,
    )
    assert result["quote"] == (
        "Shot s01-sh01: model seedance-2.0-fast, tier better, provider fal.ai, "
        "resolution 720p, duration 2.087 seconds (sent as 4 seconds), estimated cost $0.9676.\n"
        "Production line remaining: $270.00. Film remaining: $500.00."
    )
    assert result["message"].startswith("Offline is the default.")
    assert "Nothing was sent." in result["message"]
    assert result["sent"] is False


def test_cli_rejects_an_unknown_model_before_a_call(tmp_path, capsys):
    production = _harbor(tmp_path)
    _open(production)
    from movie_swarm.cli_line_producer import main

    code = main([
        "--production", str(production),
        "--run", "run-1",
        "test-shot",
        "--shot", "s01-sh01",
        "--model", "not-a-model",
    ])
    captured = capsys.readouterr()
    assert code == 1
    assert "not on the rate card" in captured.out
    assert "Nothing was sent." not in captured.out or "not on the rate card" in captured.out
