"""Published generator prices for a dry-run quote.

The numbers live in ``config/generation-rates.json``. Each one names the
page it came from and the date that page was read. A missing model is not
given a made-up price.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from movie_swarm.money import as_money
from movie_swarm.paths import config_dir


class RateCardError(Exception):
    """The rate card cannot be read."""


def rates_path() -> Path:
    return config_dir() / "generation-rates.json"


def generator_rate(card: dict, model: str) -> dict | None:
    """The published row for ``model``, or None when the card does not list it."""
    return (card.get("by_model") or {}).get(model)


def usd_per_second(row: dict):
    """The published per-second price as a dollar amount."""
    return as_money(row["usd_per_second"])


def load_rate_card(path: str | Path | None = None) -> dict:
    """Return the rate card. Generator entries are keyed by model id.

    Text rows live under ``text`` and share the same model index. A picture
    plan still reads ``generators`` only.
    """
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
    for item in data.get("text") or []:
        if not isinstance(item, dict) or not item.get("model"):
            raise RateCardError("A text model on the rate card needs a model id.")
        name = str(item["model"])
        if name in generators:
            raise RateCardError(f"{name} is listed twice on the rate card.")
        generators[name] = item
    loaded = dict(data)
    loaded["by_model"] = generators
    return loaded


def token_prices(row: dict | None, input_tokens: int):
    """Dollars per million input tokens and per million output tokens.

    Returns None when the row has no published price. Haiku's higher pair
    applies only when the prompt is over the row's token threshold.
    """
    if not row:
        return None
    base_in = row.get("usd_per_million_input_tokens")
    base_out = row.get("usd_per_million_output_tokens")
    if base_in in (None, "") or base_out in (None, ""):
        return None
    threshold = row.get("prompt_token_threshold")
    over_in = row.get("usd_per_million_input_tokens_over_threshold")
    over_out = row.get("usd_per_million_output_tokens_over_threshold")
    try:
        use_over = (
            threshold not in (None, "")
            and int(input_tokens) > int(threshold)
            and over_in not in (None, "")
            and over_out not in (None, "")
        )
        if use_over:
            return as_money(over_in), as_money(over_out)
        return as_money(base_in), as_money(base_out)
    except (TypeError, ValueError):
        return None


def token_dollars(input_tokens: int, output_tokens: int, input_rate, output_rate):
    """One quote from token counts and per-million prices. Rounded once."""
    raw = (
        Decimal(int(input_tokens)) * as_money(input_rate)
        + Decimal(int(output_tokens)) * as_money(output_rate)
    ) / Decimal(1_000_000)
    return as_money(raw)
