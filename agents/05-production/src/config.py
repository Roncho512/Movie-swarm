"""
Production Agent — Type definitions and configuration.

Shared types, pricing constants, and fal.ai endpoint mappings used
across the production workflow.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# fal.ai endpoint IDs
# ---------------------------------------------------------------------------

class Endpoint(str, Enum):
    TEXT_TO_VIDEO         = "bytedance/seedance-2.0/text-to-video"
    IMAGE_TO_VIDEO        = "bytedance/seedance-2.0/image-to-video"
    REFERENCE_TO_VIDEO    = "bytedance/seedance-2.0/reference-to-video"
    FAST_TEXT_TO_VIDEO     = "bytedance/seedance-2.0/fast/text-to-video"
    FAST_IMAGE_TO_VIDEO   = "bytedance/seedance-2.0/fast/image-to-video"
    FAST_REFERENCE_TO_VIDEO = "bytedance/seedance-2.0/fast/reference-to-video"


class Tier(str, Enum):
    STANDARD = "standard"
    FAST     = "fast"


class Resolution(str, Enum):
    P480 = "480p"
    P720 = "720p"


# ---------------------------------------------------------------------------
# Pricing (USD per second of generated video, April 2026)
# ---------------------------------------------------------------------------

PRICING: dict[tuple[Tier, Resolution, str], float] = {
    # Standard tier
    (Tier.STANDARD, Resolution.P720, "text-to-video"):      0.3034,
    (Tier.STANDARD, Resolution.P720, "image-to-video"):     0.3024,
    (Tier.STANDARD, Resolution.P720, "reference-to-video"): 0.3024,
    (Tier.STANDARD, Resolution.P480, "text-to-video"):      0.15,
    (Tier.STANDARD, Resolution.P480, "image-to-video"):     0.15,
    (Tier.STANDARD, Resolution.P480, "reference-to-video"): 0.15,
    # Fast tier
    (Tier.FAST, Resolution.P720, "text-to-video"):          0.2419,
    (Tier.FAST, Resolution.P720, "image-to-video"):         0.2419,
    (Tier.FAST, Resolution.P720, "reference-to-video"):     0.2419,
    (Tier.FAST, Resolution.P480, "text-to-video"):          0.12,
    (Tier.FAST, Resolution.P480, "image-to-video"):         0.12,
    (Tier.FAST, Resolution.P480, "reference-to-video"):     0.12,
}

# 0.6x multiplier when video inputs are provided on reference-to-video
VIDEO_INPUT_MULTIPLIER = 0.6


def estimate_cost(
    tier: Tier,
    resolution: Resolution,
    endpoint_type: str,
    duration_seconds: float,
    has_video_inputs: bool = False,
) -> float:
    """Return estimated USD cost for a single generation call."""
    key = (tier, resolution, endpoint_type)
    rate = PRICING.get(key, 0.30)  # conservative fallback
    cost = rate * duration_seconds
    if has_video_inputs and "reference" in endpoint_type:
        cost *= VIDEO_INPUT_MULTIPLIER
    return round(cost, 4)


# ---------------------------------------------------------------------------
# Data classes for the pipeline
# ---------------------------------------------------------------------------

@dataclass
class ShotSpec:
    """A single shot from the Cinematographer's shot list."""
    shot_id: str
    scene_number: int
    shot_number: int
    sequence_position: int
    generation_prompt: str
    target_duration_seconds: int
    negative_prompt: Optional[str] = None
    aspect_ratio: str = "16:9"

    # Tool routing from Cinematographer
    primary_tool: str = "seedance-2.0"
    fallback_tool: Optional[str] = None
    tool_rationale: Optional[str] = None

    # Reference assets
    character_ref_urls: list[str] = field(default_factory=list)
    environment_ref_urls: list[str] = field(default_factory=list)
    audio_ref_urls: list[str] = field(default_factory=list)
    video_ref_urls: list[str] = field(default_factory=list)
    start_frame_url: Optional[str] = None
    end_frame_url: Optional[str] = None

    # Continuity
    continuity_notes: Optional[str] = None
    from_previous_shot: Optional[str] = None
    to_next_shot: Optional[str] = None


@dataclass
class GenerationResult:
    """Result of a single fal.ai generation call."""
    shot_id: str
    endpoint: str
    tier: Tier
    resolution: Resolution
    duration_requested: int
    duration_actual: Optional[float] = None
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    seed: Optional[int] = None
    cost_usd: float = 0.0
    success: bool = False
    error: Optional[str] = None
    attempt: int = 1
    has_audio: bool = True


@dataclass
class ClipMetadata:
    """Structured metadata for a completed clip — maps to clip-metadata.schema.json."""
    shot_id: str
    scene_number: int
    shot_number: int
    sequence_position: int
    source_prompt: str
    endpoint_used: str
    tier: str
    resolution: str
    duration_seconds: float
    aspect_ratio: str
    video_url: str
    local_path: str
    seed: int
    has_native_audio: bool
    cost_usd: float
    generation_attempts: int
    status: str  # "selected", "alternate", "rejected"
    reference_assets_used: list[str] = field(default_factory=list)
    validation_notes: str = ""
    generated_at: str = ""


@dataclass
class CostEntry:
    """A single line item in the cost report."""
    shot_id: str
    endpoint: str
    tier: str
    resolution: str
    duration_seconds: float
    cost_usd: float
    pass_type: str  # "preview" or "final"
    timestamp: str = ""
