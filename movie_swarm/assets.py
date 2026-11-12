"""Where finished media lives.

With no asset root, media stays in the production folder. That folder may
live outside this repo. Set ``MOVIE_SWARM_ASSET_ROOT`` or ``asset_root`` in
``config/assets.json`` to put finished media under that root, in a directory
named for the production folder. This does not move or delete anything.
The environment variable wins over the file.
"""

from __future__ import annotations

import os
from pathlib import Path

from movie_swarm.handoff import read_handoff
from movie_swarm.paths import config_dir


ASSET_ROOT_ENV = "MOVIE_SWARM_ASSET_ROOT"


def asset_config_path() -> Path:
    return config_dir() / "assets.json"


def load_asset_config(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else asset_config_path()
    return read_handoff(path, schema="asset-config")


def configured_asset_root(config_path: str | Path | None = None) -> Path | None:
    """The external asset root, or None when media stays in the production folder."""
    env = os.environ.get(ASSET_ROOT_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    config = load_asset_config(config_path)
    raw = config.get("asset_root")
    if raw:
        return Path(str(raw)).expanduser()
    return None


def resolve_asset(
    production_dir: str | Path,
    relative_path: str,
    config_path: str | Path | None = None,
) -> Path:
    """Resolve one media path.

    With no asset root configured, this is ``production_dir / relative_path``.
    With a root configured, this is ``asset_root / <production folder name> / relative_path``.
    """
    relative = Path(relative_path)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise ValueError(
            f"Asset paths must stay inside the production folder. Got: {relative_path}"
        )
    production = Path(production_dir)
    root = configured_asset_root(config_path)
    if root is None:
        return (production / relative).resolve()
    return (root / production.name / relative).resolve()
