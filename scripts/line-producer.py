#!/usr/bin/env python3
"""Line Producer command. Run from the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from movie_swarm.cli_line_producer import main


if __name__ == "__main__":
    raise SystemExit(main())
