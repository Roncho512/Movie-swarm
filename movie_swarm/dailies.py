"""Dailies Reviewer: circle, retake, or reject each generated take.

The phrases, the shot list, and the look come from the production folder.
This module does not know which film it is reading. It does not call a paid
model. Tests pass a vision client. With no client, a text file beside the
frame can supply the description. If neither is there, the description is
empty and a required phrase cannot pass.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from movie_swarm.continuity import expected_phrases, load_prop_lock, locked_picture_drift
from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.models import ModelRoutingError, resolve_model
from movie_swarm.money import as_money, money_number


class DailiesError(Exception):
    """The review cannot be built. The message says what is missing."""


class OfflineVision:
    """No network. A sidecar text file is the description, when one exists."""

    def describe(self, *, path: str, shot_id: str) -> str:
        sidecar = Path(str(path) + ".txt")
        if sidecar.is_file():
            return sidecar.read_text(encoding="utf-8")
        return ""


# A still frame is not a clip. Duration and freeze checks apply to clips.
_DURATION_RATIO = 0.20
_DURATION_FLOOR_SECONDS = 0.5
_BLACK_FILTER = "blackdetect=d=0.5:pix_th=0.10"
_FREEZE_FILTER = "freezedetect=n=0.003:d=0.5"
_MOTION_WORDS = ("push", "pull", "pan", "tilt", "track", "dolly", "crane", "zoom", "move", "handheld", "drift")
_SUBJECT_STOPWORDS = {
    "a", "an", "the", "of", "on", "in", "at", "to", "and", "or", "with", "from",
    "for", "her", "his", "their", "she", "he", "they", "this", "that", "into",
    "over", "under", "then", "shot", "frame", "view",
}


def review_dailies(
    *,
    shot_id: str,
    prompt: str,
    props_in_frame,
    lock: dict | None,
    clip_ref: str | None = None,
) -> dict:
    """Record that generation has not reviewed this picture.

    The generation step calls this after a client returns. It does not open
    the file and it does not call a vision model. ``review_production`` is
    the review that circles a take.
    """
    return {
        "status": "not-reviewed",
        "reviewer": "dailies",
        "shot_id": shot_id,
        "watched": False,
        "clip_ref": clip_ref,
        "phrases": expected_phrases(prompt, props_in_frame, lock),
        "note": (
            "Dailies has not watched this frame and did not call a model. "
            "Review the takes manifest to circle, retake, or reject."
        ),
    }


def review_production(
    production_dir: str | Path,
    *,
    vision=None,
    manifest_path: str | Path | None = None,
    allocations: dict | None = None,
    fix_loop_spent: float = 0,
    routing_path: str | Path | None = None,
) -> dict:
    """Review every take. The result is a report. It is not a spend."""
    folder = Path(production_dir)
    manifest = _load_manifest(folder, manifest_path)
    shots = _load_shot_index(folder)
    lock = load_prop_lock(folder)
    look = _load_look(folder)
    client = vision if vision is not None else OfflineVision()
    watched = False
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for take in manifest["takes"]:
        shot_id = str(take["shot_id"])
        if shot_id not in grouped:
            grouped[shot_id] = []
            order.append(shot_id)
        reviewed, did_watch = _review_take(
            folder,
            take,
            shots.get(shot_id),
            lock,
            look,
            client,
        )
        watched = watched or did_watch
        grouped[shot_id].append(reviewed)

    shot_rows = []
    retakes = []
    unpriced = False
    for shot_id in order:
        takes = grouped[shot_id]
        best = _best(takes)
        shot_rows.append(
            {
                "shot_id": shot_id,
                "verdict": best["verdict"],
                "best_take": best["take_id"],
                "reasons": list(best["reasons"]),
                "takes": [_public_take(item) for item in takes],
            }
        )
        if best["verdict"] != "retake":
            continue
        price = _preview_price(shots.get(shot_id), routing_path)
        if price is None:
            unpriced = True
            price = 0.0
        retakes.append(
            {
                "shot_id": shot_id,
                "take_id": best["take_id"],
                "reasons": list(best["reasons"]),
                "prompt_fix": best["prompt_fix"],
                "estimate_usd": price,
                "routed_to": "production generate",
            }
        )

    estimate = money_number(sum(as_money(item["estimate_usd"]) for item in retakes)) if retakes else 0.0
    reserve, within, note = _fix_loop_fit(estimate, allocations, fix_loop_spent, bool(retakes), unpriced)
    try:
        model = str(resolve_model("dailies", purpose="review").get("model") or "")
    except ModelRoutingError:
        model = ""
    return {
        "version": "1.0.0",
        "production_id": folder.name,
        "reviewed_at": _now(),
        "source": "takes/takes-manifest.json" if manifest_path is None else Path(manifest_path).name,
        "watched": watched,
        "spent_usd": 0,
        "fix_loop_reserve_usd": reserve,
        "retake_estimate_usd": estimate,
        "within_fix_loop": within,
        "fix_loop_note": note,
        "shots": shot_rows,
        "retakes": retakes,
        "model": model,
        "draft_method": "fake-client" if vision is not None else "offline-deterministic",
    }


def render_report(report: dict) -> str:
    """The report as a table a person can read before the edit."""
    lines = [
        f"Dailies for {report['production_id']}",
        "",
        "No money was spent. A retake below is an estimate, not a charge.",
        "",
        "| Shot | Best take | Verdict | Reasons |",
        "| --- | --- | --- | --- |",
    ]
    for shot in report["shots"]:
        reasons = "; ".join(shot["reasons"]) or "The checks passed."
        best = shot["best_take"] or "none"
        lines.append(
            f"| {shot['shot_id']} | {best} | {shot['verdict']} | {_cell(reasons)} |"
        )
    lines.extend(["", "Retakes, routed back to generation:"])
    if not report["retakes"]:
        lines.append("None.")
    for item in report["retakes"]:
        lines.append(
            f"- {item['shot_id']} take {item['take_id']}. "
            f"Estimate ${item['estimate_usd']:.2f}. "
            f"Prompt fix: {item['prompt_fix']}"
        )
    lines.extend(
        [
            "",
            f"Retake estimate: ${report['retake_estimate_usd']:.2f}.",
            f"Fix-loop line: ${report['fix_loop_reserve_usd']:.2f}.",
            report.get("fix_loop_note") or "",
            "",
            "Ron approves the circled takes at the dailies gate before the editor runs.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(report: dict, production_dir: str | Path) -> tuple[Path, Path]:
    """Write the checklist file and the readable table. An invalid report is not saved."""
    folder = Path(production_dir) / "dailies"
    folder.mkdir(parents=True, exist_ok=True)
    data_path = folder / "dailies-report.json"
    text_path = folder / "dailies-report.md"
    write_handoff(data_path, report, schema="dailies-report")
    text_path.write_text(render_report(report), encoding="utf-8")
    return data_path, text_path


def run_dailies(producer, call) -> str:
    """The Director's review command. It writes the report and does not spend."""
    production = Path(call.production_dir or producer.production_dir)
    vision = call.client if call.client is not None and hasattr(call.client, "describe") else None
    allocations, spent = _budget_from_producer(producer)
    report = review_production(
        production,
        vision=vision,
        manifest_path=call.takes or call.shot_list,
        allocations=allocations,
        fix_loop_spent=spent,
    )
    data_path, text_path = write_report(report, production)
    producer.ensure_artifact("dailies-report", "dailies/dailies-report.json", "dailies-report.schema.json")
    producer.ensure_artifact("dailies-notes", "dailies/dailies-report.md")
    _ensure_credit(producer)
    if producer.gate_decision("dailies") == "approved":
        producer.run.data["notes"] = (
            "Dailies were reviewed again after Ron approved the dailies gate. "
            "The approval still stands until Ron rejects it."
        )
        producer.run.save()
    else:
        producer.set_stage("dailies", "waiting-for-review")
        producer.run.data["notes"] = (
            "The dailies report is waiting on Ron. "
            "Circled takes are not cleared for the edit until he approves the dailies gate."
        )
        producer.run.save()
    return render_report(report) + f"\nWrote {text_path}."


