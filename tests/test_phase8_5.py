"""Phase 8.5: a live provider call stays off unless every gate is open.

Nothing here opens a socket or spends money. The HTTP transport is a fake.
Harbor Night is the fixture. The Last Marker is not used.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from movie_swarm.http_retry import HttpResult
from movie_swarm.line_producer import LineProducer
from movie_swarm.money import as_money, money_number
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.providers import CallSettings, llm_for_command, run_provider_call, run_test_shot
from movie_swarm.rates import load_rate_card
from movie_swarm.treatment_doc import proposed_split
from movie_swarm.validate import validate_file


SECRET = "fal-test-key-do-not-leak-9f3a"


class Scripted:
    """Answers HTTP in order. It records the calls and does not touch the network."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        if not self.script:
            raise AssertionError(f"Unexpected {method} {url}")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


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


def _open(production: Path, split: dict | None = None) -> LineProducer:
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", stage_split=split or proposed_split(500))
    producer.approve_gate("production", "approved", "ron")
    producer.approve_gate("previs", "approved", "ron")
    return producer


def _routing(tmp_path: Path, model: str = "seedance-2.0") -> Path:
    routing = json.loads((repo_root() / "config" / "model-routing.json").read_text(encoding="utf-8"))
    routing["overrides"] = [
        {
            "role": "production",
            "shot": "s01-sh01",
            "purpose": "preview",
            "model": model,
            "provider": "fal.ai",
        }
    ]
    path = tmp_path / "routing.json"
    path.write_text(json.dumps(routing), encoding="utf-8")
    return path


def _ok_script(cost: str = "0.50"):
    return [
        HttpResult(200, json.dumps({"request_id": "job-1"}).encode()),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps({
            "video": {"url": "https://cdn.example/clip.mp4"},
            "cost_usd": cost,
        }).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ]


def _settings(transport, **kwargs) -> CallSettings:
    return CallSettings(transport=transport, sleeper=lambda _seconds: None, poll_interval=0, **kwargs)


def _no_secret(root: Path, secret: str) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        assert secret.encode() not in path.read_bytes(), path


