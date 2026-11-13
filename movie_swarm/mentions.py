"""Match a locked name, a prop part, or a wardrobe fact in shot text.

The words come from the lock. This module does not name a film.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


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


# A person, not a film. Used only when the shot does not name a locked character.
_PRONOUNS = (
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "hers",
    "herself",
    "they",
    "them",
    "their",
    "theirs",
    "themselves",
)

_CONTINUATION = ("again", "another", "still")

_STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "than",
    "that",
    "this",
    "these",
    "those",
    "with",
    "from",
    "into",
    "onto",
    "over",
    "under",
    "about",
    "after",
    "before",
    "again",
    "another",
    "still",
    "once",
    "just",
    "only",
    "very",
    "here",
    "there",
    "when",
    "while",
    "where",
    "what",
    "who",
    "whom",
    "whose",
    "which",
    "been",
    "being",
    "have",
    "has",
    "had",
    "was",
    "were",
    "are",
    "is",
    "not",
    "for",
    "his",
    "her",
    "hers",
    "him",
    "she",
    "they",
    "them",
    "their",
    "theirs",
    "you",
    "your",
    "our",
    "its",
}


def has_personal_pronoun(text: str) -> bool:
    """True when the text uses a personal pronoun as its own word."""
    return mentioned(text, list(_PRONOUNS))


def named_characters(text: str, catalog: list[dict]) -> list[str]:
    """Locked people named in text. The catalog supplies the names. Nothing is invented."""
    names = []
    for person in catalog:
        if not isinstance(person, dict) or not person.get("name"):
            continue
        if mentioned(text, character_aliases(person)) and person["name"] not in names:
            names.append(str(person["name"]))
    return names


def character_catalog(treatment: dict, locks: list[dict] | None = None) -> list[dict]:
    """One entry per person, with aliases from the treatment and from the locks."""
    by_name: dict[str, dict] = {}
    for person in (treatment or {}).get("characters") or []:
        if not isinstance(person, dict) or not person.get("name"):
            continue
        by_name[str(person["name"]).casefold()] = {
            "name": str(person["name"]),
            "aliases": list(person.get("aliases") or []),
        }
    for lock in locks or []:
        if not isinstance(lock, dict):
            continue
        for character in lock.get("characters") or []:
            if not isinstance(character, dict) or not character.get("name"):
                continue
            key = str(character["name"]).casefold()
            current = by_name.setdefault(key, {"name": str(character["name"]), "aliases": []})
            for alias in character.get("aliases") or []:
                if alias not in current["aliases"]:
                    current["aliases"].append(alias)
    return list(by_name.values())


def resolve_scene_characters(shots: list[str], catalog: list[dict], heading: str = "") -> list[dict]:
    """Carry a pronoun to one locked character, or mark the shot for review.

    A scene with exactly one locked character gives that person to a shot that
    only uses a pronoun. When more than one person is named, the pronoun uses
    the most recent shot that named exactly one, and only when nobody else was
    named in between. Anything else is left untagged.
    """
    named = [named_characters(text, catalog) for text in shots]
    heading_names = named_characters(heading, catalog) if heading else []
    everyone: list[str] = []
    for group in (heading_names, *named):
        for name in group:
            if name not in everyone:
                everyone.append(name)
    results = []
    if len(everyone) == 1:
        sole = everyone[0]
        for names, text in zip(named, shots):
            if names:
                results.append({"names": names, "inherited": False, "review": ""})
            elif has_personal_pronoun(text):
                results.append({"names": [sole], "inherited": True, "review": ""})
            else:
                results.append({"names": [], "inherited": False, "review": ""})
        return results
    recent = heading_names[0] if len(heading_names) == 1 else None
    if len(heading_names) > 1:
        recent = None
    for names, text in zip(named, shots):
        if len(names) == 1:
            recent = names[0]
            results.append({"names": names, "inherited": False, "review": ""})
        elif len(names) > 1:
            recent = None
            results.append({"names": names, "inherited": False, "review": ""})
        elif has_personal_pronoun(text) and recent:
            results.append({"names": [recent], "inherited": True, "review": ""})
        elif has_personal_pronoun(text):
            results.append(
                {
                    "names": [],
                    "inherited": False,
                    "review": "A pronoun does not name one character. Needs review.",
                }
            )
        else:
            results.append({"names": [], "inherited": False, "review": ""})
    return results


def _stem(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    if word.endswith("ing") and len(word) > 5:
        return word[:-3]
    if word.endswith("ed") and len(word) > 4:
        return word[:-2]
    return word


def _verb_stems(text: str) -> set[str]:
    stems = set()
    for word in re.findall(r"[a-z]+", text.casefold()):
        if word in _STOP or len(word) < 4:
            continue
        verbish = word.endswith("ing") or word.endswith("ed") or (word.endswith("s") and not word.endswith("ss"))
        if verbish:
            stems.add(_stem(word))
    return stems


def action_continues(previous: str, current: str) -> bool:
    """True when this shot keeps going on the previous shot's action.

    Continuation words are generic. A shared action verb is a word in this
    shot with a verb ending whose stem is also in the previous shot.
    The storyboard does not require this for a carry. A trace is not a
    reason to stop, and the stop rules are absence, a different subject,
    a tight view of another object, and a line with no picture.
    """
    if mentioned(current, list(_CONTINUATION)):
        return True
    current_stems = _verb_stems(current)
    if not current_stems:
        return False
    previous_stems = set()
    for word in re.findall(r"[a-z]+", previous.casefold()):
        if word in _STOP or len(word) < 4:
            continue
        previous_stems.add(_stem(word))
    return bool(current_stems & previous_stems)


def load_kind_nouns(production_dir: str | Path | None = None) -> dict[str, list[str]]:
    """Kind-level nouns from config, with a film file replacing any kind it names."""
    from movie_swarm.paths import repo_root

    nouns = _read_kind_nouns(repo_root() / "config" / "kind-nouns.json")
    if production_dir is not None:
        override = Path(production_dir) / "props" / "kind-nouns.json"
        if override.is_file():
            for kind, words in _read_kind_nouns(override).items():
                nouns[kind] = words
    return nouns


# Coordinating conjunctions that start another clause. The config file is the
# list the storyboard and the continuity check both read. This is the fallback
# when that file does not name ``closed_clause``.
_DEFAULT_CONJUNCTIONS = ("and", "but", "or", "nor", "so", "yet")
# Marks a part can leave behind. The config file is the list. This is the
# fallback when that file does not name ``trace_nouns``.
_DEFAULT_TRACE_NOUNS = (
    "tracks",
    "track",
    "marks",
    "prints",
    "footprints",
    "ruts",
    "skid marks",
    "tread marks",
    "trail",
    "imprint",
)
_PERFECT_AUX = {"has", "have", "had"}


def load_absence_phrases(production_dir: str | Path | None = None) -> dict:
    """Phrases that name a prop without putting it in the frame.

    ``{prop}`` stands for a name, alias, part, or kind noun. A film file
    replaces any list it includes. An empty list clears that list.
    A phrase that starts with leave, abandon, walk, or look also counts in
    the perfect: has, have, and had plus the participle. The same expansion
    applies to the ambiguous list, so "has left the prop in" stays a review.
    ``conjunctions`` are the words that start a new clause after a perfect
    absence. ``trace_nouns`` are marks a part leaves behind. A film file
    replaces a phrase list or the conjunctions. It adds trace nouns to the
    shared list, and an empty trace list adds nothing. The storyboard review,
    the frame classifier, and the continuity check all read this dict,
    including a film's ``props/absence-phrases.json``.
    """
    from movie_swarm.paths import repo_root

    loaded = _read_absence_file(repo_root() / "config" / "absence-phrases.json")
    phrases = list(loaded.get("phrases") or [])
    ambiguous = list(loaded.get("ambiguous") or [])
    if "conjunctions" in loaded:
        conjunctions = list(loaded["conjunctions"])
    else:
        conjunctions = list(_DEFAULT_CONJUNCTIONS)
    if "trace_nouns" in loaded:
        trace_nouns = list(loaded["trace_nouns"])
    else:
        trace_nouns = list(_DEFAULT_TRACE_NOUNS)
    if production_dir is not None:
        override = Path(production_dir) / "props" / "absence-phrases.json"
        if override.is_file():
            over = _read_absence_file(override)
            if "phrases" in over:
                phrases = list(over["phrases"])
            if "ambiguous" in over:
                ambiguous = list(over["ambiguous"])
            if "conjunctions" in over:
                conjunctions = list(over["conjunctions"])
            if "trace_nouns" in over:
                trace_nouns = _extend_terms(trace_nouns, over["trace_nouns"])
    return {
        "phrases": _with_perfect(phrases),
        "ambiguous": _with_perfect(ambiguous),
        "conjunctions": conjunctions,
        "trace_nouns": trace_nouns,
    }


# Generic English for the absence verbs. A film's own nouns do not belong here.
# The participle is what follows has, have, or had.
_PARTICIPLE = {
    "leave": "left",
    "leaves": "left",
    "leaving": "left",
    "left": "left",
    "abandon": "abandoned",
    "abandons": "abandoned",
    "abandoning": "abandoned",
    "abandoned": "abandoned",
    "walk": "walked",
    "walks": "walked",
    "walking": "walked",
    "walked": "walked",
    "look": "looked",
    "looks": "looked",
    "looking": "looked",
    "looked": "looked",
}


def _with_perfect(phrases: list[str]) -> list[str]:
    """Add has/have/had plus the participle in front of a known absence verb."""
    expanded: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        text = " ".join(str(value).split())
        key = text.casefold()
        if not text or key in seen:
            return
        seen.add(key)
        expanded.append(text)

    for phrase in phrases:
        add(phrase)
        words = phrase.split()
        if not words:
            continue
        participle = _PARTICIPLE.get(words[0].casefold())
        if not participle:
            continue
        rest = " ".join(words[1:])
        for auxiliary in ("has", "have", "had"):
            add(f"{auxiliary} {participle} {rest}".strip())
    return expanded


def _read_kind_nouns(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    kinds = data.get("kinds") if isinstance(data, dict) else None
    if not isinstance(kinds, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    for kind, words in kinds.items():
        if not isinstance(words, list):
            continue
        kept = []
        for word in words:
            text = " ".join(str(word).split())
            if len(text) >= 3 and text.casefold() not in {item.casefold() for item in kept}:
                kept.append(text)
        if kept:
            cleaned[str(kind).strip().casefold()] = kept
    return cleaned


def generic_nouns_for(prop: dict, props: list[dict], kind_nouns: dict[str, list[str]] | None = None) -> list[str]:
    """Nouns that can mean this prop when they are not shared with another lock.

    A lock's own ``generic_nouns`` are included. The kind word and the kind
    list are included only when this is the only lock of that kind.
    """
    labels: list[str] = []

    def add(value: str) -> None:
        text = " ".join(str(value).split())
        if len(text) < 3:
            return
        if text.casefold() not in {item.casefold() for item in labels}:
            labels.append(text)

    for noun in prop.get("generic_nouns") or []:
        add(str(noun))
    kind = str(prop.get("kind") or "").strip().casefold()
    if not kind:
        return labels
    same = [item for item in props if str(item.get("kind") or "").strip().casefold() == kind]
    if len(same) != 1:
        return labels
    add(kind)
    for noun in (kind_nouns or {}).get(kind) or []:
        add(str(noun))
    return labels


def _trace_nouns(absence: dict | None) -> list[str]:
    """Trace nouns from the dict the caller already loaded, or the shared file."""
    if isinstance(absence, dict) and "trace_nouns" in absence:
        return [str(word) for word in absence.get("trace_nouns") or []]
    loaded = load_absence_phrases()
    if "trace_nouns" in loaded:
        return list(loaded["trace_nouns"])
    return list(_DEFAULT_TRACE_NOUNS)


def _trace_follows(text: str, end: int, nouns: list[str]) -> bool:
    """True when a trace noun sits against the end of a label match.

    A space or a hyphen joins them, including a hyphen with spaces around it.
    ``tracks`` wins over ``track`` because the longer noun is tried first.
    """
    if not nouns or end >= len(text):
        return False
    rest = text[end:]
    if rest[0] == "-":
        rest = rest[1:].lstrip()
    elif rest[0].isspace():
        rest = rest.lstrip()
        if rest.startswith("-"):
            rest = rest[1:].lstrip()
    else:
        return False
    if not rest:
        return False
    for noun in sorted(nouns, key=len, reverse=True):
        if re.match(rf"{_label_pattern(noun)}(?!\w)", rest, re.I):
            return True
    return False


def _has_real_mention(text: str, labels: list[str], nouns: list[str]) -> bool:
    """True when a label stands as its own words and is not a trace compound."""
    if not text:
        return False
    for label in labels:
        cleaned = " ".join(str(label).split())
        if len(cleaned) < 2:
            continue
        pattern = rf"(?<!\w){_label_pattern(cleaned)}(?!\w)"
        for match in re.finditer(pattern, text, re.I):
            if not _trace_follows(text, match.end(), nouns):
                return True
    return False


def joined_to_trace(text: str, end: int, absence: dict | None = None) -> bool:
    """True when a trace noun is joined to this match by a space or a hyphen."""
    return _trace_follows(text, end, _trace_nouns(absence))


def named_phrase(text: str, phrases: list[str], absence: dict | None = None) -> bool:
    """True when a phrase is present and is not a trace a part leaves behind.

    The trace nouns are the shared phrase file, or the list already on
    ``absence`` when the caller loaded a film's file.
    """
    return _has_real_mention(text, phrases, _trace_nouns(absence))


def prop_mentioned(
    prop: dict,
    text: str,
    props: list[dict],
    kind_nouns: dict[str, list[str]] | None = None,
    absence: dict | None = None,
) -> bool:
    """True when the text names this prop, including an unshared generic noun.

    A label immediately followed by a trace noun is a mark left behind. It
    does not name the prop. ``absence`` is the shared phrase file, including
    a film's added nouns.
    """
    nouns = _trace_nouns(absence)
    if _has_real_mention(text, prop_labels(prop), nouns):
        return True
    for noun in generic_nouns_for(prop, props, kind_nouns):
        if not _has_real_mention(text, [noun], nouns):
            continue
        owners = [
            item
            for item in props
            if any(noun.casefold() == label.casefold() for label in generic_nouns_for(item, props, kind_nouns))
        ]
        if len(owners) == 1 and owners[0] is prop:
            return True
        if len(owners) == 1 and str(owners[0].get("prop_id") or "") == str(prop.get("prop_id") or "") and prop.get("prop_id"):
            return True
    return False


def _read_absence_file(path: Path) -> dict:
    """Return the lists a file actually includes. A missing file returns nothing."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    found = {}
    for key in ("phrases", "ambiguous"):
        if key not in data:
            continue
        words = data.get(key)
        kept = []
        if isinstance(words, list):
            for word in words:
                text = " ".join(str(word).split())
                if "{prop}" not in text or len(text) < 3:
                    continue
                if text.casefold() not in {item.casefold() for item in kept}:
                    kept.append(text)
        found[key] = kept
    clause = data.get("closed_clause")
    if isinstance(clause, dict) and "conjunctions" in clause:
        kept = []
        words = clause.get("conjunctions")
        if isinstance(words, list):
            for word in words:
                text = " ".join(str(word).split())
                if not text:
                    continue
                if text.casefold() not in {item.casefold() for item in kept}:
                    kept.append(text)
        found["conjunctions"] = kept
    if "trace_nouns" in data:
        found["trace_nouns"] = _term_list(data.get("trace_nouns"), minimum=3)
    return found


