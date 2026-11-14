"""Choose the reference images for one picture call.

The paths come from the film folder. This module does not name a film.
A quote reads the files and does not upload them. A live call uploads
later, through the fal client, and only the images this module kept.

Priority, first image of each subject before a second image from any
subject:

1. Character face, from ``characters/character-lock.json`` when that file
   is locked. A locked costume entry's ``reference_images`` fill a
   character who has no face photo there.
2. Location, from a locked ``locations/location-lock.json``. An explicit
   location on the shot wins. Otherwise a location whose ``scene_ids``
   include the shot's scene, or the scene manifest's location name.
3. Prop, from a locked ``props/hero-props.json`` (or locked prop
   definitions) that the shot already names.
4. The shot's own ``reference_images``, when the path was not already
   chosen.

The cap is the model's ``max_images``. Seedance reference-to-video
publishes 9. A missing file, a file outside the film folder, an
unsupported suffix, or a file over the published size is logged and
skipped. The call continues with whatever remains.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from movie_swarm.continuity import load_prop_lock
from movie_swarm.mentions import character_aliases, mentioned, prop_labels
from movie_swarm.money import as_money, money_number


logger = logging.getLogger("movie_swarm.references")

PRIORITY = ("character", "location", "prop", "shot")
ROLE = {
    "character": "character face",
    "location": "location",
    "prop": "prop",
    "shot": "shot image",
}
_TOKEN = re.compile(r"@Image(\d+)", re.I)
_DEFAULT_FORMATS = (
    "jpeg",
    "jpg",
    "png",
    "webp",
    "bmp",
    "tif",
    "tiff",
    "gif",
    "heic",
    "heif",
)
_DEFAULT_MAX_IMAGES = 9
_DEFAULT_MAX_BYTES = 30 * 1024 * 1024


@dataclass
class ChosenReference:
    """One image that would be sent, already inside the cap."""

    tier: str
    role: str
    label: str
    token: str
    index: int
    raw: str
    relative: str
    path: Path | None
    url: str | None
    size: int | None
    mtime_ns: int | None


@dataclass
class PreparedReferences:
    """The images for one shot, and the prompt with @Image tokens filled in."""

    chosen: list[ChosenReference] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    spec: dict | None = None
    prompt: str = ""

    @property
    def endpoint(self) -> str | None:
        if self.chosen and self.spec:
            return str(self.spec["endpoint"])
        return None

    @property
    def per_second(self):
        if self.chosen and self.spec and self.spec.get("usd_per_second") not in (None, ""):
            return as_money(self.spec["usd_per_second"])
        return None


@dataclass
class _Image:
    raw: str
    relative: str
    path: Path | None
    url: str | None
    size: int | None
    mtime_ns: int | None
    key: str


@dataclass
class _Subject:
    tier: str
    label: str
    images: list[_Image] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def reference_spec(row: dict | None) -> dict | None:
    """The published reference-to-video block, or None when the model has none."""
    if not isinstance(row, dict):
        return None
    block = row.get("reference_to_video")
    if not isinstance(block, dict) or not str(block.get("endpoint") or "").strip():
        return None
    try:
        max_images = int(block.get("max_images") or _DEFAULT_MAX_IMAGES)
    except (TypeError, ValueError):
        max_images = _DEFAULT_MAX_IMAGES
    try:
        max_bytes = int(block.get("max_bytes") or _DEFAULT_MAX_BYTES)
    except (TypeError, ValueError):
        max_bytes = _DEFAULT_MAX_BYTES
    formats = block.get("formats") or list(_DEFAULT_FORMATS)
    if not isinstance(formats, list):
        formats = list(_DEFAULT_FORMATS)
    price = block.get("usd_per_second")
    if price in (None, ""):
        price = row.get("usd_per_second")
    return {
        "endpoint": str(block["endpoint"]).strip(),
        "usd_per_second": price,
        "max_images": max(0, max_images),
        "max_bytes": max_bytes,
        "formats": {str(item).lower().lstrip(".") for item in formats if str(item).strip()},
        "image_field": str(block.get("image_field") or "image_urls"),
        "prompt_token": str(block.get("prompt_token") or "@Image"),
    }


def prepare_references(
    production_dir: str | Path,
    shot: dict,
    prompt: str,
    row: dict | None,
) -> PreparedReferences:
    """Resolve one shot's images. Reads the film folder. Does not upload."""
    folder = Path(production_dir)
    spec = reference_spec(row)
    text = prompt or ""
    if spec is None or spec["max_images"] <= 0:
        subjects = _subjects(folder, shot, text, {"formats": None, "max_bytes": None})
        skipped = [note for subject in subjects for note in subject.skipped]
        if any(subject.images for subject in subjects) or skipped:
            skipped.insert(
                0,
                "This model has no reference-to-video endpoint, so the reference images are not sent.",
            )
        prepared = PreparedReferences(skipped=skipped, spec=None, prompt=text)
        _log(shot, prepared, spec)
        return prepared
    subjects = _subjects(folder, shot, text, spec)
    kept, dropped = _cap(subjects, spec["max_images"])
    skipped = [note for subject in subjects for note in subject.skipped]
    skipped.extend(dropped)
    chosen = _number(kept)
    bound = bind_prompt(text, chosen)
    prepared = PreparedReferences(chosen=chosen, skipped=skipped, spec=spec, prompt=bound)
    _log(shot, prepared, spec)
    return prepared


