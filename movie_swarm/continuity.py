"""Put a production's locked phrases into a generation prompt.

The phrases come from the production's prop file. This module does not
know which film it is reading. A prop that is not in the shot is left alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PromptEnforcement:
    """What happened to one prompt before it could be sent."""

    prompt: str
    added: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    props_in_frame: list[str] = field(default_factory=list)


def load_prop_lock(production_dir: str | Path) -> dict | None:
    """The locked prop file, or the production's definitions when that is all there is."""
    folder = Path(production_dir)
    for relative in ("props/hero-props.json", "props/prop-definitions.json"):
        path = folder / relative
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("props"):
            return data
    return None


def enforce_prompt(prompt: str, props_in_frame, lock: dict | None) -> PromptEnforcement:
    """Add a required phrase when that prop is in frame. Record a forbidden phrase."""
    text = (prompt or "").strip()
    labels = _labels(props_in_frame)
    if not lock:
        return PromptEnforcement(prompt=text)
    added: list[str] = []
    blocked: list[str] = []
    seen: list[str] = []
    for prop in lock.get("props") or []:
        if not isinstance(prop, dict):
            continue
        if not _in_frame(prop, labels, text):
            continue
        name = str(prop.get("name") or prop.get("prop_id") or "prop")
        seen.append(name)
        for attribute in prop.get("attributes") or []:
            if not isinstance(attribute, dict):
                continue
            required = [phrase for phrase in attribute.get("required_phrases") or [] if str(phrase).strip()]
            forbidden = [phrase for phrase in attribute.get("forbidden_phrases") or [] if str(phrase).strip()]
            for phrase in forbidden:
                if _contains(text, phrase) and phrase not in blocked:
                    blocked.append(phrase)
            must_state = bool(attribute.get("must_be_stated_when_visible")) and bool(required)
            if must_state and not any(_contains(text, phrase) for phrase in required):
                phrase = required[0]
                text = f"{text} {phrase}".strip() if text else phrase
                added.append(phrase)
    return PromptEnforcement(prompt=text, added=added, blocked=blocked, props_in_frame=seen)


def expected_phrases(prompt: str, props_in_frame, lock: dict | None) -> list[str]:
    """The required phrases a later picture check would look for."""
    if not lock:
        return []
    enforced = enforce_prompt(prompt, props_in_frame, lock)
    phrases = list(enforced.added)
    labels = _labels(props_in_frame)
    for prop in lock.get("props") or []:
        if not isinstance(prop, dict) or not _in_frame(prop, labels, enforced.prompt):
            continue
        for attribute in prop.get("attributes") or []:
            if not isinstance(attribute, dict):
                continue
            if not attribute.get("must_be_stated_when_visible"):
                continue
            for phrase in attribute.get("required_phrases") or []:
                if str(phrase).strip() and phrase not in phrases and _contains(enforced.prompt, phrase):
                    phrases.append(phrase)
    return phrases


def _labels(props_in_frame) -> list[str]:
    labels = []
    for item in props_in_frame or []:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            for key in ("prop_id", "name", "label"):
                value = item.get(key)
                if value:
                    labels.append(str(value))
    return labels


def _names(prop: dict) -> list[str]:
    names = [prop.get("prop_id") or "", prop.get("name") or "", *(prop.get("aliases") or [])]
    return [str(name) for name in names if str(name).strip()]


def _in_frame(prop: dict, labels: list[str], prompt: str) -> bool:
    names = _names(prop)
    folded = {name.casefold() for name in names}
    for label in labels:
        haystack = label.casefold()
        if haystack in folded:
            return True
        if any(len(name) >= 3 and name.casefold() in haystack for name in names):
            return True
    return any(len(name) >= 3 and name.casefold() in prompt.casefold() for name in names)


def _contains(text: str, phrase: str) -> bool:
    return phrase.casefold() in text.casefold()
