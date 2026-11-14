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
publishes 9. A rate row can send some subjects as elements instead of
flat images: one frontal image, then extra angles, up to the published
caps. Character is the tier used that way when the row says so. An
element that needs extra angles is not sent when the person has only
one still. That still is sent as a reference image, and the quote says
so. ``element_reference_images`` on the character lock supplies the
extra angles. Location and prop stills stay reference images. A missing
file, a file outside the film folder, an unsupported suffix, or a file
over the published size is logged and skipped. The call continues with
whatever remains. A payload the endpoint would reject is refused before
any upload.
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
class ChosenElement:
    """One subject sent as an element: a frontal image, then extra angles."""

    tier: str
    role: str
    label: str
    token: str
    index: int
    frontal: ChosenReference
    angles: list[ChosenReference] = field(default_factory=list)
    video: str | None = None


@dataclass
class AspectFit:
    """The aspect ratio a request would send, and whether that request stops."""

    ratio: str | None
    note: str
    refuse: bool


@dataclass
class PreparedReferences:
    """The images for one shot, and the prompt with the model's tokens filled in."""

    chosen: list[ChosenReference] = field(default_factory=list)
    elements: list[ChosenElement] = field(default_factory=list)
    start: ChosenReference | None = None
    skipped: list[str] = field(default_factory=list)
    spec: dict | None = None
    prompt: str = ""

    @property
    def endpoint(self) -> str | None:
        if not self.spec:
            return None
        if self.chosen or self.elements:
            return str(self.spec["endpoint"])
        if self.start and self.spec.get("image_endpoint"):
            return str(self.spec["image_endpoint"])
        return None

    @property
    def per_second(self):
        if (self.chosen or self.elements) and self.spec and self.spec.get("usd_per_second") not in (None, ""):
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
    try:
        max_elements = int(block.get("max_elements") or 0)
    except (TypeError, ValueError):
        max_elements = 0
    try:
        max_angles = int(block.get("max_angles") or 0)
    except (TypeError, ValueError):
        max_angles = 0
    try:
        min_angles = int(block.get("min_angles") or 0)
    except (TypeError, ValueError):
        min_angles = 0
    if min_angles < 1 and max_angles > 0:
        min_angles = 1
    formats = block.get("formats") or list(_DEFAULT_FORMATS)
    if not isinstance(formats, list):
        formats = list(_DEFAULT_FORMATS)
    price = _price_for_resolution(block, row)
    if price in (None, ""):
        price = row.get("usd_per_second")
    image = row.get("image_to_video") if isinstance(row.get("image_to_video"), dict) else {}
    tiers = [str(item).strip() for item in block.get("element_tiers") or [] if str(item).strip()]
    aliases = row.get("aspect_aliases") if isinstance(row.get("aspect_aliases"), dict) else {}
    request_fields = row.get("request_fields") if isinstance(row.get("request_fields"), dict) else {}
    return {
        "endpoint": str(block["endpoint"]).strip(),
        "usd_per_second": price,
        "max_images": max(0, max_images),
        "max_elements": max(0, max_elements),
        "max_angles": max(0, max_angles),
        "min_angles": max(0, min_angles),
        "max_bytes": max_bytes,
        "formats": {str(item).lower().lstrip(".") for item in formats if str(item).strip()},
        "image_field": str(block.get("image_field") or "image_urls"),
        "element_field": str(block.get("element_field") or "").strip(),
        "element_tiers": tiers,
        "frontal_field": str(block.get("frontal_field") or "frontal_image_url"),
        "angles_field": str(block.get("angles_field") or "reference_image_urls"),
        "element_token": str(block.get("element_token") or "@Element"),
        "element_style": str(block.get("element_style") or "at"),
        "prompt_token": str(block.get("prompt_token") or "@Image"),
        "token_style": str(block.get("token_style") or "at"),
        "start_field": str(block.get("start_image_field") or "").strip(),
        "start_counts": bool(block.get("start_counts_toward_images")),
        "aspect_ratios": _ratio_list(block, "aspect_ratios"),
        "image_endpoint": str(image.get("endpoint") or "").strip(),
        "image_start_field": str(image.get("start_image_field") or "").strip(),
        "image_aspect_ratios": _ratio_list(image, "aspect_ratios"),
        "text_endpoint": str(row.get("endpoint") or "").strip(),
        "aspect_ratios_text": _ratio_list(row, "aspect_ratios"),
        "aspect_aliases": {str(key): str(value) for key, value in aliases.items()},
        "request_fields": dict(request_fields),
        "audio_note": str(row.get("audio_note") or "").strip(),
        "quote_text_endpoint": isinstance(row.get("endpoints"), dict),
        "included_square_images": block.get("included_square_images"),
        "extra_square_image_usd": block.get("extra_square_image_usd"),
        "included_reference_tokens": block.get("included_reference_tokens"),
        "text_usd": _price_for_resolution(row, row) or row.get("usd_per_second"),
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
    if spec is None or (spec["max_images"] <= 0 and spec["max_elements"] <= 0):
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
    element_subjects, image_subjects = _split_subjects(subjects, spec)
    start, start_note = _start_image(folder, shot, spec)
    if start is not None:
        for subject in image_subjects:
            subject.images = [image for image in subject.images if image.relative != start.relative]
    raw_elements, demoted, element_notes = _elements(element_subjects, spec)
    image_subjects = list(demoted) + list(image_subjects)
    reserve = 1 if start is not None and spec["start_counts"] and (raw_elements or _has_images(image_subjects)) else 0
    kept, dropped = _cap(image_subjects, max(0, spec["max_images"] - reserve))
    skipped = [note for subject in subjects for note in subject.skipped]
    if start_note:
        skipped.append(start_note)
    skipped.extend(element_notes)
    skipped.extend(dropped)
    chosen = _number(kept, spec)
    elements = _number_elements(raw_elements, spec)
    if chosen or elements:
        use_start = start if spec.get("start_field") else None
    elif start is not None and spec.get("image_endpoint"):
        use_start = start
    else:
        use_start = None
    bound = bind_prompt(text, chosen, elements, spec)
    prepared = PreparedReferences(
        chosen=chosen,
        elements=elements,
        start=use_start,
        skipped=skipped,
        spec=spec,
        prompt=bound,
    )
    _log(shot, prepared, spec)
    return prepared


def bind_prompt(
    prompt: str,
    chosen: list[ChosenReference],
    elements: list[ChosenElement] | None = None,
    spec: dict | None = None,
) -> str:
    """Name each sent image with the model's token, when the prompt does not already."""
    elements = elements or []
    spec = spec or {}
    if not chosen and not elements:
        return prompt or ""
    bits = _missing_sentences(
        prompt,
        elements,
        spec.get("element_style") or "at",
        spec.get("element_token") or "@Element",
    )
    bits.extend(
        _missing_sentences(
            prompt,
            chosen,
            spec.get("token_style") or "at",
            spec.get("prompt_token") or "@Image",
        )
    )
    if not bits:
        return prompt or ""
    text = (prompt or "").rstrip()
    if not text:
        return " ".join(bits)
    return text + "\n" + " ".join(bits)


def quote_lines(prepared: PreparedReferences) -> list[str]:
    """Sentences for a dry-run quote. Empty when this shot sends nothing new."""
    lines: list[str] = []
    spec = prepared.spec or {}
    if (prepared.chosen or prepared.elements) and spec:
        price = spec.get("usd_per_second")
        shown_price = f"${money_number(price):.4f}" if price not in (None, "") else "unknown"
        lines.append(
            f"Reference endpoint {spec['endpoint']} at {shown_price} per second. "
            "This quote does not upload files and does not call the provider."
        )
        if prepared.elements:
            shown = "; ".join(_element_shown(item) for item in prepared.elements)
            lines.append(
                "Elements that would be sent, frontal image then extra angles: "
                f"{shown}."
            )
        if prepared.chosen:
            shown = "; ".join(_image_shown(item) for item in prepared.chosen)
            lines.append(_reference_order_sentence(prepared, shown))
        if prepared.start is not None:
            lines.append(f"First frame that would be sent: {prepared.start.relative}.")
        token_line = _token_sentence(spec, len(prepared.chosen))
        if token_line:
            lines.append(token_line)
    elif prepared.start is not None and spec.get("image_endpoint"):
        shown_price = _shown_price(spec.get("text_usd"))
        lines.append(
            f"Image endpoint {spec['image_endpoint']} at {shown_price} per second. "
            "This quote does not upload files and does not call the provider."
        )
        lines.append(f"First frame that would be sent: {prepared.start.relative}.")
    elif spec.get("quote_text_endpoint") and spec.get("text_endpoint"):
        lines.append(
            f"Endpoint {spec['text_endpoint']} at {_shown_price(spec.get('text_usd'))} per second. "
            "This quote does not call the provider."
        )
    elif any("no reference-to-video endpoint" in note for note in prepared.skipped):
        lines.append(
            "This model has no reference-to-video endpoint, so the reference images are not sent."
        )
    for note in prepared.skipped:
        if note not in lines and "no reference-to-video endpoint" not in note:
            lines.append(note)
    if spec.get("audio_note") and spec["audio_note"] not in lines:
        lines.append(spec["audio_note"])
    blocked = reference_request_refusal(prepared)
    if blocked and blocked not in lines:
        lines.insert(0, blocked)
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


def picture_kind(prepared: PreparedReferences | None) -> str:
    """Which fal path this shot would use: reference, image, or text."""
    if prepared is None or not prepared.spec:
        return "text"
    if prepared.elements or prepared.chosen:
        return "reference"
    if prepared.start and prepared.spec.get("image_endpoint"):
        return "image"
    return "text"


def allowed_for(row: dict | None, prepared: PreparedReferences | None):
    """The aspect ratios the active endpoint publishes. None means send the film's ratio."""
    spec = prepared.spec if prepared is not None else None
    kind = picture_kind(prepared)
    if kind == "image":
        if spec is not None and spec.get("image_aspect_ratios") is not None:
            return spec["image_aspect_ratios"]
        return []
    if kind == "reference" and spec is not None and spec.get("aspect_ratios") is not None:
        return spec["aspect_ratios"]
    if spec is not None and spec.get("aspect_ratios_text") is not None:
        return spec["aspect_ratios_text"]
    if isinstance(row, dict) and "aspect_ratios" in row:
        return row.get("aspect_ratios")
    return None


def aliases_for(row: dict | None, prepared: PreparedReferences | None) -> dict:
    spec = prepared.spec if prepared is not None else None
    if spec and isinstance(spec.get("aspect_aliases"), dict) and spec["aspect_aliases"]:
        return spec["aspect_aliases"]
    if isinstance(row, dict) and isinstance(row.get("aspect_aliases"), dict):
        return row["aspect_aliases"]
    return {}


def fit_aspect(asked, allowed, aliases: dict | None = None) -> AspectFit:
    """Keep a published ratio. Map an alias when the row names one. Do not crop to 16:9."""
    if allowed is None:
        text = str(asked).strip() if asked else ""
        return AspectFit(text or None, "", False)
    if isinstance(allowed, list) and len(allowed) == 0:
        return AspectFit(
            None,
            "This endpoint has no aspect_ratio field. The picture follows the start image "
            "and is not cropped to 16:9.",
            False,
        )
    text = str(asked).strip() if asked else ""
    if not text:
        return AspectFit(None, "", False)
    names = [str(item) for item in allowed]
    if text in names:
        return AspectFit(text, "", False)
    alias = str((aliases or {}).get(text) or "").strip()
    if alias and alias in names:
        return AspectFit(
            alias,
            f"The film asks for {text}. This model accepts {alias}, so the request uses {alias}. "
            "The picture is not cropped to 16:9.",
            False,
        )
    listed = ", ".join(names)
    return AspectFit(
        None,
        f"The film asks for {text}. This model accepts {listed}. "
        "The request is refused so the picture is not cropped. Nothing was sent.",
        True,
    )


def film_aspect(production_dir: str | Path) -> str | None:
    """The aspect ratio on the film's treatment, when that file names one."""
    path = Path(production_dir) / "treatment" / "treatment.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    ratio = (data.get("deliverables") or {}).get("aspect_ratio")
    text = str(ratio).strip() if ratio else ""
    return text or None


def _price_for_resolution(block: dict | None, row: dict | None):
    if not isinstance(block, dict):
        return None
    prices = block.get("resolution_prices")
    resolution = row.get("resolution") if isinstance(row, dict) else None
    if isinstance(prices, dict) and resolution in prices and prices[resolution] not in (None, ""):
        return prices[resolution]
    value = block.get("usd_per_second")
    if value not in (None, ""):
        return value
    return None


def _ratio_list(block: dict, key: str):
    if key not in block:
        return None
    value = block.get(key)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _shown_price(price) -> str:
    if price in (None, ""):
        return "unknown"
    return f"${money_number(price):.4f}"


def _split_subjects(subjects: list[_Subject], spec: dict) -> tuple[list[_Subject], list[_Subject]]:
    tiers = set(spec.get("element_tiers") or [])
    if not spec.get("max_elements") or not tiers:
        return [], subjects
    elements = [subject for subject in subjects if subject.tier in tiers]
    images = [subject for subject in subjects if subject.tier not in tiers]
    return elements, images


def _has_images(subjects: list[_Subject]) -> bool:
    return any(subject.images for subject in subjects)


def _start_image(folder: Path, shot: dict, spec: dict) -> tuple[ChosenReference | None, str | None]:
    if not spec.get("start_field") and not spec.get("image_start_field"):
        return None, None
    raw = str(shot.get("start_image") or "").strip()
    if not raw:
        return None, None
    image, note = _inspect(folder, raw, spec)
    if note or image is None:
        return None, note
    chosen = ChosenReference(
        tier="shot",
        role="first frame",
        label="first frame",
        token="",
        index=0,
        raw=image.raw,
        relative=image.relative,
        path=image.path,
        url=image.url,
        size=image.size,
        mtime_ns=image.mtime_ns,
    )
    return chosen, None


def _elements(
    subjects: list[_Subject],
    spec: dict,
) -> tuple[list[tuple[_Subject, _Image, list[_Image]]], list[_Subject], list[str]]:
    limit = int(spec.get("max_elements") or 0)
    angles_cap = int(spec.get("max_angles") or 0)
    min_angles = int(spec.get("min_angles") or 0)
    kept: list[tuple[_Subject, _Image, list[_Image]]] = []
    demoted: list[_Subject] = []
    dropped: list[str] = []
    for subject in subjects:
        if not subject.images:
            continue
        if min_angles >= 1 and len(subject.images) < 1 + min_angles:
            demoted.append(subject)
            dropped.append(_single_still_note(subject, min_angles))
            continue
        if len(kept) >= limit:
            for image in subject.images:
                dropped.append(f"Not sent, over the {limit} element cap: {image.relative}.")
            continue
        frontal = subject.images[0]
        angles = subject.images[1:1 + angles_cap]
        if angles_cap and not angles:
            demoted.append(subject)
            dropped.append(_single_still_note(subject, 1))
            continue
        for image in subject.images[1 + angles_cap:]:
            dropped.append(f"Not sent, over the {angles_cap} extra-angle cap: {image.relative}.")
        kept.append((subject, frontal, angles))
    return kept, demoted, dropped


def _single_still_note(subject: _Subject, min_angles: int) -> str:
    count = len(subject.images)
    still = "1 still" if count == 1 else f"{count} stills"
    extra = "1 extra angle" if min_angles == 1 else f"{min_angles} extra angles"
    label = subject.label or ROLE.get(subject.tier, "subject")
    return (
        f"{label} has {still}, so the still is sent as a reference image, not an element. "
        f"This endpoint needs a frontal image and at least {extra}."
    )


def reference_request_refusal(prepared: PreparedReferences | None) -> str | None:
    """Stop a payload the endpoint would reject. Does not upload or call out."""
    if prepared is None:
        return None
    spec = prepared.spec or {}
    if not prepared.elements and not spec.get("element_field"):
        return None
    try:
        max_elements = int(spec.get("max_elements") or 0)
    except (TypeError, ValueError):
        max_elements = 0
    try:
        max_angles = int(spec.get("max_angles") or 0)
    except (TypeError, ValueError):
        max_angles = 0
    try:
        min_angles = int(spec.get("min_angles") or 0)
    except (TypeError, ValueError):
        min_angles = 0
    try:
        max_images = int(spec.get("max_images") or 0)
    except (TypeError, ValueError):
        max_images = 0
    if max_elements and len(prepared.elements) > max_elements:
        return (
            f"This request has {len(prepared.elements)} elements. "
            f"The endpoint accepts at most {max_elements}. Nothing was sent."
        )
    frames = len(prepared.chosen) + (1 if prepared.start is not None else 0)
    if max_images and frames > max_images:
        return (
            f"This request has {frames} reference images, counting first, middle, and end frames. "
            f"The endpoint accepts at most {max_images}. Nothing was sent."
        )
    requires_angles = min_angles >= 1 or max_angles > 0
    angle_cap = max_angles or 3
    for element in prepared.elements:
        if element.frontal is not None and element.video:
            return (
                f"{element.label} has both a frontal image and a video. "
                "The endpoint accepts one or the other, not both. Nothing was sent."
            )
        if requires_angles and element.frontal is not None and not element.angles and not element.video:
            return (
                f"{element.label} has a frontal image and no extra angle. "
                f"The endpoint needs a frontal image and 1 to {angle_cap} extra angles, or a video. "
                "Nothing was sent."
            )
        if element.angles and len(element.angles) > angle_cap:
            return (
                f"{element.label} has {len(element.angles)} extra angles. "
                f"The endpoint accepts at most {angle_cap}. Nothing was sent."
            )
    return None


def _reference_order_sentence(prepared: PreparedReferences, shown: str) -> str:
    has_character = any(item.tier == "character" for item in prepared.chosen)
    if prepared.elements and not has_character:
        lead = "location, then prop, then the shot's own images"
    else:
        lead = "character face first, then location, then prop, then the shot's own images"
    return (
        "References that would be sent, "
        f"{lead}, one image per subject before a second from the same subject: {shown}."
    )


def _number_elements(
    kept: list[tuple[_Subject, _Image, list[_Image]]],
    spec: dict,
) -> list[ChosenElement]:
    style = spec.get("element_style") or "at"
    prefix = spec.get("element_token") or "@Element"
    elements = []
    for index, (subject, frontal, angles) in enumerate(kept, start=1):
        token = _format_token(style, prefix, index)
        role = ROLE[subject.tier]
        elements.append(
            ChosenElement(
                tier=subject.tier,
                role=role,
                label=subject.label or role,
                token=token,
                index=index,
                frontal=_as_chosen(subject, frontal, token, index),
                angles=[_as_chosen(subject, image, token, index) for image in angles],
            )
        )
    return elements


def _as_chosen(subject: _Subject, image: _Image, token: str, index: int) -> ChosenReference:
    role = ROLE[subject.tier]
    return ChosenReference(
        tier=subject.tier,
        role=role,
        label=subject.label or role,
        token=token,
        index=index,
        raw=image.raw,
        relative=image.relative,
        path=image.path,
        url=image.url,
        size=image.size,
        mtime_ns=image.mtime_ns,
    )


def _format_token(style: str, prefix: str, index: int) -> str:
    if style == "word":
        return f"{prefix} {index}"
    return f"{prefix}{index}"


def _missing_sentences(prompt: str, items, style: str, prefix: str) -> list[str]:
    if not items:
        return []
    present = _present(prompt, style, prefix)
    missing = [item for item in items if item.index not in present]
    return [_token_sentence_for(item, style) for item in missing]


def _present(prompt: str, style: str, prefix: str) -> set[int]:
    if style == "word":
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(prefix)}\s+(\d+)", re.I)
    else:
        pattern = re.compile(rf"{re.escape(prefix)}(\d+)", re.I)
    return {int(match.group(1)) for match in pattern.finditer(prompt or "")}


