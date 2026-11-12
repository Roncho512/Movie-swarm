"""One film budget and one calculator.

A production may keep ``budget.json``. Line shares are percentages of that
total. When the trailer is on, Marketing and Distribution takes its share and
the other lines scale down so the dollars still equal the budget. Contingency
is held back inside the budget. Retakes and tier upgrades draw on it after a
line is spent.

A film with no budget file is not given this math. The run keeps the cap in
``config/gates.json`` and the locked split, which is today's behavior.

The 10 percent marketing share and the 10 percent contingency share are the
proposed defaults for a budget this command writes. They are not applied to a
film that has no budget file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from movie_swarm.duration import billed_runtime
from movie_swarm.gates import budget_cap_usd
from movie_swarm.handoff import read_handoff, write_handoff
from movie_swarm.money import as_money, money_number
from movie_swarm.paths import config_dir


MARKETING_STAGE = "marketing-distribution"
DEFAULT_TOTAL = 500
PROPOSED_MARKETING_PERCENT = 10
PROPOSED_CONTINGENCY_PERCENT = 10
DEFAULT_TAKES = 2
DEFAULT_FIX_RATE = 1
DEFAULT_TIER = "good"

# The locked $500 split, as percentages. At $500 with no trailer and no
# contingency these become the current dollar ceilings.
DEFAULT_SHARES = (
    ("production", 54),
    ("sound-designer", 11),
    ("fix-loop", 10),
    ("qa", 9),
    ("art-director", 5),
    ("director", 4),
    ("editor", 3),
    ("cinematographer", 2),
    ("screenwriter", 1),
    ("line-producer", 1),
)

LINE_ORDER = tuple(name for name, _share in DEFAULT_SHARES)
TIERS = ("good", "better", "best")


class BudgetError(Exception):
    """The budget cannot be read or written. The message says why."""


@dataclass
class BudgetMath:
    """Dollar ceilings for one film budget."""

    total: Decimal
    lines: dict[str, Decimal]
    marketing: Decimal
    contingency: Decimal
    trailer_on: bool

    def spendable(self) -> dict[str, Decimal]:
        rows = dict(self.lines)
        if self.trailer_on:
            rows[MARKETING_STAGE] = self.marketing
        return rows


def budget_path(production_dir: str | Path) -> Path:
    return Path(production_dir) / "budget.json"


def rate_card_path() -> Path:
    return config_dir() / "rate-card.json"


def load_rate_card(path: str | Path | None = None) -> dict:
    document = Path(path) if path else rate_card_path()
    try:
        data = json.loads(document.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BudgetError(f"The rate card could not be read. {exc}") from exc
    if not isinstance(data, dict):
        raise BudgetError("The rate card must be a JSON object.")
    return data


def load_film_budget(production_dir: str | Path) -> dict | None:
    """The film's budget file, or None when the film does not have one."""
    path = budget_path(production_dir)
    if not path.is_file():
        return None
    return read_handoff(path, schema="film-budget")


def default_share_map() -> dict[str, float]:
    return {name: float(share) for name, share in DEFAULT_SHARES}


def fallback_document(total_usd: float | None = None) -> dict:
    """The budget a film uses when it has no budget file.

    Contingency is 0 and the trailer is off, so the lines match today's split.
    """
    total = DEFAULT_TOTAL if total_usd is None else total_usd
    return {
        "version": "1.0.0",
        "total_usd": money_number(total),
        "currency": "USD",
        "line_shares": default_share_map(),
        "contingency_share": 0,
        "trailer_on": False,
        "marketing_share": 0,
        "tiers": {name: DEFAULT_TIER for name in LINE_ORDER},
        "production_resolution": "720p",
        "note": "No budget file. This is the $500 split with no trailer and no contingency.",
    }


