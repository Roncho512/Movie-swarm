"""Choose the picture model for one test shot, and price that one shot.

Precedence is ``--model``, then ``--tier``, then the film's ``budget.json``
tier for the stage, then ``config/model-routing.json``. The tier names in
that file match the budget rate card.

A model with no provider endpoint is not replaced. The caller refuses the
live call and names the wired choices. Switching to a cheaper wired model
on its own would bill a different model than the one the budget named.
"""

from __future__ import annotations

from decimal import Decimal

from movie_swarm.budget import load_film_budget
from movie_swarm.models import ModelRoutingError, load_model_routing, resolve_model
from movie_swarm.money import as_money, money_number
from movie_swarm.rates import generator_rate, load_rate_card


TIERS = ("good", "better", "best")
PICTURE_STAGE = "production"


class ShotModelError(Exception):
    """The requested model or tier cannot be used. Nothing was sent."""


def resolve_shot_model(
    production_dir,
    *,
    model: str | None = None,
    tier: str | None = None,
    shot_id: str | None = None,
    scene: str | None = None,
    purpose: str = "preview",
    routing_path=None,
    rates_path=None,
    stage: str = PICTURE_STAGE,
) -> dict:
    """Return the picture model for this shot. Does not call a provider."""
    routing = load_model_routing(routing_path)
    role = (routing.get("roles") or {}).get(stage)
    if not isinstance(role, dict):
        raise ShotModelError(f"config/model-routing.json has no {stage} role.")
    tiers = role.get("tiers") or {}
    if not isinstance(tiers, dict):
        tiers = {}
    card = load_rate_card(rates_path)
    requested_model = (model or "").strip() or None
    requested_tier = (tier or "").strip() or None
    _check_flags(requested_model, requested_tier, tiers, card, stage)

    note = ""
    provider_hint = role.get("provider")
    if requested_model:
        chosen = requested_model
        source = "model"
        chosen_tier = _tier_for(tiers, chosen)
        if requested_tier and tiers.get(requested_tier) != chosen:
            note = f"--model {chosen} overrides --tier {requested_tier}."
            chosen_tier = _tier_for(tiers, chosen)
        elif requested_tier:
            chosen_tier = requested_tier
    elif requested_tier:
        chosen = str(tiers[requested_tier])
        chosen_tier = requested_tier
        source = "tier"
    else:
        budget_tier = _budget_tier(production_dir, stage)
        if budget_tier:
            if budget_tier not in TIERS:
                raise ShotModelError(
                    f"budget.json sets {stage} to {budget_tier}. A tier is good, better, or best."
                )
            if budget_tier not in tiers:
                raise ShotModelError(
                    f"config/model-routing.json has no {stage} model for tier {budget_tier}."
                )
            chosen = str(tiers[budget_tier])
            chosen_tier = budget_tier
            source = "budget"
        else:
            try:
                resolved = resolve_model(
                    stage,
                    purpose=purpose,
                    scene=scene,
                    shot=shot_id,
                    config_path=routing_path,
                )
            except ModelRoutingError as exc:
                raise ShotModelError(str(exc)) from exc
            chosen = str(resolved.get("model") or "")
            chosen_tier = _tier_for(tiers, chosen)
            source = "routing"
            provider_hint = resolved.get("provider") or provider_hint

    row = generator_rate(card, chosen) if chosen else None
    if row is None:
        raise ShotModelError(
            f"No rate is published for {chosen or 'the routed model'}. Nothing was sent."
        )
    provider = str(row.get("provider") or provider_hint or "fal.ai")
    resolution = str(row.get("resolution") or "unset")
    note = _resolution_note(production_dir, resolution, note)
    return {
        "model": chosen,
        "tier": chosen_tier,
        "provider": provider,
        "resolution": resolution,
        "source": source,
        "wired": bool(row.get("endpoint")),
        "endpoint": row.get("endpoint") or None,
        "note": note,
    }


def format_shot_quote(producer, shot: dict, choice: dict, rates_path=None) -> str:
    """One shot's model, price, and the money still left. Nothing is spent."""
    from movie_swarm.continuity import enforce_prompt, load_prop_lock
    from movie_swarm.generation import _pass_cost
    from movie_swarm.references import prepare_references, quote_lines

    card = load_rate_card(rates_path)
    lock = load_prop_lock(producer.production_dir)
    enforced = enforce_prompt(shot.get("prompt") or "", shot.get("props") or [], lock)
    row = generator_rate(card, choice["model"])
    prepared = prepare_references(producer.production_dir, shot, enforced.prompt, row)
    priced = _pass_cost(shot, choice["model"], card, per_second=prepared.per_second)
    duration = shot.get("duration_seconds")
    if priced["priced"]:
        cost = f"${money_number(priced['usd']):.4f}"
    else:
        cost = "unknown"
    duration_part = f"duration {_duration_text(duration)}"
    pieces = priced["pieces"] if priced["priced"] else []
    if len(pieces) == 1 and duration is not None and as_money(pieces[0]) != as_money(duration):
        duration_part += f" (sent as {_duration_text(pieces[0])})"
    elif len(pieces) > 1:
        shown = " and ".join(_duration_text(piece) for piece in pieces)
        duration_part += f" (sent as {shown})"
    tier = choice.get("tier") or "unset"
    line = (
        f"Shot {shot.get('shot_id')}: model {choice['model']}, tier {tier}, "
        f"provider {choice['provider']}, resolution {choice['resolution']}, "
        f"{duration_part}, estimated cost {cost}."
    )
    stage_left, film_left = remaining_money(producer, PICTURE_STAGE)
    parts = [
        line,
        f"Production line remaining: {stage_left}. Film remaining: {film_left}.",
    ]
    if choice.get("note"):
        parts.append(str(choice["note"]))
    parts.extend(quote_lines(prepared))
    return "\n".join(parts)