def _review_take(folder: Path, take: dict, shot: dict | None, lock, look, client) -> tuple[dict, bool]:
    take_id = str(take["take_id"])
    relative = str(take["file"])
    path = Path(relative) if Path(relative).is_absolute() else folder / relative
    kind = str(take.get("kind") or "frame")
    technical = _technical(path, kind, shot)
    if technical["status"] == "fail" and technical.get("reject"):
        skipped = {"status": "skipped", "detail": "The file cannot be reviewed, so this check did not run."}
        reasons = list(technical["reasons"])
        return (
            {
                "take_id": take_id,
                "file": relative,
                "verdict": "reject",
                "reasons": reasons,
                "description_source": "none",
                "prompt_fix": "",
                "checks": {
                    "technical": _slim(technical),
                    "continuity": skipped,
                    "shot_match": skipped,
                    "look_match": skipped,
                },
            },
            False,
        )

    description, source = _describe(client, path, str(take["shot_id"]))
    continuity = _continuity(description, shot, lock)
    shot_match = _shot_match(description, shot, technical, kind)
    look_match = _look_match(description, look)
    failed = [item for item in (technical, continuity, shot_match, look_match) if item["status"] == "fail"]
    public_checks = {
        "technical": _slim(technical),
        "continuity": _slim(continuity),
        "shot_match": _slim(shot_match),
        "look_match": _slim(look_match),
    }
    if failed:
        reasons = []
        for item in failed:
            reasons.extend(item.get("reasons") or _split_detail(item.get("detail")))
        prompt_fix = _prompt_fix(shot, look, continuity, shot_match, look_match)
        verdict = "retake"
    else:
        reasons = [_circle_sentence(public_checks)]
        prompt_fix = ""
        verdict = "circle"
    return (
        {
            "take_id": take_id,
            "file": relative,
            "verdict": verdict,
            "reasons": reasons,
            "description_source": source,
            "prompt_fix": prompt_fix,
            "checks": public_checks,
        },
        source != "none",
    )


