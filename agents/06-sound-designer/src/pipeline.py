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
# SFX Library Definition for The Last Marker
# ---------------------------------------------------------------------------

# These are the sound effects needed for the production, derived from
# the shot list's sound_notes fields. Each entry defines what to generate.

LAST_MARKER_SFX_LIBRARY = [
    AudioAsset(
        asset_id="engine-healthy",
        asset_type="sfx",
        prompt="A vintage single-cylinder motorcycle engine at high RPM, cruising at 60 mph on an open road. Fast, steady, powerful exhaust note with rapid firing rhythm. Mechanical valve clatter at speed. Air rushing past the engine. Not idling — this engine is working hard, moving fast. Raw exhaust, no muffler.",
        dest_path="sfx/engine-healthy.mp3",
        duration=15.0,
        prompt_influence=0.7,
        assigned_shots=["s01-sh01", "s01-sh02", "s01-sh03", "s01-sh04", "s01-sh05"],
        layer_notes="Primary engine sound for Scene 1. Loop as needed.",
    ),
    AudioAsset(
        asset_id="engine-skip",
        asset_type="sfx",
        prompt="Single-cylinder vintage motorcycle engine with intermittent misfire. Deep thump rhythm with every third beat missing — a skip in the pattern. Engine recovers each time but the skip returns. Mechanical distress. 1960s British motorcycle.",
        dest_path="sfx/engine-skip.mp3",
        duration=10.0,
        prompt_influence=0.7,
        assigned_shots=["s01-sh05", "s02-sh01"],
        layer_notes="Engine degradation begins. Crossfade from healthy to this.",
    ),
    AudioAsset(
        asset_id="engine-death",
        asset_type="sfx",
        prompt="A motorcycle engine misfiring and shutting down. The engine fires unevenly three times, each firing weaker than the last, with longer gaps between. Then the engine stops completely and there is total mechanical silence. No human sounds. Only metal and exhaust. The final silence should last five seconds.",
        dest_path="sfx/engine-death.mp3",
        duration=8.0,
        prompt_influence=0.8,
        assigned_shots=["s02-sh01"],
        layer_notes="The central event of Scene 2. The silence after must be absolute.",
    ),
    AudioAsset(
        asset_id="engine-kick-fail",
        asset_type="sfx",
        prompt="Boot stomping on a motorcycle kick-start lever. Metallic clank of the lever. Engine turns over — compression, release — but does not catch. No ignition. Just the mechanical turning and the boot impact. Repeat once.",
        dest_path="sfx/engine-kick-fail.mp3",
        duration=4.0,
        prompt_influence=0.8,
        assigned_shots=["s04-sh02", "s04-sh03"],
        layer_notes="First and second kick attempts. Engine turns but doesn't fire.",
    ),
    AudioAsset(
        asset_id="engine-kick-catch",
        asset_type="sfx",
        prompt="Boot on motorcycle kick-start lever, engine turns, catches fire briefly then dies, catches again on second compression and holds. Rough idle — uneven, skipping every few beats. Not healthy. Something compromised choosing to function. Single-cylinder vintage motorcycle.",
        dest_path="sfx/engine-kick-catch.mp3",
        duration=6.0,
        prompt_influence=0.8,
        assigned_shots=["s04-sh04", "s04-sh05"],
        layer_notes="Third kick succeeds. Engine runs rough.",
    ),
    AudioAsset(
        asset_id="engine-rough-idle",
        asset_type="sfx",
        prompt="Single-cylinder vintage motorcycle engine running rough at low RPM. Uneven rhythm, skipping every few beats. Mechanical distress but still running. Compromised but functional. Deep thump with irregular gaps.",
        dest_path="sfx/engine-rough-idle.mp3",
        duration=15.0,
        prompt_influence=0.7,
        assigned_shots=["s04-sh05", "s04-sh06", "s04-sh07"],
        layer_notes="Final engine state. Rough but running. Fades over closing shot.",
    ),
    AudioAsset(
        asset_id="desert-wind-light",
        asset_type="sfx",
        prompt="Light desert wind. Dry air moving across flat terrain. Gentle, constant, with occasional soft gusts. No vegetation rustling — just air on sand and rock. Lonely and vast.",
        dest_path="sfx/desert-wind-light.mp3",
        duration=20.0,
        prompt_influence=0.4,
        assigned_shots=["s01-sh01", "s03-sh01", "s03-sh02"],
        layer_notes="Background ambient for wide shots. Loop as needed.",
    ),
    AudioAsset(
        asset_id="desert-silence",
        asset_type="sfx",
        prompt="Complete silence with very faint, almost subliminal low-frequency room tone. Not digital silence — the silence of a vast empty desert where the air itself is still. Barely perceptible.",
        dest_path="sfx/desert-silence.mp3",
        duration=10.0,
        prompt_influence=0.3,
        assigned_shots=["s02-sh01", "s02-sh03", "s03-sh01"],
        layer_notes="The silence after the engine dies. Also used for diagnostic scene.",
    ),
    AudioAsset(
        asset_id="tire-hardpan",
        asset_type="sfx",
        prompt="Motorcycle tire rolling on hard desert ground at moderate speed. Continuous hiss and crunch of dry packed earth under rubber. Small pebbles and grit. Steady and rhythmic.",
        dest_path="sfx/tire-hardpan.mp3",
        duration=10.0,
        prompt_influence=0.6,
        assigned_shots=["s01-sh02", "s01-sh04"],
        layer_notes="Layer under engine sound for riding shots.",
    ),
    AudioAsset(
        asset_id="pebble-spray",
        asset_type="sfx",
        prompt="Spray of sand and small pebbles kicked up by a motorcycle tire. Brief burst of grit hitting the ground and scattering. Desert terrain.",
        dest_path="sfx/pebble-spray.mp3",
        duration=3.0,
        prompt_influence=0.7,
        assigned_shots=["s01-sh04"],
        layer_notes="Low angle pass-by shot.",
    ),
    AudioAsset(
        asset_id="boot-on-lever",
        asset_type="sfx",
        prompt="A heavy leather boot stomping down on a metal motorcycle kick-start lever. Single impact. Metallic clang with leather thud.",
        dest_path="sfx/boot-on-lever.mp3",
        duration=1.5,
        prompt_influence=0.8,
        assigned_shots=["s04-sh02", "s04-sh03"],
        layer_notes="Punctuation sound for kick attempts.",
    ),
    AudioAsset(
        asset_id="cooling-metal",
        asset_type="sfx",
        prompt="Hot metal cooling and ticking. Quiet, irregular metallic clicks as a motorcycle engine cools down after being turned off. Tick... tick... tick. Slowing.",
        dest_path="sfx/cooling-metal.mp3",
        duration=15.0,
        prompt_influence=0.6,
        assigned_shots=["s02-sh02", "s02-sh03", "s03-sh01"],
        layer_notes="Diagnostic scene ambient. Engine cooling after death.",
    ),
    AudioAsset(
        asset_id="spark-plug-pull",
        asset_type="sfx",
        prompt="A spark plug being unscrewed from a motorcycle engine by hand. Metal threading out of metal. Then the plug pulled free with a slight pop. Close-mic mechanical detail.",
        dest_path="sfx/spark-plug-pull.mp3",
        duration=4.0,
        prompt_influence=0.7,
        assigned_shots=["s02-sh02"],
        layer_notes="Diagnostic detail shot.",
    ),
]

