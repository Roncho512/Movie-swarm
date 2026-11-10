"""Shared foundation for Movie Swarm.

Agents hand work to each other as JSON files. This package checks those
files, keeps a run record, and reads the review-gate, budget, model, and
asset-root settings.

Invalid handoffs raise ``HandoffError`` with the file name, the schema, and
what is wrong. The file is not passed on.
"""

from movie_swarm.assets import configured_asset_root, resolve_asset
from movie_swarm.gates import budget_cap_usd, is_stage_gated, would_exceed_budget
from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.models import resolve_model
from movie_swarm.run_state import RunState
from movie_swarm.validate import validate_file

__all__ = [
    "HandoffError",
    "RunState",
    "budget_cap_usd",
    "configured_asset_root",
    "is_stage_gated",
    "read_handoff",
    "resolve_asset",
    "resolve_model",
    "validate_file",
    "would_exceed_budget",
    "write_handoff",
]