def bind_prompt(prompt: str, chosen: list[ChosenReference]) -> str:
    """Name each sent image as @Image1, @Image2, when the prompt does not already."""
    if not chosen:
        return prompt or ""
    present = {int(match.group(1)) for match in _TOKEN.finditer(prompt or "")}
    missing = [item for item in chosen if item.index not in present]
    if not missing:
        return prompt or ""
    bits = [f"Use {item.token} as the {item.role} ({item.label})." for item in missing]
    text = (prompt or "").rstrip()
    if not text:
        return " ".join(bits)
    return text + "\n" + " ".join(bits)


def quote_lines(prepared: PreparedReferences) -> list[str]:
    """Sentences for a dry-run quote. Empty when this shot sends no references."""
    lines: list[str] = []
    if prepared.chosen and prepared.spec:
        price = prepared.spec.get("usd_per_second")
        shown_price = f"${money_number(price):.4f}" if price not in (None, "") else "unknown"
        lines.append(
            f"Reference endpoint {prepared.spec['endpoint']} at {shown_price} per second. "
            "This quote does not upload files and does not call the provider."
        )
        shown = "; ".join(
            f"{item.token} {item.role} {item.relative}" for item in prepared.chosen
        )
        lines.append(
            "References that would be sent, character face first, then location, then prop, "
            "then the shot's own images, one image per subject before a second from the same "
            f"subject: {shown}."
        )
    elif any("no reference-to-video endpoint" in note for note in prepared.skipped):
        lines.append(
            "This model has no reference-to-video endpoint, so the reference images are not sent."
        )
    for note in prepared.skipped:
        if note not in lines and "no reference-to-video endpoint" not in note:
            lines.append(note)
    return lines


def upload_urls(chosen: list[ChosenReference], upload) -> list[str]:
    """Turn kept images into URLs. ``upload`` is called only for local files."""
    urls = []
    for item in chosen:
        if item.url:
            urls.append(item.url)
            continue
        urls.append(upload(item.path))
    return urls


def _subjects(folder: Path, shot: dict, prompt: str, spec: dict) -> list[_Subject]:
    subjects: list[_Subject] = []
    subjects.extend(_character_subjects(folder, shot, prompt, spec))
    subjects.extend(_location_subjects(folder, shot, spec))
    subjects.extend(_prop_subjects(folder, shot, spec))
    subjects.extend(_shot_subjects(folder, shot, spec, subjects))
    return subjects