def _token_sentence_for(item, style: str) -> str:
    if style == "word":
        return f"{item.token} is the {item.role} ({item.label})."
    return f"Use {item.token} as the {item.role} ({item.label})."


def _image_shown(item: ChosenReference) -> str:
    return f"{item.token} {item.role} {item.relative}"


def _element_shown(item: ChosenElement) -> str:
    base = f"{item.token} {item.role} {item.frontal.relative}"
    if not item.angles:
        return base
    angles = ", ".join(angle.relative for angle in item.angles)
    return f"{base} (angles {angles})"


def _token_sentence(spec: dict, count: int) -> str:
    included = spec.get("included_square_images")
    extra = spec.get("extra_square_image_usd")
    tokens = spec.get("included_reference_tokens")
    if included in (None, "") or extra in (None, "") or tokens in (None, ""):
        return ""
    try:
        free = int(included)
    except (TypeError, ValueError):
        return ""
    if count <= free:
        return (
            f"Reference tokens: the first {tokens} are included. With no video or audio, "
            f"the first {free} square images add no charge. This quote adds none."
        )
    over = count - free
    return (
        f"Reference tokens: the first {tokens} are included. With no video or audio, "
        f"the first {free} square images add no charge, and each further square image "
        f"is ${extra}. This shot would send {count} reference images. Pixel size is not "
        f"measured, so the dollar line does not add a token charge for the {over} images past {free}."
    )


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
            "images": _image_list(entry, "reference_images", "element_reference_images"),
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


