"""
pipeline.py — The Production agent's core execution loop.

Reads a shot list JSON (from the Cinematographer), determines the right
Seedance endpoint and parameters for each shot, runs a two-pass generation
(preview → final), validates outputs, and writes clip metadata + cost report.

Usage:
    from src.pipeline import ProductionPipeline
    pipeline = ProductionPipeline("path/to/shot-list.json", "path/to/output/")
    pipeline.run(pass_type="preview")  # fast tier, 480p
    pipeline.run(pass_type="final")    # standard tier, 720p
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import (
    ClipMetadata,
    CostEntry,
    Endpoint,
    GenerationResult,
    Resolution,
    ShotSpec,
    Tier,
    estimate_cost,
)
from .fal_client import download_video, ensure_url, generate_shot

logger = logging.getLogger("production.pipeline")


# ---------------------------------------------------------------------------
# Shot list loader
# ---------------------------------------------------------------------------


def _parse_reference_assets(refs_raw) -> dict[str, list[str]]:
    """
    Parse reference_assets from the shot list.

    The shot list stores refs as an array of objects:
        [{"asset_type": "character-ref", "path": "visual-assets/...", ...}, ...]

    We bucket them by type and return paths/URLs grouped:
        {"character_refs": [...], "environment_refs": [...], "prop_refs": [...],
         "vehicle_refs": [...], "audio_refs": [], "video_refs": []}
    """
    buckets: dict[str, list[str]] = {
        "character_refs": [],
        "environment_refs": [],
        "prop_refs": [],
        "vehicle_refs": [],
        "audio_refs": [],
        "video_refs": [],
    }

    if isinstance(refs_raw, dict):
        # Legacy format: {"character_refs": [...], "environment_refs": [...]}
        for key in buckets:
            buckets[key] = refs_raw.get(key, [])
        return buckets

    if not isinstance(refs_raw, list):
        return buckets

    type_map = {
        "character-ref": "character_refs",
        "environment-ref": "environment_refs",
        "prop-ref": "prop_refs",
        "vehicle-ref": "vehicle_refs",
        "audio-ref": "audio_refs",
        "video-ref": "video_refs",
    }

    for ref in refs_raw:
        asset_type = ref.get("asset_type", "")
        path = ref.get("path", ref.get("url", ""))
        bucket = type_map.get(asset_type)
        if bucket and path:
            buckets[bucket].append(path)

    return buckets


def load_shot_list(path: str | Path) -> list[ShotSpec]:
    """Parse a shot-list.schema.json file into ShotSpec objects."""
    raw = json.loads(Path(path).read_text())
    shots_raw = raw.get("shots", [])
    specs = []
    for s in shots_raw:
        routing = s.get("tool_routing", {})
        refs = _parse_reference_assets(s.get("reference_assets", []))
        # Combine character + vehicle + prop refs as image references
        # (Seedance treats them all as image inputs)
        image_refs = refs["character_refs"] + refs["vehicle_refs"] + refs["prop_refs"]
        env_refs = refs["environment_refs"]

        specs.append(ShotSpec(
            shot_id=s["shot_id"],
            scene_number=s["scene_number"],
            shot_number=s["shot_number"],
            sequence_position=s["sequence_position"],
            generation_prompt=s["generation_prompt"],
            target_duration_seconds=s.get("target_duration_seconds", 8),
            negative_prompt=s.get("negative_prompt"),
            aspect_ratio=s.get("aspect_ratio", "16:9"),
            primary_tool=routing.get("primary_tool", "seedance-2.0"),
            fallback_tool=routing.get("fallback_tool"),
            tool_rationale=routing.get("rationale"),
            character_ref_urls=image_refs,
            environment_ref_urls=env_refs,
            audio_ref_urls=refs["audio_refs"],
            video_ref_urls=refs["video_refs"],
            start_frame_url=None,
            end_frame_url=None,
            continuity_notes=s.get("continuity_notes"),
            from_previous_shot=s.get("from_previous_shot"),
            to_next_shot=s.get("to_next_shot"),
        ))
    return sorted(specs, key=lambda s: s.sequence_position)


# ---------------------------------------------------------------------------
# Endpoint selection
# ---------------------------------------------------------------------------


def select_endpoint(shot: ShotSpec, tier: Tier) -> str:
    """
    Choose the right Seedance endpoint based on what reference assets
    the shot requires.

    Priority:
    1. Has image refs + audio refs or video refs → reference-to-video
    2. Has a start frame image → image-to-video
    3. Text only → text-to-video
    """
    has_image_refs = bool(shot.character_ref_urls or shot.environment_ref_urls)
    has_audio_refs = bool(shot.audio_ref_urls)
    has_video_refs = bool(shot.video_ref_urls)
    has_start_frame = bool(shot.start_frame_url)

    if has_image_refs or has_audio_refs or has_video_refs:
        if tier == Tier.FAST:
            return Endpoint.FAST_REFERENCE_TO_VIDEO
        return Endpoint.REFERENCE_TO_VIDEO

    if has_start_frame:
        if tier == Tier.FAST:
            return Endpoint.FAST_IMAGE_TO_VIDEO
        return Endpoint.IMAGE_TO_VIDEO

    if tier == Tier.FAST:
        return Endpoint.FAST_TEXT_TO_VIDEO
    return Endpoint.TEXT_TO_VIDEO


def _endpoint_type(endpoint: str) -> str:
    """Extract the endpoint type slug for pricing lookup."""
    for suffix in ("reference-to-video", "image-to-video", "text-to-video"):
        if endpoint.endswith(suffix):
            return suffix
    return "text-to-video"


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def build_payload(
    shot: ShotSpec,
    endpoint: str,
    resolution: Resolution,
    resolve_refs: bool = True,
) -> dict[str, Any]:
    """
    Build the fal.ai request payload for a given shot and endpoint.

    If resolve_refs is False, local paths are included as-is (for dry-run
    inspection) rather than being uploaded to fal storage.
    """
    def ref(path_or_url: str) -> str:
        if resolve_refs:
            return ensure_url(path_or_url)
        return path_or_url

    payload: dict[str, Any] = {
        "prompt": shot.generation_prompt,
        "resolution": resolution.value,
        "duration": str(shot.target_duration_seconds),
        "aspect_ratio": shot.aspect_ratio,
        "generate_audio": True,
    }

    ep_type = _endpoint_type(endpoint)

    if ep_type == "image-to-video":
        if shot.start_frame_url:
            payload["image_url"] = ref(shot.start_frame_url)
        elif shot.character_ref_urls:
            payload["image_url"] = ref(shot.character_ref_urls[0])
        if shot.end_frame_url:
            payload["end_image_url"] = ref(shot.end_frame_url)

    elif ep_type == "reference-to-video":
        all_image_urls = []
        for url in shot.character_ref_urls + shot.environment_ref_urls:
            all_image_urls.append(ref(url))
        if all_image_urls:
            payload["image_urls"] = all_image_urls[:9]

        if shot.video_ref_urls:
            payload["video_urls"] = [ref(u) for u in shot.video_ref_urls[:3]]

        if shot.audio_ref_urls:
            payload["audio_urls"] = [ref(u) for u in shot.audio_ref_urls[:3]]

    return payload


# ---------------------------------------------------------------------------
# Clip validation
# ---------------------------------------------------------------------------


def validate_clip(local_path: Path, expected_duration: int) -> tuple[bool, str]:
    """
    Validate a downloaded clip using ffprobe.
    Returns (is_valid, notes).
    """
    if not local_path.exists():
        return False, "File does not exist"

    if local_path.stat().st_size < 1000:
        return False, f"File too small: {local_path.stat().st_size} bytes"

    # Use ffprobe to check duration and streams
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(local_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return False, f"ffprobe failed: {result.stderr[:200]}"

        probe = json.loads(result.stdout)
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration", 0))
        streams = probe.get("streams", [])

        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        notes = []
        if not has_video:
            return False, "No video stream found"

        if abs(duration - expected_duration) > 2:
            notes.append(
                f"Duration mismatch: expected ~{expected_duration}s, got {duration:.1f}s"
            )

        if not has_audio:
            notes.append("No audio stream (may be expected for some shots)")

        return True, "; ".join(notes) if notes else "OK"

    except FileNotFoundError:
        # ffprobe not installed — skip validation
        return True, "ffprobe not available, skipping deep validation"
    except Exception as e:
        return False, f"Validation error: {e}"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class ProductionPipeline:
    """
    Orchestrates video generation for an entire shot list.

    Typical usage:
        pipeline = ProductionPipeline("shot-list.json", "output/")
        pipeline.run(pass_type="preview")   # 480p fast pass
        # review previews, then:
        pipeline.run(pass_type="final")     # 720p standard pass
    """

    def __init__(
        self,
        shot_list_path: str | Path,
        output_dir: str | Path,
        max_retries: int = 3,
        generation_timeout: int = 300,
    ):
        self.shots = load_shot_list(shot_list_path)
        self.output_dir = Path(output_dir)
        self.max_retries = max_retries
        self.generation_timeout = generation_timeout

        # Accumulated results
        self.results: list[GenerationResult] = []
        self.clip_metadata: list[ClipMetadata] = []
        self.cost_log: list[CostEntry] = []

    def run(
        self,
        pass_type: str = "final",
        shot_ids: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> list[GenerationResult]:
        """
        Execute a generation pass.

        Args:
            pass_type: "preview" (fast/480p) or "final" (standard/720p)
            shot_ids: If provided, only generate these shots. Otherwise all.
            dry_run: If True, build payloads and log them but don't call fal.
        """
        if not dry_run:
            raise RuntimeError(
                "Paid generation is closed in this build. "
                "A real run has to go through the Director, and Ron has to approve the generation gate. "
                "No provider was called."
            )
        tier = Tier.FAST if pass_type == "preview" else Tier.STANDARD
        resolution = Resolution.P480 if pass_type == "preview" else Resolution.P720
        subdir = "preview" if pass_type == "preview" else "final"
        clips_dir = self.output_dir / "clips" / subdir
        clips_dir.mkdir(parents=True, exist_ok=True)

        shots_to_run = self.shots
        if shot_ids:
            id_set = set(shot_ids)
            shots_to_run = [s for s in self.shots if s.shot_id in id_set]

        logger.info(
            "Starting %s pass: %d shots, tier=%s, resolution=%s",
            pass_type, len(shots_to_run), tier.value, resolution.value,
        )

        results = []
        for i, shot in enumerate(shots_to_run, 1):
            logger.info(
                "[%d/%d] Generating %s — %ds, %s",
                i, len(shots_to_run),
                shot.shot_id,
                shot.target_duration_seconds,
                shot.aspect_ratio,
            )

            endpoint = select_endpoint(shot, tier)
            payload = build_payload(shot, endpoint, resolution, resolve_refs=not dry_run)
            ep_type = _endpoint_type(endpoint)

            cost_est = estimate_cost(
                tier, resolution, ep_type,
                shot.target_duration_seconds,
                has_video_inputs=bool(shot.video_ref_urls),
            )

            if dry_run:
                logger.info(
                    "  [DRY RUN] endpoint=%s, est_cost=$%.2f",
                    endpoint, cost_est,
                )
                logger.debug("  payload=%s", json.dumps(payload, indent=2)[:500])
                results.append(GenerationResult(
                    shot_id=shot.shot_id,
                    endpoint=endpoint,
                    tier=tier,
                    resolution=resolution,
                    duration_requested=shot.target_duration_seconds,
                    cost_usd=cost_est,
                    success=False,
                    error="dry_run",
                ))
                continue

            # Retry loop with exponential backoff
            dest = clips_dir / f"{shot.shot_id}{'_preview' if pass_type == 'preview' else ''}.mp4"
            gen_result = self._generate_with_retries(
                shot, endpoint, payload, dest, tier, resolution, cost_est
            )
            results.append(gen_result)

            # Log cost
            self.cost_log.append(CostEntry(
                shot_id=shot.shot_id,
                endpoint=endpoint,
                tier=tier.value,
                resolution=resolution.value,
                duration_seconds=gen_result.duration_actual or shot.target_duration_seconds,
                cost_usd=gen_result.cost_usd,
                pass_type=pass_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

            # Build clip metadata if successful
            if gen_result.success:
                refs_used = (
                    shot.character_ref_urls
                    + shot.environment_ref_urls
                    + shot.audio_ref_urls
                    + shot.video_ref_urls
                )
                valid, notes = validate_clip(dest, shot.target_duration_seconds)
                self.clip_metadata.append(ClipMetadata(
                    shot_id=shot.shot_id,
                    scene_number=shot.scene_number,
                    shot_number=shot.shot_number,
                    sequence_position=shot.sequence_position,
                    source_prompt=shot.generation_prompt,
                    endpoint_used=endpoint,
                    tier=tier.value,
                    resolution=resolution.value,
                    duration_seconds=gen_result.duration_actual or shot.target_duration_seconds,
                    aspect_ratio=shot.aspect_ratio,
                    video_url=gen_result.video_url or "",
                    local_path=str(dest),
                    seed=gen_result.seed or 0,
                    has_native_audio=gen_result.has_audio,
                    cost_usd=gen_result.cost_usd,
                    generation_attempts=gen_result.attempt,
                    status="selected" if pass_type == "final" else "preview",
                    reference_assets_used=refs_used,
                    validation_notes=notes,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                ))

        self.results.extend(results)

        # Write outputs
        self._write_clip_metadata()
        self._write_cost_report()
        self._write_summary(pass_type, results)

        return results

    def _generate_with_retries(
        self,
        shot: ShotSpec,
        endpoint: str,
        payload: dict,
        dest: Path,
        tier: Tier,
        resolution: Resolution,
        cost_est: float,
    ) -> GenerationResult:
        """Try generation up to max_retries times with exponential backoff."""
        ep_type = _endpoint_type(endpoint)

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "  Attempt %d/%d — endpoint=%s, est=$%.2f",
                    attempt, self.max_retries, endpoint, cost_est,
                )
                result_data = generate_shot(
                    endpoint, payload, dest,
                    timeout=self.generation_timeout,
                )
                return GenerationResult(
                    shot_id=shot.shot_id,
                    endpoint=endpoint,
                    tier=tier,
                    resolution=resolution,
                    duration_requested=shot.target_duration_seconds,
                    duration_actual=shot.target_duration_seconds,  # fal doesn't return exact
                    video_url=result_data["video_url"],
                    local_path=result_data["local_path"],
                    seed=result_data.get("seed"),
                    cost_usd=cost_est,
                    success=True,
                    attempt=attempt,
                    has_audio=True,
                )

            except Exception as e:
                logger.warning(
                    "  Attempt %d failed for %s: %s",
                    attempt, shot.shot_id, e,
                )
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    logger.info("  Backing off %ds before retry...", backoff)
                    time.sleep(backoff)

        # All attempts exhausted
        return GenerationResult(
            shot_id=shot.shot_id,
            endpoint=endpoint,
            tier=tier,
            resolution=resolution,
            duration_requested=shot.target_duration_seconds,
            cost_usd=0.0,
            success=False,
            error=f"Failed after {self.max_retries} attempts",
            attempt=self.max_retries,
        )

    # -------------------------------------------------------------------
    # Output writers
    # -------------------------------------------------------------------

    def _write_clip_metadata(self):
        """Write clip-metadata.json conforming to clip-metadata.schema.json."""
        out = self.output_dir / "clip-metadata.json"
        data = {
            "production_id": self.output_dir.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "clips": [asdict(c) for c in self.clip_metadata],
        }
        out.write_text(json.dumps(data, indent=2))
        logger.info("Wrote clip metadata → %s (%d clips)", out, len(self.clip_metadata))

    def _write_cost_report(self):
        """Write running cost log."""
        out = self.output_dir / "cost-report.json"
        data = {
            "entries": [asdict(e) for e in self.cost_log],
            "total_usd": round(sum(e.cost_usd for e in self.cost_log), 2),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        out.write_text(json.dumps(data, indent=2))
        logger.info("Wrote cost report → %s (total: $%.2f)", out, data["total_usd"])

    def _write_summary(self, pass_type: str, results: list[GenerationResult]):
        """Write a human-readable summary."""
        out = self.output_dir / f"{pass_type}-summary.txt"
        lines = [
            f"Production Pass: {pass_type.upper()}",
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"Total shots: {len(results)}",
            f"Succeeded: {sum(1 for r in results if r.success)}",
            f"Failed: {sum(1 for r in results if not r.success)}",
            f"Total cost: ${sum(r.cost_usd for r in results):.2f}",
            "",
            "--- Per-Shot Results ---",
        ]
        for r in results:
            status = "OK" if r.success else f"FAILED ({r.error})"
            lines.append(
                f"  {r.shot_id}: {status} | {r.endpoint} | "
                f"${r.cost_usd:.2f} | attempts={r.attempt}"
            )
        out.write_text("\n".join(lines))
        logger.info("Wrote summary → %s", out)
