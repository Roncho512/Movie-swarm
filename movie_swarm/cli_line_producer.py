"""Command line for the Line Producer.

Nothing here waits for a typed answer. Pass flags, or pass a JSON file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from movie_swarm.budget import (
    BudgetError,
    estimate_film,
    format_estimate,
    load_film_budget,
    proposed_document,
    read_estimate_inputs,
    write_film_budget,
)
from movie_swarm.line_producer import LineProducer, LineProducerError
from movie_swarm.money import money_number
from movie_swarm.llm import LLMError
from movie_swarm.models import ModelRoutingError
from movie_swarm.providers import llm_for_command, run_test_shot
from movie_swarm.shot_model import ShotModelError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Line Producer: budget, gates, credits, and status for one film run."
    )
    parser.add_argument("--production", required=True, help="Production folder")
    parser.add_argument("--run", help="Run id. Required except for start, which can choose one.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Allow one real provider call. Offline is the default. A live call still needs the generation gate, the key, and a known price.",
    )
    parser.add_argument(
        "--price-override",
        type=float,
        help="Dollars for one call when the rate card has no price. Approve that request before the call is sent.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Open a run for this production")
    start.add_argument("--stage", default="treatment")

    status = sub.add_parser("status", help="Say where the run is, in plain language")
    status.add_argument(
        "--narrate",
        action="store_true",
        help="Add one sentence from the cheap model. Needs --live, the generation gate, the key, and a known price.",
    )

    spend = sub.add_parser("spend", help="Record a spend, or pause and write an approval request")
    spend.add_argument("--stage", required=True)
    spend.add_argument("--amount", required=True, type=float)
    spend.add_argument("--description", required=True)
    spend.add_argument("--kind", choices=["generation", "retake"], default="generation")

    gate = sub.add_parser("approve-gate", help="Record Ron's approval or rejection of a gate")
    gate.add_argument("--stage")
    gate.add_argument("--decision", choices=["approved", "rejected", "approve", "reject"])
    gate.add_argument("--by", default="ron")
    gate.add_argument("--note", default="")
    gate.add_argument("--file", help="JSON file with stage, decision, by, note, and optional stage_split")

    decide = sub.add_parser("decide", help="Approve or reject one spend request")
    decide.add_argument("--request")
    decide.add_argument("--decision", choices=["approved", "rejected", "approve", "reject"])
    decide.add_argument("--by", default="ron")
    decide.add_argument("--note", default="")
    decide.add_argument("--file", help="JSON file with request_id, decision, by, and note")

    credit = sub.add_parser("credit", help="Add a credit line")
    credit.add_argument("--role", required=True)
    credit.add_argument("--name", required=True)
    credit.add_argument("--note", default="")

    budget = sub.add_parser(
        "budget",
        help="Estimate the film from its brief, write budget.json, and print budget, estimate, spend, and over or under.",
    )
    budget.add_argument("--write", action="store_true", help="Write or update budget.json")
    budget.add_argument("--total", type=float, help="Film budget in dollars. Defaults to the brief or $500.")
    budget.add_argument("--trailer", choices=["on", "off"], help="Turn the trailer line on or off")
    budget.add_argument("--contingency", type=float, help="Percent held back. 10 means 10 percent.")
    budget.add_argument("--marketing", type=float, help="Marketing percent, used when the trailer is on.")
    budget.add_argument("--tier", action="append", default=[], help="stage=good, stage=better, or stage=best")
    budget.add_argument("--resolution", choices=["720p", "1080p"])
    budget.add_argument("--upgrade", help="stage=tier. Changes that tier when the line plus contingency can hold it.")

    shot = sub.add_parser(
        "test-shot",
        help="Prepare exactly one picture call for one shot. Sends it only with --live, and only when the gate, the key, and the price all allow it.",
    )
    shot.add_argument("--shot", required=True, help="Shot id, for example s01-sh01")
    shot.add_argument("--model", help="Picture model id from the rate card. Wins over --tier and the budget.")
    shot.add_argument("--tier", choices=["good", "better", "best"], help="Picture tier. Wins over the budget tier.")
    shot.add_argument(
        "--wait",
        type=float,
        help="Seconds to wait for fal to finish this shot. The default is 600, from config/providers.json.",
    )

    release = sub.add_parser(
        "release",
        help="Release a booked estimate that produced nothing. The original ledger entry stays.",
    )
    release.add_argument("--entry", required=True, help="Ledger entry id, for example spend-014")
    release.add_argument("--by", default="ron")
    release.add_argument("--note", default="")

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (LineProducerError, BudgetError, ShotModelError, ModelRoutingError, OSError, json.JSONDecodeError) as exc:
        print(exc)
        return 1


def _run(args) -> int:
    production = Path(args.production)
    if args.command == "start":
        producer = LineProducer.start(production, run_id=args.run, stage=args.stage)
        print(producer.status_text())
        return 0
    if args.command == "budget":
        return _budget_command(production, args)
    if not args.run:
        print("Pass --run with the run id.")
        return 1
    producer = LineProducer.open(production, args.run)
    if args.command == "status":
        narration = ""
        if args.narrate:
            if not args.live:
                print("Offline is the default. Pass --live to add a model sentence. Nothing was sent.")
            else:
                client = llm_for_command(
                    production,
                    args.run,
                    live=True,
                    offline=False,
                    price_override=args.price_override,
                )
                try:
                    narration = client.complete(
                        role="line-producer",
                        purpose="status",
                        system="Add one short sentence for Ron. Do not change any dollar amount.",
                        user=producer.status_text(),
                        max_tokens=200,
                    )
                except LLMError as exc:
                    print(exc)
                    print(producer.status_text())
                    return 2
        print(producer.status_text(narration))
        return 0
    if args.command == "spend":
        result = producer.record_spend(args.stage, args.amount, args.description, kind=args.kind)
        print(result.message)
        return 0 if result.recorded else 2
    if args.command == "approve-gate":
        payload = _file(args.file)
        stage = args.stage or payload.get("stage")
        decision = args.decision or payload.get("decision")
        by = payload.get("by") or args.by
        note = args.note or payload.get("note") or ""
        split = payload.get("stage_split")
        if not stage or not decision:
            print("approve-gate needs a stage and a decision, on the command or in the file.")
            return 1
        print(producer.approve_gate(stage, decision, by, note=note, stage_split=split))
        return 0
    if args.command == "decide":
        payload = _file(args.file)
        request_id = args.request or payload.get("request_id")
        decision = args.decision or payload.get("decision")
        by = payload.get("by") or args.by
        note = args.note or payload.get("note") or ""
        if not request_id or not decision:
            print("decide needs a request id and a decision, on the command or in the file.")
            return 1
        print(producer.decide_request(request_id, decision, by, note=note))
        return 0
    if args.command == "credit":
        producer.add_credit(args.role, args.name, args.note)
        print(f"Added credit: {args.role} — {args.name}")
        return 0
    if args.command == "release":
        released = producer.release_booked_estimate(args.entry, by=args.by, note=args.note)
        print(
            f"Released {args.entry}. ${money_number(released['amount_usd']):.2f} came off the running total. "
            f"The original entry is still on the ledger. {released['request_id']} records the release."
        )
        return 0
    if args.command == "test-shot":
        from movie_swarm.providers import CallSettings

        if args.wait is not None and args.wait <= 0:
            print("Pass --wait as a number of seconds greater than zero. Nothing was sent.")
            return 1
        result = run_test_shot(
            producer,
            args.shot,
            live=args.live,
            settings=CallSettings(price_override=args.price_override, wait_seconds=args.wait),
            model=args.model,
            tier=args.tier,
        )
        print(result["message"])
        if result.get("output"):
            print(f"File: {result['output']}")
            print(f"Location setting: {result.get('location')}")
        if result["status"] in {"generated", "replayed", "offline"}:
            return 0
        return 2
    print("Unknown command.")
    return 1


def _budget_command(production: Path, args) -> int:
    """Write the film budget when asked, then print the one-screen report."""
    inputs = read_estimate_inputs(production)
    existing = load_film_budget(production)
    tiers = {}
    for item in args.tier or []:
        if "=" not in item:
            raise BudgetError(f"A tier looks like production=better. Got {item}.")
        name, _, value = item.partition("=")
        tiers[name.strip()] = value.strip()
    if args.upgrade:
        if not args.run:
            print("Pass --run with the run id.")
            return 1
        if "=" not in args.upgrade:
            raise BudgetError("An upgrade looks like production=best.")
        stage, _, tier = args.upgrade.partition("=")
        producer = LineProducer.open(production, args.run)
        print(producer.upgrade_tier(stage.strip(), tier.strip()))
        producer = LineProducer.open(production, args.run)
        document = load_film_budget(production)
        if document is None:
            return 2
        print(format_estimate(production, estimate_film(production, document, inputs), producer.record, float(producer.run.data["cost_usd"])))
        return 0
    if args.write or existing is None and args.write:
        trailer = inputs["trailer_on"]
        if args.trailer == "on":
            trailer = True
        elif args.trailer == "off":
            trailer = False
        elif existing is not None:
            trailer = bool(existing.get("trailer_on"))
        total = args.total
        if total is None and existing is not None:
            total = float(existing["total_usd"])
        if total is None:
            total = 500
        contingency = args.contingency
        if contingency is None and existing is not None:
            contingency = float(existing["contingency_share"])
        if contingency is None:
            contingency = 10
        marketing = args.marketing
        if marketing is None and existing is not None:
            marketing = float(existing["marketing_share"])
        if marketing is None:
            marketing = 10
        merged = dict((existing or {}).get("tiers") or {})
        merged.update(tiers)
        resolution = args.resolution or (existing or {}).get("production_resolution") or "720p"
        document = proposed_document(
            total,
            trailer_on=trailer,
            contingency_percent=contingency,
            marketing_percent=marketing,
            tiers=merged,
            production_resolution=resolution,
        )
        if existing and isinstance(existing.get("line_shares"), dict):
            document["line_shares"] = existing["line_shares"]
        write_film_budget(production, document)
        print(f"Wrote {production / 'budget.json'}.")
    else:
        document = existing
    if document is None:
        print("This film has no budget.json. Pass --write to create one. The report below uses the $500 fallback.")
        from movie_swarm.budget import fallback_document

        document = fallback_document()
    spent = 0.0
    record = {"ledger": []}
    if args.run:
        try:
            producer = LineProducer.open(production, args.run)
        except LineProducerError as exc:
            print(exc)
            return 1
        spent = float(producer.run.data["cost_usd"])
        record = producer.record
    print(format_estimate(production, estimate_film(production, document, inputs), record, spent))
    return 0


def _file(path: str | None) -> dict:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LineProducerError("The decision file must be a JSON object.")
    return data