def _character_subjects(folder: Path, shot: dict, prompt: str, spec: dict) -> list[_Subject]:
    faces = _locked_entries(
        folder,
        "characters/character-lock.json",
        "characters",
        "character_id",
    )
    costumes = _locked_entries(
        folder,
        "wardrobe/costume-lock.json",
        "characters",
        "character_id",
        fallback="wardrobe/costume-definitions.json",
    )
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for entry in faces:
        key = str(entry.get("character_id") or entry.get("name") or "").casefold()
        if not key or key in by_id:
            continue
        by_id[key] = {
            "names": _character_names(entry),
            "label": str(entry.get("name") or entry.get("character_id") or "character"),
            "images": _image_list(entry),
        }
        order.append(key)
    for entry in costumes:
        key = str(entry.get("character_id") or entry.get("name") or "").casefold()
        if not key:
            continue
        images = _image_list(entry)
        if key not in by_id:
            by_id[key] = {
                "names": _character_names(entry),
                "label": str(entry.get("name") or entry.get("character_id") or "character"),
                "images": images,
            }
            order.append(key)
        elif not by_id[key]["images"]:
            by_id[key]["images"] = images
    queries, explicit = _character_queries(shot)
    matched = []
    for key in order:
        entry = by_id[key]
        if explicit:
            if queries and _matches(entry["names"], queries):
                matched.append(entry)
        elif mentioned(prompt, entry["names"]):
            matched.append(entry)
    return [_subject("character", item["label"], folder, item["images"], spec) for item in matched]


def _location_subjects(folder: Path, shot: dict, spec: dict) -> list[_Subject]:
    entries = _locked_entries(folder, "locations/location-lock.json", "locations", "location_id")
    queries, explicit = _location_queries(shot)
    matched = []
    if explicit:
        if queries:
            matched = [entry for entry in entries if _matches(_location_names(entry), queries)]
    else:
        scene_id = str(shot.get("scene_id") or "").strip()
        matched = [
            entry
            for entry in entries
            if scene_id and scene_id in set(_scene_ids(entry))
        ]
        if not matched:
            place = _scene_place(folder, scene_id)
            if place:
                matched = [entry for entry in entries if _matches(_location_names(entry), [place])]
    subjects = []
    for entry in matched:
        label = str(entry.get("name") or entry.get("location_id") or "location")
        subjects.append(_subject("location", label, folder, _image_list(entry), spec))
    return subjects


def _prop_subjects(folder: Path, shot: dict, spec: dict) -> list[_Subject]:
    document = load_prop_lock(folder)
    if not isinstance(document, dict) or document.get("status") != "locked":
        if isinstance(document, dict) and document.get("props"):
            logger.info("The prop file is not locked, so its photos are not sent.")
        return []
    queries, explicit = _prop_queries(shot)
    if not explicit or not queries:
        return []
    subjects = []
    for prop in document.get("props") or []:
        if not isinstance(prop, dict):
            continue
        names = prop_labels(prop)
        if prop.get("prop_id"):
            names = names + [str(prop["prop_id"])]
        if not _matches(names, queries):
            continue
        label = str(prop.get("name") or prop.get("prop_id") or "prop")
        subjects.append(_subject("prop", label, folder, _image_list(prop), spec))
    return subjects


def _shot_subjects(folder: Path, shot: dict, spec: dict, earlier: list[_Subject]) -> list[_Subject]:
    raws = [str(item).strip() for item in shot.get("reference_images") or [] if str(item).strip()]
    if not raws:
        return []
    taken = {image.key for subject in earlier for image in subject.images}
    subject = _Subject("shot", "shot")
    for raw in raws:
        image, note = _inspect(folder, raw, spec)
        if note:
            subject.skipped.append(note)
            continue
        if image is None or image.key in taken:
            continue
        taken.add(image.key)
        subject.images.append(image)
    if not subject.images and not subject.skipped:
        return []
    return [subject]


