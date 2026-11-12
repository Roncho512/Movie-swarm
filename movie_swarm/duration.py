"""Turn a shot length into the duration a picture model will accept.

The numbers live on the generator row. A verified row follows the page it
cites. A row that is not verified is not given a tighter rule than the one
already written down.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from movie_swarm.money import as_money


def seconds_text(value) -> str:
    number = as_money(value)
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")


def clip_lengths(duration, row: dict | None) -> tuple[list[Decimal], list[str]]:
    """The lengths one quote uses. Each length is a value the row allows."""
    row = row or {}
    original = as_money(duration)
    seconds = original
    notes: list[str] = []
    floor = _bound(row.get("min_seconds"))
    cap = _bound(row.get("max_seconds"))
    whole = bool(row.get("whole_seconds"))
    label = row.get("label") or row.get("model") or "This model"
    status = str(row.get("duration_rule_status") or "")
    if whole:
        seconds = original.to_integral_value(rounding=ROUND_CEILING)
    if floor is not None and seconds < floor:
        notes.append(_minimum_note(original, seconds, floor, cap, label, status))
        return [floor], notes
    if cap is None or seconds <= cap:
        if whole and seconds != original:
            notes.append(
                f"The shot is {seconds_text(original)} seconds. {label} accepts whole seconds, "
                f"so the request uses {seconds_text(seconds)}. {_tail(status)}"
            )
        elif floor is None and cap is None:
            notes.append(
                f"The quote uses the shot length for {label}. "
                "This card does not apply a length limit for that generator."
            )
        return [seconds], notes
    pieces: list[Decimal] = []
    remaining = seconds
    while remaining > 0:
        piece = cap if remaining > cap else remaining
        if piece <= 0:
            break
        if floor is not None and piece < floor:
            notes.append(
                f"The last piece was shorter than {seconds_text(floor)} seconds, "
                f"so it is quoted at the published minimum. {_tail(status)}"
            )
            piece = floor
        pieces.append(piece)
        remaining = as_money(remaining - piece)
        if len(pieces) > 100:
            break
    notes.append(
        f"The shot is longer than {seconds_text(cap)} seconds, "
        f"so it is quoted as {len(pieces)} clips. {_tail(status)}"
    )
    return pieces, notes


def billed_runtime(runtime, shots, row: dict | None) -> tuple[Decimal, list[str]]:
    """Bill a film from its runtime and shot count, using the same per-shot rule.

    Each shot is treated as an even share of the runtime, then rounded the way
    one request would round that share. A short share is not priced below the
    model's minimum.
    """
    count = as_money(shots if shots else 1)
    if count <= 0:
        count = as_money(1)
    each = as_money(as_money(runtime) / count)
    lengths, notes = clip_lengths(each, row)
    per_shot = sum((as_money(piece) for piece in lengths), as_money(0))
    return as_money(per_shot * count), notes


def request_value(seconds, row: dict | None):
    """The duration field for one request. Seedance wants a string. Kling wants an integer."""
    number = as_money(seconds)
    if row and row.get("duration_format") == "integer":
        return int(number.to_integral_value())
    if row and (row.get("whole_seconds") or row.get("duration_format") == "string"):
        return str(int(number.to_integral_value()))
    return seconds_text(number)


def _bound(value):
    if value in (None, ""):
        return None
    return as_money(value)


def _tail(status: str) -> str:
    if status == "verified":
        return "This follows the published duration rule."
    if status == "unverified":
        return "This duration rule is unverified."
    return "This is an assumption."


def _minimum_note(original, seconds, floor, cap, label, status: str) -> str:
    if status == "verified" and cap is not None:
        return (
            f"The shot is {seconds_text(original)} seconds. {label} accepts a whole number from "
            f"{seconds_text(floor)} to {seconds_text(cap)}, so the request uses {seconds_text(floor)}. "
            f"{_tail(status)}"
        )
    if status == "verified":
        return (
            f"The shot is {seconds_text(original)} seconds. {label} accepts a minimum of "
            f"{seconds_text(floor)} seconds, so the request uses {seconds_text(floor)}. {_tail(status)}"
        )
    if status == "unverified":
        return (
            f"The shot is {seconds_text(original)} seconds. {label} is quoted at "
            f"{seconds_text(floor)} seconds. {_tail(status)}"
        )
    return (
        f"The shot is {seconds_text(seconds)} seconds. {label} publishes a minimum of "
        f"{seconds_text(floor)} seconds, so the quote uses {seconds_text(floor)}. {_tail(status)}"
    )