def _describe(client, path: Path, shot_id: str) -> tuple[str, str]:
    if isinstance(client, OfflineVision):
        text = client.describe(path=str(path), shot_id=shot_id)
        source = "sidecar" if Path(str(path) + ".txt").is_file() and text.strip() else "none"
        return text, source if text.strip() else "none"
    text = client.describe(path=str(path), shot_id=shot_id)
    return str(text or ""), "client" if str(text or "").strip() else "none"


def _technical(path: Path, kind: str, shot: dict | None) -> dict:
    if not path.is_file():
        return {
            "status": "fail",
            "reject": True,
            "reasons": [f"The file is not on disk: {path.name}."],
            "detail": f"The file is not on disk: {path.name}.",
            "duration_seconds": None,
        }
    if path.stat().st_size == 0:
        return {
            "status": "fail",
            "reject": True,
            "reasons": ["The file is empty."],
            "detail": "The file is empty.",
            "duration_seconds": None,
        }
    probe = _probe(path)
    reasons = []
    black = False
    frozen = False
    if kind == "clip":
        scan = _scan_clip(path)
        black = bool(scan.get("black"))
        frozen = bool(scan.get("frozen")) and _expects_motion(shot)
        if black:
            reasons.append("The clip has a black stretch.")
        if frozen:
            movement = (shot or {}).get("camera_movement") or "movement"
            reasons.append(f"The clip is frozen and the shot list asked for camera movement: {movement}.")
        if scan.get("note") and not black and not frozen:
            probe_note = scan["note"]
        else:
            probe_note = ""
    else:
        probe_note = "A still frame is not checked for duration, black frames, or frozen motion."
    detail_bits = ["The file is on disk."]
    if probe.get("summary"):
        detail_bits.append(probe["summary"])
    if probe_note:
        detail_bits.append(probe_note)
    if reasons:
        detail_bits.extend(reasons)
    return {
        "status": "fail" if reasons else "pass",
        "reject": False,
        "reasons": reasons,
        "detail": " ".join(detail_bits),
        "duration_seconds": probe.get("duration_seconds") if kind == "clip" else None,
    }


def _continuity(description: str, shot: dict | None, lock) -> dict:
    props = (shot or {}).get("props") or []
    if lock is None:
        return {
            "status": "skipped",
            "detail": "No prop file was found, so locked phrases were not checked.",
            "reasons": [],
            "drift": {"required_missing": [], "forbidden_hit": []},
        }
    drift = locked_picture_drift(description, props, lock)
    if not props and not drift["reasons"]:
        return {
            "status": "skipped" if not drift["checked"] else "pass",
            "detail": (
                "No locked prop is listed in this shot."
                if not drift["checked"]
                else "The description does not use a forbidden phrase."
            ),
            "reasons": [],
            "drift": drift,
        }
    if drift["reasons"]:
        return {
            "status": "fail",
            "detail": " ".join(drift["reasons"]),
            "reasons": drift["reasons"],
            "drift": drift,
        }
    return {
        "status": "pass",
        "detail": "The picture description matches the locked phrases.",
        "reasons": [],
        "drift": drift,
    }