def _subject(tier: str, label: str, folder: Path, raws: list[str], spec: dict) -> _Subject:
    subject = _Subject(tier, label)
    seen = set()
    for raw in raws:
        image, note = _inspect(folder, raw, spec)
        if note:
            subject.skipped.append(note)
            continue
        if image is None or image.key in seen:
            continue
        seen.add(image.key)
        subject.images.append(image)
    return subject


def _cap(subjects: list[_Subject], limit: int) -> tuple[list[tuple[_Subject, _Image]], list[str]]:
    """One image per subject, in priority order, then a second, until the cap."""
    pools = [(subject, list(subject.images)) for subject in subjects]
    kept: list[tuple[_Subject, _Image]] = []
    while len(kept) < limit:
        added = False
        for subject, pool in pools:
            if not pool:
                continue
            kept.append((subject, pool.pop(0)))
            added = True
            if len(kept) >= limit:
                break
        if not added:
            break
    dropped = []
    for subject, pool in pools:
        for image in pool:
            dropped.append(
                f"Not sent, over the {limit} image cap: {image.relative}."
            )
    return kept, dropped


def _number(kept: list[tuple[_Subject, _Image]]) -> list[ChosenReference]:
    chosen = []
    for index, (subject, image) in enumerate(kept, start=1):
        role = ROLE[subject.tier]
        label = subject.label or role
        chosen.append(
            ChosenReference(
                tier=subject.tier,
                role=role,
                label=label,
                token=f"@Image{index}",
                index=index,
                raw=image.raw,
                relative=image.relative,
                path=image.path,
                url=image.url,
                size=image.size,
                mtime_ns=image.mtime_ns,
            )
        )
    return chosen


def _inspect(folder: Path, raw: str, spec: dict) -> tuple[_Image | None, str | None]:
    text = str(raw).strip()
    if not text:
        return None, None
    if text.startswith(("http://", "https://")):
        return _Image(text, text, None, text, None, None, f"url:{text}"), None
    if text.startswith("file:"):
        return None, "A reference path uses a file URL and was skipped."
    root = folder.resolve()
    candidate = Path(text)
    try:
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        resolved.relative_to(root)
    except ValueError:
        return None, "A reference path is outside the film folder and was skipped."
    relative = _relative(root, resolved, text)
    if not resolved.is_file():
        return None, f"Skipped missing reference {relative}. The file is not in the film folder."
    suffix = resolved.suffix.lower().lstrip(".")
    formats = spec.get("formats")
    if formats is not None and suffix not in formats:
        return None, (
            f"Skipped reference {relative}. The suffix is not one this endpoint accepts."
        )
    try:
        stat = resolved.stat()
    except OSError:
        return None, f"Skipped reference {relative}. The file could not be read."
    max_bytes = spec.get("max_bytes")
    if stat.st_size <= 0:
        return None, f"Skipped reference {relative}. The file is empty."
    if max_bytes is not None and stat.st_size > max_bytes:
        return None, (
            f"Skipped reference {relative}. The file is over the {max_bytes} byte limit."
        )
    return (
        _Image(text, relative, resolved, None, stat.st_size, stat.st_mtime_ns, f"file:{resolved}"),
        None,
    )


def _relative(root: Path, resolved: Path, raw: str) -> str:
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return raw


def _locked_entries(
    folder: Path,
    relative: str,
    key: str,
    id_key: str,
    fallback: str | None = None,
) -> list[dict]:
    label = relative
    path = folder / relative
    if not path.is_file() and fallback:
        path = folder / fallback
        label = fallback
    if not path.is_file():
        return []
    document = _read_lock(path, label)
    if not isinstance(document, dict):
        return []
    if document.get("status") != "locked":
        logger.info("%s is not locked, so its photos are not sent.", label)
        return []
    entries = []
    for item in document.get(key) or []:
        if isinstance(item, dict) and (item.get(id_key) or item.get("name")):
            entries.append(item)
    return entries


