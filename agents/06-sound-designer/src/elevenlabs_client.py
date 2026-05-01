"""
elevenlabs_client.py — Wrapper around the ElevenLabs Python SDK.

Handles:
  - Text-to-speech (dialogue generation)
  - Sound effects generation
  - Music generation
  - Voice search and selection
  - File saving and cost tracking
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("sound_designer.elevenlabs")


def _get_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "ELEVENLABS_API_KEY environment variable is not set. "
            "Get your key from https://elevenlabs.io → Developers → API Keys"
        )
    return key


def _get_client():
    """Lazy-initialize the ElevenLabs client."""
    from elevenlabs.client import ElevenLabs
    return ElevenLabs(api_key=_get_api_key())


def _save_audio(audio_data, dest_path: str | Path) -> Path:
    """Save audio data (bytes or iterator) to a file."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(audio_data, bytes):
        dest.write_bytes(audio_data)
    else:
        # Iterator of chunks
        with open(dest, "wb") as f:
            for chunk in audio_data:
                if isinstance(chunk, bytes):
                    f.write(chunk)

    logger.info("Saved audio → %s (%.1f KB)", dest, dest.stat().st_size / 1024)
    return dest


# ---------------------------------------------------------------------------
# Voice Search
# ---------------------------------------------------------------------------


def search_voices(query: str = "", language: str = "en", max_results: int = 10) -> list[dict]:
    """
    Search ElevenLabs voice library.
    Returns list of dicts with voice_id, name, description, preview_url.
    """
    client = _get_client()
    response = client.voices.search(
        search=query,
    )
    voices = []
    for v in response.voices[:max_results]:
        voices.append({
            "voice_id": v.voice_id,
            "name": v.name,
            "description": getattr(v, "description", ""),
            "preview_url": getattr(v, "preview_url", ""),
            "labels": getattr(v, "labels", {}),
        })
    return voices


# ---------------------------------------------------------------------------
# Text-to-Speech (Dialogue)
# ---------------------------------------------------------------------------


def generate_dialogue(
    text: str,
    voice_id: str,
    dest_path: str | Path,
    model: str = "eleven_v3",
    output_format: str = "mp3_44100_128",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
) -> dict[str, Any]:
    """
    Generate dialogue audio from text.

    Args:
        text: The dialogue line to speak.
        voice_id: ElevenLabs voice ID.
        dest_path: Where to save the audio file.
        model: Model ID (eleven_v3 for quality, eleven_flash_v2_5 for speed).
        output_format: Audio format string.
        stability: Voice stability (0-1). Lower = more expressive.
        similarity_boost: How closely to match the voice (0-1).
        style: Style exaggeration (0-1). Higher = more dramatic.

    Returns:
        Dict with local_path, character_count, estimated_cost.
    """
    client = _get_client()

    audio = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model,
        output_format=output_format,
        voice_settings={
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
        },
    )

    saved = _save_audio(audio, dest_path)
    char_count = len(text)

    return {
        "local_path": str(saved),
        "character_count": char_count,
        "voice_id": voice_id,
        "model": model,
        "type": "dialogue",
    }


# ---------------------------------------------------------------------------
# Sound Effects
# ---------------------------------------------------------------------------


def generate_sfx(
    prompt: str,
    dest_path: str | Path,
    duration: Optional[float] = None,
    prompt_influence: float = 0.5,
    model: str = "eleven_text_to_sound_v2",
    output_format: str = "mp3_44100_128",
) -> dict[str, Any]:
    """
    Generate a sound effect from a text description.

    Args:
        prompt: Description of the sound effect.
        dest_path: Where to save the audio file.
        duration: Duration in seconds (0.5-30). None = auto.
        prompt_influence: How literally to follow the prompt (0-1).
        model: Model ID.
        output_format: Audio format.

    Returns:
        Dict with local_path, prompt, duration, type.
    """
    client = _get_client()

    kwargs = {
        "text": prompt,
        "model_id": model,
        "output_format": output_format,
        "prompt_influence": prompt_influence,
    }
    if duration is not None:
        kwargs["duration_seconds"] = duration

    audio = client.text_to_sound_effects.convert(**kwargs)

    saved = _save_audio(audio, dest_path)

    return {
        "local_path": str(saved),
        "prompt": prompt,
        "duration_requested": duration,
        "prompt_influence": prompt_influence,
        "type": "sfx",
    }


# ---------------------------------------------------------------------------
# Music Generation
# ---------------------------------------------------------------------------


def generate_music(
    prompt: str,
    dest_path: str | Path,
    duration: Optional[float] = None,
    output_format: str = "mp3_44100_128",
) -> dict[str, Any]:
    """
    Generate music from a text description.

    Args:
        prompt: Description of the music.
        dest_path: Where to save the audio file.
        duration: Duration in seconds. None = auto.
        output_format: Audio format.

    Returns:
        Dict with local_path, prompt, type.
    """
    client = _get_client()

    kwargs = {
        "prompt": prompt,
        "output_format": output_format,
    }
    audio = client.music.compose(**kwargs)

    saved = _save_audio(audio, dest_path)

    return {
        "local_path": str(saved),
        "prompt": prompt,
        "duration_requested": duration,
        "type": "music",
    }
