"""Which generator each role uses.

The map is ``config/model-routing.json``. Later, a director can add an entry
under ``overrides`` for one scene or one shot. This phase only reads the file.
The agents still call the generators hardcoded in their own programs.
"""

from __future__ import annotations

from pathlib import Path

from movie_swarm.handoff import read_handoff
from movie_swarm.paths import config_dir


class ModelRoutingError(Exception):
    """The model map has no answer for this role or purpose."""


def model_config_path() -> Path:
    return config_dir() / "model-routing.json"


def load_model_routing(config_path: str | Path | None = None) -> dict:
    path = Path(config_path) if config_path else model_config_path()
    return read_handoff(path, schema="model-routing")


def _specificity(override: dict) -> int:
    return sum(1 for key in ("scene", "shot", "purpose") if override.get(key))


def _override_matches(override: dict, *, scene: str | None, shot: str | None, purpose: str | None) -> bool:
    if override.get("scene") and override["scene"] != scene:
        return False
    if override.get("shot") and override["shot"] != shot:
        return False
    if override.get("purpose") and override["purpose"] != purpose:
        return False
    return True


def resolve_model(
    role: str,
    *,
    scene: str | None = None,
    shot: str | None = None,
    purpose: str | None = None,
    config_path: str | Path | None = None,
) -> dict:
    """Return the generator configured for ``role``.

    ``purpose`` picks a model inside a role that has several (dialogue, sfx,
    score). A matching ``overrides`` entry replaces the role default. The
    most specific match wins. The returned dict is a copy.
    """
    config = load_model_routing(config_path)
    roles = config["roles"]
    if role not in roles:
        known = ", ".join(sorted(roles))
        raise ModelRoutingError(
            f"No model configured for role '{role}'. Configured roles: {known}. "
            "Add the role to config/model-routing.json."
        )

    chosen = dict(roles[role])
    purposes = chosen.get("purposes") or {}
    if purpose:
        if purpose not in purposes:
            available = ", ".join(sorted(purposes)) or "(none)"
            raise ModelRoutingError(
                f"Role '{role}' has no model for purpose '{purpose}'. "
                f"Configured purposes: {available}."
            )
        chosen["model"] = purposes[purpose]
        chosen["purpose"] = purpose

    winner = None
    winner_rank = -1
    for override in config.get("overrides") or []:
        if override.get("role") != role:
            continue
        if not _override_matches(override, scene=scene, shot=shot, purpose=purpose):
            continue
        # Equal specificity: the later entry in the file wins.
        rank = _specificity(override)
        if rank >= winner_rank:
            winner = override
            winner_rank = rank

    if winner:
        for key in ("model", "provider", "scene", "shot", "purpose"):
            if key in winner:
                chosen[key] = winner[key]
        chosen["override"] = True
    return chosen
