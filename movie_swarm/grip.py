"""Key Grip: camera support and rigging for each shot.

Support follows the shot list's movement. Rigging follows the gaffer's plan.
A rig the documents do not name is not added. A package that asks for one
support while the shot asks for another is flagged, and the shot list wins.
"""

from __future__ import annotations

from pathlib import Path

from movie_swarm.camera import package_path
from movie_swarm.gaffer import plan_path
from movie_swarm.prep_inputs import load_shots
from movie_swarm.previs_common import (
    approved_treatment,
    load_optional,
    model_name,
    now,
    save_pair,
    source_blob,
    system_prompt,
    try_model_json,
)


def grip_path(production_dir: Path) -> Path:
    return production_dir / "grip" / "grip-plan.json"


def support_for(movement: str) -> tuple[str, str]:
    """Map a shot-list movement to a support. Unknown movement is left as written."""
    text = (movement or "").casefold()
    if any(word in text for word in ("crane", "jib")):
        return "crane", "The shot list asks for a crane or a jib."
    if any(word in text for word in ("dolly", "track", "push", "pull")):
        return "dolly", "The shot list asks for a move along the ground."
    if "steadicam" in text:
        return "steadicam", "The shot list asks for a stabilized body rig."
    if "handheld" in text or "hand held" in text:
        return "handheld", "The shot list asks for a handheld camera."
    if any(word in text for word in ("pan", "tilt")):
        return "head", "The shot list asks for a pan or a tilt on a head."
    if not text or "static" in text or "locked" in text:
        return "sticks", "The shot list asks for a static camera."
    return "as-written", f"The shot list says: {movement}. No support was invented."


def build_grip_plan(production_dir: Path, llm=None) -> dict:
    production_dir = Path(production_dir)
    approved_treatment(production_dir)
    shots, shot_source = load_shots(production_dir)
    package = load_optional(package_path(production_dir), "camera-package")
    gaffer = load_optional(plan_path(production_dir), "lighting-plan")
    offline = _offline(production_dir, shots, shot_source, package, gaffer)
    drafted = _from_model(llm, offline)
    document = drafted or offline
    save_pair(grip_path(production_dir), document, "grip-plan", _markdown(document))
    return document


def _offline(production_dir, shots, shot_source, package, gaffer) -> dict:
    by_scene = {}
    if gaffer:
        for scene in gaffer.get("scenes") or []:
            if isinstance(scene, dict) and scene.get("scene_id"):
                by_scene[scene["scene_id"]] = scene
    package_support = _package_support(package)
    rows = []
    for shot in shots:
        support, support_note = support_for(shot.get("camera_movement") or "")
        scene = by_scene.get(shot.get("scene_id"))
        rigging = _rigging(scene)
        consistent_camera, camera_note = _camera_check(support, package_support, shot)
        consistent_gaffer = scene is not None
        gaffer_note = (
            "Rigging uses the gaffer's plan for this scene."
            if scene is not None
            else "No lighting plan for this scene. No flag, bounce, or extra source was added."
        )
        note = " ".join(part for part in (support_note, camera_note, gaffer_note) if part)
        rows.append(
            {
                "shot_id": shot["shot_id"],
                "scene_id": shot.get("scene_id") or "unassigned",
                "camera_movement": shot.get("camera_movement") or "not named",
                "support": support,
                "rigging": rigging,
                "consistent_with_camera": consistent_camera,
                "consistent_with_gaffer": consistent_gaffer,
                "note": note,
            }
        )
    return {
        "version": "1.0.0",
        "production_id": production_dir.name,
        "source": {
            "shots": shot_source,
            "camera": "camera/camera-package.json" if package else None,
            "lighting": "lighting/lighting-plan.json" if gaffer else None,
        },
        "package_support": package_support or "not named",
        "shots": rows,
        "draft_method": "offline-deterministic",
        "model": model_name("key-grip", "plan"),
        "note": "Support follows the shot list. Rigging follows the gaffer. Nothing else was added.",
        "created_at": now(),
    }


def _package_support(package: dict | None) -> str | None:
    if not package:
        return None
    parts = [str(package.get("summary") or ""), str(package.get("look_name") or "")]
    for lens in package.get("lenses") or []:
        if isinstance(lens, dict):
            parts.append(str(lens.get("name") or ""))
            parts.append(str(lens.get("use") or ""))
    blob = " ".join(parts).casefold()
    for word in ("handheld", "hand held", "dolly", "crane", "sticks", "tripod", "static"):
        if word in blob:
            if word == "hand held":
                return "handheld"
            if word == "tripod":
                return "sticks"
            return word
    return None


def _camera_check(support: str, package_support: str | None, shot: dict) -> tuple[bool, str]:
    if not package_support or package_support == support:
        return True, "The support matches the camera package." if package_support else "The camera package did not name a support."
    if support == "as-written":
        return True, "The shot list did not name a standard support, so it was not forced to match the package."
    movement = shot.get("camera_movement") or "not named"
    return (
        False,
        f"The camera package says {package_support}. The shot list says {movement}, so the support stays {support}.",
    )


def _rigging(scene: dict | None) -> str:
    if not scene:
        return "No lighting plan was found for this scene. No flag, bounce, or extra source was added."
    practicals = str(scene.get("practicals") or "not named")
    fill = str(scene.get("fill") or "not named")
    parts = []
    if practicals != "not named":
        parts.append(f"Shape spill only around the practical the gaffer named: {practicals}")
    else:
        parts.append("The gaffer did not name a practical. Do not add one.")
    if fill == "not named":
        parts.append("The gaffer did not name a fill. Do not add one.")
    else:
        parts.append(f"Fill stays what the gaffer named: {fill}")
    return " ".join(parts)


def _from_model(llm, offline) -> dict | None:
    if llm is None:
        return None
    drafted = try_model_json(
        llm,
        role="key-grip",
        purpose="plan",
        system=system_prompt(
            "You are the Key Grip. Rewrite the note only. Do not change the support or the rigging. "
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


def _markdown(document: dict) -> str:
    lines = ["# Grip plan", "", document.get("note") or "", ""]
    for shot in document.get("shots") or []:
        lines.append(f"## {shot['shot_id']}")
        lines.append("")
        lines.append(f"Support: {shot['support']}.")
        lines.append(shot["rigging"])
        lines.append(shot["note"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
