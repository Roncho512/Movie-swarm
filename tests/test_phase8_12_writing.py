"""Phase 8.12: a Claude writing call has its own approval.

Picture and audio calls still wait on the generation gate. Nothing here opens
a socket or spends money. The HTTP transport is a fake. Harbor Night is the
fixture. The Last Marker archive is not used.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.budget import proposed_document, write_film_budget
from movie_swarm.cli_director import main as director_main
from movie_swarm.cli_line_producer import main as line_main
from movie_swarm.http_retry import HttpResult
from movie_swarm.line_producer import LineProducer
from movie_swarm.money import as_money, money_number
from movie_swarm.paths import repo_root
from movie_swarm.providers import CallSettings, quote_text_call, run_provider_call
from movie_swarm.rates import generator_rate, load_rate_card, token_prices
from movie_swarm.validate import validate_file


SECRET = "anthropic-test-key-do-not-leak"
SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
READ_ON = "2026-11-12"


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


def _harbor(destination: Path) -> Path:
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", destination)
    return destination


def _budget(production: Path, *, director_share: float = 4, total: float = 500) -> None:
    document = proposed_document(total, trailer_on=False, contingency_percent=0)
    if director_share != 4:
        document["line_shares"]["production"] = money_number(
            as_money(document["line_shares"]["production"]) + as_money(4) - as_money(director_share)
        )
        document["line_shares"]["director"] = director_share
    write_film_budget(production, document)


def _open(production: Path) -> LineProducer:
    return LineProducer.start(production, run_id="run-1")


def _settings(transport) -> CallSettings:
    return CallSettings(transport=transport, sleeper=lambda _seconds: None, poll_interval=0)


def _reply(text: str = "The dock is quiet.", usage: dict | None = None) -> HttpResult:
    payload = {"content": [{"type": "text", "text": text}]}
    if usage is not None:
        payload["usage"] = usage
    return HttpResult(200, json.dumps(payload).encode())


def _text_call(producer, transport, *, model="claude-sonnet-5-5", max_tokens=100, prompt="Write a line."):
    return run_provider_call(
        producer,
        live=True,
        kind="text",
        stage="director",
        provider="anthropic",
        model=model,
        prompt=prompt,
        system="Be brief.",
        role="director",
        purpose="draft",
        max_tokens=max_tokens,
        settings=_settings(transport),
        label="director/draft",
    )


def _no_secret(root: Path, secret: str) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes(), path


def test_the_published_text_prices_are_on_both_cards():
    card = load_rate_card()
    expected = {
        "claude-haiku-5-5": ("0.10", "0.50"),
        "claude-sonnet-5-5": ("2", "10"),
        "claude-opus-5-5": ("4", "20"),
    }
    for name, (input_rate, output_rate) in expected.items():
        row = generator_rate(card, name)
        assert row["usd_per_million_input_tokens"] == input_rate
        assert row["usd_per_million_output_tokens"] == output_rate
        assert row["source"] == SOURCE
        assert row["source_date"] == READ_ON
    haiku = generator_rate(card, "claude-haiku-5-5")
    assert token_prices(haiku, 100000) == (as_money("0.10"), as_money("0.50"))
    assert token_prices(haiku, 100001) == (as_money("0.50"), as_money("2.50"))
    dated = generator_rate(card, "claude-sonnet-4-20250514")
    assert dated["usd_per_million_input_tokens"] is None
    assert dated["usd_per_million_output_tokens"] is None
    assert "not list" in dated["note"]
    mirror = json.loads((repo_root() / "config" / "rate-card.json").read_text(encoding="utf-8"))
    by_name = {row["model"]: row for row in mirror["text"]["models"]}
    assert by_name["claude-opus-5-5"]["usd_per_million_output_tokens"] == "20"
    assert by_name["claude-sonnet-4-20250514"]["usd_per_million_input_tokens"] is None
    assert by_name["claude-sonnet-4-20250514"]["source_date"] == READ_ON


def test_a_text_call_without_writing_approval_quotes_and_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    production = _harbor(tmp_path / "harbor-night")
    _budget(production)
    producer = _open(production)
    transport = Scripted([_reply()])
    result = _text_call(producer, transport)
    quote = quote_text_call(
        "claude-sonnet-5-5", "Be brief.", "Write a line.", 100, label="director/draft",
    )
    assert result["status"] == "quoted"
    assert result["sent"] is False
    assert result["message"] == quote["text"] + " Record a writing approval for this run before a text call is sent. Nothing was sent."
    assert "claude-sonnet-5-5" in result["message"]
    assert "estimate, character count / 4" in result["message"]
    assert "Max output tokens: 100" in result["message"]
    assert f"Worst case: ${quote['worst_case_usd']:.4f}" in result["message"]
    assert quote["input_tokens_estimate"] == (len("Be brief.") + len("Write a line.")) // 4
    assert transport.calls == []
    opened = LineProducer.open(production, "run-1")
    assert opened.run.data["cost_usd"] == 0
    assert opened.gate_decision("generation") != "approved"
    assert opened.record["stage_allocations"]["status"] == "unlocked"
    assert SECRET not in result["message"]


def test_a_text_call_is_sent_while_the_generation_gate_is_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    production = _harbor(tmp_path / "harbor-night")
    _budget(production)
    producer = _open(production)
    producer.approve_writing(1, "Ron", note="Treatment draft.")
    transport = Scripted([_reply(usage={"input_tokens": 100, "output_tokens": 50})])
    result = _text_call(producer, transport)
    assert result["status"] == "generated", result["message"]
    assert result["sent"] is True
    assert len(transport.calls) == 1
    sent = transport.calls[0]
    assert sent["url"] == "https://api.anthropic.com/v1/messages"
    assert sent["headers"]["x-api-key"] == SECRET
    assert sent["body"]["model"] == "claude-sonnet-5-5"
    assert sent["body"]["max_tokens"] == 100
    finished = LineProducer.open(production, "run-1")
    assert finished.gate_decision("generation") != "approved"
    assert finished.record["stage_allocations"]["status"] == "unlocked"
    entry = next(item for item in finished.record["ledger"] if item["kind"] == "generation")
    assert entry["writing"] is True
    assert entry["actual_source"] == "usage"
    assert as_money(entry["actual_usd"]) == as_money("0.0007")
    assert as_money(entry["amount_usd"]) == as_money("0.0007")
    assert as_money(entry["estimate_usd"]) > as_money(entry["actual_usd"])
    assert as_money(finished.run.data["cost_usd"]) == as_money("0.0007")
    assert "from the reported token usage" in entry["description"]
    assert "100 input tokens" in entry["description"]
    assert SECRET not in entry["description"]
    assert SECRET not in result["message"]
    _no_secret(production, SECRET)
    checked = validate_file(production / "runs" / "run-1" / "line-producer.json")
    assert checked.ok, checked.errors

    again = _text_call(finished, Scripted([_reply(usage={"input_tokens": 100, "output_tokens": 50})]))
    assert again["status"] == "replayed", again["message"]
    assert as_money(LineProducer.open(production, "run-1").run.data["cost_usd"]) == as_money("0.0007")


def test_picture_and_audio_still_wait_on_the_generation_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fal-test-key-do-not-leak")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "eleven-test-key-do-not-leak")
    production = _harbor(tmp_path / "harbor-night")
    _budget(production)
    producer = _open(production)
    producer.approve_writing(5, "Ron", note="Writing only.")
    picture = Scripted([])
    video = run_provider_call(
        producer,
        live=True,
        kind="video",
        stage="production",
        provider="fal.ai",
        model="seedance-2.0",
        prompt="A dock at night.",
        duration_seconds=4,
        shot_id="s01-sh01",
        settings=_settings(picture),
    )
    audio = Scripted([])
    sound = run_provider_call(
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
        settings=_settings(audio),
    )
    assert video["status"] == "refused"
    assert "generation gate" in video["message"]
    assert sound["status"] == "refused"
    assert "generation gate" in sound["message"]
    assert picture.calls == []
    assert audio.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert LineProducer.open(production, "run-1").gate_decision("generation") != "approved"


def test_the_writing_ceiling_the_line_and_the_cap_are_checked(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    production = _harbor(tmp_path / "harbor-night")
    _budget(production)
    producer = _open(production)
    producer.approve_writing(0.0001, "Ron", note="Too small.")
    transport = Scripted([_reply()])
    held = _text_call(producer, transport, max_tokens=8000)
    assert held["status"] == "refused"
    assert "writing approval" in held["message"]
    assert "Nothing was sent." in held["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    tight = _harbor(tmp_path / "line")
    _budget(tight, director_share=0)
    line_producer = _open(tight)
    line_producer.approve_writing(20, "Ron", note="The line is empty.")
    line_transport = Scripted([_reply()])
    over_line = _text_call(line_producer, line_transport)
    assert over_line["status"] == "refused"
    assert "budget line" in over_line["message"]
    assert line_transport.calls == []
    assert LineProducer.open(tight, "run-1").run.data["cost_usd"] == 0

    capped = _harbor(tmp_path / "cap")
    _budget(capped)
    cap_producer = _open(capped)
    cap_producer.approve_writing(20, "Ron", note="The film is already at the cap.")
    cap_producer.run.data["cost_usd"] = 500
    cap_producer.run.save()
    cap_transport = Scripted([_reply()])
    over_cap = _text_call(cap_producer, cap_transport)
    assert over_cap["status"] == "refused"
    assert "over the" in over_cap["message"]
    assert "budget" in over_cap["message"]
    assert cap_transport.calls == []
    assert LineProducer.open(capped, "run-1").run.data["cost_usd"] == 500


def test_missing_usage_books_the_estimate(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    production = _harbor(tmp_path / "harbor-night")
    _budget(production)
    producer = _open(production)
    producer.approve_writing(1, "Ron", note="No usage object.")
    transport = Scripted([_reply()])
    result = _text_call(producer, transport)
    assert result["status"] == "generated", result["message"]
    quote = quote_text_call(
        "claude-sonnet-5-5", "Be brief.", "Write a line.", 100, label="director/draft",
    )
    entry = next(item for item in LineProducer.open(production, "run-1").record["ledger"] if item["kind"] == "generation")
    assert entry["actual_source"] == "estimate"
    assert entry["actual_usd"] is None
    assert as_money(entry["amount_usd"]) == as_money(quote["worst_case_usd"])
    assert "did not report a dollar amount" in entry["description"]
    assert SECRET not in entry["description"]


def test_a_null_price_is_refused_even_with_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    production = _harbor(tmp_path / "harbor-night")
    _budget(production)
    producer = _open(production)
    producer.approve_writing(5, "Ron", note="The id is not priced.")
    transport = Scripted([_reply()])
    result = _text_call(producer, transport, model="claude-sonnet-4-20250514")
    assert result["status"] == "refused"
    assert "no published price" in result["message"]
    assert "Nothing was sent." in result["message"]
    assert transport.calls == []
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_intake_prints_the_quote_and_does_not_replace_the_treatment(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    production = tmp_path / "draft-film"
    screenplay = production / "screenplay" / "story.md"
    screenplay.parent.mkdir(parents=True)
    screenplay.write_text("Ada waits on the dock.\n", encoding="utf-8")
    code = director_main(
        ["--production", str(production), "--run", "run-1", "--live", "intake", "--screenplay", str(screenplay)]
    )
    printed = capsys.readouterr().out
    assert code == 2
    assert "Worst case:" in printed
    assert "estimate, character count / 4" in printed
    assert "Nothing was sent." in printed
    assert "claude-sonnet-5-5" in printed
    assert not (production / "treatment" / "treatment.json").exists()
    opened = LineProducer.open(production, "run-1")
    assert opened.run.data["cost_usd"] == 0
    assert "writing_approval" not in opened.record
    approved = line_main(
        [
            "--production",
            str(production),
            "--run",
            "run-1",
            "approve-writing",
            "--by",
            "Ron",
            "--max-usd",
            "1",
            "--note",
            "Treatment draft.",
        ]
    )
    assert approved == 0
    record = LineProducer.open(production, "run-1").record
    assert record["writing_approval"]["status"] == "approved"
    assert record["writing_approval"]["by"] == "Ron"
    assert record["writing_approval"]["max_usd"] == 1
    assert LineProducer.open(production, "run-1").gate_decision("generation") != "approved"