def _shot_match(description: str, shot: dict | None, technical: dict, kind: str) -> dict:
    if shot is None:
        return {
            "status": "fail",
            "detail": "This take's shot id is not on the shot list.",
            "reasons": ["This take's shot id is not on the shot list."],
        }
    reasons = []
    expected = str(shot.get("shot_type") or "").strip()
    if expected and not _has_phrase(description, expected):
        reasons.append(f"Framing does not match the shot list. The shot list says {expected}.")
    subject = str(shot.get("description") or "").strip()
    words = _subject_words(subject)
    if words and not any(word.casefold() in description.casefold() for word in words):
        reasons.append(f"The subject does not match the shot list. The shot list says: {subject}")
    target = shot.get("duration_seconds")
    observed = technical.get("duration_seconds")
    if kind == "clip" and target is not None and observed is not None:
        tolerance = max(_DURATION_FLOOR_SECONDS, _DURATION_RATIO * float(target))
        if abs(float(observed) - float(target)) > tolerance:
            reasons.append(
                f"Duration {float(observed):.2f}s is outside the shot list {float(target):.2f}s. "
                f"Tolerance is {tolerance:.2f}s."
            )
    if reasons:
        return {"status": "fail", "detail": " ".join(reasons), "reasons": reasons}
    skipped_duration = kind != "clip" or observed is None or target is None
    extra = ""
    if skipped_duration and kind == "clip" and target is not None and observed is None:
        extra = " Duration was not read, so it was not compared."
    return {
        "status": "pass",
        "detail": "The take matches the shot list." + extra,
        "reasons": [],
    }


def _look_match(description: str, look: dict | None) -> dict:
    if not look:
        return {
            "status": "skipped",
            "detail": "No look file was found, so the look was not compared.",
            "reasons": [],
        }
    phrases = _look_phrases(look)
    if not phrases:
        return {
            "status": "skipped",
            "detail": "The look file did not name a phrase long enough to check.",
            "reasons": [],
        }
    if any(_has_phrase(description, phrase) or phrase.casefold() in description.casefold() for phrase in phrases):
        return {
            "status": "pass",
            "detail": f"The description matches the look {look.get('look_name') or ''}".strip() + ".",
            "reasons": [],
        }
    name = look.get("look_name") or "the look file"
    reason = f"The description does not match the look. The look file says {name}."
    return {"status": "fail", "detail": reason, "reasons": [reason]}


def _prompt_fix(shot, look, continuity, shot_match, look_match) -> str:
    parts = []
    base = ""
    if shot:
        base = str(shot.get("prompt") or shot.get("description") or "").strip()
    if base:
        parts.append(base)
    drift = continuity.get("drift") or {}
    for phrase in drift.get("required_missing") or []:
        parts.append(f"State this locked phrase: {phrase}.")
    for phrase in drift.get("forbidden_hit") or []:
        parts.append(f"Do not show this: {phrase}.")
    if shot_match.get("status") == "fail" and shot:
        if shot.get("shot_type"):
            parts.append(f"Match the shot list framing: {shot['shot_type']}.")
        if shot.get("description"):
            parts.append(f"Match the shot list subject: {shot['description']}")
    if look_match.get("status") == "fail" and look:
        summary = str(look.get("summary") or look.get("look_name") or "").strip()
        if summary:
            parts.append(f"Match the look: {summary}")
    if not parts:
        parts.append("Generate this shot again so it matches the shot list and the locked props.")
    return " ".join(parts)


def _circle_sentence(checks: dict) -> str:
    names = []
    if checks["continuity"]["status"] == "pass":
        names.append("the locked phrases")
    if checks["shot_match"]["status"] == "pass":
        names.append("the shot list")
    if checks["look_match"]["status"] == "pass":
        names.append("the look")
    if not names:
        return "Circled. The checks that ran did not fail."
    if len(names) == 1:
        return f"Circled. The take matches {names[0]}."
    return "Circled. The take matches " + ", ".join(names[:-1]) + f", and {names[-1]}."


def _best(takes: list[dict]) -> dict:
    rank = {"circle": 0, "retake": 1, "reject": 2}
    return sorted(takes, key=lambda item: rank.get(item["verdict"], 9))[0]


def _public_take(item: dict) -> dict:
    return {
        "take_id": item["take_id"],
        "file": item["file"],
        "verdict": item["verdict"],
        "reasons": list(item["reasons"]),
        "description_source": item["description_source"],
        "checks": item["checks"],
    }


def _slim(result: dict) -> dict:
    return {"status": result["status"], "detail": result.get("detail") or ""}


def _split_detail(detail: str | None) -> list[str]:
    text = (detail or "").strip()
    return [text] if text else []