def proposed_document(
    total_usd: float,
    *,
    trailer_on: bool = False,
    contingency_percent: float = PROPOSED_CONTINGENCY_PERCENT,
    marketing_percent: float = PROPOSED_MARKETING_PERCENT,
    tiers: dict | None = None,
    production_resolution: str = "720p",
    note: str = "",
) -> dict:
    """A new budget. Marketing is 10 percent and contingency is 10 percent unless told otherwise."""
    chosen = {name: DEFAULT_TIER for name in LINE_ORDER}
    for name, tier in (tiers or {}).items():
        if name not in chosen and name != MARKETING_STAGE:
            raise BudgetError(f"{name} is not a budget line.")
        if tier not in TIERS:
            raise BudgetError(f"A tier is good, better, or best. Got {tier}.")
        if name in chosen:
            chosen[name] = tier
    if production_resolution not in {"720p", "1080p"}:
        raise BudgetError("Picture resolution is 720p or 1080p.")
    document = {
        "version": "1.0.0",
        "total_usd": money_number(total_usd),
        "currency": "USD",
        "line_shares": default_share_map(),
        "contingency_share": money_number(contingency_percent),
        "trailer_on": bool(trailer_on),
        "marketing_share": money_number(marketing_percent),
        "tiers": chosen,
        "production_resolution": production_resolution,
        "note": note.strip()
        or (
            "Line shares match the locked split. "
            "When the trailer is on, Marketing and Distribution takes its share and the other lines scale down. "
            "Contingency is held back inside the budget. "
            "The 10 percent marketing share and the 10 percent contingency share are proposals."
        ),
    }
    compute(document)
    return document


def write_film_budget(production_dir: str | Path, document: dict) -> Path:
    path = budget_path(production_dir)
    compute(document)
    write_handoff(path, document, schema="film-budget")
    return path


