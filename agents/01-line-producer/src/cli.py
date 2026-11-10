"""Line Producer command, from this agent's folder: python3 -m src.cli"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from movie_swarm.cli_line_producer import main


if __name__ == "__main__":
    raise SystemExit(main())