def _term_list(words, *, minimum: int) -> list[str]:
    kept = []
    if not isinstance(words, list):
        return kept
    for word in words:
        text = " ".join(str(word).split())
        if len(text) < minimum:
            continue
        if text.casefold() not in {item.casefold() for item in kept}:
            kept.append(text)
    return kept


def _extend_terms(base: list[str], extra: list[str]) -> list[str]:
    """Shared nouns first, then any film noun that is not already there."""
    merged = list(base)
    seen = {item.casefold() for item in merged}
    for item in extra:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _match_labels(prop: dict, props: list[dict], kind_nouns: dict[str, list[str]] | None) -> list[str]:
    labels = prop_labels(prop)
    for noun in generic_nouns_for(prop, props, kind_nouns):
        if noun.casefold() not in {item.casefold() for item in labels}:
            labels.append(noun)
    return labels


def _label_pattern(label: str) -> str:
    return re.escape(" ".join(label.split())).replace(r"\ ", r"[\s-]+")


def _covering_span(text: str, template: str, label: str, start: int, end: int) -> tuple[int, int] | None:
    """The template match that contains this label hit, or None."""
    if "{prop}" not in template:
        return None
    phrase = " ".join(template.replace("{prop}", label).split())
    pattern = rf"(?<!\w){_label_pattern(phrase)}(?!\w)"
    for match in re.finditer(pattern, text, re.I):
        if match.start() <= start and match.end() >= end:
            return match.start(), match.end()
    return None


