"""Turn approved boards into a quote, and stop before a paid call.

A plan prices each shot and does not call a provider. A generate call
refuses to touch a client until the generation gate is open. The default
client still does not open a network connection.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from movie_swarm.continuity import enforce_prompt, load_prop_lock
from movie_swarm.dailies import review_dailies
from movie_swarm.duration import clip_lengths, seconds_text as _seconds_text
from movie_swarm.models import resolve_model
from movie_swarm.money import as_money, money_number
from movie_swarm.rates import generator_rate, load_rate_card, usd_per_second
from movie_swarm.references import prepare_references, quote_lines


class GenerationError(Exception):
    """The plan or the call cannot be built. The message says what is missing."""


class OfflineGenerationClient:
    """The client this build uses. It records nothing on a provider."""

    def generate(self, request: dict) -> dict:
        return {
            "status": "not-sent",
            "cost_usd": 0,
            "shot_id": request.get("shot_id"),
            "detail": "No live provider is connected. The call was not sent. No image or video was made.",
        }


def load_shots(production_dir: str | Path) -> tuple[list[dict], str]:
    """Read boards first, then a shot list. The shapes are whatever the files use."""
    folder = Path(production_dir)
    storyboard = folder / "storyboard" / "storyboard.json"
    if storyboard.is_file():
        frames = _read_json(storyboard).get("frames") or []
        if frames:
            shots = [_from_frame(frame) for frame in frames if isinstance(frame, dict)]
            _merge_shot_list(folder, shots)
            return shots, "storyboard/storyboard.json"
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = folder / relative
        if not path.is_file():
            continue
        data = _read_json(path)
        if data.get("superseded") is True:
            continue
        shots = data.get("shots") or []
        if shots:
            return [_from_shot(shot) for shot in shots if isinstance(shot, dict)], relative
    return [], ""


def build_generation_plan(
    production_dir: str | Path,
    *,
    allocations: dict | None = None,
    routing_path: str | Path | None = None,
    rates_path: str | Path | None = None,
) -> dict:
    """Price one production. The result is a quote. It is not a spend."""
    folder = Path(production_dir)
    card = load_rate_card(rates_path)
    shots, source = load_shots(folder)
    if not shots:
        raise GenerationError(
            "No boards and no shot list. The estimator needs storyboard/storyboard.json "
            "or a shot list, and it did not find either."
        )
    lock = load_prop_lock(folder)
    priced_shots = [
        _price_shot(shot, card, lock, routing_path=routing_path, folder=folder)
        for shot in shots
    ]
    picture = _sum(item["shot_usd"] for item in priced_shots)
    retake = _sum(item["retake_usd"] for item in priced_shots)
    stages = _stage_totals(picture, retake, allocations or {})
    return {
        "production_id": folder.name,
        "title": _title(folder),
        "source": source,
        "checked_on": card.get("checked_on") or "",
        "dry_run": True,
        "spent_usd": 0,
        "assumptions": list(card.get("assumptions") or []),
        "rates": [_public_rate(row) for row in card["generators"]],
        "shots": priced_shots,
        "picture_usd": money_number(picture),
        "retake_reserve_usd": money_number(retake),
        "fix_loop_reserve_usd": money_number(_fix_loop_reserve(allocations or {})),
        "stages": stages,
        "prop_lock": "loaded" if lock else "missing",
    }


def render_plan(plan: dict) -> str:
    """The quote in sentences, for a person to read before any money moves."""
    lines = [
        f"Generation plan for {plan['title']}",
        "",
        "This is a dry run. No image or video was requested, and no money was spent.",
        f"Rates were read on {plan['checked_on']}.",
        "",
        "Published rates:",
    ]
    for rate in plan["rates"]:
        lines.append(
            f"- {rate['label']}, {rate['resolution']}: ${rate['usd_per_second']} per second. "
            f"{rate['quote']} Source: {rate['source']} ({rate['source_date']})."
        )
    lines.extend(["", "Assumptions:"])
    for item in plan["assumptions"]:
        lines.append(f"- {item}")
    if plan["prop_lock"] == "missing":
        lines.append("- No prop file was found, so no locked phrase was added. That is a gap, not a guess about the props.")
    lines.extend(["", "Shots:"])
    for shot in plan["shots"]:
        lines.append(_shot_sentence(shot))
        if shot["added_phrases"]:
            joined = "; ".join(shot["added_phrases"])
            lines.append(f"  Locked phrase added because the prop is in frame: {joined}.")
        if shot["blocked"]:
            joined = "; ".join(shot["blocked"])
            lines.append(f"  This prompt would not be sent. It contains a forbidden phrase: {joined}.")
        for note in shot["notes"]:
            lines.append(f"  {note}")
    lines.extend(["", "Totals by stage, set against the locked split:"])
    for stage in plan["stages"]:
        lines.append(_stage_sentence(stage))
    lines.extend(
        [
            "",
            (
                f"Retake reserve: ${plan['retake_reserve_usd']:.2f}. "
                "Assumption: one extra preview of every priced shot. It is included in the production total above."
            ),
            (
                f"Fix-loop reserve: ${plan['fix_loop_reserve_usd']:.2f}. "
                "That figure is the locked fix-loop allocation when the split has one. "
                "This dry run does not price a fix call."
            ),
            "",
            "Nothing in this plan is a permission to spend. A paid call waits on the generation gate.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_plan(plan: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write the quote as sentences and as JSON. The folder is the caller's."""
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    text_path = folder / "generation-plan.md"
    data_path = folder / "generation-plan.json"
    text_path.write_text(render_plan(plan), encoding="utf-8")
    data_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return text_path, data_path