def _number(kept: list[tuple[_Subject, _Image]], spec: dict | None = None) -> list[ChosenReference]:
    spec = spec or {}
    style = spec.get("token_style") or "at"
    prefix = spec.get("prompt_token") or "@Image"
    chosen = []
    for index, (subject, image) in enumerate(kept, start=1):
        chosen.append(_as_chosen(subject, image, _format_token(style, prefix, index), index))
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


def _image_list(entry: dict, *fields: str) -> list[str]:
    names = fields or ("reference_images",)
    images = []
    seen = set()
    for name in names:
        for item in entry.get(name) or []:
            if isinstance(item, str) and item.strip():
                text = item.strip()
            elif isinstance(item, dict) and str(item.get("path") or "").strip():
                text = str(item["path"]).strip()
            else:
                continue
            if text in seen:
                continue
            seen.add(text)
            images.append(text)
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
    elements = ", ".join(_element_shown(item) for item in prepared.elements) or "none"
    sent = ", ".join(f"{item.token} {item.role} {item.relative}" for item in prepared.chosen) or "none"
    logger.info(
        "Reference priority for %s: character face, then location, then prop, then the shot's own images. "
        "Cap %s. Elements %s. Sending %s.",
        shot_id,
        cap,
        elements,
        sent,
    )
    for note in prepared.skipped:
        logger.warning("%s", note)

