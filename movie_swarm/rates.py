"""Published generator prices for a dry-run quote.

The numbers live in ``config/generation-rates.json``. Each one names the
page it came from and the date that page was read. A missing model is not
given a made-up price.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.money import as_money
from movie_swarm.paths import config_dir


class RateCardError(Exception):
    """The rate card cannot be read."""


def rates_path() -> Path:
    return config_dir() / "generation-rates.json"


def load_rate_card(path: str | Path | None = None) -> dict:
    """Return the rate card. Generator entries are keyed by model id."""
    card_path = Path(path) if path else rates_path()
    try:
        data = json.loads(card_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RateCardError(f"The rate card could not be read: {card_path}. {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("generators"), list):
        raise RateCardError(f"The rate card at {card_path} has no generator list.")
    generators = {}
    for item in data["generators"]:
        if not isinstance(item, dict) or not item.get("model"):
            raise RateCardError("A generator on the rate card needs a model id.")
        generators[str(item["model"])] = item
    loaded = dict(data)
    loaded["by_model"] = generators
    return loaded


def generator_rate(card: dict, model: str) -> dict | None:
    """The published row for ``model``, or None when the card does not list it."""
    return (card.get("by_model") or {}).get(model)


def usd_per_second(row: dict):
    """The published per-second price as a dollar amount."""
    return as_money(row["usd_per_second"])