def generate_shots(
    production_dir: str | Path,
    *,
    client,
    gate_open: bool,
    routing_path: str | Path | None = None,
) -> dict:
    """Prepare prompts and, only when the gate is open, hand them to ``client``.

    A closed gate returns before ``client.generate`` is called. A blocked
    prompt, one that contains a forbidden phrase, is not handed over either.
    """
    folder = Path(production_dir)
    shots, source = load_shots(folder)
    if not gate_open:
        return {
            "status": "paused",
            "source": source,
            "called": False,
            "message": "The generation gate is closed. No provider was called.",
            "shots": [],
        }
    if client is None:
        client = OfflineGenerationClient()
    lock = load_prop_lock(folder)
    results = []
    called = False
    for shot in shots:
        enforced = enforce_prompt(shot["prompt"], shot["props"], lock)
        preview_model, _ = _resolve("preview", shot, routing_path)
        request = {
            "shot_id": shot["shot_id"],
            "prompt": enforced.prompt,
            "duration_seconds": shot["duration_seconds"],
            "model": preview_model,
            "props_in_frame": shot["props"],
        }
        images = [str(path) for path in shot.get("reference_images") or [] if str(path).strip()]
        if images:
            request["reference_images"] = images
        if enforced.blocked:
            results.append(
                {
                    "shot_id": shot["shot_id"],
                    "status": "blocked",
                    "called": False,
                    "prompt": enforced.prompt,
                    "blocked": enforced.blocked,
                    "review": review_dailies(
                        shot_id=shot["shot_id"],
                        prompt=enforced.prompt,
                        props_in_frame=shot["props"],
                        lock=lock,
                    ),
                }
            )
            continue
        response = client.generate(request)
        called = True
        results.append(
            {
                "shot_id": shot["shot_id"],
                "status": response.get("status") or "returned",
                "called": True,
                "prompt": enforced.prompt,
                "added_phrases": enforced.added,
                "blocked": [],
                "response": response,
                "review": review_dailies(
                    shot_id=shot["shot_id"],
                    prompt=enforced.prompt,
                    props_in_frame=shot["props"],
                    lock=lock,
                    clip_ref=response.get("clip_ref"),
                ),
            }
        )
    if called and all(item["status"] == "not-sent" for item in results):
        message = "No live provider is connected. The call was not sent. No image or video was made."
    elif called and any(item["status"] in {"refused", "failed", "generated", "replayed", "offline"} for item in results):
        message = " ".join(
            str((item.get("response") or {}).get("detail") or item["status"])
            for item in results
            if item["status"] in {"refused", "failed", "generated", "replayed", "offline"}
        )
    elif called:
        message = "The client was asked. This build's default client does not call a provider."
    elif results and all(item["status"] == "blocked" for item in results):
        message = "Every prompt was blocked by a locked phrase. No provider was called."
    else:
        message = "No shot was sent."
    return {
        "status": "dry-run",
        "source": source,
        "called": called,
        "message": message,
        "shots": results,
    }


