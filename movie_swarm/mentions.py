"""Match a locked name, a prop part, or a wardrobe fact in shot text.

The words come from the lock. This module does not name a film.
"""

from __future__ import annotations

import re


# Phrases the engine must not write when a hero prop is simply in frame.
# A production's own sentence is kept. These are the engine's words.
ADVERTISING_PHRASES = (
    "featured product",
    "product shot",
    "product placement",
    "hero shot of the product",
    "advertisement",
    "advertising",
    "advert",
    "sponsor",
    "sponsorship",
    "commercial",
)

_GARMENTS = (
    "shirts",
    "shirt",
    "vests",
    "vest",
    "pants",
    "coats",
    "coat",
    "boots",
    "boot",
    "goggles",
    "goggle",
    "hats",
    "hat",
    "jackets",
    "jacket",
    "dresses",
    "dress",
    "scarves",
    "scarf",
    "helmets",
    "helmet",
    "gloves",
    "glove",
    "skirts",
    "skirt",
    "uniform",
    "robe",
    "trousers",
    "jeans",
    "shoes",
    "shoe",
    "belt",
    "gown",
    "cape",
    "sweater",
    "blouse",
    "shorts",
    "tie",
    "cloak",
    "armor",
)


def mentioned(text: str, phrases: list[str]) -> bool:
    """True when any phrase stands as its own words in text.

    A hyphen and a space count as the same gap, so a part written either way
    still matches. A shorter word inside a longer one does not.
    """
    if not text:
        return False
    for phrase in phrases:
        cleaned = " ".join(str(phrase).split())
        if len(cleaned) < 2:
            continue
        flexible = re.escape(cleaned).replace(r"\ ", r"[\s-]+")
        if re.search(rf"(?<!\w){flexible}(?!\w)", text, re.I):
            return True
    return False


def character_aliases(character: dict) -> list[str]:
    """Full name, first name, surname, screenplay cue forms, and explicit aliases.

    A screenplay cue is the name in capitals, often the surname alone. Matching
    ignores case, so the capital form is the same word as the mixed-case one.
    Explicit aliases on the lock are added as written.
    """
    names: list[str] = []

    def add(value: str) -> None:
        text = " ".join(str(value).split())
        if len(text) < 2:
            return
        if text.casefold() not in {item.casefold() for item in names}:
            names.append(text)

    full = str(character.get("name") or "").strip()
    if full:
        add(full)
        parts = full.split()
        if len(parts) >= 2:
            add(parts[0])
            add(parts[-1])
        add(full.upper())
        if len(parts) >= 2:
            add(parts[-1].upper())
            add(parts[0].upper())
    for alias in character.get("aliases") or []:
        add(str(alias))
    return names


def prop_labels(prop: dict) -> list[str]:
    """Name, id, aliases, and optional parts. Parts are how a detail shot names the prop."""
    labels: list[str] = []

    def add(value: str) -> None:
        text = " ".join(str(value).split())
        if len(text) < 2:
            return
        if text.casefold() not in {item.casefold() for item in labels}:
            labels.append(text)

    add(str(prop.get("name") or ""))
    add(str(prop.get("prop_id") or ""))
    for key in ("aliases", "parts"):
        for item in prop.get(key) or []:
            add(str(item))
    return labels


def advertising_phrases(text: str) -> list[str]:
    """Engine wording that frames a hero prop as an advertisement."""
    folded = text.casefold()
    found = []
    for phrase in ADVERTISING_PHRASES:
        if phrase in folded and phrase not in found:
            found.append(phrase)
    return found


