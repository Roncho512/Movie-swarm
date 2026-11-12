"""Phase 8.11: a picture call with no reported dollars stays an estimate."""

from __future__ import annotations

import json

from movie_swarm.http_retry import HttpResult
from movie_swarm.line_producer import LineProducer, estimate_backed_spend
from movie_swarm.money import as_money
from movie_swarm.providers import run_test_shot
from movie_swarm.validate import validate_file
from tests.test_phase8_10_fal import _submit_body
from tests.test_phase8_5 import SECRET, Scripted, _harbor, _open, _settings


def _finish(cost=None) -> list:
    body = {"video": {"url": "https://cdn.example/clip.mp4"}}
    if cost is not None:
        body["cost_usd"] = cost
    return [
        _submit_body(),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps(body).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ]


def test_a_missing_dollar_amount_is_marked_as_an_estimate(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(Scripted(_finish())),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "generated", result["message"]
    assert "not a measured charge" in result["message"]
    finished = LineProducer.open(production, "run-1")
    entry = next(item for item in finished.record["ledger"] if item.get("call_phase") == "settled")
    assert entry["actual_usd"] is None
    assert entry["actual_source"] == "estimate"
    assert as_money(entry["amount_usd"]) == as_money(entry["estimate_usd"])
    assert as_money(finished.run.data["cost_usd"]) == as_money(entry["estimate_usd"])
    text = finished.status_text()
    assert "still the estimate" in text
    assert "did not report a dollar amount" in text
    assert SECRET not in text
    assert SECRET not in json.dumps(finished.record)
    checked = validate_file(production / "runs" / "run-1" / "line-producer.json")
    assert checked.ok, checked.errors


def test_a_reported_dollar_amount_is_a_measured_charge(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(Scripted(_finish("0.50"))),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "generated", result["message"]
    finished = LineProducer.open(production, "run-1")
    entry = next(item for item in finished.record["ledger"] if item.get("call_phase") == "settled")
    assert entry["actual_source"] == "provider"
    assert as_money(entry["actual_usd"]) == as_money("0.50")
    assert "still the estimate" not in finished.status_text()
    checked = validate_file(production / "runs" / "run-1" / "line-producer.json")
    assert checked.ok, checked.errors


def test_a_released_estimate_is_not_still_on_the_spend():
    record = {
        "ledger": [
            {
                "entry_id": "spend-001",
                "kind": "generation",
                "amount_usd": 0.9676,
                "actual_source": "estimate",
            },
            {
                "entry_id": "spend-002",
                "kind": "release",
                "amount_usd": 0.9676,
                "releases_entry_id": "spend-001",
            },
            {
                "entry_id": "spend-003",
                "kind": "generation",
                "amount_usd": 0.5,
                "actual_source": "provider",
            },
        ]
    }
    assert estimate_backed_spend(record) == 0
