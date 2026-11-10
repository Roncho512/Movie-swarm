"""Human review gates and the film budget cap.

Both live in ``config/gates.json``. Changing a switch or the cap is an edit
to that file. This module only answers questions. It does not run the pipeline.
"""

from __future__ import annotations

from pathlib import Path

from movie_swarm.handoff import read_handoff
from movie_swarm.money import as_money
from movie_swarm.paths import config_dir


def gate_config_path() -> Path:
    return config_dir() / "gates.json"


def load_gate_config(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else gate_config_path()
    return read_handoff(path, schema="gate-config")


def _stage_key(stage: str) -> str:
    """Normalize 'Sound Designer', sound_designer, and sound-designer to one key."""
    flattened = stage.strip().lower().replace("_", " ").replace("-", " ")
    return "-".join(flattened.split())


def is_stage_gated(stage: str, config_path: str | Path | None = None) -> bool:
    """Return True when a person reviews ``stage`` before the pipeline moves on.

    Stage names match the keys in ``config/gates.json`` (for example
    ``sound-designer``). ``Sound Designer`` and ``sound_designer`` match that key.
    A stage with no switch raises ``ValueError`` so a typo cannot skip a review.
    """
    config = load_gate_config(config_path)
    key = _stage_key(stage)
    gates = config["gates"]
    if key not in gates:
        known = ", ".join(sorted(gates))
        raise ValueError(
            f"No review gate for stage '{stage}'. "
            f"Configured stages: {known}. "
            "Add a true/false switch for it in config/gates.json."
        )
    return bool(gates[key])


def budget_cap_usd(config_path: str | Path | None = None) -> float:
    """The film budget cap in US dollars."""
    config = load_gate_config(config_path)
    return float(as_money(config["budget_cap_usd"]))


def would_exceed_budget(
    additional_usd: float | int | str,
    *,
    spent_usd: float | int | str = 0,
    cap_usd: float | int | str | None = None,
    config_path: str | Path | None = None,
) -> bool:
    """Return True when spent plus this new amount is over the cap.

    Landing exactly on the cap is allowed. ``cap_usd`` defaults to the cap in
    the gate config. Pass ``spent_usd`` from the run state when a run is open.
    """
    additional = as_money(additional_usd)
    spent = as_money(spent_usd)
    if additional < 0 or spent < 0:
        raise ValueError("Spend amounts cannot be negative.")
    cap = as_money(budget_cap_usd(config_path) if cap_usd is None else cap_usd)
    return (spent + additional) > cap