def wardrobe_key_facts(phrase: str) -> list[str]:
    """Short garment facts from a long wardrobe paragraph.

    A phrase of eight words or fewer is already a fact. A longer paragraph is
    split into the garment clauses it names. Nothing is added that the
    paragraph did not say.
    """
    text = " ".join(str(phrase).split()).strip()
    if not text:
        return []
    if len(text.split()) <= 8:
        return [text.rstrip(".")]
    facts: list[str] = []
    for chunk in re.split(r"[.;]", text):
        for piece in re.split(r",|\band\b", chunk):
            cleaned = piece.strip(" ,")
            cleaned = re.sub(
                r"^(?:he|she|they)\s+(?:wears|has|is wearing)\s+",
                "",
                cleaned,
                flags=re.I,
            )
            cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned, flags=re.I)
            cleaned = re.split(
                r"\b(?:when|while|that have|that has|from)\b",
                cleaned,
                maxsplit=1,
                flags=re.I,
            )[0]
            cleaned = cleaned.strip(" ,.")
            if not cleaned or len(cleaned.split()) > 8:
                continue
            if re.fullmatch(r"no\s+\w+", cleaned, re.I):
                _add_fact(facts, cleaned)
                continue
            if any(re.search(rf"\b{word}\b", cleaned, re.I) for word in _GARMENTS):
                _add_fact(facts, cleaned)
    return facts


def phrases_stated(text: str, phrases: list[str], *, lock_reference: str = "") -> bool:
    """True when the shot states the lock.

    A short required phrase must appear. A long wardrobe paragraph is stated
    when every key fact appears, or when the shot carries ``wardrobe lock: <id>``.
    Prop checks pass an empty lock reference, so they stay exact.
    """
    cleaned = [str(phrase).strip() for phrase in phrases if str(phrase).strip()]
    if not cleaned:
        return True
    if any(phrase.casefold() in text.casefold() for phrase in cleaned):
        return True
    reference = str(lock_reference or "").strip()
    if reference and re.search(rf"(?i)(?<!\w)wardrobe lock:\s*{re.escape(reference)}(?!\w)", text):
        return True
    if not reference:
        return False
    facts: list[str] = []
    saw_long = False
    for phrase in cleaned:
        if len(phrase.split()) <= 8:
            return False
        saw_long = True
        derived = wardrobe_key_facts(phrase)
        if not derived:
            return False
        facts.extend(derived)
    return bool(saw_long and facts and all(fact.casefold() in text.casefold() for fact in facts))


def character_prompt_line(character: dict, text: str, *, allow_key_facts: bool) -> str:
    """The wardrobe words a prompt still needs.

    Short required phrases are copied. A long paragraph becomes its key facts.
    When those facts cannot be derived, a ``wardrobe lock: <id>`` reference is
    used instead of pasting the whole paragraph.
    """
    lines: list[str] = []
    character_id = str(character.get("character_id") or "").strip()
    for attribute in character.get("attributes") or []:
        if not isinstance(attribute, dict) or not attribute.get("must_be_stated_when_visible"):
            continue
        required = [str(phrase).strip() for phrase in attribute.get("required_phrases") or [] if str(phrase).strip()]
        if not required or phrases_stated(text, required, lock_reference=character_id if allow_key_facts else ""):
            continue
        added = False
        for phrase in required:
            if len(phrase.split()) <= 8 or not allow_key_facts:
                _add_fact(lines, phrase.rstrip(".") + ".")
                added = True
                continue
            missing = [fact for fact in wardrobe_key_facts(phrase) if fact.casefold() not in text.casefold()]
            if missing:
                for fact in missing:
                    _add_fact(lines, fact.rstrip(".") + ".")
                added = True
        if not added and allow_key_facts and character_id:
            _add_fact(lines, f"Wardrobe lock: {character_id}.")
    return " ".join(lines)


def faithful_spec(spec: str) -> str:
    """The locked spec, unchanged.

    A prompt may repeat this text. It does not add a fact the spec did not state.
    """
    return " ".join(str(spec or "").split()).strip()


def _add_fact(facts: list[str], fact: str) -> None:
    if fact and fact.casefold() not in {item.casefold() for item in facts}:
        facts.append(fact)
