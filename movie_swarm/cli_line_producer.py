"""Command line for the Line Producer.

Nothing here waits for a typed answer. Pass flags, or pass a JSON file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from movie_swarm.line_producer import LineProducer, LineProducerError
from movie_swarm.llm import LLMError, client_from_environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Line Producer: budget, gates, credits, and status for one film run."
    )
    parser.add_argument("--production", required=True, help="Production folder")
    parser.add_argument("--run", help="Run id. Required except for start, which can choose one.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Open a run for this production")
    start.add_argument("--stage", default="treatment")

    status = sub.add_parser("status", help="Say where the run is, in plain language")
    status.add_argument(
        "--narrate",
        action="store_true",
        help="Add one sentence from the cheap model when ANTHROPIC_API_KEY is set",
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

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (LineProducerError, OSError, json.JSONDecodeError) as exc:
        print(exc)
        return 1


def _run(args) -> int:
    production = Path(args.production)
    if args.command == "start":
        producer = LineProducer.start(production, run_id=args.run, stage=args.stage)
        print(producer.status_text())
        return 0
    if not args.run:
        print("Pass --run with the run id.")
        return 1
    producer = LineProducer.open(production, args.run)
    if args.command == "status":
        narration = ""
        if args.narrate:
            client = client_from_environment()
            if client is None:
                print("ANTHROPIC_API_KEY is not set, so the status has no model sentence.")
            else:
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
    print("Unknown command.")
    return 1


def _file(path: str | None) -> dict:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LineProducerError("The decision file must be a JSON object.")
    return data
