"""
pipeline.py — The Sound Designer agent's core execution loop.

Reads the shot list (for sound_notes per shot) and clip metadata (for
native audio status), then generates missing audio assets via ElevenLabs.

Usage:
    from src.pipeline import SoundDesignPipeline
    pipeline = SoundDesignPipeline(
        shot_list_path="shot-lists/shot-list.json",
        output_dir="audio/",
    )
    pipeline.generate_sfx_library()     # Generate all needed SFX
    pipeline.generate_dialogue()         # Generate dialogue lines
    pipeline.generate_music()            # Generate score
    pipeline.write_audio_manifest()      # Write structured output
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .elevenlabs_client import generate_sfx, generate_dialogue, generate_music

logger = logging.getLogger("sound_designer.pipeline")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class AudioAsset:
    """A single audio asset (SFX, dialogue, music, or ambient)."""
    asset_id: str
    asset_type: str          # "sfx", "dialogue", "music", "ambient"
    prompt: str
    dest_path: str
    duration: Optional[float] = None
    prompt_influence: float = 0.5
    generated: bool = False
    local_path: str = ""
    error: Optional[str] = None
    # Dialogue-specific
    voice_id: Optional[str] = None
    text: Optional[str] = None
    # Shot assignments
    assigned_shots: list[str] = field(default_factory=list)
    layer_notes: str = ""


@dataclass
class ShotAudioPlan:
    """Audio plan for a single shot."""
    shot_id: str
    sound_notes: str
    color_notes: str
    native_audio_status: str   # "keep", "replace", "fill", "layer"
    assigned_assets: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shot list loader (sound-relevant fields only)
# ---------------------------------------------------------------------------


def load_sound_plan(shot_list_path: str | Path) -> list[ShotAudioPlan]:
    """Extract sound-relevant info from the shot list."""
    raw = json.loads(Path(shot_list_path).read_text())
    plans = []
    for s in raw.get("shots", []):
        plans.append(ShotAudioPlan(
            shot_id=s["shot_id"],
            sound_notes=s.get("sound_notes", ""),
            color_notes=s.get("color_notes", ""),
            native_audio_status="layer",  # default: assume native audio exists but needs layering
            assigned_assets=[],
        ))
    return plans


# ---------------------------------------------------------------------------
# Sound library
# ---------------------------------------------------------------------------

# Prompts live in the production folder, in audio/sound-prompts.json.
# This program loads that file. It does not keep a film's prompts.


def _asset(item: dict, default_type: str) -> AudioAsset:
    """One library row, whatever production wrote it."""
    asset_id = str(item["asset_id"])
    return AudioAsset(
        asset_id=asset_id,
        asset_type=str(item.get("asset_type") or default_type),
        prompt=str(item.get("prompt") or ""),
        dest_path=str(item.get("dest_path") or f"{default_type}/{asset_id}.mp3"),
        duration=item.get("duration"),
        prompt_influence=float(item.get("prompt_influence", 0.5)),
        voice_id=item.get("voice_id"),
        text=item.get("text"),
        assigned_shots=[str(shot) for shot in item.get("assigned_shots") or []],
        layer_notes=str(item.get("layer_notes") or ""),
    )


def load_sound_library(path: str | Path) -> dict:
    """Read sfx, dialogue, and music prompts from a production file."""
    library_path = Path(path)
    data = json.loads(library_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{library_path} must be a JSON object.")
    return {
        "production_id": str(data.get("production_id") or ""),
        "path": str(library_path),
        "sfx": [_asset(item, "sfx") for item in data.get("sfx") or [] if isinstance(item, dict)],
        "dialogue": [_asset(item, "dialogue") for item in data.get("dialogue") or [] if isinstance(item, dict)],
        "music": [_asset(item, "music") for item in data.get("music") or [] if isinstance(item, dict)],
    }


def find_sound_library(shot_list_path: str | Path) -> Path | None:
    """Walk up from a shot list to audio/sound-prompts.json. Stop at the first hit."""
    current = Path(shot_list_path).resolve()
    for parent in [current.parent, *list(current.parents)[:8]]:
        candidate = parent / "audio" / "sound-prompts.json"
        if candidate.is_file():
            return candidate
    return None


def _refuse_paid_audio() -> None:
    raise RuntimeError(
        "Paid audio generation is closed in this build. "
        "A real run has to go through the Director, and Ron has to approve the generation gate. "
        "No audio was requested."
    )



# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class SoundDesignPipeline:
    """
    Orchestrates audio asset generation for a production.

    Usage:
        pipeline = SoundDesignPipeline("shot-list.json", "audio/")
        pipeline.generate_sfx_library()
        pipeline.generate_dialogue(voice_id="JBFqnCBsd6RMkjVDRZzb")
        pipeline.generate_music()
        pipeline.write_audio_manifest()
    """

    def __init__(
        self,
        shot_list_path: str | Path,
        output_dir: str | Path,
        library_path: str | Path | None = None,
    ):
        self.shot_plans = load_sound_plan(shot_list_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        library_file = Path(library_path) if library_path else find_sound_library(shot_list_path)
        if library_file is not None and Path(library_file).is_file():
            loaded = load_sound_library(library_file)
        else:
            loaded = {"production_id": "", "sfx": [], "dialogue": [], "music": []}
        self.production_id = loaded["production_id"]
        if not self.production_id:
            try:
                raw = json.loads(Path(shot_list_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            if isinstance(raw, dict):
                self.production_id = str(raw.get("production_id") or "")
        self.sfx_assets = list(loaded["sfx"])
        self.dialogue_assets = list(loaded["dialogue"])
        self.music_assets = list(loaded["music"])
        self.generation_log: list[dict] = []

    def generate_sfx_library(
        self,
        asset_ids: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> list[AudioAsset]:
        """Generate sound effects. Optionally filter by asset_id."""
        if not dry_run:
            _refuse_paid_audio()
        assets = self.sfx_assets
        if asset_ids:
            id_set = set(asset_ids)
            assets = [a for a in assets if a.asset_id in id_set]

        logger.info("Generating %d sound effects...", len(assets))

        for i, asset in enumerate(assets, 1):
            dest = self.output_dir / asset.dest_path
            logger.info("[%d/%d] %s → %s", i, len(assets), asset.asset_id, dest)

            if dry_run:
                logger.info("  [DRY RUN] prompt: %s...", asset.prompt[:80])
                continue

            try:
                result = generate_sfx(
                    prompt=asset.prompt,
                    dest_path=dest,
                    duration=asset.duration,
                    prompt_influence=asset.prompt_influence,
                )
                asset.generated = True
                asset.local_path = result["local_path"]
                self.generation_log.append({
                    "asset_id": asset.asset_id,
                    "type": "sfx",
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error("  Failed: %s", e)
                asset.error = str(e)
                self.generation_log.append({
                    "asset_id": asset.asset_id,
                    "type": "sfx",
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        return assets

    def generate_dialogue_assets(
        self,
        voice_id: str,
        model: str = "eleven_v3",
        dry_run: bool = False,
    ) -> list[AudioAsset]:
        """Generate dialogue lines."""
        if not dry_run:
            _refuse_paid_audio()
        logger.info("Generating %d dialogue lines...", len(self.dialogue_assets))

        for asset in self.dialogue_assets:
            dest = self.output_dir / asset.dest_path
            asset.voice_id = voice_id
            logger.info("  %s: '%s'", asset.asset_id, asset.text)

            if dry_run:
                logger.info("  [DRY RUN] voice_id=%s", voice_id)
                continue

            try:
                result = generate_dialogue(
                    text=asset.text,
                    voice_id=voice_id,
                    dest_path=dest,
                    model=model,
                    stability=0.3,       # More expressive
                    similarity_boost=0.8,
                    style=0.2,           # Slight style for weariness
                )
                asset.generated = True
                asset.local_path = result["local_path"]
                self.generation_log.append({
                    "asset_id": asset.asset_id,
                    "type": "dialogue",
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error("  Failed: %s", e)
                asset.error = str(e)

        return self.dialogue_assets

    def generate_music_assets(
        self,
        dry_run: bool = False,
    ) -> list[AudioAsset]:
        """Generate music/score."""
        if not dry_run:
            _refuse_paid_audio()
        logger.info("Generating %d music tracks...", len(self.music_assets))

        for asset in self.music_assets:
            dest = self.output_dir / asset.dest_path
            logger.info("  %s: %s...", asset.asset_id, asset.prompt[:60])

            if dry_run:
                logger.info("  [DRY RUN]")
                continue

            try:
                result = generate_music(
                    prompt=asset.prompt,
                    dest_path=dest,
                    duration=asset.duration,
                )
                asset.generated = True
                asset.local_path = result["local_path"]
                self.generation_log.append({
                    "asset_id": asset.asset_id,
                    "type": "music",
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error("  Failed: %s", e)
                asset.error = str(e)

        return self.music_assets

    def write_audio_manifest(self):
        """Write the audio manifest JSON."""
        all_assets = self.sfx_assets + self.dialogue_assets + self.music_assets

        # Build per-shot assignments
        shot_assignments = {}
        for asset in all_assets:
            for shot_id in asset.assigned_shots:
                if shot_id not in shot_assignments:
                    shot_assignments[shot_id] = []
                shot_assignments[shot_id].append({
                    "asset_id": asset.asset_id,
                    "asset_type": asset.asset_type,
                    "local_path": asset.local_path or asset.dest_path,
                    "layer_notes": asset.layer_notes,
                })

        manifest = {
            "production_id": self.production_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "assets": [
                {
                    "asset_id": a.asset_id,
                    "asset_type": a.asset_type,
                    "local_path": a.local_path or a.dest_path,
                    "prompt": a.prompt,
                    "duration_requested": a.duration,
                    "generated": a.generated,
                    "assigned_shots": a.assigned_shots,
                    "layer_notes": a.layer_notes,
                }
                for a in all_assets
            ],
            "shot_assignments": shot_assignments,
            "generation_log": self.generation_log,
        }

        out = self.output_dir / "audio-manifest.json"
        out.write_text(json.dumps(manifest, indent=2))
        logger.info("Wrote audio manifest → %s", out)