def _phrase_covers(text: str, template: str, label: str, start: int, end: int) -> bool:
    return _covering_span(text, template, label, start, end) is not None


def _is_clause_punct(char: str) -> bool:
    return not (char.isalnum() or char.isspace() or char == "_")


def _tail_is_closed(tail: str, conjunctions: set[str]) -> bool:
    """True when nothing after the object continues the same clause.

    The end of the text, punctuation, or a conjunction that starts the next
    clause all close it. A word such as "in" or "running" does not.
    """
    index = 0
    length = len(tail)
    while index < length and (tail[index].isspace() or _is_clause_punct(tail[index])):
        index += 1
    if index >= length:
        return True
    found = re.match(r"[A-Za-z]+", tail[index:])
    if not found:
        return False
    return found.group(0).casefold() in conjunctions


def _match_is_perfect(text: str, template: str, match_start: int) -> bool:
    words = template.split()
    if words and words[0].casefold() in _PERFECT_AUX:
        return True
    before = re.search(r"([A-Za-z]+)\W*$", text[:match_start])
    return bool(before and before.group(1).casefold() in _PERFECT_AUX)


def _perfect_tail_closed(
    text: str,
    label: str,
    start: int,
    end: int,
    phrases: list[str],
    conjunctions: set[str],
) -> bool:
    """True when has, have, or had plus an absence phrase ends the clause."""
    for template in phrases:
        span = _covering_span(text, template, label, start, end)
        if span is None:
            continue
        match_start, match_end = span
        if not _match_is_perfect(text, template, match_start):
            continue
        if _tail_is_closed(text[match_end:], conjunctions):
            return True
    return False


