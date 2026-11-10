"""Locations the shared package uses inside the repo."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Top of the movie-swarm checkout."""
    return Path(__file__).resolve().parent.parent


def schemas_dir() -> Path:
    return repo_root() / "schemas"


def config_dir() -> Path:
    return repo_root() / "config"