LAST_MARKER_DIALOGUE = [
    AudioAsset(
        asset_id="vega-primero-llegas",
        asset_type="dialogue",
        text="Primero llegas. Despues compites.",
        prompt="A quiet, private decision spoken aloud. Barely audible. Under the breath.",
        dest_path="dialogue/vega-primero-llegas.mp3",
        voice_id=None,  # To be selected — needs Mexican male, mid-30s, weathered
        assigned_shots=["s04-sh06"],
        layer_notes="The only spoken words in the film. Barely audible under engine. Mix very low.",
    ),
]

LAST_MARKER_MUSIC = [
    AudioAsset(
        asset_id="closing-guitar",
        asset_type="music",
        prompt="Solo nylon-string acoustic guitar. Three simple notes — a Mexican folk phrase, a question not an answer. Played once. Four seconds of silence. Played once more. Then silence. Sparse, lonely, unhurried. No accompaniment, no percussion, no bass. Just the guitar and the desert.",
        dest_path="music/closing-guitar.mp3",
        duration=20.0,
        assigned_shots=["s04-sh07"],
        layer_notes="Enters after engine fades in the closing shot. The last sound before silence.",
    ),
]


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
    ):
        self.shot_plans = load_sound_plan(shot_list_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Asset registries
        self.sfx_assets = list(LAST_MARKER_SFX_LIBRARY)
        self.dialogue_assets = list(LAST_MARKER_DIALOGUE)
        self.music_assets = list(LAST_MARKER_MUSIC)
        self.generation_log: list[dict] = []

    def generate_sfx_library(
        self,
        asset_ids: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> list[AudioAsset]:
        """Generate sound effects. Optionally filter by asset_id."""
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
            "production_id": "the-last-marker",
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