def _ambiguous_covers(text: str, template: str, label: str, start: int, end: int) -> bool:
    """An ambiguous continuation counts only inside the same clause as the object."""
    span = _covering_span(text, template, label, start, end)
    if span is None:
        return False
    between = text[end:span[1]]
    return not any(_is_clause_punct(char) and char not in "-'" for char in between)


def _span_state(
    text: str,
    label: str,
    start: int,
    end: int,
    phrases: list[str],
    ambiguous: list[str],
    conjunctions: set[str],
) -> str:
    """One label hit.

    A perfect-tense absence with nothing after the object is absence. Punctuation,
    or a conjunction that starts the next clause, is still nothing. An ambiguous
    continuation in the same clause, such as "in", "on", "running", or "there",
    is a review. The storyboard review reads this same state.
    """
    if _perfect_tail_closed(text, label, start, end, phrases, conjunctions):
        return "absent"
    if any(_ambiguous_covers(text, template, label, start, end) for template in ambiguous):
        return "ambiguous"
    if any(_phrase_covers(text, template, label, start, end) for template in phrases):
        return "absent"
    return "in-frame"


def _mention_states(
    text: str,
    spans: list[tuple[int, int, str]],
    phrases: list[str],
    ambiguous: list[str],
    conjunctions: set[str],
) -> list[str]:
    """One state per mention. Overlapping labels are the same mention.

    A longer label such as "the bike" sits on the same word as the alias "bike".
    The absence template already includes "the", so the longer label does not
    match it and would otherwise look like a second, in-frame mention.
    """
    ordered = sorted(spans, key=lambda item: (item[0], item[1]))
    clusters: list[dict] = []
    for start, end, label in ordered:
        if clusters and start < clusters[-1]["end"]:
            clusters[-1]["hits"].append((start, end, label))
            clusters[-1]["end"] = max(clusters[-1]["end"], end)
        else:
            clusters.append({"end": end, "hits": [(start, end, label)]})
    states = []
    for cluster in clusters:
        local = [
            _span_state(text, label, start, end, phrases, ambiguous, conjunctions)
            for start, end, label in cluster["hits"]
        ]
        if "ambiguous" in local:
            states.append("ambiguous")
        elif "absent" in local:
            states.append("absent")
        else:
            states.append("in-frame")
    return states


