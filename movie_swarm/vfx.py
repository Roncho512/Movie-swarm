"""VFX Supervisor: a breakdown before production, and a review of dailies.

A shot is flagged when the production's VFX notes name it, or when the shot
text itself names an effect. The task, the method, and the risk are the
production's words. Turnover notes are for the Editor and the Colorist.
The review reads the dailies report. It does not call a model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff
from movie_swarm.prep_inputs import load_shots
from movie_swarm.previs_common import (
    PrevisError,
    approved_treatment,
    model_name,
    now,
    save_pair,
    source_blob,
    system_prompt,
    try_model_json,
)


_WORDS = (
    "visual effect",
    "green screen",
    "set extension",
    "wire removal",
    "compositing",
    "composite",
    "matte",
    "vfx",
    "cgi",
)


def needs_path(production_dir: Path) -> Path:
    return production_dir / "vfx" / "vfx-needs.json"


def breakdown_path(production_dir: Path) -> Path:
    return production_dir / "vfx" / "vfx-breakdown.json"


def review_path(production_dir: Path) -> Path:
    return production_dir / "vfx" / "vfx-review.json"


def build_breakdown(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    approved_treatment(production_dir)
    shots, shot_source = load_shots(production_dir)
    needs = _needs(production_dir)
    offline = _offline(production_dir, shots, shot_source, needs)
    drafted = _from_model(llm, offline)
    document = drafted or offline
    save_pair(breakdown_path(production_dir), document, "vfx-breakdown", _markdown(document))
    return document


def review_vfx(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    approved_treatment(production_dir)
    breakdown = _read_breakdown(production_dir)
    report = _read_dailies(production_dir)
    manifest = _read_manifest(production_dir)
    document = _review(production_dir, breakdown, report, manifest)
    if llm is not None:
        document["summary"] = _model_summary(llm, document) or document["summary"]
    save_pair(review_path(production_dir), document, "vfx-review", _review_markdown(document))
    return document


def turnover_markdown(production_dir: Path, audience: str) -> str:
    """Sentences for the editor or the colorist, when a breakdown exists."""
    path = breakdown_path(Path(production_dir))
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    lines = ["", f"## VFX turnover for the {audience}", ""]
    found = False
    for item in data.get("turnover") or []:
        if not isinstance(item, dict):
            continue
        if audience not in (item.get("for") or []):
            continue
        text = str(item.get(audience) or "").strip()
        if not text:
            continue
        found = True
        lines.append(f"- {item.get('shot_id')}: {text}")
    if not found:
        return ""
    lines.append("")
    return "\n".join(lines)


def _needs(production_dir: Path) -> dict | None:
    path = needs_path(production_dir)
    if not path.is_file():
        return None
    try:
        data = read_handoff(path, schema="vfx-needs")
    except HandoffError as exc:
        raise PrevisError(str(exc)) from exc
    return data


def _offline(production_dir, shots, shot_source, needs) -> dict:
    items = []
    for shot in shots:
        items.extend(_rows_for_shot(shot, needs))
    if items:
        note = "Each row is a shot the production marked for VFX, or a shot whose own text names an effect."
    else:
        note = "No shot was marked for VFX. No effect was invented."
    turnover = [_turnover(item) for item in items]
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "source": {
            "shots": shot_source,
            "needs": "vfx/vfx-needs.json" if needs else None,
        },
        "shots": items,
        "turnover": turnover,
        "draft_method": "offline-deterministic",
        "model": model_name("vfx-supervisor", "breakdown"),
        "note": note,
        "created_at": now(),
    }


def _rows_for_shot(shot: dict, needs: dict | None) -> list[dict]:
    text = shot.get("text") or ""
    rows = []
    matched_spans = []
    for item in (needs or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        phrase = str(item.get("match") or "").strip()
        shot_ids = [str(value) for value in item.get("shot_ids") or [] if str(value).strip()]
        hit = (phrase and phrase.casefold() in text.casefold()) or shot["shot_id"] in shot_ids
        if not hit:
            continue
        if phrase:
            matched_spans.append(phrase.casefold())
        rows.append(
            {
                "shot_id": shot["shot_id"],
                "scene_id": shot.get("scene_id") or "unassigned",
                "task": str(item.get("task") or "The production marked this shot."),
                "method": str(item.get("method") or "not named"),
                "risk": str(item.get("risk") or "The production did not name a risk."),
                "match": phrase or shot["shot_id"],
                "source": "vfx/vfx-needs.json",
            }
        )
    folded = text.casefold()
    for word in _WORDS:
        if not _mentions(folded, word):
            continue
        if any(word in span or span in word for span in matched_spans):
            continue
        rows.append(
            {
                "shot_id": shot["shot_id"],
                "scene_id": shot.get("scene_id") or "unassigned",
                "task": f"The shot text names {word}.",
                "method": word,
                "risk": "The shot names an effect and has no separate VFX note. The note was not invented.",
                "match": word,
                "source": "shot text",
            }
        )
    return rows


def _mentions(text: str, word: str) -> bool:
    if " " in word:
        return word in text
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _turnover(item: dict) -> dict:
    method = item["method"]
    shot_id = item["shot_id"]
    return {
        "shot_id": shot_id,
        "for": ["editor", "colorist"],
        "editor": (
            f"Keep {shot_id} in the cut. The task is {item['task']} "
            f"The method is {method}. Do not drop the shot to avoid the work."
        ),
        "colorist": (
            f"Grade the plate and the element of {shot_id} as one shot. "
            f"The method is {method}. Do not treat them as two looks."
        ),
    }


def _read_breakdown(production_dir: Path) -> dict:
    path = breakdown_path(production_dir)
    if not path.is_file():
        raise PrevisError("No VFX breakdown. Run the VFX Supervisor breakdown before the review.")
    try:
        return read_handoff(path, schema="vfx-breakdown")
    except HandoffError as exc:
        raise PrevisError(str(exc)) from exc


def _read_dailies(production_dir: Path) -> dict:
    path = production_dir / "dailies" / "dailies-report.json"
    if not path.is_file():
        raise PrevisError("No dailies report. Review the takes before the VFX review.")
    try:
        return read_handoff(path, schema="dailies-report")
    except HandoffError as exc:
        raise PrevisError(str(exc)) from exc


def _read_manifest(production_dir: Path) -> dict:
    path = production_dir / "takes" / "takes-manifest.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _review(production_dir, breakdown, report, manifest) -> dict:
    by_shot = {}
    for row in report.get("shots") or []:
        if isinstance(row, dict) and row.get("shot_id"):
            by_shot[str(row["shot_id"])] = row
    prompts = {}
    for take in manifest.get("takes") or []:
        if isinstance(take, dict) and take.get("shot_id"):
            prompts.setdefault(str(take["shot_id"]), [])
            prompts[str(take["shot_id"])].append(str(take.get("prompt") or ""))
    rows = []
    for item in breakdown.get("shots") or []:
        shot_id = item["shot_id"]
        dailies = by_shot.get(shot_id)
        if dailies is None:
            rows.append(
                {
                    "shot_id": shot_id,
                    "task": item["task"],
                    "dailies_verdict": "missing",
                    "status": "not-reviewed",
                    "detail": f"{shot_id} is on the VFX breakdown and is not in the dailies report.",
                }
            )
            continue
        verdict = str(dailies.get("verdict") or "")
        text = _dailies_text(dailies, prompts.get(shot_id) or [])
        phrase = str(item.get("match") or "")
        if verdict != "circle":
            status = "fail"
            detail = f"{shot_id} is a VFX shot and dailies marked it {verdict or 'unreviewed'}."
        elif phrase and phrase.casefold() not in text.casefold():
            status = "fail"
            detail = f"{shot_id} was circled and does not show the VFX note \"{phrase}\"."
        else:
            status = "pass"
            detail = f"{shot_id} was circled and still shows the VFX note."
        rows.append(
            {
                "shot_id": shot_id,
                "task": item["task"],
                "dailies_verdict": verdict or "missing",
                "status": status,
                "detail": detail,
            }
        )
    failed = [row for row in rows if row["status"] != "pass"]
    if not rows:
        summary = "No VFX shot was on the breakdown, so there was nothing to review."
        verdict = "clear"
    elif failed:
        summary = f"{len(failed)} VFX shot(s) did not pass the dailies review."
        verdict = "drift"
    else:
        summary = "The circled VFX shots still match the breakdown."
        verdict = "clear"
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "verdict": verdict,
        "summary": summary,
        "sources": ["vfx/vfx-breakdown.json", "dailies/dailies-report.json"],
        "shots": rows,
        "draft_method": "offline-deterministic",
        "model": model_name("vfx-supervisor", "review"),
        "checked_at": now(),
    }


def _dailies_text(row: dict, prompts: list[str]) -> str:
    parts = list(prompts)
    parts.extend(str(item) for item in row.get("reasons") or [])
    for take in row.get("takes") or []:
        if not isinstance(take, dict):
            continue
        parts.extend(str(item) for item in take.get("reasons") or [])
        checks = take.get("checks") or {}
        if isinstance(checks, dict):
            for check in checks.values():
                if isinstance(check, dict) and check.get("detail"):
                    parts.append(str(check["detail"]))
    return " ".join(part for part in parts if part)


def _from_model(llm, offline) -> dict | None:
    if llm is None:
        return None
    drafted = try_model_json(
        llm,
        role="vfx-supervisor",
        purpose="breakdown",
        system=system_prompt(
            "You are the VFX Supervisor. Rewrite the note only. Do not change the breakdown. "
            "Return {\"note\": \"...\"}."
        ),
        user=source_blob(offline.get("note")),
    )
    if not drafted:
        return None
    text = drafted.get("note")
    if not isinstance(text, str) or not text.strip():
        return None
    document = dict(offline)
    document["note"] = text.strip()
    document["draft_method"] = "model"
    return document


def _model_summary(llm, document: dict) -> str | None:
    drafted = try_model_json(
        llm,
        role="vfx-supervisor",
        purpose="review",
        system=system_prompt(
            "You are the VFX Supervisor. Rewrite the summary in one or two sentences. "
            "Do not add shots. Return {\"summary\": \"...\"}."
        ),
        user=document["summary"],
    )
    if not drafted:
        return None
    text = drafted.get("summary")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _markdown(document: dict) -> str:
    lines = ["# VFX breakdown", "", document.get("note") or "", ""]
    if not document.get("shots"):
        lines.append("No VFX shots.")
        lines.append("")
    for shot in document.get("shots") or []:
        lines.append(f"## {shot['shot_id']}")
        lines.append("")
        lines.append(f"Task: {shot['task']}")
        lines.append(f"Method: {shot['method']}")
        lines.append(f"Risk: {shot['risk']}")
        lines.append("")
    if document.get("turnover"):
        lines.append("## Turnover")
        lines.append("")
        for item in document["turnover"]:
            lines.append(f"- Editor, {item['shot_id']}: {item['editor']}")
            lines.append(f"- Colorist, {item['shot_id']}: {item['colorist']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _review_markdown(document: dict) -> str:
    lines = ["# VFX review", "", f"Verdict: {document['verdict']}.", "", document.get("summary") or "", ""]
    for shot in document.get("shots") or []:
        lines.append(f"- {shot['shot_id']}: {shot['status']}. {shot['detail']}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
