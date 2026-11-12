"""Post Supervisor: package a picture-locked cut for delivery.

The delivery spec, the cue sheet, and the loudness target come from the
production folder. This module does not know which film it is reading. It
does not call a paid model. ffmpeg renders when it is installed. When it is
not, the plan and the caption sidecars are still written.

QC is the local technical pass: duration, resolution, frame rate, loudness,
black frames, frozen frames, and caption timing. It uses the same ffprobe
and ffmpeg filters as the dailies reviewer. It does not call the QA
program's model.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from movie_swarm.assets import ASSET_ROOT_ENV, configured_asset_root
from movie_swarm.dailies import _filter_hit, _frame_rate
from movie_swarm.gates import load_gate_config
from movie_swarm.handoff import HandoffError, read_handoff, write_handoff
from movie_swarm.models import ModelRoutingError, resolve_model


class DeliveryError(Exception):
    """Delivery cannot be built. The message says what is missing."""


_EBU_INTEGRATED_LUFS = -23.0
_EBU_TRUE_PEAK_DBTP = -1.0
_EBU_TOLERANCE_LUFS = 0.5
_EBU_CITATION = (
    "EBU R128, Loudness normalisation and permitted maximum level of audio signals "
    "(https://tech.ebu.ch/docs/r/r128.pdf). "
    "Programme loudness is -23.0 LUFS. True peak is no higher than -1.0 dBTP. "
    "A miss of more than 0.5 LU is outside the target unless the production sets another tolerance."
)
_H264_CITATION = (
    "ITU-T H.264 (ISO/IEC 14496-10), Advanced Video Coding "
    "(https://www.itu.int/rec/T-REC-H.264). "
    "The high-quality master uses the High profile and 4:2:0 video in an MP4 file when ProRes is not selected. "
    "CRF 18 is this studio's ffmpeg quality setting for that file. It is not a published price."
)
_PRORES_CITATION = (
    "Apple ProRes White Paper "
    "(https://www.apple.com/final-cut-pro/docs/Apple_ProRes_White_Paper.pdf). "
    "ProRes 422 HQ is used when the delivery spec asks for ProRes, or when the spec leaves the codec open, "
    "and ffmpeg has a ProRes encoder."
)
_BT709_CITATION = (
    "ITU-R BT.709 (https://www.itu.int/rec/R-REC-BT.709). "
    "When the delivery spec does not set a frame size, the master is 1920 by 1080, the HD frame in that recommendation."
)
_WEB_CITATION = (
    "YouTube recommended upload encoding (https://support.google.com/youtube/answer/1722171). "
    "A web variant is H.264 video and AAC audio in an MP4 file. "
    "1280 by 720 is the 720p size named there when the spec does not set a web size."
)
_SAFE_CITATION = (
    "EBU R95, Safe areas for 16:9 television production (https://tech.ebu.ch/docs/r/r095.pdf). "
    "This studio uses a 3.5 percent action-safe inset and a 5 percent graphics-safe inset "
    "unless the delivery spec sets its own. A 9:16 or 1:1 frame is a center crop of the master. "
    "Essential action stays in the region that survives that crop. Titles stay inside the graphics-safe inset "
    "of the delivered frame."
)
_VTT_CITATION = (
    "W3C WebVTT (https://www.w3.org/TR/webvtt1/). "
    "Sidecar captions are WebVTT and SubRip (SRT). "
    "SRT is the text subtitle file with comma-separated milliseconds. It is not an ITU standard. "
    "Times come from the dialogue cues on the cue sheet."
)
_SHA_CITATION = (
    "FIPS PUB 180-4, Secure Hash Standard "
    "(https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf). "
    "Each delivered file is checksummed with SHA-256."
)
_ACTION_INSET = 3.5
_GRAPHICS_INSET = 5.0
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def deliver_production(
    production_dir: str | Path,
    *,
    color_mix_approved: bool = False,
    spent_usd: float = 0,
    budget_cap_usd: float = 500,
    stage_split: dict | None = None,
    stage_spent: dict | None = None,
    gate_records: list | None = None,
) -> dict:
    """Write the delivery plan, captions, renders, QC, and manifest. Nothing is spent."""
    if not color_mix_approved:
        raise DeliveryError(
            "Final delivery did not run. Ron has not approved the color-mix gate."
        )
    folder = Path(production_dir)
    cut = _load_cut(folder)
    runtime = float(cut.get("runtime_seconds") or 0)
    spec, spec_source = _load_spec(folder)
    encoders = ffmpeg_encoders()
    plan = _build_plan(folder, cut, spec, spec_source, encoders, runtime)
    package = Path(plan["location"]["resolved"])
    package.mkdir(parents=True, exist_ok=True)
    _write_pointer(folder, plan["location"])
    caption_files = _write_captions(package, plan)
    plan["captions"]["files"] = caption_files
    render = _render_package(folder, package, cut, plan)
    plan["render"] = render
    if render.get("burned"):
        plan["captions"]["burned_file"] = render["burned"]
    qc = build_qc_report(folder.name, plan, package, production_dir=folder)
    plan["ready_for_delivery_approval"] = qc["verdict"] == "pass"
    plan_path, plan_md = _write_plan(package, plan)
    qc_path, qc_md = _write_qc(package, qc)
    manifest = _manifest(
        folder,
        plan,
        qc,
        package,
        spent_usd=spent_usd,
        budget_cap_usd=budget_cap_usd,
        stage_split=stage_split or {},
        stage_spent=stage_spent or {},
        gate_records=gate_records or [],
    )
    manifest_path, manifest_md = _write_manifest(package, manifest)
    return {
        "plan": plan,
        "qc": qc,
        "manifest": manifest,
        "package_dir": package,
        "plan_path": plan_path,
        "plan_markdown": plan_md,
        "qc_path": qc_path,
        "qc_markdown": qc_md,
        "manifest_path": manifest_path,
        "manifest_markdown": manifest_md,
        "report": _approval_line(plan["ready_for_delivery_approval"]),
    }


def run_delivery(producer, call) -> str:
    """The Director's deliver command. It does not spend, and it does not approve itself."""
    if not producer.gate_is_open("color-mix"):
        raise DeliveryError("Final delivery did not run. Ron has not approved the color-mix gate.")
    production = Path(call.production_dir or producer.production_dir)
    from movie_swarm.graphics import build_graphics, guide_is_approved

    if guide_is_approved(production):
        build_graphics(production)
    split = dict((producer.record.get("stage_allocations") or {}).get("split") or {})
    result = deliver_production(
        production,
        color_mix_approved=True,
        spent_usd=float(producer.run.data["cost_usd"]),
        budget_cap_usd=float(producer.run.data["budget_cap_usd"]),
        stage_split=split,
        stage_spent={stage: producer.stage_spent(stage) for stage in split},
        gate_records=list(producer.record.get("gate_decisions") or []),
    )
    _register(producer, production, result)
    _ensure_credit(producer, "Post Supervisor", "Post Supervisor")
    if producer.gate_decision("delivery") == "approved":
        mark_delivered(
            production,
            by=_latest_by(producer, "delivery"),
            note=_latest_note(producer, "delivery"),
            decided_at=_latest_when(producer, "delivery"),
        )
        producer.run.data["notes"] = (
            "Delivery was written again after the delivery gate was approved. "
            "The approval still stands. The film is delivered."
        )
        producer.run.data["status"] = "completed"
        producer.run.save()
    else:
        producer.set_stage("delivery", "waiting-for-review")
        producer.run.data["notes"] = (
            "The delivery package is waiting on Ron. "
            "The film is not delivered until he approves the delivery gate."
        )
        producer.run.save()
    text = render_plan_markdown(result["plan"])
    text += "\n" + render_qc_markdown(result["qc"])
    return text + f"\nWrote {result['manifest_markdown']}."