def remaining_money(producer, stage: str) -> tuple[str, str]:
    """Stage line left, then the film left. ``not locked`` when there is no line yet."""
    from movie_swarm.budget import lines_for_check, load_film_budget

    spent = as_money(producer.run.data["cost_usd"])
    cap = producer._film_cap()
    film_left = cap - spent
    if film_left < 0:
        film_left = as_money(0)
    film_text = f"${money_number(film_left):.2f}"
    stage_spent = as_money(producer.stage_spent(stage))
    ceiling = None
    if load_film_budget(producer.production_dir) is not None:
        ceiling = as_money((lines_for_check(producer.production_dir) or {}).get(stage, 0))
    elif producer.record["stage_allocations"]["status"] == "approved":
        ceiling = as_money((producer.record["stage_allocations"]["split"] or {}).get(stage, 0))
    if ceiling is None:
        return "not locked", film_text
    left = ceiling - stage_spent
    if left < 0:
        left = as_money(0)
    return f"${money_number(left):.2f}", film_text


def unwired_note(model: str, rates_path=None, routing_path=None) -> str:
    """Say the model has no endpoint, and name the wired picture models."""
    card = load_rate_card(rates_path)
    tiers: dict = {}
    try:
        routing = load_model_routing(routing_path)
        raw = (routing.get("roles") or {}).get(PICTURE_STAGE, {}).get("tiers") or {}
        if isinstance(raw, dict):
            tiers = raw
    except (OSError, ModelRoutingError, KeyError, TypeError):
        tiers = {}
    wired = [
        row for row in card.get("generators") or []
        if isinstance(row, dict) and row.get("endpoint") and row.get("model")
    ]
    wired.sort(key=lambda row: as_money(row.get("usd_per_second") or 0))
    if not wired:
        choices = "The rate card has no picture model with an endpoint."
    else:
        bits = []
        for row in wired:
            name = str(row["model"])
            tier = _tier_for(tiers, name)
            flag = f"--model {name}"
            if tier:
                flag += f" or --tier {tier}"
            label = row.get("label") or name
            bits.append(f"{label} ({flag})")
        choices = "Wired picture models: " + "; ".join(bits) + "."
    return (
        f"No provider endpoint is configured for {model or '(unset)'}. Nothing was sent. {choices}"
    )


def wired_model_ids(rates_path=None) -> list[str]:
    """Picture models that name an endpoint, cheapest first."""
    card = load_rate_card(rates_path)
    rows = [
        row for row in card.get("generators") or []
        if isinstance(row, dict) and row.get("endpoint") and row.get("model")
    ]
    rows.sort(key=lambda row: as_money(row.get("usd_per_second") or 0))
    return [str(row["model"]) for row in rows]


def _check_flags(model: str | None, tier: str | None, tiers: dict, card: dict, stage: str) -> None:
    if tier and tier not in TIERS:
        raise ShotModelError("A tier is good, better, or best.")
    if tier and tier not in tiers:
        raise ShotModelError(f"config/model-routing.json has no {stage} model for tier {tier}.")
    if model and generator_rate(card, model) is None:
        known = ", ".join(sorted((card.get("by_model") or {})))
        raise ShotModelError(f"{model} is not on the rate card. Known models: {known}.")
    if tier and generator_rate(card, str(tiers.get(tier) or "")) is None:
        raise ShotModelError(
            f"The {tier} tier names {tiers.get(tier)}, which is not on the rate card."
        )


def _budget_tier(production_dir, stage: str) -> str | None:
    budget = load_film_budget(production_dir)
    if not budget:
        return None
    value = str((budget.get("tiers") or {}).get(stage) or "").strip()
    return value or None


def _tier_for(tiers: dict, model: str) -> str | None:
    for name, value in tiers.items():
        if value == model:
            return str(name)
    return None


def _resolution_note(production_dir, resolution: str, note: str) -> str:
    budget = load_film_budget(production_dir)
    if not budget:
        return note
    asked = str(budget.get("production_resolution") or "").strip()
    if not asked or asked == resolution or resolution == "unset":
        return note
    extra = (
        f"The film budget asks for {asked}. "
        f"This estimate uses the {resolution} rate on the generation rate card."
    )
    return (note + " " + extra).strip()


def _duration_text(value) -> str:
    if value is None:
        return "unset"
    try:
        number = as_money(value)
    except (ValueError, TypeError):
        return "unset"
    if number == number.to_integral():
        shown = str(int(number))
    else:
        shown = format(number.normalize(), "f")
    unit = "second" if number == Decimal("1") else "seconds"
    return f"{shown} {unit}"
