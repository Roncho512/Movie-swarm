#!/usr/bin/env python3
"""Validate JSON handoffs against the schemas in schemas/.

Command line:

    python3 scripts/validate-schema.py path/to/shot-list.json
    python3 scripts/validate-schema.py path/to/file.json --schema shot-list
    python3 scripts/validate-schema.py --production productions/the-last-marker

From Python, import the function (this file's name has a hyphen, so import
the package instead):

    from movie_swarm.validate import validate_file
    result = validate_file("productions/the-last-marker/shot-lists/shot-list.json")
    if not result.ok:
        raise SystemExit(result.text())
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from movie_swarm.validate import audit_exit_code, audit_production, format_audit, validate_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a JSON file against the matching schema in schemas/."
    )
    parser.add_argument("path", nargs="?", help="JSON file to validate")
    parser.add_argument(
        "--schema",
        help="Schema name or path. Example: shot-list or schemas/shot-list.schema.json",
    )
    parser.add_argument(
        "--production",
        help="Audit every JSON file in a production folder",
    )
    args = parser.parse_args(argv)

    if args.production:
        items = audit_production(args.production)
        print(format_audit(items))
        return audit_exit_code(items)

    if not args.path:
        parser.error("Give a JSON file, or pass --production.")

    result = validate_file(args.path, args.schema)
    print(result.text())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