def test_offline_is_the_default_even_when_the_key_is_set(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=False,
        settings=_settings(transport),
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "offline"
    assert result["sent"] is False
    assert result["message"].startswith("Offline is the default.")
    assert "Nothing was sent." in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert llm_for_command(production, "run-1", live=False, offline=False) is None


def test_a_closed_generation_gate_refuses_the_call(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    transport = Scripted(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "refused"
    assert "generation gate" in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert LineProducer.open(production, "run-1").gate_decision("generation") != "approved"


def test_a_missing_key_refuses_the_call(tmp_path, monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "refused"
    assert "FAL_KEY is not set" in result["message"]
    assert SECRET not in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_an_over_budget_call_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production, split={"production": 1, "treatment": 0})
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "refused"
    assert "allocation" in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_a_missing_endpoint_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_ok_script())
    result = run_test_shot(producer, "s01-sh01", live=True, settings=_settings(transport))
    assert result["status"] == "refused"
    assert "gemini-omni-1.2-flash" in result["message"]
    assert "endpoint" in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_an_unknown_price_is_refused_until_an_override_is_approved(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "eleven-test-key-do-not-leak")
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted([HttpResult(200, b"fake-audio")])
    settings = _settings(transport)
    refused = run_provider_call(
        producer,
        live=True,
        kind="audio",
        stage="sound-designer",
        provider="elevenlabs",
        model="eleven_v3",
        prompt="A dock bell.",
        duration_seconds=2,
        cue_id="bell",
        purpose="sfx",
        settings=settings,
        label="bell",
    )
    assert refused["status"] == "refused"
    assert "no published price" in refused["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    waiting = _settings(transport, price_override=0.25)
    held = run_provider_call(
        producer,
        live=True,
        kind="audio",
        stage="sound-designer",
        provider="elevenlabs",
        model="eleven_v3",
        prompt="A dock bell.",
        duration_seconds=2,
        cue_id="bell",
        purpose="sfx",
        settings=waiting,
        label="bell",
    )
    assert held["status"] == "refused"
    assert "req-" in held["message"]
    assert transport.calls == []
    request_id = LineProducer.open(production, "run-1").record["requests"][-1]["request_id"]
    LineProducer.open(production, "run-1").decide_request(request_id, "approved", "ron", note="One call.")
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    sent = run_provider_call(
        LineProducer.open(production, "run-1"),
        live=True,
        kind="audio",
        stage="sound-designer",
        provider="elevenlabs",
        model="eleven_v3",
        prompt="A dock bell.",
        duration_seconds=2,
        cue_id="bell",
        purpose="sfx",
        settings=waiting,
        label="bell",
    )
    assert sent["status"] == "generated", sent["message"]
    assert len(transport.calls) == 1
    assert transport.calls[0]["headers"].get("xi-api-key") == "eleven-test-key-do-not-leak"
    assert "Authorization" not in transport.calls[0]["url"]
    booked = LineProducer.open(production, "run-1")
    assert booked.run.data["cost_usd"] == 0.25
    entry = next(item for item in booked.record["ledger"] if item["kind"] == "generation")
    assert entry["estimate_usd"] == 0.25
    assert entry["actual_usd"] is None
    assert "did not report a dollar amount" in entry["description"]
    checked = validate_file(production / "runs" / "run-1" / "line-producer.json")
    assert checked.ok, checked.errors


def test_a_live_call_records_the_estimate_before_and_the_actual_after(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    seen = {}

    class Watching(Scripted):
        def __call__(self, method, url, headers, body, timeout):
            if method == "POST" and "phase" not in seen:
                record = json.loads((production / "runs" / "run-1" / "line-producer.json").read_text())
                entry = next(item for item in record["ledger"] if item.get("call_phase") == "reserved")
                seen["phase"] = entry["call_phase"]
                seen["amount"] = entry["amount_usd"]
                seen["estimate"] = entry["estimate_usd"]
            return super().__call__(method, url, headers, body, timeout)

    transport = Watching(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "generated", result["message"]
    assert seen["phase"] == "reserved"
    assert as_money(seen["estimate"]) == as_money("1.2136")
    assert as_money(seen["amount"]) == as_money("1.2136")
    finished = LineProducer.open(production, "run-1")
    entry = next(item for item in finished.record["ledger"] if item.get("call_phase") == "settled")
    assert as_money(entry["estimate_usd"]) == as_money("1.2136")
    assert as_money(entry["actual_usd"]) == as_money("0.50")
    assert as_money(entry["amount_usd"]) == as_money("0.50")
    assert finished.run.data["cost_usd"] == 0.5
    assert "The provider reported" in entry["description"]
    assert result["output"].startswith("live/video/")
    media = production / result["output"]
    assert media.is_file()
    assert media.read_bytes() == b"fake-video-bytes"
    download = next(call for call in transport.calls if call["url"].startswith("https://cdn.example"))
    assert "Authorization" not in download["headers"]
    assert SECRET not in json.dumps(download["headers"])
    checked = validate_file(production / "runs" / "run-1" / "line-producer.json")
    assert checked.ok, checked.errors
    stage_before = "treatment"
    assert finished.run.data["stage"] == stage_before
    assert finished.run.data["status"] != "completed"
    assert finished.gate_decision("generation") == "approved"


def test_a_rerun_of_the_same_request_does_not_call_or_charge_again(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_ok_script())
    routing = _routing(tmp_path)
    first = run_test_shot(producer, "s01-sh01", live=True, settings=_settings(transport), routing_path=routing)
    assert first["status"] == "generated"
    calls = len(transport.calls)
    spent = LineProducer.open(production, "run-1").run.data["cost_usd"]
    second = run_test_shot(
        LineProducer.open(production, "run-1"),
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        routing_path=routing,
    )
    assert second["status"] == "replayed"
    assert "not charged again" in second["message"].casefold() or "Nothing was charged again" in second["message"]
    assert len(transport.calls) == calls
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == spent
    replay = next(item for item in LineProducer.open(production, "run-1").record["ledger"] if item.get("call_phase") == "replayed")
    assert replay["kind"] == "dry-run"
    assert replay["amount_usd"] == 0


def test_a_retryable_failure_backs_off_and_a_timeout_is_not_sent_twice(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    delays = []
    script = [
        HttpResult(503, b"busy"),
        HttpResult(503, b"busy"),
        *_ok_script(),
    ]
    transport = Scripted(script)
    settings = CallSettings(
        transport=transport,
        sleeper=delays.append,
        poll_interval=0,
    )
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=settings,
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "generated", result["message"]
    posts = [call for call in transport.calls if call["method"] == "POST"]
    assert len(posts) == 3
    assert delays == [0.5, 1.0]

    timed_production = _harbor(tmp_path / "clock")
    timed_producer = _open(timed_production)
    timed_producer.approve_gate("generation", "approved", "ron")
    stage = timed_producer.run.data["stage"]
    exploding = Scripted([TimeoutError("The provider did not answer before the timeout.")])
    failed = run_test_shot(
        timed_producer,
        "s01-sh01",
        live=True,
        settings=_settings(exploding),
        routing_path=_routing(tmp_path),
    )
    assert failed["status"] == "failed"
    assert "timeout" in failed["message"].casefold()
    assert "still at this stage" in failed["message"]
    held = LineProducer.open(timed_production, "run-1")
    assert held.run.data["status"] == "waiting-for-review"
    assert held.run.data["stage"] == stage
    assert held.gate_decision("generation") == "approved"
    assert as_money(held.run.data["cost_usd"]) == as_money("1.2136")
    again = Scripted([HttpResult(200, b"should-not-be-sent")])
    replay = run_test_shot(
        held,
        "s01-sh01",
        live=True,
        settings=_settings(again),
        routing_path=_routing(tmp_path),
    )
    assert again.calls == []
    assert "not sent again" in replay["message"]
    assert LineProducer.open(timed_production, "run-1").run.data["cost_usd"] == held.run.data["cost_usd"]


def test_the_key_never_appears_in_saved_output_or_messages(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    body = json.dumps({"error": f"refused {SECRET}"}).encode()
    transport = Scripted([HttpResult(500, body), HttpResult(500, body), HttpResult(500, body)])
    records = []

    class Grab(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Grab()
    logging.getLogger().addHandler(handler)
    try:
        result = run_test_shot(
            producer,
            "s01-sh01",
            live=True,
            settings=_settings(transport),
            routing_path=_routing(tmp_path),
        )
    finally:
        logging.getLogger().removeHandler(handler)
    assert result["status"] == "failed"
    blob = json.dumps(result)
    assert SECRET not in blob
    assert "[redacted]" in result["message"] or SECRET not in result["message"]
    _no_secret(production, SECRET)
    for message in records:
        assert SECRET not in message

    from movie_swarm.cli_line_producer import main

    code = main([
        "--production", str(production),
        "--run", "run-1",
        "test-shot",
        "--shot", "s01-sh01",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "Nothing was sent." in captured.out
    assert SECRET not in captured.out
    assert SECRET not in captured.err


def test_downloaded_media_uses_the_asset_root(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    root = tmp_path / "drive"
    monkeypatch.setenv("MOVIE_SWARM_ASSET_ROOT", str(root))
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_ok_script())
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "generated", result["message"]
    assert result["location"] == "MOVIE_SWARM_ASSET_ROOT"
    saved = root / "harbor-night" / result["output"]
    assert saved.is_file()
    assert saved.read_bytes() == b"fake-video-bytes"
    assert not (production / result["output"]).exists()
    config = json.loads((repo_root() / "config" / "assets.json").read_text(encoding="utf-8"))
    assert config["asset_root"] is None


def test_audio_color_and_delivery_prices_stay_unknown():
    card = load_rate_card()
    models = {row["model"] for row in card["generators"]}
    for name in ("eleven_v3", "eleven_text_to_sound_v2", "elevenlabs-music-compose"):
        assert name not in models
    text = json.dumps(card)
    assert "color grade" not in text.casefold()
    assert "delivery" in " ".join(card["assumptions"]).casefold()
    gemini = next(row for row in card["generators"] if row["model"] == "gemini-omni-1.2-flash")
    assert "endpoint" not in gemini
    seedance = next(row for row in card["generators"] if row["model"] == "seedance-2.0")
    assert seedance["endpoint"] == "bytedance/seedance-2.0/text-to-video"
    assert seedance["usd_per_second"] == "0.3034"


def test_env_example_is_empty_and_env_is_ignored():
    example = (repo_root() / ".env.example").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=" in example
    assert "FAL_KEY=" in example
    assert "ELEVENLABS_API_KEY=" in example
    for line in example.splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        _name, value = line.split("=", 1)
        assert value.strip() == ""
    ignore = (repo_root() / ".gitignore").read_text(encoding="utf-8")
    assert ".env\n" in ignore or ignore.endswith(".env")


def test_a_connection_error_releases_the_reservation(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    production = _harbor(tmp_path)
    producer = _open(production)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted([
        ConnectionError("The provider could not be reached."),
        ConnectionError("The provider could not be reached."),
        ConnectionError("The provider could not be reached."),
    ])
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        routing_path=_routing(tmp_path),
    )
    assert result["status"] == "failed"
    assert "Nothing was booked" in result["message"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert len(transport.calls) == 3
    assert LineProducer.open(production, "run-1").run.data["status"] == "waiting-for-review"
