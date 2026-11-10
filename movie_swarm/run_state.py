"""File-based record of one production run.

The file is plain JSON checked against ``schemas/run-state.schema.json``.
It records the stage, the status, the artifacts produced, and the money
spent against the cap that was in force when the run opened.

Recording a cost does not refuse the spend. Ask ``would_exceed_budget``
before spending. This module keeps the record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from movie_swarm.gates import budget_cap_usd
from movie_swarm.handoff import read_handoff, write_handoff
from movie_swarm.money import as_money, money_number


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_run_id(run_id: str) -> str:
    if (
        not run_id
        or run_id in (".", "..")
        or "/" in run_id
        or "\\" in run_id
        or ".." in run_id
    ):
        raise ValueError(f"run_id must be a plain folder name, got {run_id!r}.")
    return run_id


def default_run_state_path(production_dir: str | Path, run_id: str) -> Path:
    safe_id = _check_run_id(run_id)
    return Path(production_dir) / "runs" / safe_id / "run-state.json"


class RunState:
    """One run-state file. ``data`` is the JSON object. ``path`` is where it lives."""

    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = Path(path)

    @classmethod
    def create(
        cls,
        production_dir: str | Path,
        *,
        run_id: str | None = None,
        stage: str = "screenwriter",
        status: str = "pending",
        budget_cap: float | None = None,
        notes: str = "",
        config_path: str | Path | None = None,
    ) -> "RunState":
        """Open a new run and write its state file."""
        production = Path(production_dir)
        production_id = production.name
        chosen_id = _check_run_id(run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        cap = budget_cap_usd(config_path) if budget_cap is None else money_number(budget_cap)
        data = {
            "production_id": production_id,
            "run_id": chosen_id,
            "stage": stage,
            "status": status,
            "artifacts": [],
            "cost_usd": 0.0,
            "budget_cap_usd": money_number(cap),
            "updated_at": _now(),
            "notes": notes,
        }
        path = default_run_state_path(production, chosen_id)
        write_handoff(path, data, schema="run-state")
        return cls(data, path)

    @classmethod
    def load(cls, path: str | Path) -> "RunState":
        document = Path(path)
        data = read_handoff(document, schema="run-state")
        return cls(data, document)

    def save(self) -> Path:
        self.data["updated_at"] = _now()
        return write_handoff(self.path, self.data, schema="run-state")

    def set_stage(self, stage: str, status: str | None = None) -> None:
        self.data["stage"] = stage
        if status is not None:
            self.data["status"] = status
        self.save()

    def add_artifact(self, name: str, path: str, schema: str | None = None) -> None:
        item = {"name": name, "path": path}
        if schema:
            item["schema"] = schema
        self.data["artifacts"].append(item)
        self.save()

    def add_cost(self, amount_usd: float | int | str) -> float:
        """Add to the running spend and return the new total. Does not check the cap."""
        amount = as_money(amount_usd)
        if amount < 0:
            raise ValueError("Cannot record a negative cost.")
        self.data["cost_usd"] = float(as_money(self.data["cost_usd"]) + amount)
        self.save()
        return self.data["cost_usd"]
