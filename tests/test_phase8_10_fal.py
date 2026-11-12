"""Phase 8.10: the fal queue call matches the documented request, and a rejected call is released.

Nothing here opens a socket or spends money. Harbor Night is the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.budget import estimate_film, proposed_document
from movie_swarm.duration import clip_lengths, request_value
from movie_swarm.http_retry import HttpResult
from movie_swarm.line_producer import LineProducer
from movie_swarm.money import as_money
from movie_swarm.paths import repo_root
from movie_swarm.providers import CallSettings, run_test_shot
from movie_swarm.rates import load_rate_card
from movie_swarm.validate import validate_file
from tests.test_phase8_5 import SECRET, Scripted, _harbor, _open, _settings


FAL_QUEUE = "https://queue.fal.run"
FAST_ENDPOINT = "bytedance/seedance-2.0/fast/text-to-video"
FAST_URL = f"{FAL_QUEUE}/{FAST_ENDPOINT}"
STATUS_URL = f"{FAL_QUEUE}/bytedance/seedance-2.0/requests/job-1/status"
RESULT_URL = f"{FAL_QUEUE}/bytedance/seedance-2.0/requests/job-1"


def _row(model: str) -> dict:
    return next(item for item in load_rate_card()["generators"] if item["model"] == model)


def _submit_body(request_id="job-1", **extra) -> HttpResult:
    payload = {"request_id": request_id, "status_url": STATUS_URL, "response_url": RESULT_URL}
    payload.update(extra)
    return HttpResult(200, json.dumps(payload).encode())


def _completed_script():
    return [
        _submit_body(),
        HttpResult(200, json.dumps({"status": "COMPLETED", "response_url": RESULT_URL}).encode()),
        HttpResult(200, json.dumps({
            "video": {"url": "https://cdn.example/clip.mp4"},
            "cost_usd": "0.50",
        }).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ]


def test_duration_rules_match_the_pages_that_were_read():
    fast = _row("seedance-2.0-fast")
    full = _row("seedance-2.0")
    kling = _row("kling-4.0")
    gemini = _row("gemini-omni-1.2-flash")
    assert fast["duration_rule_status"] == "verified"
    assert fast["whole_seconds"] is True
    assert fast["min_seconds"] == "4"
    assert fast["max_seconds"] == "15"
    assert fast["duration_format"] == "string"
    assert fast["allowed_resolutions"] == ["480p", "720p"]
    assert fast["duration_source"].endswith("/fast/text-to-video/api")
    assert "endpoint" in fast
    assert full["duration_rule_status"] == "verified"
    assert full["allowed_resolutions"] == ["480p", "720p", "1080p", "4k"]
    assert full["min_seconds"] == "4"
    assert full["max_seconds"] == "15"
    assert kling["duration_rule_status"] == "verified"
    assert kling["whole_seconds"] is True
    assert kling["duration_format"] == "integer"
    assert kling["min_seconds"] == "3"
    assert kling["max_seconds"] == "30"
    assert kling["allowed_resolutions"] == ["720p", "1080p"]
    assert "endpoint" not in kling
    assert gemini["duration_rule_status"] == "assumption"
    assert gemini["whole_seconds"] is False
    assert "endpoint" not in gemini


def test_a_short_shot_rounds_up_and_the_quote_uses_that_length():
    fast = _row("seedance-2.0-fast")
    lengths, notes = clip_lengths("2.087", fast)
    assert lengths == [as_money(4)]
    assert request_value(lengths[0], fast) == "4"
    assert "verified" in " ".join(notes).casefold() or "published" in " ".join(notes).casefold()
    assert "assumption" not in " ".join(notes).casefold()
    longer, _notes = clip_lengths("4.1", fast)
    assert longer == [as_money(5)]
    exact, exact_notes = clip_lengths(4, fast)
    assert exact == [as_money(4)]
    assert exact_notes == []
    kling = _row("kling-4.0")
    kling_lengths, _kling_notes = clip_lengths("2.2", kling)
    assert kling_lengths == [as_money(3)]
    assert request_value(kling_lengths[0], kling) == 3
    gemini = _row("gemini-omni-1.2-flash")
    inside, inside_notes = clip_lengths("4.5", gemini)
    assert inside == [as_money("4.5")]
    assert inside_notes == []


def test_the_budget_estimate_uses_the_same_minimum():
    document = proposed_document(500, trailer_on=False, contingency_percent=0, tiers={"production": "better"})
    estimate = estimate_film(
        Path("."),
        document,
        inputs={
            "runtime_seconds": 2.087,
            "shots": 1,
            "takes_per_shot": 1,
            "fix_rate": 0,
            "trailer_on": False,
            "notes": [],
        },
    )
    production = next(row for row in estimate["lines"] if row["stage"] == "production")
    assert production["estimate_usd"] == 0.9676
    assert "4" in production["detail"]
    html = (repo_root() / "tools" / "budget-calculator" / "index.html").read_text(encoding="utf-8")
    assert "billedRuntime" in html
    assert "min: 4" in html


def test_the_queue_post_matches_the_documented_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_completed_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "generated", result["message"]
    post = transport.calls[0]
    assert post["method"] == "POST"
    assert post["url"] == FAST_URL
    assert set(post["headers"]) >= {"Authorization", "Content-Type"}
    body = post["body"]
    assert "input" not in body
    assert set(body) >= {"prompt", "duration", "resolution", "aspect_ratio", "generate_audio"}
    assert isinstance(body["prompt"], str) and body["prompt"]
    assert body["duration"] == "4"
    assert body["resolution"] == "720p"
    assert body["aspect_ratio"] == "16:9"
    assert body["generate_audio"] is True
    assert SECRET not in json.dumps(body)
    assert transport.calls[1]["method"] == "GET"
    assert transport.calls[1]["url"] == STATUS_URL
    assert transport.calls[2]["method"] == "GET"
    assert transport.calls[2]["url"] == RESULT_URL
    assert "/fast/text-to-video/requests/" not in transport.calls[1]["url"]
    assert "/fast/text-to-video/requests/" not in transport.calls[2]["url"]


def test_polling_falls_back_to_the_app_id_when_the_submit_omits_urls(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    script = [
        HttpResult(200, json.dumps({"request_id": "job-9"}).encode()),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps({"video": {"url": "https://cdn.example/clip.mp4"}}).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ]
    transport = Scripted(script)
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "generated", result["message"]
    assert transport.calls[1]["url"] == f"{FAL_QUEUE}/bytedance/seedance-2.0/requests/job-9/status"
    assert transport.calls[2]["url"] == f"{FAL_QUEUE}/bytedance/seedance-2.0/requests/job-9"


def test_a_completed_error_body_releases_the_estimate(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    detail = {
        "detail": [
            {
                "type": "missing",
                "loc": ["body", "prompt"],
                "msg": "Field required",
                "input": {"input": {"prompt": SECRET, "duration": "2.087"}},
            }
        ]
    }
    transport = Scripted([
        _submit_body(),
        HttpResult(200, json.dumps({"status": "COMPLETED", "response_url": RESULT_URL}).encode()),
        HttpResult(200, json.dumps(detail).encode()),
    ])
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "failed"
    assert "prompt: Field required" in result["message"]
    assert "Nothing was produced" in result["message"]
    assert SECRET not in result["message"]
    assert result["sent"] is False
    finished = LineProducer.open(production, "run-1")
    assert finished.run.data["cost_usd"] == 0
    original = next(item for item in finished.record["ledger"] if item["kind"] == "generation")
    release = next(item for item in finished.record["ledger"] if item["kind"] == "release")
    assert as_money(original["amount_usd"]) == as_money("0.9676")
    assert original["actual_usd"] is None
    assert release["releases_entry_id"] == original["entry_id"]
    assert as_money(release["amount_usd"]) == as_money(original["amount_usd"])
    request = next(item for item in finished.record["requests"] if item["kind"] == "release")
    assert request["status"] == "approved"
    assert request["books_money"] is False
    assert SECRET not in json.dumps(finished.record)
    checked = validate_file(production / "runs" / "run-1" / "line-producer.json")
    assert checked.ok, checked.errors


def test_a_stuck_estimate_can_be_released_by_hand(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted([
        HttpResult(500, b"busy"),
        HttpResult(500, b"busy"),
        HttpResult(500, b"busy"),
    ])
    failed = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="seedance-2.0-fast",
    )
    assert failed["status"] == "failed"
    held = LineProducer.open(production, "run-1")
    booked = next(item for item in held.record["ledger"] if item["kind"] == "generation")
    assert as_money(held.run.data["cost_usd"]) == as_money(booked["amount_usd"])
    assert booked["actual_usd"] is None
    from movie_swarm.cli_line_producer import main

    code = main([
        "--production", str(production),
        "--run", "run-1",
        "release",
        "--entry", booked["entry_id"],
        "--by", "ron",
        "--note", "The provider produced nothing.",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert booked["entry_id"] in captured.out
    assert "still on the ledger" in captured.out
    assert SECRET not in captured.out
    released = LineProducer.open(production, "run-1")
    assert released.run.data["cost_usd"] == 0
    original = released.ledger_entry(booked["entry_id"])
    assert as_money(original["amount_usd"]) == as_money(booked["amount_usd"])
    offset = next(item for item in released.record["ledger"] if item["kind"] == "release")
    assert offset["releases_entry_id"] == booked["entry_id"]
    record = next(item for item in released.record["requests"] if item["kind"] == "release")
    assert record["status"] == "approved"
    assert record["decided_by"] == "ron"
    assert "produced nothing" in record["note"]
    checked = validate_file(production / "runs" / "run-1" / "line-producer.json")
    assert checked.ok, checked.errors
    again = main([
        "--production", str(production),
        "--run", "run-1",
        "release",
        "--entry", booked["entry_id"],
        "--by", "ron",
    ])
    assert again == 1
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_one_call_refuses_a_shot_longer_than_the_model_allows(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    board = json.loads((production / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))
    board["frames"][0]["duration_seconds"] = 20
    (production / "storyboard" / "storyboard.json").write_text(json.dumps(board), encoding="utf-8")
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_completed_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="seedance-2.0-fast",
    )
    assert result["status"] == "refused"
    assert "Nothing was sent." in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_the_guide_names_the_four_second_price():
    guide = (repo_root() / "START-HERE.md").read_text(encoding="utf-8")
    assert "4 seconds" in guide
    assert "$0.9676" in guide
    assert "sent as 4 seconds" in guide
