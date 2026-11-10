"""Line Producer: cap, stage split, gates, and Ron's decisions."""

from __future__ import annotations

import json

import pytest

from movie_swarm.handoff import write_handoff
from movie_swarm.line_producer import LineProducer, LineProducerError
from movie_swarm.treatment_doc import proposed_split


def _treatment(production, split=None, cap=500):
    production.mkdir(parents=True, exist_ok=True)
    (production / "treatment").mkdir(exist_ok=True)
    document = {
        "version": "0.1.0",
        "status": "draft",
        "approval": {"state": "pending", "by": None, "at": None, "note": ""},
        "production_id": production.name,
        "title": "Demo",
        "logline": "A rider chooses.",
        "theme_and_emotional_intent": {"theme": "Survival", "emotional_intent": "Relief."},
        "tone_and_genre": {"tone": "Sparse", "genre": "western"},
        "characters": [{"name": "Miguel", "role": "protagonist", "look": "Lean."}],
        "scenes": [{"what_happens": "He rides.", "emotional_purpose": "The desert is larger."}],
        "deliverables": {"aspect_ratio": "2.39:1", "resolution": "1920x1080", "length": "3 minutes"},
        "open_questions": [],
        "constraints_and_budget": {
            "budget_cap_usd": cap,
            "stage_split": split if split is not None else proposed_split(cap),
        },
    }
    write_handoff(production / "treatment" / "treatment.json", document, schema="treatment")


def test_start_copies_the_film_cap_and_names_ron(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    producer = LineProducer.start(production, run_id="run-1")
    assert producer.run.data["budget_cap_usd"] == 500
    assert producer.run.data["cost_usd"] == 0
    assert producer.run.data["status"] == "waiting-for-review"
    assert producer.record["credits"][0] == {"role": "Executive Producer", "name": "Ron"}
    text = producer.status_text()
    assert "Spent: $0.00 of $500.00" in text
    assert "waiting on Ron" in text
    assert "Stage allocations are not locked" in text


def test_spend_under_the_cap_is_recorded(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    producer = LineProducer.start(production, run_id="run-1")
    result = producer.record_spend("director", 2, "model draft")
    assert result.recorded is True
    assert result.total_usd == 2
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 2
    assert producer.record["ledger"][0]["kind"] == "generation"


def test_spend_over_the_cap_pauses_and_can_be_approved(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    producer = LineProducer.start(production, run_id="run-1")
    producer.record_spend("director", 500, "fill the cap")
    paused = producer.record_spend("line-producer", 20, "one more pass")
    assert paused.recorded is False
    assert paused.request_id
    assert "over the $500.00 cap" in paused.message
    assert producer.run.data["cost_usd"] == 500
    message = producer.decide_request(paused.request_id, "approved", "ron", note="Allow it.")
    assert "now spent" in message
    reloaded = LineProducer.open(production, "run-1")
    assert reloaded.run.data["cost_usd"] == 520
    assert "approved past the $500.00 cap" in reloaded.status_text()


def test_rejected_extra_spend_is_not_charged(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    producer = LineProducer.start(production, run_id="run-1")
    producer.record_spend("director", 500, "fill the cap")
    paused = producer.record_spend("line-producer", 5, "no")
    producer.decide_request(paused.request_id, "rejected", "ron")
    assert producer.run.data["cost_usd"] == 500


def test_stage_allocation_blocks_a_retake_until_ron_approves(tmp_path):
    production = tmp_path / "demo"
    _treatment(production, split={"production": 10, "director": 0})
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", note="Lock the small split.")
    producer.approve_gate("production", "approved", "ron", note="Picture may spend.")
    assert producer.record["stage_allocations"]["status"] == "approved"
    first = producer.record_spend("production", 6, "first take")
    assert first.recorded is True
    retake = producer.record_spend("production", 5, "retake the wide", kind="retake")
    assert retake.recorded is False
    assert "allocation" in retake.message
    assert producer.stage_spent("production") == 6
    producer.decide_request(retake.request_id, "approved", "ron")
    assert producer.stage_spent("production") == 11
    assert producer.record["stage_allocations"]["split"]["production"] == 11
    kinds = [entry["kind"] for entry in producer.record["ledger"]]
    assert kinds == ["generation", "retake"]


def test_split_over_the_cap_is_not_locked(tmp_path):
    production = tmp_path / "demo"
    _treatment(production, split={"production": 600})
    producer = LineProducer.start(production, run_id="run-1")
    with pytest.raises(LineProducerError) as caught:
        producer.approve_gate("treatment", "approved", "ron")
    assert "over" in str(caught.value)
    assert producer.record["stage_allocations"]["status"] == "unlocked"
    assert producer.gate_decision("treatment") is None


def test_crew_spend_waits_for_the_gate(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    producer = LineProducer.start(production, run_id="run-1")
    paused = producer.record_spend("production", 1, "a clip")
    assert paused.recorded is False
    assert "treatment gate" in paused.message
    assert producer.run.data["cost_usd"] == 0


def test_unknown_stage_is_refused(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    producer = LineProducer.start(production, run_id="run-1")
    with pytest.raises(LineProducerError) as caught:
        producer.record_spend("colorist", 1, "grade")
    assert "colorist" in str(caught.value)


def test_approve_gate_from_a_file(tmp_path):
    production = tmp_path / "demo"
    _treatment(production)
    producer = LineProducer.start(production, run_id="run-1")
    decision = {
        "stage": "treatment",
        "decision": "approved",
        "by": "ron",
        "note": "Lock it.",
    }
    path = tmp_path / "ron.json"
    path.write_text(json.dumps(decision), encoding="utf-8")
    from movie_swarm.cli_line_producer import main

    code = main([
        "--production",
        str(production),
        "--run",
        "run-1",
        "approve-gate",
        "--file",
        str(path),
    ])
    assert code == 0
    reloaded = LineProducer.open(production, "run-1")
    assert reloaded.gate_decision("treatment") == "approved"
    assert reloaded.record["stage_allocations"]["status"] == "approved"
    treatment = json.loads((production / "treatment" / "treatment.json").read_text())
    assert treatment["status"] == "approved"
    assert treatment["approval"]["by"] == "ron"