def _preview_price(shot: dict | None, routing_path) -> float | None:
    if not shot or shot.get("duration_seconds") is None:
        return None
    from movie_swarm.generation import quote_preview_usd

    return quote_preview_usd(
        {
            "shot_id": shot.get("shot_id") or "",
            "scene_id": shot.get("scene_id") or "",
            "duration_seconds": shot.get("duration_seconds"),
        },
        routing_path,
    )


def _fix_loop_fit(estimate: float, allocations: dict | None, spent: float, has_retakes: bool, unpriced: bool):
    reserve = 0.0
    if allocations and "fix-loop" in allocations:
        reserve = money_number(allocations["fix-loop"])
    room = as_money(reserve) - as_money(spent)
    if room < 0:
        room = as_money(0)
    if not has_retakes:
        return reserve, True, "There is no retake, so the fix-loop line is untouched. Nothing was charged."
    if unpriced:
        return (
            reserve,
            False,
            "A retake has no published preview rate, so it is not cleared to spend. Nothing was charged.",
        )
    if allocations is None or "fix-loop" not in (allocations or {}):
        return (
            reserve,
            False,
            "No locked fix-loop line was found, so the retake estimate is not cleared to spend. Nothing was charged.",
        )
    if as_money(estimate) <= room:
        return (
            reserve,
            True,
            f"The retake estimate ${estimate:.2f} fits the fix-loop line. Nothing was charged.",
        )
    return (
        reserve,
        False,
        f"The retake estimate ${estimate:.2f} is over the fix-loop line. "
        "The list is saved. Nothing was charged, and the retakes are not cleared to spend.",
    )


def _budget_from_producer(producer) -> tuple[dict | None, float]:
    record = producer.record.get("stage_allocations") or {}
    if record.get("status") != "approved":
        return None, 0.0
    return dict(record.get("split") or {}), float(producer.stage_spent("fix-loop"))


def _ensure_credit(producer) -> None:
    have = {item["role"] for item in producer.record["credits"]}
    if "Dailies Reviewer" in have:
        return
    producer.record["credits"].append({"role": "Dailies Reviewer", "name": "Dailies Reviewer"})
    producer._save_record()


def _load_manifest(folder: Path, manifest_path: str | Path | None) -> dict:
    path = Path(manifest_path) if manifest_path else folder / "takes" / "takes-manifest.json"
    if not path.is_file():
        raise DailiesError(
            f"No takes manifest at {path}. "
            "Dailies needs a takes file. Each take names a shot id and a clip or frame."
        )
    try:
        data = read_handoff(path, schema="takes-manifest")
    except HandoffError as exc:
        raise DailiesError(str(exc)) from exc
    return data


def _load_shot_index(folder: Path) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = folder / relative
        if not path.is_file():
            continue
        data = _read_json(path)
        for shot in data.get("shots") or []:
            if isinstance(shot, dict) and shot.get("shot_id"):
                index[str(shot["shot_id"])] = _normalize_shot(shot)
        if index:
            return index
    board = folder / "storyboard" / "storyboard.json"
    if board.is_file():
        for frame in _read_json(board).get("frames") or []:
            if isinstance(frame, dict) and frame.get("shot_id"):
                index[str(frame["shot_id"])] = _normalize_frame(frame)
    return index


def _normalize_shot(shot: dict) -> dict:
    scene = shot.get("scene_id")
    if not scene and shot.get("scene_number") is not None:
        scene = f"s{int(shot['scene_number']):02d}"
    duration = shot.get("target_duration_seconds", shot.get("duration_seconds"))
    return {
        "shot_id": str(shot.get("shot_id") or ""),
        "scene_id": str(scene or ""),
        "shot_type": str(shot.get("shot_type") or ""),
        "description": str(shot.get("description") or ""),
        "framing_notes": str(shot.get("framing_notes") or ""),
        "camera_movement": str(shot.get("camera_movement") or ""),
        "prompt": str(shot.get("generation_prompt") or shot.get("description") or ""),
        "props": shot.get("props_in_shot") or shot.get("props_in_frame") or shot.get("props") or [],
        "duration_seconds": _duration(duration),
    }


def _normalize_frame(frame: dict) -> dict:
    return {
        "shot_id": str(frame.get("shot_id") or ""),
        "scene_id": str(frame.get("scene_id") or ""),
        "shot_type": str(frame.get("shot_type") or ""),
        "description": str(frame.get("what_we_see") or ""),
        "framing_notes": "",
        "camera_movement": "",
        "prompt": str(frame.get("board_prompt") or frame.get("what_we_see") or ""),
        "props": frame.get("props_in_frame") or [],
        "duration_seconds": _duration(frame.get("duration_seconds")),
    }


