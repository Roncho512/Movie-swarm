"""A crew call reaches an agent only after the Line Producer allows it."""

from __future__ import annotations

import json

from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.line_producer import LineProducer
from movie_swarm.treatment_doc import proposed_split
from tests.test_line_producer import _treatment


def test_dispatch_pauses_until_the_gates_are_open(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    LineProducer.start(production, run_id="run-1")
    called = []

    def handler(call):
        called.append(call.agent)
        return "ran"

    director = Director(production)
    call = CrewCall(agent="production", command="estimate", estimated_cost_usd=0, note="estimate")
    paused = director.dispatch(call, "run-1", handler=handler)
    assert paused.status == "paused"
    assert called == []
    assert paused.request_id

    _treatment(production)
    producer = LineProducer.open(production, "run-1")
    producer.approve_gate("treatment", "approved", "ron")
    still = director.dispatch(call, "run-1", handler=handler)
    assert still.status == "paused"
    assert "production gate" in still.message
    assert called == []

    producer.approve_gate("production", "approved", "ron")
    waiting_on_previs = director.dispatch(call, "run-1", handler=handler)
    assert waiting_on_previs.status == "paused"
    assert "previs" in waiting_on_previs.message
    assert called == []
    producer.approve_gate("previs", "approved", "ron")
    allowed = director.dispatch(call, "run-1", handler=handler)
    assert allowed.status == "ran"
    assert called == ["production"]
    assert producer.run.data["cost_usd"] == 0
    reloaded = LineProducer.open(production, "run-1")
    assert reloaded.record["ledger"][-1]["kind"] == "dry-run"
    assert reloaded.run.data["cost_usd"] == 0


def test_dispatch_pauses_when_the_estimate_breaks_the_cap(tmp_path):
    production = tmp_path / "demo"
    _treatment(production, split=proposed_split(500))
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("production", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    called = []
    director = Director(production)
    call = CrewCall(agent="qa", command="dry-run", estimated_cost_usd=600, note="too much")
    # QA gate is still closed, so close that first by approving it.
    producer.approve_gate("qa", "approved", "ron")
    result = director.dispatch(call, "run-1", handler=lambda c: called.append(c) or "no")
    assert result.status == "paused"
    assert "cap" in result.message
    assert called == []
    producer = LineProducer.open(production, "run-1")
    producer.decide_request(result.request_id, "approved", "ron")
    assert producer.run.data["cost_usd"] == 0
    again = director.dispatch(call, "run-1", handler=lambda c: called.append(c.agent) or "yes")
    assert again.status == "ran"
    assert called == ["qa"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_unknown_agent_is_refused(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    LineProducer.start(production, run_id="run-1")
    result = Director(production).dispatch(
        CrewCall(agent="colorist", command="dry-run", estimated_cost_usd=1),
        "run-1",
        handler=lambda call: "no",
    )
    assert result.status == "refused"
    assert "colorist" in result.message


def test_production_estimate_runs_for_real_without_charging(tmp_path):
    production = tmp_path / "demo"
    _treatment(production)
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("production", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    shot_list = tmp_path / "shot-list.json"
    shot_list.write_text(
        json.dumps({
            "shots": [{
                "shot_id": "s01-sh01",
                "scene_number": 1,
                "shot_number": 1,
                "sequence_position": 1,
                "generation_prompt": "Wide desert.",
                "target_duration_seconds": 4,
            }]
        }),
        encoding="utf-8",
    )
    result = Director(production).dispatch(
        CrewCall(
            agent="production",
            command="estimate",
            estimated_cost_usd=0,
            shot_list=str(shot_list),
            note="local estimate",
        ),
        "run-1",
    )
    assert result.status == "ran", result.message
    assert "TOTAL" in result.output
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_stage_allocation_blocks_a_cheap_looking_overage(tmp_path):
    production = tmp_path / "demo"
    _treatment(production, split={"production": 1, "treatment": 0})
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("production", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    called = []
    result = Director(production).dispatch(
        CrewCall(agent="production", command="dry-run", estimated_cost_usd=5, note="over the stage"),
        "run-1",
        handler=lambda call: called.append(True) or "no",
    )
    assert result.status == "paused"
    assert "allocation" in result.message
    assert called == []
