"""Phase 8.11: a fal picture call waits long enough for a real Seedance job.

Nothing here opens a socket. The sleeper records the pauses.
"""

from __future__ import annotations

import json

from movie_swarm.http_retry import HttpResult
from movie_swarm.line_producer import LineProducer
from movie_swarm.paths import repo_root
from movie_swarm.providers import CallSettings, poll_window, run_test_shot
from tests.test_phase8_10_fal import STATUS_URL, _submit_body
from tests.test_phase8_5 import SECRET, Scripted, _harbor, _open, _settings


def _status(state, **extra) -> HttpResult:
    payload = {"status": state}
    payload.update(extra)
    return HttpResult(200, json.dumps(payload).encode())


def _ready(cost=None) -> list:
    body = {"video": {"url": "https://cdn.example/clip.mp4"}}
    if cost is not None:
        body["cost_usd"] = cost
    return [
        _status("COMPLETED"),
        HttpResult(200, json.dumps(body).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ]


def test_the_default_wait_is_ten_minutes_with_a_rising_pause():
    window = poll_window(CallSettings())
    assert window["wait"] == 600
    assert window["start"] == 5
    assert window["step"] == 5
    assert window["maximum"] == 15
    assert window["every"] == 30
    config = json.loads((repo_root() / "config" / "providers.json").read_text(encoding="utf-8"))
    assert config["fal"]["wait_seconds"] == 600
    assert config["fal"]["backoff_start_seconds"] == 5
    assert config["fal"]["backoff_max_seconds"] == 15


def test_the_pauses_rise_and_a_progress_line_names_the_status(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    script = [
        _submit_body(),
        _status("IN_QUEUE", queue_position=2),
        _status("IN_QUEUE", queue_position=1),
        _status("IN_PROGRESS"),
        _status("IN_PROGRESS"),
        *_ready("0.50"),
    ]
    transport = Scripted(script)
    pauses = []
    lines = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=CallSettings(
            transport=transport,
            sleeper=pauses.append,
            progress=lines.append,
            poll_interval=5,
            poll_interval_max=15,
            wait_seconds=600,
            progress_every=30,
        ),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "generated", result["message"]
    assert pauses == [5, 10, 15, 15]
    assert lines == ["Waiting 30s. fal status IN_PROGRESS."]
    assert SECRET not in " ".join(lines)
    assert transport.calls[1]["url"] == STATUS_URL


def test_a_queue_position_is_printed_including_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted([
        _submit_body(),
        _status("IN_QUEUE", queue_position=0),
        *_ready("0.50"),
    ])
    lines = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=CallSettings(
            transport=transport,
            sleeper=lambda _seconds: None,
            progress=lines.append,
            poll_interval=5,
            poll_interval_max=15,
            wait_seconds=600,
            progress_every=5,
        ),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "generated", result["message"]
    assert lines == ["Waiting 5s. fal status IN_QUEUE. Queue position 0."]


def test_a_short_wait_keeps_the_estimate_and_a_rerun_does_not_resend(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted([
        _submit_body(),
        _status("IN_PROGRESS"),
        _status("IN_PROGRESS"),
        _status("IN_PROGRESS"),
    ])
    pauses = []
    failed = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=CallSettings(
            transport=transport,
            sleeper=pauses.append,
            progress=lambda _line: None,
            poll_interval=5,
            poll_interval_max=15,
            wait_seconds=12,
        ),
        model="seedance-2.0-fast",
    )
    assert failed["status"] == "failed"
    assert "did not finish before the poll limit" in failed["message"]
    assert "estimate stays booked" in failed["message"]
    assert "does not send a new one" in failed["message"]
    assert pauses == [5, 7]
    assert [call["method"] for call in transport.calls] == ["POST", "GET", "GET"]
    held = LineProducer.open(production, "run-1")
    booked = next(item for item in held.record["ledger"] if item["kind"] == "generation")
    assert booked["actual_source"] == "estimate"
    assert booked["actual_usd"] is None
    assert held.run.data["cost_usd"] == booked["amount_usd"]

    again = Scripted(_ready())
    collected = run_test_shot(
        held,
        "s01-sh01",
        live=True,
        settings=_settings(again),
        model="seedance-2.0-fast",
    )
    assert collected["status"] == "generated", collected["message"]
    assert [call["method"] for call in again.calls] == ["GET", "GET", "GET"]
    assert SECRET not in collected["message"]


def test_a_providers_file_can_change_the_pauses(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    config = {
        "version": "1.0.0",
        "fal": {
            "wait_seconds": 12,
            "backoff_start_seconds": 4,
            "backoff_step_seconds": 4,
            "backoff_max_seconds": 8,
            "progress_every_seconds": 100,
        },
    }
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    transport = Scripted([
        _submit_body(),
        _status("IN_QUEUE"),
        _status("IN_PROGRESS"),
        _status("IN_PROGRESS"),
    ])
    pauses = []
    failed = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=CallSettings(
            transport=transport,
            sleeper=pauses.append,
            progress=lambda _line: None,
            providers_path=path,
        ),
        model="seedance-2.0-fast",
    )
    assert failed["status"] == "failed"
    assert pauses == [4, 8]
    assert "poll limit" in failed["message"]


def test_the_wait_flag_is_passed_and_zero_is_refused(tmp_path, monkeypatch):
    production = _harbor(tmp_path)
    _open(production)
    seen = {}

    def fake(_producer, shot_id, **kwargs):
        seen["shot"] = shot_id
        seen["wait"] = kwargs["settings"].wait_seconds
        return {"status": "offline", "message": "Offline is the default. Nothing was sent.", "output": None}

    monkeypatch.setattr("movie_swarm.cli_line_producer.run_test_shot", fake)
    from movie_swarm.cli_line_producer import main

    code = main([
        "--production", str(production),
        "--run", "run-1",
        "test-shot",
        "--shot", "s01-sh01",
        "--wait", "90",
    ])
    assert code == 0
    assert seen == {"shot": "s01-sh01", "wait": 90.0}
    refused = main([
        "--production", str(production),
        "--run", "run-1",
        "test-shot",
        "--shot", "s01-sh01",
        "--wait", "0",
    ])
    assert refused == 1
    assert seen["wait"] == 90.0


def test_the_guide_tells_ron_to_expect_a_few_minutes():
    guide = (repo_root() / "START-HERE.md").read_text(encoding="utf-8")
    assert "--wait" in guide
    assert "10 minutes" in guide
    assert "IN_QUEUE" in guide
    assert "IN_PROGRESS" in guide
    assert "poll limit" in guide
    assert "same request" in guide
