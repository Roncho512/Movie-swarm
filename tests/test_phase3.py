"""Phase 3 studio: a generation quote, a paid-call gate, and continuity on the prompt.

The proof is Harbor Night, a synthetic production. Nothing here prices or
writes The Last Marker.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.generation import (
    OfflineGenerationClient,
    build_generation_plan,
    generate_shots,
    render_plan,
)
from movie_swarm.line_producer import LineProducer
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.treatment_doc import proposed_split


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
            },
            {
                "shot_id": "s01-sh02",
                "scene_id": "s01",
                "duration_seconds": 20,
                "board_prompt": "The dock at night.",
                "props_in_frame": [],
            },
        ]
    }
    board = production / "storyboard"
    board.mkdir()
    (board / "storyboard.json").write_text(json.dumps(frames), encoding="utf-8")
    return production


def _open_picture_gates(production: Path, split: dict | None = None) -> LineProducer:
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", stage_split=split)
    producer.approve_gate("production", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    return producer


class FakeClient:
    def __init__(self):
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        return {"status": "fake", "cost_usd": 0, "clip_ref": None}


def test_harbor_plan_prices_published_rates_and_adds_the_lock(tmp_path):
    production = _harbor(tmp_path)
    plan = build_generation_plan(production, allocations=proposed_split(500))
    text = render_plan(plan)

    assert plan["title"] == "Harbor Night"
    assert plan["dry_run"] is True
    assert plan["spent_usd"] == 0
    assert plan["picture_usd"] == 3.36
    assert plan["retake_reserve_usd"] == 1.68
    assert plan["fix_loop_reserve_usd"] == 50
    first, second = plan["shots"]
    assert first["generator"].startswith("Gemini Omni 1.2 Flash")
    assert first["takes_allowed"] == 2
    assert first["requested_seconds"] == 4
    assert first["preview_usd"] == 0.28
    assert first["final_usd"] == 0.28
    assert "scarf on the right shoulder" in first["prompt"]
    assert "scarf on the right shoulder" in first["added_phrases"]
    assert second["pieces"] == [15, 5]
    assert second["billed_seconds"] == 20
    production_row = next(row for row in plan["stages"] if row["stage"] == "production")
    art_row = next(row for row in plan["stages"] if row["stage"] == "art-director")
    assert production_row["estimated_usd"] == 5.04
    assert production_row["locked_usd"] == 270
    assert production_row["within_allocation"] is True
    assert art_row["estimated_usd"] == 0
    assert art_row["locked_usd"] == 25
    assert "https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemini-omni-1-2-flash/" in text
    assert "2026-11-05" in text
    assert "This is an assumption." in text or "Assumption" in text
    assert "the-last-marker" not in text.casefold()
    assert "breitling" not in text.casefold()


def test_dispatch_writes_the_quote_without_spending(tmp_path):
    production = _harbor(tmp_path)
    _open_picture_gates(production)
    output = tmp_path / "quote"
    result = Director(production).dispatch(
        CrewCall(
            agent="production",
            command="plan",
            estimated_cost_usd=0,
            output_dir=str(output),
            note="dry-run quote",
        ),
        "run-1",
    )
    assert result.status == "ran", result.message
    written = (output / "generation-plan.md").read_text(encoding="utf-8")
    assert "Harbor Night" in written
    assert "No image or video was requested" in written
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert not (repo_root() / "productions" / "the-last-marker" / "generation-plan.md").exists()


def test_generate_waits_for_the_generation_gate(tmp_path):
    production = _harbor(tmp_path)
    _open_picture_gates(production)
    client = FakeClient()
    paused = Director(production).dispatch(
        CrewCall(
            agent="production",
            command="generate",
            estimated_cost_usd=0,
            client=client,
            note="paid picture",
        ),
        "run-1",
    )
    assert paused.status == "paused"
    assert "generation gate" in paused.message
    assert client.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    closed = generate_shots(production, client=client, gate_open=False)
    assert closed["called"] is False
    assert client.calls == []


def test_an_open_gate_still_uses_the_offline_client(tmp_path):
    production = _harbor(tmp_path)
    producer = _open_picture_gates(production)
    producer.approve_gate("generation", "approved", "ron")
    result = Director(production).dispatch(
        CrewCall(agent="production", command="generate", estimated_cost_usd=0, note="still offline"),
        "run-1",
    )
    assert result.status == "ran", result.message
    assert "No image or video was made" in result.output
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    offline = generate_shots(production, client=OfflineGenerationClient(), gate_open=True)
    assert all(item["response"]["status"] == "not-sent" for item in offline["shots"])
    assert all(item["review"]["watched"] is False for item in offline["shots"])
    assert all(item["review"]["status"] == "not-reviewed" for item in offline["shots"])
    assert "scarf on the right shoulder" in offline["shots"][0]["review"]["phrases"]


def test_a_fake_client_runs_only_after_approval_and_keeps_the_phrase(tmp_path):
    production = _harbor(tmp_path)
    producer = _open_picture_gates(production)
    producer.approve_gate("generation", "approved", "ron")
    client = FakeClient()
    result = Director(production).dispatch(
        CrewCall(agent="production", command="generate", estimated_cost_usd=0, client=client),
        "run-1",
    )
    assert result.status == "ran", result.message
    assert [call["shot_id"] for call in client.calls] == ["s01-sh01", "s01-sh02"]
    assert "scarf on the right shoulder" in client.calls[0]["prompt"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_a_forbidden_phrase_is_not_sent(tmp_path):
    production = _harbor(tmp_path)
    board = json.loads((production / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))
    board["frames"][0]["board_prompt"] = "A scarf on the left shoulder."
    (production / "storyboard" / "storyboard.json").write_text(json.dumps(board), encoding="utf-8")
    client = FakeClient()
    result = generate_shots(production, client=client, gate_open=True)
    assert result["shots"][0]["status"] == "blocked"
    assert [call["shot_id"] for call in client.calls] == ["s01-sh02"]


def test_the_stage_allocation_blocks_before_the_client(tmp_path):
    production = _harbor(tmp_path)
    _open_picture_gates(production, split={"production": 1, "treatment": 0})
    producer = LineProducer.open(production, "run-1")
    producer.approve_gate("generation", "approved", "ron")
    client = FakeClient()
    result = Director(production).dispatch(
        CrewCall(agent="production", command="generate", estimated_cost_usd=5, client=client, note="over the stage"),
        "run-1",
    )
    assert result.status == "paused"
    assert "allocation" in result.message
    assert client.calls == []


def test_a_routing_override_uses_the_alternate_rate(tmp_path):
    production = _harbor(tmp_path)
    routing = json.loads((repo_root() / "config" / "model-routing.json").read_text(encoding="utf-8"))
    routing["overrides"] = [
        {"role": "production", "shot": "s01-sh01", "model": "kling-4.0", "provider": "kling"}
    ]
    path = tmp_path / "model-routing.json"
    path.write_text(json.dumps(routing), encoding="utf-8")
    plan = build_generation_plan(production, allocations={"production": 270}, routing_path=path)
    first = plan["shots"][0]
    assert first["preview_model"] == "kling-4.0"
    assert first["preview_usd"] == 0.628
    assert "Kling 4.0" in first["generator"]
    assert "routing override" in first["generator"]


def test_an_unknown_generator_is_not_given_a_made_up_price(tmp_path):
    production = _harbor(tmp_path)
    routing = json.loads((repo_root() / "config" / "model-routing.json").read_text(encoding="utf-8"))
    routing["overrides"] = [
        {"role": "production", "shot": "s01-sh02", "model": "unlisted-model", "provider": "none"}
    ]
    path = tmp_path / "model-routing.json"
    path.write_text(json.dumps(routing), encoding="utf-8")
    plan = build_generation_plan(production, routing_path=path)
    second = plan["shots"][1]
    assert second["priced"] is False
    assert second["shot_usd"] is None
    assert any("unlisted-model" in note for note in second["notes"])
