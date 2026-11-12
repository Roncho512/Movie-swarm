"""Load a repo-root ``.env`` without overriding the environment.

The commands in ``scripts/`` call this at start. A variable that is already
set is left alone. A missing file is not an error. Values are not printed,
returned, or logged.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from movie_swarm.paths import repo_root


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# Tests set this so a repo ``.env`` cannot leak film folders or keys into the suite.
# An explicit path still loads. ``load_env()`` with no path is the auto-load.
SKIP_ENV_FILE = "MOVIE_SWARM_SKIP_ENV_FILE"


def autoload_disabled() -> bool:
    """True when ``load_env()`` should not read the repo ``.env``."""
    flag = os.environ.get(SKIP_ENV_FILE, "").strip().casefold()
    return flag in {"1", "true", "yes"}


def load_env(path: str | Path | None = None) -> list[str]:
    """Set unset variables from a KEY=VALUE file.

    Returns the names that were set. The values are not returned.
    A call with no path is the auto-load of the repo ``.env``. That auto-load
    does nothing when ``MOVIE_SWARM_SKIP_ENV_FILE`` is set. A caller that
    passes a path still reads that file.
    """
    if path is None and autoload_disabled():
        return []
    env_path = Path(path) if path is not None else repo_root() / ".env"
    if not env_path.is_file():
        return []
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return []
    set_names: list[str] = []
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not _NAME.match(key) or key in os.environ:
            continue
        os.environ[key] = _unquote(value.strip())
        set_names.append(key)
    return set_names


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