def _load_look(folder: Path) -> dict | None:
    path = folder / "look" / "look.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _look_phrases(look: dict) -> list[str]:
    chunks = [look.get("summary") or "", look.get("look_name") or ""]
    for key in ("lighting", "framing"):
        for item in look.get(key) or []:
            if isinstance(item, dict):
                chunks.append(item.get("description") or "")
            elif isinstance(item, str):
                chunks.append(item)
    for color in look.get("palette") or []:
        chunks.append(str(color))
    phrases = []
    seen = set()
    for chunk in chunks:
        for part in re.split(r"[.;]", str(chunk)):
            phrase = " ".join(part.split())
            folded = phrase.casefold()
            if " " in phrase and len(phrase) >= 8 and folded not in seen:
                seen.add(folded)
                phrases.append(phrase)
    return phrases


def _probe(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {
            "duration_seconds": None,
            "summary": "ffprobe is not installed, so duration, resolution, and frame rate were not read.",
        }
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "duration_seconds": None,
            "summary": "ffprobe did not finish, so duration, resolution, and frame rate were not read.",
        }
    if completed.returncode != 0 or not completed.stdout.strip():
        return {
            "duration_seconds": None,
            "summary": "ffprobe could not read this file. Duration, resolution, and frame rate were not checked.",
        }
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"duration_seconds": None, "summary": "ffprobe did not return readable technical data."}
    stream = next((item for item in data.get("streams") or [] if item.get("codec_type") == "video"), {})
    duration = (data.get("format") or {}).get("duration")
    seconds = None
    if duration not in (None, "", "N/A"):
        try:
            seconds = float(duration)
        except (TypeError, ValueError):
            seconds = None
    width = stream.get("width")
    height = stream.get("height")
    rate = _frame_rate(stream.get("avg_frame_rate"))
    bits = []
    if width and height:
        bits.append(f"{width}x{height}")
    if rate:
        bits.append(f"{rate:g} fps")
    if seconds is not None and seconds > 0:
        bits.append(f"{seconds:.2f}s")
    summary = "ffprobe read " + ", ".join(bits) + "." if bits else "ffprobe did not report a size, a frame rate, or a duration."
    return {"duration_seconds": seconds if seconds and seconds > 0 else None, "summary": summary}


def _scan_clip(path: Path) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            "black": False,
            "frozen": False,
            "note": "ffmpeg is not installed, so black frames and frozen frames were not scanned.",
        }
    black = _filter_hit(path, _BLACK_FILTER, "black_start")
    frozen = _filter_hit(path, _FREEZE_FILTER, "freeze_start")
    if black is None or frozen is None:
        return {
            "black": False,
            "frozen": False,
            "note": "ffmpeg could not scan this clip, so black frames and frozen frames were not judged.",
        }
    return {"black": black, "frozen": frozen, "note": ""}


def _filter_hit(path: Path, video_filter: str, needle: str) -> bool | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        completed = subprocess.run(
            [ffmpeg, "-i", str(path), "-vf", video_filter, "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 and needle not in (completed.stderr or ""):
        return None
    return needle in (completed.stderr or "")


def _expects_motion(shot: dict | None) -> bool:
    if not shot:
        return False
    text = f"{shot.get('camera_movement') or ''} {shot.get('shot_type') or ''}".casefold()
    return any(word in text for word in _MOTION_WORDS)


def _subject_words(description: str) -> list[str]:
    words = []
    for raw in re.findall(r"[A-Za-z0-9']+", description):
        word = raw.strip("'")
        if len(word) < 4 or word.casefold() in _SUBJECT_STOPWORDS:
            continue
        words.append(word)
    return words


def _has_phrase(text: str, phrase: str) -> bool:
    normalized = (text or "").casefold().replace("-", " ")
    needle = phrase.casefold().replace("-", " ").strip()
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", normalized) is not None


def _frame_rate(value) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    if "/" in text:
        left, right = text.split("/", 1)
        try:
            denominator = float(right)
            if denominator == 0:
                return None
            return float(left) / denominator
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _duration(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DailiesError(f"{path.name} is not valid JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise DailiesError(f"{path.name} must be a JSON object.")
    return data


def _cell(text: str) -> str:
    return text.replace("|", "/")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
