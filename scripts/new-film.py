#!/usr/bin/env python3
"""Create a film folder under the films root.

    python3 scripts/new-film.py <name>
    python3 scripts/new-film.py <name> --total 500
    python3 scripts/new-film.py <name> --git

The folder is created outside this repo. --git runs git init there.
It does not add a remote and it does not push. Nothing is spent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from movie_swarm.envfile import load_env

load_env()

from movie_swarm.budget import BudgetError
from movie_swarm.films import FilmsError, create_film


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a film folder in the films root. Spends nothing.")
    parser.add_argument("name", help="Film folder name, such as my-film")
    parser.add_argument("--total", type=float, help="Film budget in dollars. Omit it to flag the calculator default.")
    parser.add_argument("--git", action="store_true", help="git init in the new folder. No remote and no push.")
    args = parser.parse_args(argv)
    try:
        create_film(args.name, total_usd=args.total, git=args.git)
    except (FilmsError, BudgetError) as exc:
        print(exc)
        return 1
    print(f"Created {args.name} in the films root.")
    if args.total is None:
        print("Total was not asked. budget.json uses the calculator default and says so.")
    else:
        print(f"Total asked: ${args.total:.2f}.")
    if args.git:
        print("Local git repo. No remote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