def compute(document: dict) -> BudgetMath:
    """Turn percentages into dollar ceilings.

    Marketing, when the trailer is on, is a percent of the film budget. Every
    other line is multiplied by the rest, so the lines plus marketing equal
    the budget. Contingency is then held back from every line, including
    marketing. The spendable lines plus the reserve equal the budget.

    With the trailer off and contingency at 0, each line is its percentage of
    the budget. At $500 that is the locked split.
    """
    try:
        total = as_money(document["total_usd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BudgetError(f"The film budget needs a total. {exc}") from exc
    if total <= 0:
        raise BudgetError("The film budget has to be more than zero.")
    shares = document.get("line_shares") or {}
    if not isinstance(shares, dict):
        raise BudgetError("Line shares must be an object of percentages.")
    missing = [name for name in LINE_ORDER if name not in shares]
    if missing:
        raise BudgetError("The budget is missing line shares: " + ", ".join(missing) + ".")
    try:
        percents = {name: as_money(shares[name]) for name in LINE_ORDER}
    except (TypeError, ValueError) as exc:
        raise BudgetError(f"A line share is not a percentage. {exc}") from exc
    if any(value < 0 or value > 100 for value in percents.values()):
        raise BudgetError("A line share is a percentage from 0 to 100.")
    share_total = sum(percents.values(), as_money(0))
    if share_total != as_money(100):
        raise BudgetError(
            f"Line shares add up to {money_number(share_total)}, not 100. "
            "Marketing and contingency are separate fields."
        )
    try:
        contingency_percent = as_money(document.get("contingency_share") or 0)
        marketing_percent = as_money(document.get("marketing_share") or 0)
    except (TypeError, ValueError) as exc:
        raise BudgetError(f"A budget share is not a percentage. {exc}") from exc
    if contingency_percent < 0 or contingency_percent > 100:
        raise BudgetError("Contingency is a percentage from 0 to 100.")
    if marketing_percent < 0 or marketing_percent > 100:
        raise BudgetError("The marketing share is a percentage from 0 to 100.")
    trailer_on = bool(document.get("trailer_on"))
    if trailer_on and marketing_percent >= 100:
        raise BudgetError("Marketing cannot take the whole budget. Leave room for the other lines.")

    marketing_gross = as_money(total * marketing_percent / as_money(100)) if trailer_on else as_money(0)
    working = total - marketing_gross
    scale = as_money(1) - (marketing_percent / as_money(100)) if trailer_on else as_money(1)
    gross: dict[str, Decimal] = {}
    running = as_money(0)
    names = list(LINE_ORDER)
    for name in names[:-1]:
        amount = as_money(total * percents[name] / as_money(100) * scale)
        gross[name] = amount
        running += amount
    gross[names[-1]] = as_money(working - running)

    keep = as_money(1) - (contingency_percent / as_money(100))
    lines = {name: as_money(amount * keep) for name, amount in gross.items()}
    marketing = as_money(marketing_gross * keep)
    contingency = as_money(total * contingency_percent / as_money(100))
    drift = total - sum(lines.values(), as_money(0)) - marketing - contingency
    if drift != 0:
        if contingency_percent > 0:
            contingency = as_money(contingency + drift)
        elif trailer_on:
            marketing = as_money(marketing + drift)
        else:
            lines[names[-1]] = as_money(lines[names[-1]] + drift)
    return BudgetMath(
        total=total,
        lines=lines,
        marketing=marketing,
        contingency=contingency,
        trailer_on=trailer_on,
    )


def lines_for_check(production_dir: str | Path) -> dict[str, float] | None:
    """Spendable line dollars from budget.json, or None when there is no file."""
    document = load_film_budget(production_dir)
    if document is None:
        return None
    math = compute(document)
    return {name: money_number(amount) for name, amount in math.spendable().items()}


def file_total(production_dir: str | Path) -> float | None:
    document = load_film_budget(production_dir)
    if document is None:
        return None
    return money_number(document["total_usd"])


def contingency_pool(document: dict) -> Decimal:
    return compute(document).contingency


def contingency_used(record: dict) -> Decimal:
    total = as_money(0)
    for entry in record.get("ledger") or []:
        if entry.get("kind") == "dry-run":
            continue
        amount = as_money(entry.get("contingency_usd") or 0)
        if entry.get("kind") == "release":
            total -= amount
        else:
            total += amount
    if total < 0:
        return as_money(0)
    return total


def contingency_left(document: dict, record: dict) -> Decimal:
    left = contingency_pool(document) - contingency_used(record)
    if left < 0:
        return as_money(0)
    return left


def trailer_enabled(production_dir: str | Path) -> bool:
    """True only when this film's budget turns the trailer on."""
    document = load_film_budget(production_dir)
    return bool(document and document.get("trailer_on"))


def position_word(spent, ceiling) -> tuple[str, Decimal]:
    """``under``, ``on``, or ``over``, and the unsigned gap."""
    gap = as_money(spent) - as_money(ceiling)
    if gap > 0:
        return "over", gap
    if gap < 0:
        return "under", as_money(0) - gap
    return "on", as_money(0)


def report_from_record(production_dir: str | Path, record: dict, spent_total: float) -> list[str]:
    document = load_film_budget(production_dir)
    if document is None:
        return []
    spent_by_stage: dict[str, Decimal] = {}
    overages = as_money(0)
    for entry in record.get("ledger") or []:
        if entry.get("kind") == "dry-run":
            overages += as_money(entry.get("overage_usd") or 0)
            continue
        sign = -1 if entry.get("kind") == "release" else 1
        stage = entry.get("stage")
        spent_by_stage[stage] = spent_by_stage.get(stage, as_money(0)) + (
            sign * as_money(entry.get("amount_usd") or 0)
        )
        overages += sign * as_money(entry.get("overage_usd") or 0)
    math = compute(document)
    word, gap = position_word(spent_total, math.total)
    if word == "on":
        head = f"Film budget: ${money_number(math.total):.2f}. On budget."
    else:
        head = (
            f"Film budget: ${money_number(math.total):.2f}. "
            f"{word.capitalize()} budget by ${money_number(gap):.2f}."
        )
    left = contingency_left(document, record)
    lines = [
        head,
        f"Contingency left: ${money_number(left):.2f} of ${money_number(math.contingency):.2f}.",
    ]
    seen = set()
    for name, ceiling in math.spendable().items():
        seen.add(name)
        spent = spent_by_stage.get(name, as_money(0))
        place, distance = position_word(spent, ceiling)
        if place == "on":
            lines.append(f"  {name}: ${money_number(spent):.2f} of ${money_number(ceiling):.2f}. On the line.")
        else:
            lines.append(
                f"  {name}: ${money_number(spent):.2f} of ${money_number(ceiling):.2f}. "
                f"{place.capitalize()} the line by ${money_number(distance):.2f}."
            )
    if overages > 0:
        lines.append(f"Approved overages on the ledger: ${money_number(overages):.2f}.")
    lines.append("Approving an overage does not change budget.json.")
    return lines


def read_estimate_inputs(production_dir: str | Path) -> dict:
    """Runtime, shots, takes, and fix rate from the brief, then the treatment.

    Missing numbers use a documented default and say so.
    """
    folder = Path(production_dir)
    brief = _read_json(folder / "production-brief.json")
    treatment = _read_json(folder / "treatment" / "treatment.json")
    notes: list[str] = []
    runtime = _number(brief.get("target_runtime_seconds"))
    if runtime is None:
        runtime = _number((brief.get("deliverables") or {}).get("target_runtime_seconds") if isinstance(brief.get("deliverables"), dict) else None)
    if runtime is None:
        runtime = _parse_length(str((treatment.get("deliverables") or {}).get("length") or ""))
        if runtime is not None:
            notes.append("Runtime comes from the treatment length.")
    if runtime is None:
        scenes = treatment.get("scenes") or []
        total = as_money(0)
        counted = False
        for scene in scenes:
            if isinstance(scene, dict) and scene.get("approximate_duration_seconds") is not None:
                try:
                    total += as_money(scene["approximate_duration_seconds"])
                    counted = True
                except (TypeError, ValueError):
                    continue
        if counted and total > 0:
            runtime = float(total)
            notes.append("Runtime is the sum of the treatment scene lengths.")
    if runtime is None:
        runtime = 60.0
        notes.append("No runtime was named. The estimate uses 60 seconds.")
    shots = _number(brief.get("shot_count"))
    if shots is None:
        shot_list = _read_json(folder / "storyboard" / "shot-list.json")
        rows = shot_list.get("shots") if isinstance(shot_list.get("shots"), list) else None
        if rows:
            shots = float(len(rows))
            notes.append("Shot count comes from the storyboard shot list.")
    if shots is None:
        scenes = treatment.get("scenes") or []
        if isinstance(scenes, list) and scenes:
            shots = float(len(scenes))
            notes.append("No shot count was named. The estimate uses one shot per treatment scene.")
    if shots is None or shots <= 0:
        shots = 1.0
        notes.append("No shots were named. The estimate uses 1 shot.")
    takes = _number(brief.get("takes_per_shot"))
    if takes is None:
        takes = float(DEFAULT_TAKES)
        notes.append(f"No take count was named. The estimate uses {DEFAULT_TAKES} takes per shot.")
    fix_rate = _number(brief.get("fix_rate"))
    if fix_rate is None:
        fix_rate = float(DEFAULT_FIX_RATE)
        notes.append(
            "No fix rate was named. The estimate uses 1, one extra preview for every shot, "
            "counted on the fix-loop line."
        )
    trailer = brief.get("trailer_on")
    if trailer is None:
        trailer = False
    return {
        "runtime_seconds": float(runtime),
        "shots": float(shots),
        "takes_per_shot": float(takes),
        "fix_rate": float(fix_rate),
        "trailer_on": bool(trailer),
        "notes": notes,
    }


def estimate_film(
    production_dir: str | Path,
    document: dict,
    inputs: dict | None = None,
    rates: dict | None = None,
) -> dict:
    """Price a film from its brief and the tiers on the budget. Unknown rates stay unknown."""
    folder = Path(production_dir)
    inputs = inputs or read_estimate_inputs(folder)
    rates = rates or load_rate_card()
    math = compute(document)
    tiers = document.get("tiers") or {}
    resolution = document.get("production_resolution") or "720p"
    runtime = as_money(inputs["runtime_seconds"])
    takes = as_money(inputs["takes_per_shot"])
    fix_rate = as_money(inputs["fix_rate"])
    picture = _picture_rate(rates, str(tiers.get("production") or DEFAULT_TIER), resolution)
    rows = []
    for name, ceiling in math.spendable().items():
        tier = str(tiers.get(name) or DEFAULT_TIER)
        estimate, status, detail = _line_estimate(
            name,
            tier,
            runtime,
            takes,
            fix_rate,
            picture,
            rates,
            inputs,
        )
        place = None
        distance = None
        if estimate is not None:
            place, distance = position_word(estimate, ceiling)
        rows.append(
            {
                "stage": name,
                "tier": tier,
                "ceiling_usd": money_number(ceiling),
                "estimate_usd": None if estimate is None else money_number(estimate),
                "rate_status": status,
                "detail": detail,
                "position": place,
                "gap_usd": None if distance is None else money_number(distance),
            }
        )
    return {
        "inputs": {
            "runtime_seconds": money_number(runtime),
            "shots": money_number(inputs["shots"]),
            "takes_per_shot": money_number(takes),
            "fix_rate": money_number(fix_rate),
            "trailer_on": math.trailer_on,
            "notes": list(inputs.get("notes") or []),
        },
        "total_usd": money_number(math.total),
        "contingency_usd": money_number(math.contingency),
        "lines": rows,
    }


def format_estimate(production_dir: str | Path, estimate: dict, record: dict | None, spent_total: float) -> str:
    lines = [
        f"Budget: ${estimate['total_usd']:.2f}",
        (
            f"Runtime {estimate['inputs']['runtime_seconds']:.2f}s, "
            f"{estimate['inputs']['shots']:.0f} shots, "
            f"{estimate['inputs']['takes_per_shot']:.0f} takes, "
            f"fix rate {estimate['inputs']['fix_rate']:.2f}."
        ),
    ]
    for note in estimate["inputs"]["notes"]:
        lines.append(note)
    if estimate["inputs"]["trailer_on"]:
        lines.append("Trailer: on. Marketing and Distribution is in the budget.")
    else:
        lines.append("Trailer: off. Marketing and Distribution is not charged.")
    lines.append(f"Contingency reserve: ${estimate['contingency_usd']:.2f}.")
    on_disk = load_film_budget(production_dir)
    if record is not None and on_disk is not None:
        left = contingency_left(on_disk, record)
        lines.append(f"Contingency left: ${money_number(left):.2f}.")
        lines.extend(report_from_record(production_dir, record, spent_total)[:1])
    lines.append("")
    lines.append("Line | tier | ceiling | estimate | under / over")
    for row in estimate["lines"]:
        estimated = "unknown" if row["estimate_usd"] is None else f"${row['estimate_usd']:.2f}"
        if row["position"] is None:
            gap = "no estimate"
        elif row["position"] == "on":
            gap = "on the line"
        else:
            gap = f"{row['position']} by ${row['gap_usd']:.2f}"
        lines.append(
            f"{row['stage']} | {row['tier']} | ${row['ceiling_usd']:.2f} | {estimated} | {gap}"
        )
        if row["detail"]:
            lines.append(f"  {row['detail']}")
    word, gap = position_word(spent_total, estimate["total_usd"])
    lines.append("")
    if word == "on":
        lines.append(f"Spent to date: ${spent_total:.2f}. On budget.")
    else:
        lines.append(f"Spent to date: ${spent_total:.2f}. {word.capitalize()} budget by ${money_number(gap):.2f}.")
    return "\n".join(lines)


def set_tier(document: dict, stage: str, tier: str) -> dict:
    if stage not in LINE_ORDER:
        raise BudgetError(f"{stage} is not a stage on this budget.")
    if tier not in TIERS:
        raise BudgetError("A tier is good, better, or best.")
    updated = json.loads(json.dumps(document))
    updated.setdefault("tiers", {})[stage] = tier
    return updated


def stage_estimate_usd(document: dict, stage: str, inputs: dict, rates: dict | None = None) -> tuple[Decimal | None, str]:
    """The estimate for one stage at the tiers currently on the document."""
    rates = rates or load_rate_card()
    resolution = document.get("production_resolution") or "720p"
    picture = _picture_rate(rates, str((document.get("tiers") or {}).get("production") or DEFAULT_TIER), resolution)
    estimate, status, _detail = _line_estimate(
        stage,
        str((document.get("tiers") or {}).get(stage) or DEFAULT_TIER),
        as_money(inputs["runtime_seconds"]),
        as_money(inputs["takes_per_shot"]),
        as_money(inputs["fix_rate"]),
        picture,
        rates,
        inputs,
    )
    return estimate, status


def _line_estimate(name, tier, runtime, takes, fix_rate, picture, rates, inputs):
    if name == "production":
        if picture["usd_per_second"] is None:
            return None, picture["status"], picture["note"]
        billed, notes = billed_runtime(runtime, inputs.get("shots") or 1, picture)
        amount = as_money(billed * takes * picture["usd_per_second"])
        detail = picture["note"]
        if billed != runtime and notes:
            detail = f"{detail} {notes[0]}".strip()
        return amount, picture["status"], detail
    if name == "fix-loop":
        if picture["usd_per_second"] is None:
            return None, picture["status"], "The fix-loop estimate uses the picture rate. " + picture["note"]
        billed, notes = billed_runtime(runtime, inputs.get("shots") or 1, picture)
        amount = as_money(billed * fix_rate * picture["usd_per_second"])
        detail = "One extra preview for each shot the fix rate counts. Priced at the production tier."
        if billed != runtime and notes:
            detail = f"{detail} {notes[0]}".strip()
        return amount, picture["status"], detail
    if name == "sound-designer":
        return _sound_estimate(rates, tier, runtime, inputs)
    if name == MARKETING_STAGE:
        return as_money(0), "known", "The trailer is cut from approved takes. This pass does not price a new shot."
    return None, "unknown", "This stage has no rate on the rate card. The estimate is unknown."


def _sound_estimate(rates: dict, tier: str, runtime: Decimal, inputs: dict):
    stage = (rates.get("stages") or {}).get("sound-designer") or {}
    row = ((stage.get("tiers") or {}).get(tier)) or ((stage.get("tiers") or {}).get("good")) or {}
    status = str(row.get("status") or "unknown")
    try:
        music = as_money(row["music_usd_per_minute"])
        sfx = as_money(row["sfx_usd_per_minute"])
    except (KeyError, TypeError, ValueError):
        return None, "unknown", "The rate card has no music or effects price for this tier."
    minutes = runtime / as_money(60)
    amount = as_money(minutes * music + minutes * sfx)
    note = (
        "Music and effects are estimated as the runtime. "
        "Speech is added only when the brief gives a character count. "
        + str(row.get("note") or "")
    )
    characters = _number(inputs.get("dialogue_characters"))
    if characters is not None and row.get("speech_usd_per_1k_chars") is not None:
        try:
            speech = as_money(row["speech_usd_per_1k_chars"])
        except (TypeError, ValueError):
            speech = None
        if speech is not None:
            amount = as_money(amount + (as_money(characters) / as_money(1000) * speech))
            note = "Speech uses the character count on the brief. " + note
    return amount, status, note.strip()


def _picture_rate(rates: dict, tier: str, resolution: str) -> dict:
    stage = (rates.get("stages") or {}).get("production") or {}
    if resolution == "1080p":
        row = stage.get("top_option") or {}
        return _rate_row(row, "The 1080p top option has no price on the rate card.")
    row = ((stage.get("tiers") or {}).get(tier)) or {}
    return _rate_row(row, f"The {tier} picture tier has no price on the rate card.")


def _rate_row(row: dict, missing: str) -> dict:
    status = str(row.get("status") or "unknown")
    note = str(row.get("note") or "")
    try:
        price = as_money(row["usd_per_second"])
    except (KeyError, TypeError, ValueError):
        return {"usd_per_second": None, "status": "unknown", "note": missing}
    if status != "known":
        note = note or "This price is prefilled. The repo has not verified it, so the rate stays unknown."
    priced = {"usd_per_second": price, "status": status, "note": note}
    for key in (
        "min_seconds",
        "max_seconds",
        "whole_seconds",
        "duration_rule_status",
        "label",
        "model",
    ):
        if key in row:
            priced[key] = row[key]
    return priced


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _parse_length(text: str) -> float | None:
    cleaned = text.strip().lower()
    if not cleaned:
        return None
    minutes = re.search(r"(\d+(?:\.\d+)?)\s*min", cleaned)
    if minutes:
        return float(minutes.group(1)) * 60
    seconds = re.search(r"(\d+(?:\.\d+)?)\s*sec", cleaned)
    if seconds:
        return float(seconds.group(1))
    return None


def fallback_cap(config_path: str | Path | None = None) -> float:
    return budget_cap_usd(config_path)
