#!/usr/bin/env python3
"""Check the machine. Does not spend. Run from the repo root.

    python3 scripts/doctor.py
    python3 scripts/doctor.py --ping
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from movie_swarm.envfile import load_env

load_env()

from movie_swarm.doctor import main


if __name__ == "__main__":
    raise SystemExit(main())
