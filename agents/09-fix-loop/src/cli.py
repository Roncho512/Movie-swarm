#!/usr/bin/env python3
"""
Fix Loop CLI

Workflow:

  # Step 1: Generate fix plan from latest QA report
  python3 -m src.cli plan ../../productions/the-last-marker

  # Step 2: See what needs fixing (human-readable instructions)
  python3 -m src.cli show ../../productions/the-last-marker

  # Step 3: Regenerate clips manually in Flow/Seedance using the modified prompts

  # Step 4: Mark fixes as complete (point to the new clip)
  python3 -m src.cli complete FIX-01-001 ../../productions/the-last-marker --clip clips/selected/s01-sh02.mp4

  # Step 5: Finalize the iteration
  python3 -m src.cli finalize ../../productions/the-last-marker

  # Step 6: Re-run editor, then QA, then check verdict
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .pipeline import FixLoopPipeline, FixPlan, FixTask, FixLog


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Deserialization helper
# ---------------------------------------------------------------------------


def _task_from_dict(d: dict) -> FixTask:
    """Reconstruct a FixTask from a JSON dict, supplying defaults for
    any missing fields."""
    return FixTask(
        task_id=d.get("task_id", "???"),
        finding_id=d.get("finding_id", "???"),
        severity=d.get("severity", "major"),
        assigned_to=d.get("assigned_to", "production"),
        shots_affected=d.get("shots_affected", []),
        action=d.get("action", "regenerate"),
        description=d.get("description", ""),
        recommendation=d.get("recommendation", ""),
        original_prompt=d.get("original_prompt", ""),
        modified_prompt=d.get("modified_prompt", ""),
        prompt_modifications=d.get("prompt_modifications", []),
        reference_assets=d.get("reference_assets", []),
        status=d.get("status", "pending"),
        attempts=d.get("attempts", 0),
        max_attempts=d.get("max_attempts", 3),
        result_notes=d.get("result_notes", ""),
        new_clip_path=d.get("new_clip_path", ""),
    )


def _load_latest_plan(fixer: FixLoopPipeline) -> bool:
    """Load the latest fix plan from disk into fixer.plan.
    Returns True if a plan was found."""
    plan_files = sorted(fixer.fix_dir.glob("fix-plan-v*.json"))
    if not plan_files:
        return False

    raw = json.loads(plan_files[-1].read_text())
    tasks = [_task_from_dict(t) for t in raw.get("fix_tasks", [])]

    fixer.plan = FixPlan(
        production_id=raw["production_id"],
        qa_report_version=raw["qa_report_version"],
        iteration=raw["iteration"],
        created_at=raw["created_at"],
        fix_tasks=tasks,
        summary=raw.get("summary", {}),
        overall_status=raw.get("overall_status", "pending"),
    )

    # Initialize a log for this iteration
    completed = len([t for t in tasks if t.status == "complete"])
    failed = len([t for t in tasks if t.status == "failed"])
    skipped = len([t for t in tasks if t.status == "skipped"])

    fixer.log = FixLog(
        production_id=raw["production_id"],
        iteration=raw["iteration"],
        started_at=raw["created_at"],
        tasks_completed=completed,
        tasks_failed=failed,
        tasks_skipped=skipped,
        clips_regenerated=[t.new_clip_path for t in tasks
                          if t.status == "complete" and t.new_clip_path],
    )
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_plan(args):
    """Generate a fix plan from the latest QA report."""
    fixer = FixLoopPipeline(args.production_dir)
    plan = fixer.generate_fix_plan(include_minor=args.include_minor)

    print(f"\nFix Plan — Iteration {plan.iteration}")
    print(f"QA Report: v{plan.qa_report_version}")
    print(f"Tasks: {plan.summary.get('total_tasks', 0)}")

    if plan.summary.get("total_tasks", 0) == 0:
        verdict = plan.summary.get("verdict", "")
        if verdict == "approved":
            print("\nQA APPROVED — no fixes needed!")
        else:
            print("\nNo actionable findings at current severity filter.")
            print("Run with --include-minor to include minor findings.")
        return 0

    by_agent = plan.summary.get("by_agent", {})
    by_severity = plan.summary.get("by_severity", {})
    print(f"  By agent: {by_agent}")
    print(f"  By severity: {by_severity}")

    if plan.summary.get("max_iterations_reached"):
        print(f"\n  WARNING: Max iterations reached. Review findings manually.")

    print(f"\nRun 'show' to see detailed fix instructions:")
    print(f"  python3 -m src.cli show {args.production_dir}")
    return 0


def cmd_show(args):
    """Show detailed fix instructions for manual execution."""
    fixer = FixLoopPipeline(args.production_dir)

    if not _load_latest_plan(fixer):
        print("No fix plan found. Run 'plan' first.")
        return 1

    fixer.print_fix_instructions()
    return 0


def cmd_complete(args):
    """Mark a fix task as complete."""
    fixer = FixLoopPipeline(args.production_dir)

    if not _load_latest_plan(fixer):
        print("No fix plan found. Run 'plan' first.")
        return 1

    fixer.mark_fix_complete(
        task_id=args.task_id,
        new_clip_path=args.clip or "",
        notes=args.notes or "",
    )

    # Re-write the plan with updated status
    fixer._write_fix_plan()
    return 0


def cmd_finalize(args):
    """Finalize the current fix iteration."""
    fixer = FixLoopPipeline(args.production_dir)

    if not _load_latest_plan(fixer):
        print("No fix plan found. Run 'plan' first.")
        return 1

    fixer.finalize_iteration()
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="fix-loop",
        description="Movie Swarm Fix Loop — QA-driven regeneration coordinator",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    # plan
    p_plan = sub.add_parser("plan", help="Generate fix plan from latest QA report")
    p_plan.add_argument("production_dir", type=Path)
    p_plan.add_argument("--include-minor", action="store_true",
                       help="Include minor severity findings")

    # show
    p_show = sub.add_parser("show", help="Show fix instructions for manual execution")
    p_show.add_argument("production_dir", type=Path)

    # complete
    p_comp = sub.add_parser("complete", help="Mark a fix task as complete")
    p_comp.add_argument("task_id", help="Fix task ID (e.g., FIX-01-001)")
    p_comp.add_argument("production_dir", type=Path)
    p_comp.add_argument("--clip", help="Path to the new clip (relative to production dir)")
    p_comp.add_argument("--notes", help="Notes about the fix")

    # finalize
    p_fin = sub.add_parser("finalize", help="Finalize the current fix iteration")
    p_fin.add_argument("production_dir", type=Path)

    args = parser.parse_args()
    setup_logging(args.verbose)

    commands = {
        "plan": cmd_plan,
        "show": cmd_show,
        "complete": cmd_complete,
        "finalize": cmd_finalize,
    }
    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