def prop_frame_state(
    prop: dict,
    text: str,
    props: list[dict],
    kind_nouns: dict[str, list[str]] | None = None,
    absence: dict | None = None,
) -> str:
    """How a named prop sits in the shot: in-frame, absent, ambiguous, or unnamed.

    Every mention inside an absence phrase keeps the prop out of the frame.
    A perfect-tense absence with nothing after the object is absent. Punctuation,
    or a conjunction from the shared phrase file, still counts as nothing.
    An ambiguous continuation in the same clause, or a mix of an absence phrase
    and a bare mention, is not guessed. A label immediately followed by a trace
    noun is not a mention and not an absence. It does not put the prop in
    frame, and it does not block a carry from the previous shot. Overlapping
    labels of one mention are one decision. The storyboard review and the
    continuity check use this same result.
    """
    nouns = _trace_nouns(absence)
    if not prop_mentioned(prop, text, props, kind_nouns, absence):
        return "unnamed"
    phrases = list((absence or {}).get("phrases") or [])
    ambiguous = list((absence or {}).get("ambiguous") or [])
    if isinstance(absence, dict) and "conjunctions" in absence:
        conjunctions = {str(word).casefold() for word in absence.get("conjunctions") or []}
    else:
        conjunctions = {word.casefold() for word in _DEFAULT_CONJUNCTIONS}
    spans = []
    for label in _match_labels(prop, props, kind_nouns):
        for match in re.finditer(rf"(?<!\w){_label_pattern(label)}(?!\w)", text, re.I):
            if _trace_follows(text, match.end(), nouns):
                continue
            spans.append((match.start(), match.end(), label))
    if not spans:
        return "unnamed"
    states = _mention_states(text, spans, phrases, ambiguous, conjunctions)
    if any(state == "ambiguous" for state in states):
        return "ambiguous"
    if states and all(state == "absent" for state in states):
        return "absent"
    if any(state == "absent" for state in states) and any(state == "in-frame" for state in states):
        return "ambiguous"
    return "in-frame"


