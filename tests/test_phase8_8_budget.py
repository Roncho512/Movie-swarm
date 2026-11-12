"""Phase 8.8 budget: one film budget, one calculator.

A film with no budget file keeps the $500 cap and the locked split.
Nothing here calls a provider. Spent stays $0 unless a test records a fake spend.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.budget import (
    MARKETING_STAGE,
    compute,
    fallback_document,
    load_film_budget,
    proposed_document,
    write_film_budget,
)
from movie_swarm.line_producer import LineProducer
from movie_swarm.money import as_money, money_number
from movie_swarm.paths import repo_root
from movie_swarm.validate import validate_file
from tests.test_line_producer import _treatment


def _film(tmp_path: Path, total: float, *, trailer: bool = False, contingency: float = 0, marketing: float = 10) -> Path:
    production = tmp_path / "harbor-night"
    _treatment(production, cap=total)
    document = proposed_document(
        total,
        trailer_on=trailer,
        contingency_percent=contingency,
        marketing_percent=marketing,
    )
    write_film_budget(production, document)
    return production


def test_default_budget_matches_todays_ceilings():
    math = compute(fallback_document(500))
    assert math.trailer_on is False
    assert money_number(math.contingency) == 0
    assert money_number(math.marketing) == 0
    expected = {
        "production": 270,
        "sound-designer": 55,
        "fix-loop": 50,
        "qa": 45,
        "art-director": 25,
        "director": 20,
        "editor": 15,
        "cinematographer": 10,
        "screenwriter": 5,
        "line-producer": 5,
    }
    for name, amount in expected.items():
        assert money_number(math.lines[name]) == amount
    assert money_number(sum(math.lines.values(), as_money(0))) == 500


def test_custom_budgets_scale_the_same_shares(tmp_path):
    small = compute(load_film_budget(_film(tmp_path, 50)))
    assert money_number(small.lines["production"]) == 27
    assert money_number(small.lines["sound-designer"]) == 5.5
    assert money_number(small.lines["director"]) == 2
    assert money_number(small.lines["line-producer"]) == 0.5
    assert money_number(sum(small.lines.values(), as_money(0))) == 50
    large = compute(load_film_budget(_film(tmp_path / "big", 2000)))
    assert money_number(large.lines["production"]) == 1080
    assert money_number(large.lines["editor"]) == 60
    assert money_number(sum(large.lines.values(), as_money(0))) == 2000


def test_trailer_adds_marketing_and_the_total_still_matches():
    math = compute(proposed_document(500, trailer_on=True, contingency_percent=0, marketing_percent=10))
    assert math.trailer_on is True
    assert money_number(math.marketing) == 50
    assert money_number(math.lines["production"]) == 243
    total = sum(math.lines.values(), as_money(0)) + math.marketing
    assert money_number(total) == 500
    assert MARKETING_STAGE in math.spendable()


def test_a_retake_draws_on_contingency_after_the_line_is_spent(tmp_path):
    production = _film(tmp_path, 500, contingency=10)
    producer = LineProducer.start(production, run_id="run-1")
    first = producer.record_spend("director", 18, "fill the line")
    assert first.recorded is True
    retake = producer.record_spend("director", 5, "retake the close", kind="retake")
    assert retake.recorded is True
    assert retake.request_id is None
    entry = producer.record["ledger"][-1]
    assert entry["kind"] == "retake"
    assert entry["contingency_usd"] == 5
    assert "overage_usd" not in entry
    text = producer.status_text()
    assert "Contingency left: $45.00" in text


def test_an_overage_pauses_and_an_approval_does_not_edit_the_budget(tmp_path):
    production = _film(tmp_path, 50, contingency=0)
    original = (production / "budget.json").read_text(encoding="utf-8")
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    assert producer.run.data["budget_cap_usd"] == 50
    filled = producer.record_spend("director", 2, "fill the line")
    assert filled.recorded is True
    paused = producer.record_spend("director", 1, "one more pass")
    assert paused.recorded is False
    assert paused.request_id
    assert "budget" in paused.message
    assert producer.run.data["cost_usd"] == 2
    message = producer.decide_request(paused.request_id, "approved", "ron", note="Allow the extra dollar.")
    assert "Approved overage" in message
    assert producer.run.data["cost_usd"] == 3
    assert (production / "budget.json").read_text(encoding="utf-8") == original
    assert producer.record["stage_allocations"]["split"]["director"] == 2
    overage = producer.record["ledger"][-1]["overage_usd"]
    assert overage == 1
    text = producer.status_text()
    assert "Over budget by $3.00" not in text
    assert "Over the line by $1.00" in text
    assert "Approved overages on the ledger: $1.00" in text


def test_a_generation_does_not_quietly_use_contingency(tmp_path):
    production = _film(tmp_path, 500, contingency=10)
    producer = LineProducer.start(production, run_id="run-1")
    producer.record_spend("director", 18, "fill the line")
    paused = producer.record_spend("director", 1, "another generation")
    assert paused.recorded is False
    assert producer.run.data["cost_usd"] == 18


def test_tier_upgrade_within_the_line_and_past_it(tmp_path):
    within = _film(tmp_path / "within", 500, contingency=0)
    (within / "production-brief.json").write_text(
        json.dumps({"target_runtime_seconds": 1, "shot_count": 1, "takes_per_shot": 1, "fix_rate": 0}),
        encoding="utf-8",
    )
    producer = LineProducer.start(within, run_id="run-1")
    message = producer.upgrade_tier("production", "better")
    assert "now better" in message
    assert load_film_budget(within)["tiers"]["production"] == "better"
    assert producer.run.data["cost_usd"] == 0

    beyond = _film(tmp_path / "beyond", 50, contingency=0)
    (beyond / "production-brief.json").write_text(
        json.dumps({"target_runtime_seconds": 1000, "shot_count": 1, "takes_per_shot": 2, "fix_rate": 0}),
        encoding="utf-8",
    )
    other = LineProducer.start(beyond, run_id="run-1")
    paused = other.upgrade_tier("production", "best")
    assert "does not fit" in paused
    assert load_film_budget(beyond)["tiers"]["production"] == "good"
    request_id = other.record["requests"][-1]["request_id"]
    other.decide_request(request_id, "approved", "ron")
    assert load_film_budget(beyond)["tiers"]["production"] == "best"
    assert load_film_budget(beyond)["total_usd"] == 50
    assert other.record["ledger"][-1]["overage_usd"] > 0
    assert other.run.data["cost_usd"] == 0


def test_budget_schema_and_calculator_export_round_trip(tmp_path):
    production = _film(tmp_path, 50, trailer=True, contingency=10)
    result = validate_file(production / "budget.json")
    assert result.ok, result.errors
    fixture = repo_root() / "tests" / "fixtures" / "budget" / "export.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    folder = tmp_path / "imported"
    folder.mkdir()
    (folder / "budget.json").write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_film_budget(folder)
    math = compute(loaded)
    assert loaded["trailer_on"] is True
    assert money_number(math.total) == 500
    assert money_number(sum(math.spendable().values(), as_money(0)) + math.contingency) == 500
    html = (repo_root() / "tools" / "budget-calculator" / "index.html").read_text(encoding="utf-8")
    for needle in (
        "line_shares",
        "contingency_share",
        "trailer_on",
        "marketing_share",
        "Marketing and Distribution",
        "0.3034",
        "0.2419",
        "0.682",
        "0.08",
        "0.12",
        "0.15",
    ):
        assert needle in html
    assert "exportDocument" in html


def test_budget_code_names_no_film():
    banned = (
        "last marker",
        "leone",
        "spaghetti",
        "1967",
        "baja",
        "breitling",
        "triumph",
        "morricone",
        "1965",
    )
    roots = [
        repo_root() / "movie_swarm" / "budget.py",
        repo_root() / "schemas" / "film-budget.schema.json",
        repo_root() / "config" / "rate-card.json",
        repo_root() / "tools" / "budget-calculator" / "index.html",
    ]
    offenders = []
    for path in roots:
        text = path.read_text(encoding="utf-8").casefold()
        for word in banned:
            if word in text:
                offenders.append(f"{path.name}: {word}")
    assert offenders == []