def mark_delivered(
    production_dir: str | Path,
    *,
    by: str,
    note: str = "",
    decided_at: str | None = None,
) -> str:
    """Stamp the manifest when the delivery gate is approved. Does not spend."""
    path = find_manifest(production_dir)
    if path is None:
        return "No delivery manifest was on disk to stamp."
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DeliveryError(f"{path.name} is not valid JSON. {exc}") from exc
    when = decided_at or _now()
    data["delivery_approved"] = True
    data["delivered"] = True
    data["approved_by"] = by
    data["approved_at"] = when
    data["approval_note"] = note.strip()
    updated = False
    for row in data.get("gates") or []:
        if row.get("stage") == "delivery" and row.get("decision") != "approved":
            row["decision"] = "approved"
            row["by"] = by
            row["decided_at"] = when
            row["note"] = note.strip()
            updated = True
            break
    if not updated:
        data.setdefault("gates", []).append(
            {
                "stage": "delivery",
                "decision": "approved",
                "by": by,
                "decided_at": when,
                "note": note.strip(),
            }
        )
    write_handoff(path, data, schema="delivery-manifest")
    _write_manifest_markdown(path.with_name("delivery-manifest.md"), data)
    return "The delivery manifest now says the film is delivered."


def find_manifest(production_dir: str | Path) -> Path | None:
    """The manifest in the production folder, or the one the location pointer names."""
    folder = Path(production_dir)
    local = folder / "delivery" / "delivery-manifest.json"
    if local.is_file():
        return local
    pointer = folder / "delivery" / "location.json"
    if not pointer.is_file():
        return None
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    resolved = data.get("resolved")
    if not resolved:
        return None
    candidate = Path(str(resolved)) / "delivery-manifest.json"
    if candidate.is_file():
        return candidate
    return None


def build_qc_report(production_id: str, plan: dict, package: str | Path, production_dir: str | Path | None = None) -> dict:
    """Pass or fail each technical check. A missing tool or a missing file is skipped, not a pass."""
    root = Path(package)
    runtime = float(plan.get("cut_runtime_seconds") or 0)
    tolerances = plan.get("qc_tolerances") or {}
    checks = []
    master_name = (plan.get("master") or {}).get("filename")
    if master_name:
        checks.extend(
            _video_checks(
                root / master_name,
                _rel_name(plan, master_name),
                "master",
                plan.get("master") or {},
                plan.get("loudness") or {},
                tolerances,
                runtime,
            )
        )
    for variant in plan.get("variants") or []:
        name = variant.get("filename")
        if not name:
            continue
        checks.extend(
            _video_checks(
                root / name,
                _rel_name(plan, name),
                variant.get("id") or "variant",
                variant,
                plan.get("loudness") or {},
                tolerances,
                runtime,
            )
        )
    poster = plan.get("poster") or {}
    if poster.get("filename"):
        checks.extend(_poster_checks(root / poster["filename"], _rel_name(plan, poster["filename"]), poster))
    checks.append(_caption_check(root, plan, runtime))
    if production_dir is not None:
        from movie_swarm.graphics import qc_checks

        checks.extend(qc_checks(production_dir))
    verdict = "fail" if any(item["status"] == "fail" for item in checks) else "pass"
    return {
        "version": "1.0.0",
        "production_id": production_id,
        "kind": "qc-report",
        "created_at": _now(),
        "verdict": verdict,
        "spent_usd": 0,
        "cut_runtime_seconds": round(runtime, 3),
        "checks": checks,
        "draft_method": "offline-deterministic",
    }


