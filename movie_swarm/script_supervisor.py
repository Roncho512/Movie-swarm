"""Script Supervisor: flag drift against the locked hero props.

A shot or a scene drifts when it uses a phrase the production forbade, or
when a shot shows a prop and never states a phrase the production required.
The phrases come from the locked file. This module has no list of its own.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.handoff import HandoffError, read_handoff
from movie_swarm.previs_common import (
    PrevisError,
    approved_treatment,
    model_name,
    now,
    save_pair,
)
from movie_swarm.prop_master import locked_path


def check_path(production_dir: Path) -> Path:
    return production_dir / "continuity" / "continuity-check.json"


def check_continuity(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    approved_treatment(production_dir)
    path = locked_path(production_dir)
    if not path.is_file():
        raise PrevisError(
            "No locked hero props. Run the Prop Master before the continuity check."
        )
    try:
        locked = read_handoff(path, schema="hero-props")
    except HandoffError as exc:
        raise PrevisError(str(exc)) from exc
    if locked.get("status") != "locked":
        raise PrevisError("The hero prop file is not locked yet.")
    documents, sources = _documents(production_dir)
    findings = _findings(locked, documents)
    contradictions = sum(1 for item in findings if item["kind"] == "contradiction")
    missing = sum(1 for item in findings if item["kind"] == "unstated")
    if findings:
        summary = (
            f"{len(findings)} drift finding(s): {contradictions} contradiction(s) "
            f"and {missing} missing lock(s). "
            "Scenes are checked for forbidden phrases. "
            "A shot that shows a prop is also flagged when a required phrase is missing."
        )
    else:
        summary = "No drift. The checked scenes and shots match the locked props."
    document = {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "verdict": "drift" if findings else "clear",
        "summary": summary,
        "sources": sources,
        "findings": findings,
        "checked_at": now(),
        "draft_method": "offline-deterministic",
        "model": model_name("script-supervisor", "check"),
    }
    if llm is not None:
        document["summary"] = _model_summary(llm, document) or document["summary"]
    save_pair(check_path(production_dir), document, "continuity-check", _markdown(document))
    return document


def _model_summary(llm, document: dict) -> str | None:
    """A short wording pass. The findings themselves stay the offline check."""
    from movie_swarm.previs_common import system_prompt, try_model_json

    drafted = try_model_json(
        llm,
        role="script-supervisor",
        purpose="check",
        system=system_prompt(
            "You are the Script Supervisor. Rewrite the summary in one or two sentences. "
            "Do not add findings. Return {\"summary\": \"...\"}."
        ),
        user=document["summary"],
    )
    if not drafted:
        return None
    text = drafted.get("summary")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _documents(production_dir: Path) -> tuple[list[dict], list[str]]:
    treatment = approved_treatment(production_dir)
    documents = []
    sources = ["treatment/treatment.json"]
    for index, scene in enumerate(treatment.get("scenes") or [], start=1):
        scene_id = str(scene.get("scene_id") or f"s{index:02d}")
        text = " ".join(
            part for part in (scene.get("heading"), scene.get("what_happens")) if part
        )
        documents.append(
            {
                "kind": "scene",
                "scene_id": scene_id,
                "shot_id": None,
                "source": f"treatment scene {scene_id}",
                "text": text,
                "structured_ids": set(),
            }
        )
    for relative in ("storyboard/shot-list.json", "shot-lists/shot-list.json"):
        path = production_dir / relative
        if not path.is_file():
            continue
        sources.append(relative)
        documents.extend(_shots(path, relative))
    return documents, sources


def _shots(path: Path, label: str) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrevisError(f"{label} is not valid JSON. {exc}") from exc
    shots = []
    for shot in data.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        structured = set()
        for item in shot.get("props_in_shot") or []:
            if isinstance(item, dict) and item.get("prop_id"):
                structured.add(str(item["prop_id"]))
            elif isinstance(item, str):
                structured.add(item)
        for vehicle in shot.get("vehicles_in_shot") or []:
            if isinstance(vehicle, str):
                structured.add(vehicle)
        text = " ".join(
            str(shot.get(key) or "")
            for key in ("description", "generation_prompt", "continuity_notes", "framing_notes")
        )
        shot_id = str(shot.get("shot_id") or "")
        shots.append(
            {
                "kind": "shot",
                "scene_id": None,
                "shot_id": shot_id,
                "source": f"{label} {shot_id}".strip(),
                "text": text,
                "structured_ids": structured,
            }
        )
    return shots


def _findings(locked: dict, documents: list[dict]) -> list[dict]:
    findings = []
    for prop in locked.get("props") or []:
        for attribute in prop.get("attributes") or []:
            findings.extend(_attribute_findings(prop, attribute, documents))
    for fact in locked.get("facts") or []:
        findings.extend(_fact_findings(fact, documents))
    for index, finding in enumerate(findings, start=1):
        finding["finding_id"] = f"c-{index:03d}"
    return findings


def _attribute_findings(prop: dict, attribute: dict, documents: list[dict]) -> list[dict]:
    found = []
    label = attribute.get("label") or attribute.get("attribute_id")
    value = attribute.get("value") or ""
    required = [phrase for phrase in attribute.get("required_phrases") or [] if phrase.strip()]
    forbidden = [phrase for phrase in attribute.get("forbidden_phrases") or [] if phrase.strip()]
    must_state = bool(attribute.get("must_be_stated_when_visible")) and bool(required)
    for document in documents:
        text = document["text"]
        visible = _visible(prop, text, document["structured_ids"])
        for phrase in forbidden:
            if _contains(text, phrase) and (visible or document["kind"] == "scene"):
                found.append(
                    _finding(
                        kind="contradiction",
                        severity="critical",
                        prop_id=prop["prop_id"],
                        attribute_id=attribute["attribute_id"],
                        document=document,
                        expected=value,
                        observed=phrase,
                        detail=(
                            f"{prop['name']}: {label} is locked as {value}. "
                            f"{document['source']} says \"{phrase}\"."
                        ),
                    )
                )
        if document["kind"] == "shot" and visible and must_state:
            if not any(_contains(text, phrase) for phrase in required):
                found.append(
                    _finding(
                        kind="unstated",
                        severity="major",
                        prop_id=prop["prop_id"],
                        attribute_id=attribute["attribute_id"],
                        document=document,
                        expected=value,
                        observed="not stated",
                        detail=(
                            f"{prop['name']}: {label} is locked as {value}. "
                            f"{document['source']} shows the prop and does not state it."
                        ),
                    )
                )
    return found


def _fact_findings(fact: dict, documents: list[dict]) -> list[dict]:
    found = []
    blob = "\n".join(document["text"] for document in documents)
    value = fact.get("value") or ""
    for phrase in fact.get("forbidden_phrases") or []:
        if phrase.strip() and _contains(blob, phrase):
            where = _first_hit(documents, phrase)
            found.append(
                _finding(
                    kind="contradiction",
                    severity="critical",
                    fact_id=fact["fact_id"],
                    document=where,
                    expected=value,
                    observed=phrase,
                    detail=(
                        f"{fact['label']} is locked as {value}. "
                        f"{where['source']} says \"{phrase}\"."
                    ),
                )
            )
    required = [phrase for phrase in fact.get("required_phrases") or [] if phrase.strip()]
    if fact.get("must_be_stated") and required and not any(_contains(blob, phrase) for phrase in required):
        anchor = documents[0] if documents else {
            "scene_id": None,
            "shot_id": None,
            "source": "the checked files",
        }
        found.append(
            _finding(
                kind="unstated",
                severity="major",
                fact_id=fact["fact_id"],
                document=anchor,
                expected=value,
                observed="not stated",
                detail=f"{fact['label']} is locked as {value}. None of the checked files state it.",
            )
        )
    return found


def _visible(prop: dict, text: str, structured_ids: set[str]) -> bool:
    if prop.get("prop_id") in structured_ids:
        return True
    haystack = text.casefold()
    names = [prop.get("name") or "", *(prop.get("aliases") or [])]
    return any(len(name) >= 3 and name.casefold() in haystack for name in names)


def _contains(text: str, phrase: str) -> bool:
    return phrase.casefold() in text.casefold()


def _first_hit(documents: list[dict], phrase: str) -> dict:
    for document in documents:
        if _contains(document["text"], phrase):
            return document
    return documents[0] if documents else {"scene_id": None, "shot_id": None, "source": "the checked files"}


def _finding(*, kind, severity, document, expected, observed, detail, prop_id=None, fact_id=None, attribute_id=None) -> dict:
    item = {
        "severity": severity,
        "kind": kind,
        "detail": detail,
        "source": document.get("source") or "",
        "expected": expected,
        "observed": observed,
    }
    if prop_id:
        item["prop_id"] = prop_id
    if fact_id:
        item["fact_id"] = fact_id
    if attribute_id:
        item["attribute_id"] = attribute_id
    if document.get("scene_id"):
        item["scene_id"] = document["scene_id"]
    if document.get("shot_id"):
        item["shot_id"] = document["shot_id"]
    return item


def _markdown(document: dict) -> str:
    lines = [
        "# Continuity check",
        "",
        f"Verdict: {document['verdict']}.",
        "",
        document.get("summary") or "",
        "",
    ]
    if not document["findings"]:
        lines.append("Nothing drifted.")
        lines.append("")
    for finding in document["findings"]:
        lines.append(f"- {finding['detail']}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