def quote_preview_usd(shot: dict, routing_path=None) -> float | None:
    """The price of one preview of this shot. None when the model is not on the rate card.

    This is an estimate. It does not spend and it does not call a provider.
    """
    card = load_rate_card()
    model, _override = _resolve("preview", shot, routing_path)
    priced = _pass_cost(shot, model, card)
    if not priced["priced"]:
        return None
    return money_number(priced["usd"])


def run_picture(producer, call) -> str:
    """The Director's plan and generate commands. Neither one spends."""
    allocations = _locked_split(producer)
    if call.command == "plan":
        plan = build_generation_plan(
            call.production_dir,
            allocations=allocations,
        )
        text = render_plan(plan)
        if call.output_dir:
            text_path, _data_path = write_plan(plan, call.output_dir)
            return text + f"\nWrote {text_path}."
        return text
    if call.command == "generate":
        client = call.client
        if client is None and getattr(call, "live", False):
            from movie_swarm.providers import CallSettings, LiveGenerationClient

            client = LiveGenerationClient(
                producer,
                live=True,
                settings=CallSettings(price_override=getattr(call, "price_override", None)),
            )
        result = generate_shots(
            call.production_dir,
            client=client or OfflineGenerationClient(),
            gate_open=True,
        )
        return result["message"]
    raise GenerationError(f"The picture pipeline has no '{call.command}' command.")


def _price_shot(shot: dict, card: dict, lock: dict | None, *, routing_path, folder: Path) -> dict:
    enforced = enforce_prompt(shot["prompt"], shot["props"], lock)
    preview_model, preview_override = _resolve("preview", shot, routing_path)
    final_model, final_override = _resolve("final", shot, routing_path)
    preview_rate, preview_refs = _reference_rate(folder, shot, enforced.prompt, preview_model, card)
    if final_model == preview_model:
        final_rate, final_refs = preview_rate, preview_refs
    else:
        final_rate, final_refs = _reference_rate(folder, shot, enforced.prompt, final_model, card)
    preview = _pass_cost(shot, preview_model, card, per_second=preview_rate)
    final = _pass_cost(shot, final_model, card, per_second=final_rate)
    notes = list(preview["notes"]) + [note for note in final["notes"] if note not in preview["notes"]]
    for prepared in (preview_refs, final_refs):
        if prepared is None:
            continue
        for line in quote_lines(prepared):
            if line not in notes:
                notes.append(line)
        if final_refs is preview_refs:
            break
    priced = preview["priced"] and final["priced"]
    shot_usd = preview["usd"] + final["usd"] if priced else as_money(0)
    retake_usd = preview["usd"] if priced else as_money(0)
    if not priced:
        missing = preview_model if not preview["priced"] else final_model
        notes.append(f"No published rate is on the card for {missing}, so this shot is not priced.")
    return {
        "shot_id": shot["shot_id"],
        "scene_id": shot["scene_id"],
        "preview_model": preview_model,
        "final_model": final_model,
        "generator": _generator_label(preview_model, final_model, preview_override or final_override, card),
        "requested_seconds": shot["duration_seconds"],
        "billed_seconds": money_number(preview["billed"]) if preview["priced"] else None,
        "pieces": preview["pieces"],
        "takes_allowed": 2,
        "preview_usd": money_number(preview["usd"]) if preview["priced"] else None,
        "final_usd": money_number(final["usd"]) if final["priced"] else None,
        "shot_usd": money_number(shot_usd) if priced else None,
        "retake_usd": money_number(retake_usd) if preview["priced"] else None,
        "prompt": enforced.prompt,
        "added_phrases": enforced.added,
        "blocked": enforced.blocked,
        "notes": notes,
        "priced": priced,
    }


def _pass_cost(shot: dict, model: str, card: dict, *, per_second=None) -> dict:
    row = generator_rate(card, model)
    duration = shot["duration_seconds"]
    if row is None or duration is None:
        reason = "No clip length was given, so this shot is not priced." if duration is None else ""
        return {"priced": False, "usd": as_money(0), "billed": as_money(0), "pieces": [], "notes": [reason] if reason else []}
    lengths, notes = clip_lengths(duration, row)
    billed = _sum(lengths)
    rate = as_money(per_second) if per_second is not None else usd_per_second(row)
    cost = rate * billed
    return {
        "priced": True,
        "usd": as_money(cost),
        "billed": billed,
        "pieces": [money_number(piece) for piece in lengths],
        "notes": notes,
    }


