#!/usr/bin/env python3
"""Run the offline studio from the treatment through delivery.

Stops at the first gate that is not approved. Does not approve gates.
Does not spend. The test harness that approves gates is not used here.

Usage, from the repo root:

    python3 scripts/studio.py --production path/to/a-production --run studio-1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from movie_swarm.envfile import load_env

load_env()

from movie_swarm.studio import StudioError, run_studio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the studio offline. Stops at each gate. Spends nothing.")
    parser.add_argument("--production", required=True, help="Production folder")
    parser.add_argument("--run", default="studio-1")
    args = parser.parse_args(argv)
    try:
        result = run_studio(args.production, run_id=args.run, auto_approve=False)
    except StudioError as exc:
        print(exc)
        return 1
    print(result["message"])
    print(f"Status: {result['status']}")
    if result["stopped_at"]:
        print(f"Stopped at: {result['stopped_at']}")
    if result["completed"]:
        print("Completed: " + ", ".join(result["completed"]))
    print(f"Spent: ${result['spent_usd']:.2f}")
    print(f"Generation gate: {result['generation_gate']}")
    if result["status"] == "complete":
        return 0
    if result["status"] == "stopped":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