def _read_lock(path: Path, label: str) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("%s could not be read, so its photos are not sent. %s", label, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("%s is not a JSON object, so its photos are not sent.", label)
        return None
    return data


def _image_list(entry: dict) -> list[str]:
    images = []
    for item in entry.get("reference_images") or []:
        if isinstance(item, str) and item.strip():
            images.append(item.strip())
        elif isinstance(item, dict) and str(item.get("path") or "").strip():
            images.append(str(item["path"]).strip())
    return images


def _character_names(entry: dict) -> list[str]:
    names = character_aliases(entry)
    if entry.get("character_id"):
        ident = str(entry["character_id"]).strip()
        if ident and ident.casefold() not in {name.casefold() for name in names}:
            names.append(ident)
    return names


def _location_names(entry: dict) -> list[str]:
    names = []
    for value in (entry.get("location_id"), entry.get("name"), *(entry.get("aliases") or [])):
        text = " ".join(str(value).split())
        if len(text) < 2:
            continue
        if text.casefold() not in {item.casefold() for item in names}:
            names.append(text)
    return names


def _character_queries(shot: dict) -> tuple[list[str], bool]:
    block = shot.get("reference_from") if isinstance(shot.get("reference_from"), dict) else None
    if block is not None and "characters" in block:
        return _strings(block.get("characters")), True
    listed = _strings(shot.get("characters_in_shot"))
    if listed:
        return listed, True
    return [], False


def _location_queries(shot: dict) -> tuple[list[str], bool]:
    block = shot.get("reference_from") if isinstance(shot.get("reference_from"), dict) else None
    if block is not None and "location" in block:
        value = block.get("location")
        if value in (None, "", []):
            return [], True
        return _strings(value), True
    for key in ("location_id", "location"):
        text = str(shot.get(key) or "").strip()
        if text:
            return [text], True
    return [], False


def _prop_queries(shot: dict) -> tuple[list[str], bool]:
    block = shot.get("reference_from") if isinstance(shot.get("reference_from"), dict) else None
    if block is not None and "props" in block:
        return _strings(block.get("props")), True
    labels = []
    for item in shot.get("props") or []:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            for key in ("prop_id", "name", "label"):
                value = item.get(key)
                if value and str(value).strip():
                    labels.append(str(value).strip())
    return labels, bool(labels)


def _strings(value) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _matches(names: list[str], queries: list[str]) -> bool:
    for query in queries:
        folded = query.casefold()
        if any(folded == name.casefold() for name in names):
            return True
        if mentioned(query, names) or mentioned(" ".join(names), [query]):
            return True
    return False


def _scene_place(folder: Path, scene_id: str) -> str:
    if not scene_id:
        return ""
    path = folder / "scene-manifest" / "scene-manifest.json"
    document = _read_lock(path, "scene-manifest/scene-manifest.json") if path.is_file() else None
    if not isinstance(document, dict):
        return ""
    for scene in document.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        ident = str(scene.get("scene_id") or "").strip()
        number = scene.get("scene_number")
        numbered = f"s{int(number):02d}" if isinstance(number, int) else ""
        if scene_id not in {ident, numbered}:
            continue
        return str(scene.get("location") or "").strip()
    return ""


def _scene_ids(entry: dict) -> list[str]:
    value = entry.get("scene_ids") or []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _log(shot: dict, prepared: PreparedReferences, spec: dict | None) -> None:
    if not prepared.chosen and not prepared.skipped:
        return
    shot_id = shot.get("shot_id") or "(unset)"
    cap = spec["max_images"] if spec else 0
    sent = ", ".join(f"{item.token} {item.role} {item.relative}" for item in prepared.chosen) or "none"
    logger.info(
        "Reference priority for %s: character face, then location, then prop, then the shot's own images. "
        "Cap %s. Sending %s.",
        shot_id,
        cap,
        sent,
    )
    for note in prepared.skipped:
        logger.warning("%s", note)