def _resolve(purpose: str, shot: dict, routing_path) -> tuple[str, bool]:
    chosen = resolve_model(
        "production",
        purpose=purpose,
        scene=shot.get("scene_id") or None,
        shot=shot.get("shot_id") or None,
        config_path=routing_path,
    )
    return str(chosen.get("model") or ""), bool(chosen.get("override"))


def _generator_label(preview: str, final: str, override: bool, card: dict) -> str:
    preview_label = _label(card, preview)
    final_label = _label(card, final)
    if preview == final:
        text = preview_label
    else:
        text = f"{preview_label} for the preview, {final_label} for the final"
    if override:
        text += ", from a routing override"
    return text


def _reference_rate(folder: Path, shot: dict, prompt: str, model: str, card: dict):
    """The reference-to-video price when this shot would send images on that model."""
    row = generator_rate(card, model)
    if row is None:
        return None, None
    prepared = prepare_references(folder, shot, prompt, row)
    if prepared.per_second is None:
        return None, prepared
    return prepared.per_second, prepared


def _label(card: dict, model: str) -> str:
    row = generator_rate(card, model)
    if row and row.get("label"):
        return str(row["label"])
    return model


def _stage_totals(picture: Decimal, retake: Decimal, allocations: dict) -> list[dict]:
    production = picture + retake
    estimated = {
        "production": production,
        "art-director": as_money(0),
        "sound-designer": as_money(0),
        "qa": as_money(0),
        "fix-loop": as_money(0),
    }
    names = list(allocations.keys())
    for extra in estimated:
        if extra not in names:
            names.append(extra)
    rows = []
    for name in names:
        amount = estimated.get(name, as_money(0))
        locked = allocations.get(name)
        row = {
            "stage": name,
            "estimated_usd": money_number(amount),
            "locked_usd": money_number(locked) if locked is not None else None,
        }
        if locked is not None:
            gap = as_money(locked) - amount
            row["within_allocation"] = gap >= 0
            row["room_usd"] = money_number(gap)
        else:
            row["within_allocation"] = None
            row["room_usd"] = None
        rows.append(row)
    return rows


def _fix_loop_reserve(allocations: dict):
    if "fix-loop" not in allocations:
        return as_money(0)
    return as_money(allocations["fix-loop"])


def _locked_split(producer) -> dict:
    from movie_swarm.budget import lines_for_check

    filmed = lines_for_check(producer.production_dir)
    if filmed is not None:
        return filmed
    record = producer.record["stage_allocations"]
    if record.get("status") != "approved":
        return {}
    return dict(record.get("split") or {})


def _shot_sentence(shot: dict) -> str:
    length = "no clip length" if shot["requested_seconds"] is None else f"{_seconds_text(shot['requested_seconds'])} seconds"
    if shot["priced"]:
        money = (
            f"Preview ${shot['preview_usd']:.2f}, final ${shot['final_usd']:.2f}, "
            f"shot ${shot['shot_usd']:.2f}."
        )
    else:
        money = "Not priced."
    pieces = ""
    if shot["pieces"] and len(shot["pieces"]) > 1:
        shown = ", ".join(_seconds_text(piece) for piece in shot["pieces"])
        pieces = f" Quoted as clips of {shown} seconds."
    return (
        f"- {shot['shot_id']}. Generator: {shot['generator']}. "
        f"Clip length: {length}.{pieces} "
        f"Takes allowed: {shot['takes_allowed']} (1 preview and 1 final). {money}"
    )


def _stage_sentence(stage: dict) -> str:
    name = stage["stage"]
    estimated = f"${stage['estimated_usd']:.2f}"
    if stage["locked_usd"] is None:
        return f"- {name}: estimated {estimated}. No locked ceiling for this stage."
    locked = f"${stage['locked_usd']:.2f}"
    if stage["within_allocation"]:
        room = f"${stage['room_usd']:.2f}"
        return f"- {name}: estimated {estimated}. Locked ceiling {locked}. Room left: {room}."
    over = f"${abs(stage['room_usd']):.2f}"
    return f"- {name}: estimated {estimated}. Locked ceiling {locked}. Over the ceiling by {over}."