def prop_shown(
    prop: dict,
    text: str,
    structured_ids: set[str] | list[str],
    props: list[dict],
    kind_nouns: dict[str, list[str]] | None = None,
    absence: dict | None = None,
) -> bool:
    """True when the storyboard tag or the absence rules put this prop in frame.

    A tag is the storyboard's decision, including a prop carried from the
    previous shot. The picture line is what the absence phrases read. A name
    in that line is not enough, and a later note that says "prop" is not a
    second detector.
    """
    identity = str(prop.get("prop_id") or "")
    ids = {str(item) for item in structured_ids}
    if identity and identity in ids:
        return True
    labels = prop_labels(prop)
    for item in ids:
        if mentioned(item, labels):
            return True
    return prop_frame_state(prop, text, props or [prop], kind_nouns, absence) == "in-frame"


_NON_VISUAL_CUE = re.compile(
    r"\b(fades?|fading|silence|silent|holds?|holding|black|titles?|credits?)\b",
    re.I,
)
# Stems _verb_stems actually produces. "fades" ends in "es", so the stem is "fad".
# "seconds" also ends in "s". A hold names a length. That word is not an action.
_NON_VISUAL_STEMS = {"fad", "hold", "silent", "title", "credit", "black"}
_NOT_ACTION_STEMS = {"second", "minute", "hour", "moment"}


