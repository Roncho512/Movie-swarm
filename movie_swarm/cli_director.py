"""Command line for the Director.

Intake, answers, and crew calls are files and flags. Nothing waits at a prompt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from movie_swarm.director import Director, DirectorError
from movie_swarm.dispatch import CrewCall
from movie_swarm.llm import client_from_environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Director: draft a treatment, take Ron's answers, and call crew through the Line Producer."
    )
    parser.add_argument("--production", required=True, help="Production folder")
    parser.add_argument("--run", default="phase-1")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not call a model, even if ANTHROPIC_API_KEY is set",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    intake = sub.add_parser("intake", help="Draft a treatment and the first questions")
    intake.add_argument("--screenplay", help="Markdown, Fountain, PDF, or Word")
    intake.add_argument("--partial", help="A partial treatment, JSON or Markdown")

    answer = sub.add_parser("answer", help="Apply Ron's answers and revise the draft")
    answer.add_argument("--answers", required=True, help="Answers file, or the questions file with answers filled in")

    dispatch = sub.add_parser("dispatch", help="Call a crew agent through the Line Producer")
    dispatch.add_argument(
        "--agent",
        required=True,
        choices=[
            "production",
            "sound-designer",
            "editor",
            "qa",
            "fix-loop",
            "prop-master",
            "script-supervisor",
            "cinematographer",
            "stunt-coordinator",
            "dailies",
            "composer",
            "colorist",
            "mixer",
        ],
    )
    dispatch.add_argument(
        "--crew-command",
        required=True,
        choices=["estimate", "dry-run", "plan", "generate", "lock", "check", "package", "boards", "breakdown", "review", "assemble", "spot", "grade", "mix"],
    )
    dispatch.add_argument("--estimate", type=float, required=True, help="Dollars to check against the cap. An estimate command is usually 0.")
    dispatch.add_argument("--shot-list")
    dispatch.add_argument("--output-dir")
    dispatch.add_argument("--takes", help="Takes manifest for the dailies reviewer")
    dispatch.add_argument("--note", default="")

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except DirectorError as exc:
        print(exc)
        return 1


def _run(args) -> int:
    llm = None if args.offline else client_from_environment()
    director = Director(args.production, llm=llm)
    if args.command == "intake":
        if llm is None:
            print("No model call. Drafting offline.")
        result = director.intake(screenplay=args.screenplay, partial=args.partial, run_id=args.run)
        print(f"Draft treatment: {result['treatment']}")
        print(f"Readable draft: {result['treatment_markdown']}")
        print(f"Questions: {result['questions']} ({result['question_count']} questions)")
        print(f"Run: {result['run_id']}")
        print("Status: draft. Ron has not approved it.")
        return 0
    if args.command == "answer":
        result = director.answer(args.answers, run_id=args.run)
        print(f"Treatment: {result['treatment']}")
        print(f"Questions: {result['questions']} ({result['questions_status']})")
        print(f"Required questions still open: {result['open_required']}")
        print("Status: draft. Ron has not approved it.")
        return 0
    call = CrewCall(
        agent=args.agent,
        command=args.crew_command,
        estimated_cost_usd=args.estimate,
        note=args.note,
        shot_list=args.shot_list,
        output_dir=args.output_dir,
        production_dir=args.production,
        takes=args.takes,
    )
    result = director.dispatch(call, args.run)
    print(result.message)
    if result.output:
        print(result.output)
    if result.status == "ran":
        return 0
    if result.status == "paused":
        return 2
    return 1