def _public_rate(row: dict) -> dict:
    return {
        "model": row["model"],
        "label": row.get("label") or row["model"],
        "resolution": row.get("resolution") or "",
        "usd_per_second": str(row["usd_per_second"]),
        "source": row.get("source") or "",
        "source_date": row.get("source_date") or "",
        "quote": row.get("quote") or "",
    }


def _from_frame(frame: dict) -> dict:
    shot = {
        "shot_id": str(frame.get("shot_id") or ""),
        "scene_id": str(frame.get("scene_id") or ""),
        "duration_seconds": _duration(frame.get("duration_seconds")),
        "prompt": str(frame.get("board_prompt") or frame.get("what_we_see") or ""),
        "props": frame.get("props_in_frame") or [],
    }
    _copy_reference_fields(shot, frame)
    return shot


def _from_shot(shot: dict) -> dict:
    scene = shot.get("scene_id")
    if not scene and shot.get("scene_number") is not None:
        scene = f"s{int(shot['scene_number']):02d}"
    duration = shot.get("target_duration_seconds", shot.get("duration_seconds"))
    loaded = {
        "shot_id": str(shot.get("shot_id") or ""),
        "scene_id": str(scene or ""),
        "duration_seconds": _duration(duration),
        "prompt": str(shot.get("generation_prompt") or shot.get("description") or ""),
        "props": shot.get("props_in_frame") or shot.get("props_in_shot") or [],
    }
    _copy_reference_fields(loaded, shot)
    return loaded


def _copy_reference_fields(loaded: dict, source: dict) -> None:
    """Keep the shot's own image list and the ids a lock can match. Omit empty fields."""
    images = [str(path).strip() for path in source.get("reference_images") or [] if str(path).strip()]
    if images:
        loaded["reference_images"] = images
    characters = [str(item).strip() for item in source.get("characters_in_shot") or [] if str(item).strip()]
    if characters:
        loaded["characters_in_shot"] = characters
    for key in ("location_id", "location"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            loaded[key] = value.strip()
    block = source.get("reference_from")
    if isinstance(block, dict):
        loaded["reference_from"] = block


def _merge_shot_list(folder: Path, shots: list[dict]) -> None:
    """Fill ids the storyboard frame does not carry from the shot list, when one exists."""
    index = _shot_list_index(folder)
    if not index:
        return
    for shot in shots:
        source = index.get(shot.get("shot_id") or "")
        if not isinstance(source, dict):
            continue
        if "reference_images" not in shot:
            images = [str(path).strip() for path in source.get("reference_images") or [] if str(path).strip()]
            if images:
                shot["reference_images"] = images
        if "characters_in_shot" not in shot:
            characters = [
                str(item).strip() for item in source.get("characters_in_shot") or [] if str(item).strip()
            ]
            if characters:
                shot["characters_in_shot"] = characters
        for key in ("location_id", "location"):
            if key in shot:
                continue
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                shot[key] = value.strip()
        if "reference_from" not in shot and isinstance(source.get("reference_from"), dict):
            shot["reference_from"] = source["reference_from"]


def _shot_list_index(folder: Path) -> dict:
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = folder / relative
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or data.get("superseded") is True:
            continue
        index = {}
        for item in data.get("shots") or []:
            if isinstance(item, dict) and item.get("shot_id"):
                index[str(item["shot_id"])] = item
        if index:
            return index
    return {}


def _duration(value):
    if value is None or value == "":
        return None
    return float(as_money(value))


def _title(folder: Path) -> str:
    treatment = folder / "treatment" / "treatment.json"
    if treatment.is_file():
        try:
            data = json.loads(treatment.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and data.get("title"):
            return str(data["title"])
    brief = folder / "production-brief.json"
    if brief.is_file():
        try:
            data = json.loads(brief.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and data.get("title"):
            return str(data["title"])
    return folder.name


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GenerationError(f"{path.name} is not valid JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise GenerationError(f"{path.name} must be a JSON object.")
    return data


def _sum(values) -> Decimal:
    total = as_money(0)
    for value in values:
        if value is None:
            continue
        total += as_money(value)
    return total