def no_visible_action(text: str) -> bool:
    """True when every sentence is sound, a fade, a hold, black, or a title.

    A sentence that also has an action verb, such as riding while a fade
    starts, is still a picture.
    """
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part.strip()]
    if not parts:
        return False
    return all(_sentence_has_no_picture(part) for part in parts)


def _sentence_has_no_picture(sentence: str) -> bool:
    if not _NON_VISUAL_CUE.search(sentence):
        return False
    visual = {
        stem
        for stem in _verb_stems(sentence)
        if stem not in _NON_VISUAL_STEMS and stem not in _NOT_ACTION_STEMS
    }
    return not visual


_PREVIS_TEXT_FILES = (
    "storyboard/storyboard.json",
    "storyboard/storyboard.md",
    "storyboard/shot-list.json",
    "lighting/lighting-plan.json",
    "lighting/lighting-plan.md",
    "schedule/shooting-schedule.json",
    "schedule/shooting-schedule.md",
    "stunts/action-breakdown.json",
    "stunts/action-breakdown.md",
    "camera/camera-package.json",
    "camera/camera-package.md",
    "grip/grip-plan.json",
    "grip/grip-plan.md",
    "props/hero-props.json",
    "props/hero-props.md",
    "wardrobe/costume-lock.json",
    "wardrobe/costume-lock.md",
    "makeup/makeup-lock.json",
    "makeup/makeup-lock.md",
    "vfx/vfx-breakdown.json",
    "vfx/vfx-breakdown.md",
    "graphics/research.json",
    "graphics/research.md",
    "graphics/brand-guide.json",
    "graphics/brand-guide.md",
)


def previs_advertising_hits(production_dir: str | Path) -> list[dict]:
    """Banned placement phrases in generated previs text.

    The continuity report is not scanned. A finding that quotes a phrase would
    otherwise flag itself.
    """
    root = Path(production_dir)
    hits = []
    for relative in _PREVIS_TEXT_FILES:
        path = root / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for phrase in advertising_phrases(text):
            hits.append({"path": relative, "phrase": phrase})
    return hits


def story_purpose_line(label: str) -> str:
    """Why a hero prop is in the frame. Story purpose, with no placement slang."""
    name = " ".join(str(label or "").split()).strip() or "This object"
    if advertising_phrases(name):
        name = "This object"
    return f"{name} stays in the frame for the story this scene is already telling."
