"""
pipeline.py — The Editor agent's core assembly pipeline.

Reads selected clips and audio assets, builds an FFmpeg command chain
that concatenates video, strips native audio, layers the sound design,
and exports a rough cut.

Usage:
    from src.pipeline import EditPipeline
    pipeline = EditPipeline(production_dir="productions/the-last-marker")
    pipeline.assemble_rough_cut()
"""

from __future__ import annotations

import json
import logging
import subprocess
import shlex
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("editor.pipeline")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ClipEntry:
    """A single clip in the edit timeline."""
    shot_id: str
    source_path: str
    duration: float
    start_time: float = 0.0    # Position in the assembled timeline
    transition: str = "cut"     # "cut" or "dissolve"
    transition_duration: float = 0.0


@dataclass
class AudioLayer:
    """An audio layer to mix into the timeline."""
    asset_id: str
    source_path: str
    layer_type: str            # "ambient", "sfx", "dialogue", "music"
    timeline_start: float      # When this audio begins in the timeline
    duration: Optional[float] = None  # None = use full file duration
    volume: float = 1.0        # 0.0-1.0
    loop: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    trim_start: float = 0.0   # Trim from beginning of source file
    trim_end: float = 0.0     # Trim from end of source file


@dataclass
class EditDecision:
    """The complete edit decision list."""
    production_id: str
    clips: list[ClipEntry]
    audio_layers: list[AudioLayer]
    total_duration: float
    created_at: str = ""
    output_path: str = ""


# ---------------------------------------------------------------------------
# FFmpeg helpers
# ---------------------------------------------------------------------------