def ffmpeg_encoders() -> set[str]:
    """Encoder names ffmpeg reports. Empty when ffmpeg is not installed."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return set()
    try:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    names = set()
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0][:1] in {"V", "A"}:
            names.add(parts[1])
    return names


def render_plan_markdown(plan: dict) -> str:
    """The delivery plan in sentences, before the delivery gate."""
    master = plan["master"]
    lines = [
        f"Delivery plan for {plan['production_id']}",
        "",
        "No money was spent. JSON is the delivery plan.",
        "",
        (
            f"Master: {master['codec']} {master['width']}x{master['height']} "
            f"at {master['frame_rate']:g} fps ({master['encoder']})."
        ),
        master["citation"],
        "",
        "| Variant | Frame | Crop |",
        "| --- | --- | --- |",
    ]
    if not plan["variants"]:
        lines.append("| none | | |")
    for item in plan["variants"]:
        lines.append(
            f"| {item['id']} | {item['width']}x{item['height']} {item['aspect_ratio']} | {item['crop']} |"
        )
    if plan["variants"]:
        lines.extend(["", plan["variants"][0]["safe"]["guidance"], plan["variants"][0]["safe"]["citation"]])
    lines.extend(["", f"Poster: {plan['poster']['shot_id']}. {plan['poster']['note']}"])
    lines.extend(["", f"Captions: {plan['captions']['mode']}. {plan['captions']['citation']}"])
    if not plan["captions"]["cues"]:
        lines.append("No dialogue cues, so the caption files have no lines.")
    for cue in plan["captions"]["cues"]:
        lines.append(
            f"- {cue['cue_id']}: {cue['start_seconds']:.3f}s to {cue['end_seconds']:.3f}s. {cue['text']}"
        )
    lines.extend(
        [
            "",
            f"Loudness target: {plan['loudness']['integrated_lufs']} LUFS ({plan['loudness']['standard']}).",
            plan["loudness"]["citation"],
            "",
            f"Render: {plan['render']['status']}. {plan['render']['note']}",
            "",
            plan["budget"]["note"],
            _approval_line(plan["ready_for_delivery_approval"]),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_qc_markdown(report: dict) -> str:
    """The QC report as a table. JSON is the source of truth."""
    lines = [
        f"QC report for {report['production_id']}",
        "",
        "No money was spent. Each row is one check.",
        "",
        f"Verdict: {report['verdict']}.",
        "",
        "| Check | Target | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["checks"]:
        detail = item["detail"].replace("|", "/")
        lines.append(f"| {item['kind']} | {item['target']} | {item['status']} | {detail} |")
    return "\n".join(lines).rstrip() + "\n"


def _build_plan(folder: Path, cut: dict, spec: dict, spec_source: str | None, encoders: set[str], runtime: float) -> dict:
    defaults = []
    master = _master_spec(spec, encoders, defaults)
    variants = _variants(spec, master, defaults)
    poster = _poster_spec(spec, cut, master, defaults)
    cues, cue_source = _dialogue_cues(folder)
    captions = {
        "mode": _caption_mode(spec),
        "formats": _caption_formats(spec),
        "cues": cues,
        "citation": _VTT_CITATION,
        "files": [],
        "burned_file": None,
    }
    loudness = _loudness(spec, folder)
    tolerances = _tolerances(spec, loudness)
    location = _location(folder, spec)
    if spec_source is None:
        defaults.append("spec")
    note = _spec_note(folder, spec, spec_source)
    return {
        "version": "1.0.0",
        "production_id": folder.name,
        "kind": "delivery-plan",
        "created_at": _now(),
        "cut_runtime_seconds": round(runtime, 3),
        "spent_usd": 0,
        "spec_source": spec_source,
        "spec_note": note,
        "defaults_used": defaults,
        "ready_for_delivery_approval": False,
        "delivery_approved": False,
        "sources": {
            "edit": "edit/picture-lock.json",
            "cue_sheet": cue_source,
            "mix": "color/mix.wav" if (folder / "color" / "mix.wav").is_file() else None,
            "grade": "color/grade-plan.json" if (folder / "color" / "grade-plan.json").is_file() else None,
            "spec": spec_source,
        },
        "master": master,
        "variants": variants,
        "poster": poster,
        "captions": captions,
        "loudness": loudness,
        "qc_tolerances": tolerances,
        "location": location,
        "standards": _standards(),
        "render": {
            "status": "skipped",
            "note": "Render has not run.",
            "master": None,
            "variants": [],
            "poster": None,
            "burned": None,
        },
        "budget": _budget(),
        "models": {
            "post-supervisor": _model("post-supervisor", "package"),
            "notes": _model("post-supervisor", "notes"),
            "render": "ffmpeg",
            "qc": "local",
        },
        "draft_method": "offline-deterministic",
    }


def _master_spec(spec: dict, encoders: set[str], defaults: list[str]) -> dict:
    raw = spec.get("master") if isinstance(spec.get("master"), dict) else {}
    if "width" not in raw:
        defaults.append("master.width")
    if "height" not in raw:
        defaults.append("master.height")
    if "frame_rate" not in raw:
        defaults.append("master.frame_rate")
    if "codec" not in raw:
        defaults.append("master.codec")
    width = int(raw.get("width") or 1920)
    height = int(raw.get("height") or 1080)
    frame_rate = float(raw.get("frame_rate") or 24)
    asked = str(raw.get("codec") or "prores-if-available").strip().casefold()
    prores = "prores_ks" if "prores_ks" in encoders else ("prores" if "prores" in encoders else None)
    if asked in {"prores", "prores-if-available"} and prores:
        codec = "prores"
        encoder = prores
        container = "mov"
        filename = "master.mov"
        profile = "422 HQ"
        crf = None
        citation = _PRORES_CITATION
        note = "ProRes 422 HQ is available in this ffmpeg, so the master uses it."
    else:
        codec = "h264"
        encoder = "libx264"
        container = str(raw.get("container") or "mp4")
        filename = "master.mp4"
        profile = "high"
        crf = float(raw["crf"]) if raw.get("crf") not in (None, "") else 18.0
        citation = _H264_CITATION if width != 1920 or height != 1080 else _H264_CITATION + " " + _BT709_CITATION
        if asked == "prores" and not prores:
            note = "The spec asks for ProRes. This ffmpeg has no ProRes encoder, so the master is high-quality H.264."
        elif asked == "prores-if-available" and not prores:
            note = "ProRes was not available, so the master is high-quality H.264."
        else:
            note = "The master is high-quality H.264, as the delivery spec asks." if asked == "h264" else (
                "The master is high-quality H.264."
            )
        if width == 1920 and height == 1080 and "master.width" in defaults:
            citation = _BT709_CITATION + " " + _H264_CITATION
    if container == "mov" and not filename.endswith(".mov"):
        filename = "master.mov"
    return {
        "codec": codec,
        "encoder": encoder,
        "container": container,
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "crf": crf,
        "profile": profile,
        "filename": filename,
        "citation": citation,
        "note": note,
    }


def _variants(spec: dict, master: dict, defaults: list[str]) -> list[dict]:
    raw = spec.get("variants")
    if not isinstance(raw, list) or not raw:
        defaults.append("variants")
        raw = [
            {
                "id": "web-16x9",
                "aspect_ratio": "16:9",
                "width": 1280,
                "height": 720,
                "use": "web",
            }
        ]
    action = _number(spec.get("safe_action_inset_percent"))
    graphics = _number(spec.get("safe_graphics_inset_percent"))
    action_inset = _ACTION_INSET if action is None else float(action)
    graphics_inset = _GRAPHICS_INSET if graphics is None else float(graphics)
    if spec.get("safe_action_inset_percent") is None:
        defaults.append("safe_action_inset_percent")
    if spec.get("safe_graphics_inset_percent") is None:
        defaults.append("safe_graphics_inset_percent")
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        width = int(entry.get("width") or master["width"])
        height = int(entry.get("height") or master["height"])
        aspect = str(entry.get("aspect_ratio") or _aspect_name(width, height))
        crop = str(entry.get("crop") or _crop_mode(master["width"], master["height"], width, height)).casefold()
        variant_id = _slug(str(entry.get("id") or f"variant-{width}x{height}"))
        use = str(entry.get("use") or "web")
        guidance = _crop_guidance(crop, aspect)
        citation = _SAFE_CITATION
        if use == "web" or aspect == "16:9":
            citation = _WEB_CITATION + " " + _SAFE_CITATION
        items.append(
            {
                "id": variant_id,
                "aspect_ratio": aspect,
                "width": width,
                "height": height,
                "frame_rate": master["frame_rate"],
                "crop": crop,
                "use": use,
                "filename": f"variants/{variant_id}.mp4",
                "safe": {
                    "action_inset_percent": action_inset,
                    "graphics_inset_percent": graphics_inset,
                    "citation": citation,
                    "guidance": guidance,
                },
            }
        )
    return items


def _poster_spec(spec: dict, cut: dict, master: dict, defaults: list[str]) -> dict:
    raw = spec.get("poster") if isinstance(spec.get("poster"), dict) else {}
    events = cut.get("events") or []
    wanted = str(raw.get("shot_id") or "").strip()
    chosen = None
    note = "The poster frame is one frame from the named shot."
    if wanted:
        for event in events:
            if event.get("shot_id") == wanted:
                chosen = event
                break
        if chosen is None and events:
            chosen = events[0]
            note = (
                f"The delivery spec names {wanted}, and that shot is not in the locked cut. "
                f"The poster uses {chosen.get('shot_id')} instead."
            )
    elif events:
        defaults.append("poster.shot_id")
        chosen = events[0]
        note = "The delivery spec does not name a poster shot. The poster uses the first shot in the locked cut."
    shot_id = str((chosen or {}).get("shot_id") or wanted or "poster")
    width = int(raw.get("width") or master["width"])
    height = int(raw.get("height") or master["height"])
    start = float((chosen or {}).get("source_in") or 0)
    duration = float((chosen or {}).get("duration_seconds") or 0)
    moment = start if duration <= 0.2 else min(start + (duration / 2), start + max(duration - 0.05, 0))
    return {
        "shot_id": shot_id,
        "filename": "poster.png",
        "time_seconds": round(moment, 3),
        "width": width,
        "height": height,
        "note": note,
        "source_file": (chosen or {}).get("source_file"),
    }


def _dialogue_cues(folder: Path) -> tuple[list[dict], str | None]:
    path = folder / "sound" / "cue-sheet.json"
    if not path.is_file():
        return [], None
    try:
        sheet = read_handoff(path, schema="cue-sheet")
    except HandoffError:
        return [], None
    cues = []
    for cue in sheet.get("cues") or []:
        if not isinstance(cue, dict) or cue.get("type") != "dialogue":
            continue
        if cue.get("source") == "silence":
            continue
        text = " ".join(str(cue.get("description") or cue.get("prompt") or "").split())
        if not text:
            continue
        cues.append(
            {
                "cue_id": _slug(str(cue.get("cue_id") or f"cue-{len(cues) + 1}")),
                "start_seconds": round(float(cue.get("start_seconds") or 0), 3),
                "end_seconds": round(float(cue.get("end_seconds") or 0), 3),
                "text": text,
            }
        )
    cues.sort(key=lambda item: (item["start_seconds"], item["cue_id"]))
    return cues, "sound/cue-sheet.json"


def _loudness(spec: dict, folder: Path) -> dict:
    raw = spec.get("loudness") if isinstance(spec.get("loudness"), dict) else {}
    source = "delivery/delivery-spec.json" if raw else None
    block = {}
    if not raw:
        mix_path = folder / "color" / "mix-plan.json"
        if mix_path.is_file():
            try:
                mix = json.loads(mix_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                mix = {}
            if isinstance(mix.get("loudness"), dict) and mix["loudness"].get("integrated_lufs") is not None:
                block = mix["loudness"]
                source = "color/mix-plan.json"
    if raw:
        block = raw
        source = "delivery/delivery-spec.json"
    integrated = _number(block.get("integrated_lufs"))
    peak = _number(block.get("true_peak_dbtp"))
    tolerance = _number(block.get("tolerance_lufs"))
    standard = str(block.get("standard") or "EBU R128")
    if integrated is None:
        integrated = _EBU_INTEGRATED_LUFS
    if peak is None:
        peak = _EBU_TRUE_PEAK_DBTP
    if tolerance is None:
        tolerance = _EBU_TOLERANCE_LUFS
    if standard.casefold() in {"ebu r128", "ebu-r128", "r128"}:
        citation = _EBU_CITATION
        standard = "EBU R128"
    else:
        citation = (
            f"The production set the loudness target in {source or 'the delivery spec'}. "
            "No extra standard was assumed."
        )
    if source is None:
        source = "EBU R128"
        citation = _EBU_CITATION
    return {
        "integrated_lufs": float(integrated),
        "true_peak_dbtp": float(peak),
        "tolerance_lufs": float(tolerance),
        "standard": standard,
        "citation": citation,
        "source": source,
    }


def _tolerances(spec: dict, loudness: dict) -> dict:
    raw = spec.get("qc") if isinstance(spec.get("qc"), dict) else {}
    duration = _number(raw.get("duration_tolerance_seconds"))
    rate = _number(raw.get("frame_rate_tolerance"))
    black = _number(raw.get("black_max_seconds"))
    freeze = _number(raw.get("freeze_max_seconds"))
    loud = _number(raw.get("loudness_tolerance_lufs"))
    return {
        "duration_tolerance_seconds": 0.5 if duration is None else float(duration),
        "frame_rate_tolerance": 0.05 if rate is None else float(rate),
        "black_max_seconds": 0.5 if black is None else float(black),
        "freeze_max_seconds": 0.5 if freeze is None else float(freeze),
        "loudness_tolerance_lufs": float(loudness["tolerance_lufs"] if loud is None else loud),
    }


def _location(folder: Path, spec: dict) -> dict:
    relative = _relative_folder(spec)
    env = os.environ.get(ASSET_ROOT_ENV, "").strip()
    root = configured_asset_root()
    if root is None:
        package = (folder / relative).resolve()
        setting = None
    else:
        package = (root / folder.name / relative).resolve()
        setting = ASSET_ROOT_ENV if env else "config/assets.json"
    return {"relative": relative, "setting": setting, "resolved": str(package)}


def _relative_folder(spec: dict) -> str:
    raw = str(spec.get("folder") or "delivery").strip() or "delivery"
    path = Path(raw)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise DeliveryError(
            "The delivery folder in the spec must be a relative path inside the production. "
            "Choose a drive with the asset root setting. The path is not hard-coded."
        )
    return path.as_posix()


def _write_pointer(folder: Path, location: dict) -> None:
    pointer_dir = folder / "delivery"
    pointer_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(location, indent=2) + "\n"
    (pointer_dir / "location.json").write_text(payload, encoding="utf-8")
    package = Path(location["resolved"])
    if package.resolve() != pointer_dir.resolve():
        package.mkdir(parents=True, exist_ok=True)
        (package / "location.json").write_text(payload, encoding="utf-8")


def _write_captions(package: Path, plan: dict) -> list[str]:
    cues = plan["captions"]["cues"]
    formats = set(plan["captions"]["formats"])
    written = []
    relative = plan["location"]["relative"]
    if "srt" in formats:
        text = _srt(cues)
        (package / "captions.srt").write_text(text, encoding="utf-8")
        written.append(f"{relative}/captions.srt")
    if "vtt" in formats:
        text = _vtt(cues)
        (package / "captions.vtt").write_text(text, encoding="utf-8")
        written.append(f"{relative}/captions.vtt")
    return written


def _srt(cues: list[dict]) -> str:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{_srt_time(cue['start_seconds'])} --> {_srt_time(cue['end_seconds'])}\n{cue['text']}\n"
        )
    return "\n".join(blocks).rstrip() + "\n"


def _vtt(cues: list[dict]) -> str:
    blocks = ["WEBVTT", ""]
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{_vtt_time(cue['start_seconds'])} --> {_vtt_time(cue['end_seconds'])}\n{cue['text']}\n"
        )
    return "\n".join(blocks).rstrip() + "\n"


def _render_package(folder: Path, package: Path, cut: dict, plan: dict) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    relative = plan["location"]["relative"]
    master_name = plan["master"]["filename"]
    skipped = {
        "status": "skipped",
        "note": "ffmpeg is not installed, so the picture was not rendered. The plan and the caption sidecars are written.",
        "master": None,
        "variants": [],
        "poster": None,
        "burned": None,
    }
    if not ffmpeg:
        return skipped
    work = package / "_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    try:
        segments = []
        for event in cut.get("events") or []:
            dest = work / f"seg-{int(event.get('event') or len(segments) + 1):03d}.mp4"
            _render_segment(ffmpeg, folder, event, plan["master"], dest)
            segments.append(dest)
        video = work / "video.mp4"
        _concat(ffmpeg, segments, video)
        audio = work / "audio.wav"
        mix = folder / "color" / "mix.wav"
        if mix.is_file():
            _loudnorm_trim(ffmpeg, mix, plan["loudness"], plan["cut_runtime_seconds"], audio)
            audio_note = "The mix was trimmed to the cut and loudness-normalised to the target."
        else:
            _silence(ffmpeg, plan["cut_runtime_seconds"], audio)
            audio_note = "No mix file was on disk, so the master carries silence."
        master_path = package / master_name
        master_path.parent.mkdir(parents=True, exist_ok=True)
        _mux(ffmpeg, video, audio, master_path, plan["master"])
        variant_paths = []
        for variant in plan["variants"]:
            dest = package / variant["filename"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            _variant(ffmpeg, master_path, dest, variant, plan["master"]["frame_rate"])
            variant_paths.append(f"{relative}/{variant['filename']}")
        poster_rel = None
        poster = plan["poster"]
        if poster.get("source_file"):
            poster_path = package / poster["filename"]
            _poster(ffmpeg, folder / str(poster["source_file"]), poster_path, poster)
            poster_rel = f"{relative}/{poster['filename']}"
        burned = _burn(ffmpeg, package, master_path, plan)
        note = (
            f"Rendered {master_name}. {plan['master']['note']} {audio_note} "
            f"{len(variant_paths)} variant(s)."
        )
        if burned:
            note += " Captions were burned into a second master."
        elif plan["captions"]["mode"] in {"burned-in", "both"}:
            note += " Burned-in captions were not written. The sidecar files are the captions."
        return {
            "status": "rendered",
            "note": note,
            "master": f"{relative}/{master_name}",
            "variants": variant_paths,
            "poster": poster_rel,
            "burned": burned,
        }
    except DeliveryError as exc:
        return {
            "status": "failed",
            "note": f"ffmpeg did not finish the package. The plan and the caption sidecars are written. {exc}",
            "master": None,
            "variants": [],
            "poster": None,
            "burned": None,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _render_segment(ffmpeg: str, folder: Path, event: dict, master: dict, dest: Path) -> None:
    source = folder / str(event.get("source_file") or "")
    if not source.is_file():
        raise DeliveryError(f"A locked shot is missing its file: {event.get('source_file')}.")
    duration = max(float(event.get("duration_seconds") or 0), 0.1)
    width = int(master["width"])
    height = int(master["height"])
    rate = float(master["frame_rate"])
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={rate}"
    if source.suffix.lower() in _IMAGE_SUFFIXES:
        command = [
            ffmpeg, "-y", "-loop", "1", "-i", str(source), "-t", f"{duration:.3f}",
            "-vf", vf, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(dest),
        ]
    else:
        start = max(float(event.get("source_in") or 0), 0)
        command = [
            ffmpeg, "-y", "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
            "-vf", vf, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(dest),
        ]
    _run_ffmpeg(command)


def _concat(ffmpeg: str, segments: list[Path], dest: Path) -> None:
    listing = dest.with_suffix(".txt")
    lines = []
    for segment in segments:
        escaped = str(segment).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run_ffmpeg(
        [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", str(dest),
        ]
    )


def _loudnorm_trim(ffmpeg: str, mix: Path, loudness: dict, runtime: float, dest: Path) -> None:
    integrated = float(loudness["integrated_lufs"])
    peak = min(float(loudness["true_peak_dbtp"]), -1.0)
    _run_ffmpeg(
        [
            ffmpeg, "-y", "-i", str(mix), "-t", f"{max(runtime, 0.1):.3f}",
            "-af", f"loudnorm=I={integrated}:TP={peak}:LRA=11",
            "-c:a", "pcm_s16le", str(dest),
        ]
    )


def _silence(ffmpeg: str, runtime: float, dest: Path) -> None:
    _run_ffmpeg(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={max(runtime, 0.1):.3f}",
            "-c:a", "pcm_s16le", str(dest),
        ]
    )


def _mux(ffmpeg: str, video: Path, audio: Path, dest: Path, master: dict) -> None:
    if master["codec"] == "prores":
        video_args = ["-c:v", master["encoder"], "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
        audio_args = ["-c:a", "pcm_s16le"]
    else:
        crf = master["crf"] if master["crf"] is not None else 18
        video_args = [
            "-c:v", "libx264", "-profile:v", "high", "-crf", str(crf),
            "-preset", "veryfast", "-pix_fmt", "yuv420p",
        ]
        audio_args = ["-c:a", "aac", "-b:a", "192k"]
    _run_ffmpeg(
        [
            ffmpeg, "-y", "-i", str(video), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0",
            *video_args, *audio_args, "-shortest", str(dest),
        ]
    )


def _variant(ffmpeg: str, master: Path, dest: Path, variant: dict, frame_rate: float) -> None:
    width = int(variant["width"])
    height = int(variant["height"])
    if variant.get("crop") == "center":
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={frame_rate}"
    else:
        vf = f"scale={width}:{height},fps={frame_rate}"
    _run_ffmpeg(
        [
            ffmpeg, "-y", "-i", str(master), "-vf", vf,
            "-c:v", "libx264", "-profile:v", "high", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", str(dest),
        ]
    )


def _poster(ffmpeg: str, source: Path, dest: Path, poster: dict) -> None:
    if not source.is_file():
        raise DeliveryError(f"The poster shot file is missing: {source.name}.")
    width = int(poster["width"])
    height = int(poster["height"])
    moment = max(float(poster.get("time_seconds") or 0), 0)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    if source.suffix.lower() in _IMAGE_SUFFIXES:
        command = [ffmpeg, "-y", "-i", str(source), "-vf", vf, "-frames:v", "1", str(dest)]
    else:
        command = [ffmpeg, "-y", "-ss", f"{moment:.3f}", "-i", str(source), "-vf", vf, "-frames:v", "1", str(dest)]
    _run_ffmpeg(command)


def _burn(ffmpeg: str, package: Path, master: Path, plan: dict) -> str | None:
    if plan["captions"]["mode"] not in {"burned-in", "both"}:
        return None
    srt = package / "captions.srt"
    if not srt.is_file() or not master.is_file():
        return None
    dest = package / "master-burned.mp4"
    escaped = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    try:
        _run_ffmpeg(
            [
                ffmpeg, "-y", "-i", str(master),
                "-vf", f"subtitles='{escaped}'",
                "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-c:a", "copy", str(dest),
            ]
        )
    except DeliveryError:
        if dest.exists():
            dest.unlink()
        return None
    return f"{plan['location']['relative']}/master-burned.mp4"


def _video_checks(path: Path, label: str, slug: str, spec: dict, loudness: dict, tolerances: dict, runtime: float) -> list[dict]:
    if not path.is_file() or path.stat().st_size == 0:
        return [
            _check(f"{slug}-file", label, "file", "skipped", "The file was not rendered, so this check did not run.")
        ]
    probe = _probe_media(path)
    checks = [_check(f"{slug}-file", label, "file", "pass", "The file is on disk.")]
    duration = probe.get("duration_seconds")
    tolerance = float(tolerances["duration_tolerance_seconds"])
    if duration is None:
        checks.append(_check(f"{slug}-duration", label, "duration", "skipped", probe.get("summary") or "Duration was not read."))
    elif abs(duration - runtime) > tolerance:
        checks.append(
            _check(
                f"{slug}-duration",
                label,
                "duration",
                "fail",
                f"Duration is {duration:.2f}s. The cut is {runtime:.2f}s. Tolerance is {tolerance:.2f}s.",
            )
        )
    else:
        checks.append(
            _check(
                f"{slug}-duration",
                label,
                "duration",
                "pass",
                f"Duration is {duration:.2f}s. The cut is {runtime:.2f}s.",
            )
        )
    width = probe.get("width")
    height = probe.get("height")
    if width is None or height is None:
        checks.append(_check(f"{slug}-resolution", label, "resolution", "skipped", "Resolution was not read."))
    elif int(width) != int(spec["width"]) or int(height) != int(spec["height"]):
        checks.append(
            _check(
                f"{slug}-resolution",
                label,
                "resolution",
                "fail",
                f"The file is {width}x{height}. The spec asks for {spec['width']}x{spec['height']}.",
            )
        )
    else:
        checks.append(
            _check(
                f"{slug}-resolution",
                label,
                "resolution",
                "pass",
                f"The file is {width}x{height}.",
            )
        )
    rate = probe.get("frame_rate")
    expected_rate = float(spec.get("frame_rate") or 0)
    rate_tolerance = float(tolerances["frame_rate_tolerance"])
    if rate is None or not expected_rate:
        checks.append(_check(f"{slug}-frame-rate", label, "frame-rate", "skipped", "Frame rate was not read."))
    elif abs(rate - expected_rate) > rate_tolerance:
        checks.append(
            _check(
                f"{slug}-frame-rate",
                label,
                "frame-rate",
                "fail",
                f"Frame rate is {rate:.3f} fps. The spec asks for {expected_rate:g} fps.",
            )
        )
    else:
        checks.append(_check(f"{slug}-frame-rate", label, "frame-rate", "pass", f"Frame rate is {rate:.3f} fps."))
    checks.append(_loudness_check(path, label, slug, probe, loudness, tolerances))
    checks.append(_span_check(path, label, slug, "black", "blackdetect", "black_start", float(tolerances["black_max_seconds"])))
    checks.append(_span_check(path, label, slug, "frozen", "freezedetect", "freeze_start", float(tolerances["freeze_max_seconds"])))
    return checks


def _loudness_check(path: Path, label: str, slug: str, probe: dict, loudness: dict, tolerances: dict) -> dict:
    if not probe.get("has_audio"):
        return _check(f"{slug}-loudness", label, "loudness", "skipped", "This file has no audio, so loudness was not measured.")
    duration = probe.get("duration_seconds") or 0
    if duration < 3:
        return _check(
            f"{slug}-loudness",
            label,
            "loudness",
            "skipped",
            "The file is shorter than 3 seconds, so integrated loudness was not judged.",
        )
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return _check(f"{slug}-loudness", label, "loudness", "skipped", "ffmpeg is not installed, so loudness was not measured.")
    from movie_swarm.color_mix import _read_loudness

    integrated, peak, meter = _read_loudness(ffmpeg, path)
    if integrated is None and peak is None:
        return _check(f"{slug}-loudness", label, "loudness", "skipped", "Loudness could not be read.")
    tolerance = float(tolerances["loudness_tolerance_lufs"])
    reasons = []
    if integrated is not None and abs(integrated - float(loudness["integrated_lufs"])) > tolerance:
        reasons.append(
            f"Integrated loudness is {integrated:.1f} LUFS. The target is {float(loudness['integrated_lufs']):.1f} LUFS, "
            f"plus or minus {tolerance:.1f}."
        )
    if peak is not None and peak > float(loudness["true_peak_dbtp"]) + 0.05:
        reasons.append(
            f"True peak is {peak:.1f} dBTP. The limit is {float(loudness['true_peak_dbtp']):.1f} dBTP."
        )
    if reasons:
        return _check(f"{slug}-loudness", label, "loudness", "fail", " ".join(reasons) + f" Measured with {meter}.")
    return _check(
        f"{slug}-loudness",
        label,
        "loudness",
        "pass",
        f"Integrated loudness is {integrated if integrated is not None else 'unread'} LUFS "
        f"and true peak is {peak if peak is not None else 'unread'} dBTP. Measured with {meter}.",
    )


def _span_check(path: Path, label: str, slug: str, kind: str, filter_name: str, needle: str, limit: float) -> dict:
    if shutil.which("ffmpeg") is None:
        return _check(f"{slug}-{kind}", label, kind, "skipped", "ffmpeg is not installed, so this check did not run.")
    duration = max(limit, 0.1)
    if filter_name == "blackdetect":
        video_filter = f"blackdetect=d={duration}:pix_th=0.10"
        problem = "black"
    else:
        video_filter = f"freezedetect=n=0.003:d={duration}"
        problem = "frozen"
    hit = _filter_hit(path, video_filter, needle)
    if hit is None:
        return _check(f"{slug}-{kind}", label, kind, "skipped", "ffmpeg could not scan this file.")
    if hit:
        return _check(
            f"{slug}-{kind}",
            label,
            kind,
            "fail",
            f"The file has a {problem} stretch of at least {duration:.2f}s. The limit is {limit:.2f}s.",
        )
    return _check(
        f"{slug}-{kind}",
        label,
        kind,
        "pass",
        f"No {problem} stretch longer than {limit:.2f}s.",
    )


def _poster_checks(path: Path, label: str, poster: dict) -> list[dict]:
    if not path.is_file() or path.stat().st_size == 0:
        return [_check("poster-file", label, "file", "skipped", "The poster was not rendered, so this check did not run.")]
    probe = _probe_media(path)
    checks = [_check("poster-file", label, "file", "pass", "The poster file is on disk.")]
    width = probe.get("width")
    height = probe.get("height")
    if width is None or height is None:
        checks.append(_check("poster-resolution", label, "resolution", "skipped", "Poster resolution was not read."))
    elif int(width) != int(poster["width"]) or int(height) != int(poster["height"]):
        checks.append(
            _check(
                "poster-resolution",
                label,
                "resolution",
                "fail",
                f"The poster is {width}x{height}. The spec asks for {poster['width']}x{poster['height']}.",
            )
        )
    else:
        checks.append(_check("poster-resolution", label, "resolution", "pass", f"The poster is {width}x{height}."))
    return checks


def _caption_check(package: Path, plan: dict, runtime: float) -> dict:
    captions = plan.get("captions") or {}
    cues = captions.get("cues") or []
    label = ", ".join(captions.get("files") or []) or "captions"
    problems = []
    for cue in cues:
        start = float(cue["start_seconds"])
        end = float(cue["end_seconds"])
        if start < -0.001 or end > runtime + 0.001 or end <= start:
            problems.append(
                f"{cue['cue_id']} runs {start:.3f}s to {end:.3f}s. The cut runs 0.000s to {runtime:.3f}s."
            )
    for name in ("captions.srt", "captions.vtt"):
        if name.split(".")[-1] not in set(captions.get("formats") or []):
            continue
        path = package / name
        if not path.is_file():
            problems.append(f"{name} was not written.")
            continue
        parsed = _parse_caption_times(path.read_text(encoding="utf-8"))
        if len(parsed) != len(cues):
            problems.append(f"{name} has {len(parsed)} cue(s). The cue sheet has {len(cues)} dialogue cue(s).")
        for start, end in parsed:
            if start < -0.001 or end > runtime + 0.001 or end <= start:
                problems.append(f"{name} has a cue from {start:.3f}s to {end:.3f}s, outside the cut.")
    if problems:
        return _check("captions-timing", label, "captions", "fail", " ".join(problems))
    if not cues:
        return _check("captions-timing", label, "captions", "pass", "No dialogue cues. The caption files are empty.")
    return _check(
        "captions-timing",
        label,
        "captions",
        "pass",
        f"{len(cues)} dialogue cue(s) sit inside the {runtime:.3f}s cut.",
    )


def _parse_caption_times(text: str) -> list[tuple[float, float]]:
    pattern = re.compile(
        r"(\d\d):(\d\d):(\d\d)[.,](\d\d\d)\s*-->\s*(\d\d):(\d\d):(\d\d)[.,](\d\d\d)"
    )
    found = []
    for match in pattern.finditer(text):
        parts = [int(piece) for piece in match.groups()]
        start = parts[0] * 3600 + parts[1] * 60 + parts[2] + parts[3] / 1000
        end = parts[4] * 3600 + parts[5] * 60 + parts[6] + parts[7] / 1000
        found.append((start, end))
    return found


def _manifest(
    folder: Path,
    plan: dict,
    qc: dict,
    package: Path,
    *,
    spent_usd: float,
    budget_cap_usd: float,
    stage_split: dict,
    stage_spent: dict,
    gate_records: list,
) -> dict:
    relative = plan["location"]["relative"]
    files = []
    files.append(_file_row(package / "delivery-plan.json", f"{relative}/delivery-plan.json", "plan", "Delivery plan"))
    prefix = relative.rstrip("/") + "/"
    for listed in plan["captions"].get("files") or []:
        name = listed[len(prefix):] if listed.startswith(prefix) else listed
        files.append(_file_row(package / name, listed, "captions", "Captions"))
    master_name = plan["master"]["filename"]
    files.append(
        _file_row(
            package / master_name,
            f"{relative}/{master_name}",
            "master",
            f"Master {plan['master']['codec']} {plan['master']['width']}x{plan['master']['height']}",
        )
    )
    for variant in plan["variants"]:
        files.append(
            _file_row(
                package / variant["filename"],
                f"{relative}/{variant['filename']}",
                "variant",
                f"{variant['id']} {variant['width']}x{variant['height']} crop {variant['crop']}",
            )
        )
    if plan["render"].get("burned"):
        files.append(
            _file_row(package / "master-burned.mp4", plan["render"]["burned"], "master", "Master with burned-in captions")
        )
    poster_name = plan["poster"]["filename"]
    files.append(
        _file_row(package / poster_name, f"{relative}/{poster_name}", "poster", f"Poster from {plan['poster']['shot_id']}")
    )
    from movie_swarm.graphics import package_files

    for item in package_files(folder):
        files.append(_file_row(item["path"], item["listed"], "graphics", item["label"]))
    files.append(_file_row(package / "qc-report.json", f"{relative}/qc-report.json", "qc", "QC report"))
    cap = float(budget_cap_usd)
    spent = float(spent_usd)
    return {
        "version": "1.0.0",
        "production_id": folder.name,
        "kind": "delivery-manifest",
        "created_at": _now(),
        "ready_for_delivery_approval": qc["verdict"] == "pass",
        "delivery_approved": False,
        "delivered": False,
        "approved_by": None,
        "approved_at": None,
        "approval_note": "",
        "spent_usd": 0,
        "qc_verdict": qc["verdict"],
        "qc_report": f"{relative}/qc-report.json",
        "plan": f"{relative}/delivery-plan.json",
        "location": plan["location"],
        "spend": {
            "spent_usd": round(spent, 2),
            "budget_cap_usd": round(cap, 2),
            "within_cap": spent <= cap + 0.0001,
            "currency": "USD",
            "stage_split": {str(key): float(value) for key, value in stage_split.items()},
            "stage_spent": {str(key): float(value) for key, value in stage_spent.items()},
            "rate_status": "unknown",
            "note": (
                "Delivery did not add a budget line and did not charge the cap. "
                "No delivery rate is on the rate card, so a paid packaging price is unknown and is not stored as zero. "
                f"The film has spent ${spent:.2f} of ${cap:.2f}."
            ),
        },
        "gates": _gate_rows(gate_records),
        "files": files,
        "budget": plan["budget"],
        "models": plan["models"],
        "standards": plan["standards"],
        "checksum": _SHA_CITATION,
        "draft_method": "offline-deterministic",
    }


def _gate_rows(records: list) -> list[dict]:
    rows = []
    seen = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage") or "")
        if not stage:
            continue
        rows.append(
            {
                "stage": stage,
                "decision": str(item.get("decision") or "pending"),
                "by": item.get("by"),
                "decided_at": item.get("decided_at"),
                "note": str(item.get("note") or ""),
            }
        )
        seen.add(stage)
    try:
        configured = list(load_gate_config()["gates"])
    except (OSError, HandoffError, KeyError):
        configured = []
    for stage in configured:
        if stage in seen:
            continue
        rows.append(
            {
                "stage": stage,
                "decision": "pending",
                "by": None,
                "decided_at": None,
                "note": "No decision is recorded.",
            }
        )
    return rows


def _file_row(path: Path, listed: str, role: str, label: str) -> dict:
    if path.is_file() and path.stat().st_size > 0:
        return {
            "path": listed,
            "role": role,
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "status": "present",
            "label": label,
        }
    return {
        "path": listed,
        "role": role,
        "sha256": None,
        "bytes": None,
        "status": "not-rendered",
        "label": label,
    }


def _write_plan(package: Path, plan: dict) -> tuple[Path, Path]:
    data_path = package / "delivery-plan.json"
    text_path = package / "delivery-plan.md"
    write_handoff(data_path, plan, schema="delivery-plan")
    text_path.write_text(render_plan_markdown(plan), encoding="utf-8")
    return data_path, text_path


def _write_qc(package: Path, report: dict) -> tuple[Path, Path]:
    data_path = package / "qc-report.json"
    text_path = package / "qc-report.md"
    write_handoff(data_path, report, schema="qc-report")
    text_path.write_text(render_qc_markdown(report), encoding="utf-8")
    return data_path, text_path


def _write_manifest(package: Path, manifest: dict) -> tuple[Path, Path]:
    data_path = package / "delivery-manifest.json"
    text_path = package / "delivery-manifest.md"
    write_handoff(data_path, manifest, schema="delivery-manifest")
    _write_manifest_markdown(text_path, manifest)
    return data_path, text_path


def _write_manifest_markdown(path: Path, manifest: dict) -> None:
    spend = manifest["spend"]
    lines = [
        f"Delivery manifest for {manifest['production_id']}",
        "",
        "JSON is the manifest. This page is the reading copy.",
        "",
        (
            f"Film spend: ${spend['spent_usd']:.2f} of ${spend['budget_cap_usd']:.2f}. "
            f"Within the cap: {spend['within_cap']}."
        ),
        spend["note"],
        "",
        "Stage split:",
    ]
    if not spend["stage_split"]:
        lines.append("No locked split was passed in.")
    for stage, amount in spend["stage_split"].items():
        used = spend["stage_spent"].get(stage, 0)
        lines.append(f"- {stage}: ${float(used):.2f} of ${float(amount):.2f}")
    lines.extend(["", "Gates:"])
    for gate in manifest["gates"]:
        who = gate["by"] or "nobody yet"
        when = gate["decided_at"] or "no time recorded"
        lines.append(f"- {gate['stage']}: {gate['decision']} by {who} at {when}. {gate['note']}")
    lines.extend(["", "| File | Status | SHA-256 |", "| --- | --- | --- |"])
    for item in manifest["files"]:
        digest = item["sha256"] or ""
        lines.append(f"| {item['path']} | {item['status']} | {digest} |")
    lines.extend(["", manifest["checksum"]])
    if manifest["delivered"]:
        lines.extend(["", f"Delivered. Approved by {manifest['approved_by']} at {manifest['approved_at']}."])
    else:
        lines.extend(["", "Not delivered. The delivery gate has not been approved."])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _register(producer, production: Path, result: dict) -> None:
    package = result["package_dir"]
    relative = result["plan"]["location"]["relative"]

    def slot(name: str) -> str:
        return f"{relative}/{name}"

    producer.ensure_artifact("delivery-plan", slot("delivery-plan.json"), "delivery-plan.schema.json")
    producer.ensure_artifact("delivery-plan-notes", slot("delivery-plan.md"))
    producer.ensure_artifact("qc-report", slot("qc-report.json"), "qc-report.schema.json")
    producer.ensure_artifact("qc-report-notes", slot("qc-report.md"))
    producer.ensure_artifact("delivery-manifest", slot("delivery-manifest.json"), "delivery-manifest.schema.json")
    producer.ensure_artifact("delivery-manifest-notes", slot("delivery-manifest.md"))
    if package.resolve() != (production / "delivery").resolve():
        producer.ensure_artifact("delivery-location", "delivery/location.json")


def _load_cut(folder: Path) -> dict:
    path = folder / "edit" / "picture-lock.json"
    if not path.is_file():
        raise DeliveryError(
            "No picture-lock file at edit/picture-lock.json. Final delivery did not run."
        )
    try:
        data = read_handoff(path, schema="edit-decision-list")
    except HandoffError as exc:
        raise DeliveryError(str(exc)) from exc
    if data.get("kind") != "picture-lock":
        raise DeliveryError("edit/picture-lock.json is not a picture-lock cut, so final delivery did not run.")
    if not data.get("events"):
        raise DeliveryError("The picture-lock cut has no shots, so final delivery did not run.")
    return data


def _load_spec(folder: Path) -> tuple[dict, str | None]:
    path = folder / "delivery" / "delivery-spec.json"
    if not path.is_file():
        return {}, None
    try:
        data = read_handoff(path, schema="delivery-spec")
    except HandoffError as exc:
        raise DeliveryError(str(exc)) from exc
    return data, "delivery/delivery-spec.json"


def _spec_note(folder: Path, spec: dict, spec_source: str | None) -> str:
    if spec_source is None:
        return (
            "This production has no delivery/delivery-spec.json. "
            "The plan uses the cited platform defaults."
        )
    named = str(spec.get("production_id") or "")
    if named and named != folder.name:
        return (
            f"The delivery spec names production id {named}. "
            f"The plan uses the folder name {folder.name}."
        )
    return "The frame sizes, the codec, the variants, and the poster shot come from the delivery spec."


def _standards() -> list[dict]:
    return [
        {"id": "ITU-T H.264", "citation": _H264_CITATION},
        {"id": "Apple ProRes", "citation": _PRORES_CITATION},
        {"id": "ITU-R BT.709", "citation": _BT709_CITATION},
        {"id": "YouTube upload encoding", "citation": _WEB_CITATION},
        {"id": "EBU R128", "citation": _EBU_CITATION},
        {"id": "EBU R95", "citation": _SAFE_CITATION},
        {"id": "W3C WebVTT", "citation": _VTT_CITATION},
        {"id": "FIPS 180-4", "citation": _SHA_CITATION},
    ]


def _budget() -> dict:
    return {
        "stage": "editor",
        "estimated_usd": None,
        "rate_status": "unknown",
        "note": (
            "Delivery is checked against the editor allocation. No new budget line was added. "
            "No delivery rate is on the rate card. A paid packaging call would be unknown, and this build does not make one. "
            "ffmpeg is local. Nothing was charged."
        ),
    }


def _approval_line(ready: bool) -> str:
    if ready:
        return (
            "This package is ready for the delivery gate. It is not delivered until that gate is approved."
        )
    return (
        "This package is not ready for the delivery gate. "
        "A failed check is listed in the QC report. The film is not delivered."
    )


def _caption_mode(spec: dict) -> str:
    raw = spec.get("captions") if isinstance(spec.get("captions"), dict) else {}
    mode = str(raw.get("mode") or "sidecar").strip().casefold()
    if mode not in {"sidecar", "burned-in", "both"}:
        return "sidecar"
    return mode


def _caption_formats(spec: dict) -> list[str]:
    raw = spec.get("captions") if isinstance(spec.get("captions"), dict) else {}
    formats = raw.get("formats")
    if not isinstance(formats, list) or not formats:
        return ["srt", "vtt"]
    chosen = []
    for item in formats:
        name = str(item).strip().casefold().lstrip(".")
        if name in {"srt", "vtt"} and name not in chosen:
            chosen.append(name)
    return chosen or ["srt", "vtt"]


def _crop_mode(master_w: int, master_h: int, width: int, height: int) -> str:
    if master_h <= 0 or height <= 0:
        return "scale"
    if abs((master_w / master_h) - (width / height)) < 0.02:
        return "scale"
    return "center"


def _crop_guidance(crop: str, aspect: str) -> str:
    if crop == "center":
        return (
            f"Center-crop the master to {aspect}. "
            "Keep essential action in the region that remains after the crop. "
            "Keep titles inside the graphics-safe inset of the delivered frame."
        )
    return (
        f"Scale the master to {aspect}. No crop. "
        "Keep titles inside the graphics-safe inset of the delivered frame."
    )


def _aspect_name(width: int, height: int) -> str:
    if height <= 0:
        return "16:9"
    ratio = width / height
    known = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1}
    for name, value in known.items():
        if abs(ratio - value) < 0.02:
            return name
    return f"{width}:{height}"


def _probe_media(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    empty = {"duration_seconds": None, "width": None, "height": None, "frame_rate": None, "has_audio": False, "summary": ""}
    if not ffprobe:
        empty["summary"] = "ffprobe is not installed."
        return empty
    try:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        empty["summary"] = "ffprobe did not finish."
        return empty
    if completed.returncode != 0 or not completed.stdout.strip():
        empty["summary"] = "ffprobe could not read this file."
        return empty
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        empty["summary"] = "ffprobe did not return readable data."
        return empty
    streams = data.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = any(item.get("codec_type") == "audio" for item in streams)
    duration = (data.get("format") or {}).get("duration")
    seconds = _number(duration)
    return {
        "duration_seconds": seconds if seconds and seconds > 0 else None,
        "width": video.get("width"),
        "height": video.get("height"),
        "frame_rate": _frame_rate(video.get("avg_frame_rate")),
        "has_audio": audio,
        "summary": "ffprobe read the file.",
    }


def _check(check_id: str, target: str, kind: str, status: str, detail: str) -> dict:
    return {
        "check_id": check_id,
        "target": target,
        "kind": kind,
        "status": status,
        "detail": detail,
    }


def _rel_name(plan: dict, name: str) -> str:
    relative = plan.get("location", {}).get("relative") or "delivery"
    return f"{relative}/{name}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _srt_time(seconds: float) -> str:
    return _clock(seconds, ",")


def _vtt_time(seconds: float) -> str:
    return _clock(seconds, ".")


def _clock(seconds: float, separator: str) -> str:
    millis = int(round(max(seconds, 0) * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _model(role: str, purpose: str) -> str:
    try:
        return str(resolve_model(role, purpose=purpose).get("model") or "")
    except ModelRoutingError:
        return ""


def _ensure_credit(producer, role: str, name: str) -> None:
    have = {item["role"] for item in producer.record["credits"]}
    if role in have:
        return
    producer.record["credits"].append({"role": role, "name": name})
    producer._save_record()


def _latest_by(producer, stage: str) -> str:
    found = "recorded"
    for item in producer.record.get("gate_decisions") or []:
        if item.get("stage") == stage and item.get("decision") == "approved":
            found = str(item.get("by") or found)
    return found


def _latest_note(producer, stage: str) -> str:
    found = ""
    for item in producer.record.get("gate_decisions") or []:
        if item.get("stage") == stage and item.get("decision") == "approved":
            found = str(item.get("note") or "")
    return found


def _latest_when(producer, stage: str) -> str:
    found = _now()
    for item in producer.record.get("gate_decisions") or []:
        if item.get("stage") == stage and item.get("decision") == "approved" and item.get("decided_at"):
            found = str(item["decided_at"])
    return found


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned or "item"


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_ffmpeg(command: list[str]) -> None:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeliveryError(f"ffmpeg did not finish. {exc}") from exc
    if completed.returncode != 0:
        tail = " ".join((completed.stderr or "").strip().splitlines()[-6:])
        raise DeliveryError(tail or f"ffmpeg exited {completed.returncode}.")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
