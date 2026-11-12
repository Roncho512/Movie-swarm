#!/usr/bin/env python3
"""Copy a production folder out of this repo and check the copy.

    python3 scripts/export-film.py --from productions/<name> --to <films root>/<name>

The source is not deleted. A checksum list is written in the destination
and checked against the copied files. Nothing is spent.
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

from movie_swarm.films import FilmsError, export_film


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy a production out of the repo. Does not delete the source.")
    parser.add_argument("--from", dest="source", required=True, help="In-repo production path, or its folder name")
    parser.add_argument(
        "--to",
        dest="destination",
        required=True,
        help="Destination path, or a name under the films root",
    )
    args = parser.parse_args(argv)
    try:
        result = export_film(args.source, args.destination)
    except FilmsError as exc:
        print(exc)
        return 1
    print(f"Copied {result['files']} files. Checksums match. The source was left in place.")
    print(f"Checksum list: {result['checksums']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