def probe_duration(file_path: str | Path) -> float:
    """Get the duration of a media file in seconds."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(file_path),
        ],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def run_ffmpeg(cmd: list[str], description: str = "") -> subprocess.CompletedProcess:
    """Run an FFmpeg command and log it."""
    cmd_str = " ".join(shlex.quote(str(c)) for c in cmd)
    logger.info("FFmpeg: %s", description or cmd_str[:120])
    logger.debug("Full command: %s", cmd_str)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error("FFmpeg failed: %s", result.stderr[-500:])
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-300:]}")
    return result


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class EditPipeline:
    """
    Assembles a rough cut from selected clips and audio assets.

    Expects the standard production directory layout:
        productions/{id}/clips/selected/   — one MP4 per shot
        productions/{id}/audio/            — sfx/, dialogue/, music/
        productions/{id}/edit/             — output directory
    """

    def __init__(self, production_dir: str | Path):
        self.prod_dir = Path(production_dir)
        self.clips_dir = self.prod_dir / "clips" / "selected"
        self.audio_dir = self.prod_dir / "audio"
        self.edit_dir = self.prod_dir / "edit"
        self.edit_dir.mkdir(parents=True, exist_ok=True)

        self.clips: list[ClipEntry] = []
        self.audio_layers: list[AudioLayer] = []
        self.command_log: list[str] = []

    def discover_clips(self) -> list[ClipEntry]:
        """Find all selected clips and probe their durations."""
        clip_files = sorted(self.clips_dir.glob("s*-sh*.mp4"))
        if not clip_files:
            raise FileNotFoundError(f"No clips found in {self.clips_dir}")

        entries = []
        timeline_pos = 0.0
        for f in clip_files:
            shot_id = f.stem  # e.g. "s01-sh01"
            duration = probe_duration(f)
            entries.append(ClipEntry(
                shot_id=shot_id,
                source_path=str(f),
                duration=duration,
                start_time=timeline_pos,
            ))
            timeline_pos += duration
            logger.info("  %s: %.1fs (timeline: %.1f–%.1f)",
                        shot_id, duration, entries[-1].start_time, timeline_pos)

        self.clips = entries
        return entries

    def concatenate_video(self, output_path: Optional[str | Path] = None) -> Path:
        """
        Concatenate selected clips into a single video file.
        Strips native audio — the sound design is layered separately.
        """
        if not self.clips:
            self.discover_clips()

        out = Path(output_path) if output_path else self.edit_dir / "video-only.mp4"

        # Write concat list file
        concat_list = self.edit_dir / "concat-list.txt"
        with open(concat_list, "w") as f:
            for clip in self.clips:
                abs_path = str(Path(clip.source_path).resolve())
                f.write(f"file '{abs_path}'\n")

        # Concatenate with audio stripped
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-an",                    # Strip audio
            "-c:v", "copy",           # Copy video codec (no re-encode)
            str(out),
        ]

        try:
            run_ffmpeg(cmd, "Concatenate video clips (no audio)")
        except RuntimeError:
            # If codec copy fails (different codecs), re-encode
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-an",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                str(out),
            ]
            run_ffmpeg(cmd, "Concatenate video clips (re-encoding)")

        self.command_log.append(f"Concatenated {len(self.clips)} clips → {out}")
        logger.info("Video assembled → %s", out)
        return out

    def build_audio_mix(
        self,
        total_duration: float,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        """
        Build the complete audio mix from layers.
        Returns path to the mixed audio file.
        """
        out = Path(output_path) if output_path else self.edit_dir / "audio-mix.wav"

        if not self.audio_layers:
            logger.warning("No audio layers defined — creating silent track")
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration}",
                "-c:a", "pcm_s16le",
                str(out),
            ]
            run_ffmpeg(cmd, "Generate silent audio track")
            return out

        # Strategy: render each layer as a full-length padded track,
        # then mix them all together.
        layer_files = []

        for i, layer in enumerate(self.audio_layers):
            layer_file = self.edit_dir / f"_layer_{i}_{layer.asset_id}.wav"
            self._render_layer(layer, total_duration, layer_file)
            layer_files.append(layer_file)

        # Mix all layers together
        if len(layer_files) == 1:
            # Just copy the single layer
            cmd = ["ffmpeg", "-y", "-i", str(layer_files[0]), "-c:a", "pcm_s16le", str(out)]
            run_ffmpeg(cmd, "Copy single audio layer")
        else:
            # Mix multiple layers
            inputs = []
            for lf in layer_files:
                inputs.extend(["-i", str(lf)])

            filter_parts = []
            for j in range(len(layer_files)):
                filter_parts.append(f"[{j}:a]")

            filter_str = "".join(filter_parts) + f"amix=inputs={len(layer_files)}:duration=longest:dropout_transition=0[out]"

            cmd = ["ffmpeg", "-y"] + inputs + [
                "-filter_complex", filter_str,
                "-map", "[out]",
                "-c:a", "pcm_s16le",
                str(out),
            ]
            run_ffmpeg(cmd, f"Mix {len(layer_files)} audio layers")

        # Clean up temp layer files
        for lf in layer_files:
            lf.unlink(missing_ok=True)

        self.command_log.append(f"Mixed {len(self.audio_layers)} audio layers → {out}")
        logger.info("Audio mix → %s", out)
        return out

    def _render_layer(
        self,
        layer: AudioLayer,
        total_duration: float,
        output_path: Path,
    ):
        """Render a single audio layer as a full-length padded WAV."""
        src = layer.source_path

        # Build filter chain
        filters = []

        # Trim source if needed
        if layer.trim_start > 0 or layer.trim_end > 0:
            end = f":end={layer.trim_end}" if layer.trim_end > 0 else ""
            filters.append(f"atrim=start={layer.trim_start}{end}")
            filters.append("asetpts=PTS-STARTPTS")

        # Volume adjustment
        if layer.volume != 1.0:
            filters.append(f"volume={layer.volume}")

        # Fade in/out
        if layer.fade_in > 0:
            filters.append(f"afade=t=in:d={layer.fade_in}")
        if layer.fade_out > 0:
            filters.append(f"afade=t=out:st={total_duration - layer.fade_out}:d={layer.fade_out}")

        # Pad with silence: delay to timeline position, then pad to total duration
        delay_ms = int(layer.timeline_start * 1000)
        filters.append(f"adelay={delay_ms}|{delay_ms}")
        filters.append(f"apad=whole_dur={total_duration}")

        filter_str = ",".join(filters) if filters else "anull"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-af", filter_str,
            "-c:a", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            "-t", str(total_duration),
            str(output_path),
        ]
        run_ffmpeg(cmd, f"Render layer: {layer.asset_id}")

    def merge_video_audio(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        """Merge the assembled video with the mixed audio into final output."""
        out = Path(output_path) if output_path else self.edit_dir / "rough-cut-v1.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out),
        ]
        run_ffmpeg(cmd, "Merge video + audio → rough cut")

        self.command_log.append(f"Merged video + audio → {out}")
        logger.info("Rough cut → %s (%.1f MB)", out, out.stat().st_size / 1e6)
        return out

    def assemble_rough_cut(self, output_name: str = "rough-cut-v1.mp4") -> Path:
        """
        Full assembly pipeline: discover → concat → mix audio → merge → export.
        """
        logger.info("=== Starting rough cut assembly ===")

        # 1. Discover clips
        self.discover_clips()
        total_duration = sum(c.duration for c in self.clips)
        logger.info("Total video duration: %.1fs", total_duration)

        # 2. Concatenate video (no audio)
        video_path = self.concatenate_video()

        # 3. Build audio mix
        audio_path = self.build_audio_mix(total_duration)

        # 4. Merge video + audio
        output_path = self.edit_dir / output_name
        final = self.merge_video_audio(video_path, audio_path, output_path)

        # 5. Write edit decision list
        self._write_edl(total_duration, str(final))

        # 6. Write command log
        self._write_log()

        # 7. Clean up intermediates
        (self.edit_dir / "video-only.mp4").unlink(missing_ok=True)
        (self.edit_dir / "audio-mix.wav").unlink(missing_ok=True)
        (self.edit_dir / "concat-list.txt").unlink(missing_ok=True)

        logger.info("=== Rough cut complete: %s ===", final)
        return final

    def _write_edl(self, total_duration: float, output_path: str):
        """Write the edit decision list."""
        edl = EditDecision(
            production_id=self.prod_dir.name,
            clips=self.clips,
            audio_layers=self.audio_layers,
            total_duration=total_duration,
            created_at=datetime.now(timezone.utc).isoformat(),
            output_path=output_path,
        )
        out = self.edit_dir / "edit-decision-list.json"
        out.write_text(json.dumps(asdict(edl), indent=2))
        logger.info("Wrote EDL → %s", out)

    def _write_log(self):
        """Write the assembly command log."""
        out = self.edit_dir / "assembly-log.txt"
        out.write_text("\n".join(self.command_log))
        logger.info("Wrote log → %s", out)
