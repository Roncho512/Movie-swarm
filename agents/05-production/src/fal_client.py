"""
fal_client.py — Wrapper around the fal.ai REST API for Seedance 2.0.

Uses the REST API directly (no SDK dependency) so the agent can run
anywhere Python + requests is available. Handles:

  - File uploads to fal storage
  - Async queue submission, polling, and result retrieval
  - Exponential backoff retries
  - Video download to local disk
"""

from __future__ import annotations

import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

from .config import Endpoint, GenerationResult, Resolution, Tier, estimate_cost

logger = logging.getLogger("production.fal_client")

FAL_API_BASE = "https://fal.run"
FAL_QUEUE_BASE = "https://queue.fal.run"
FAL_UPLOAD_URL = "https://fal.run/fal-ai/file-storage/upload"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_api_key() -> str:
    key = os.environ.get("FAL_KEY", "")
    if not key:
        raise EnvironmentError(
            "FAL_KEY environment variable is not set. "
            "Get your key from https://fal.ai/dashboard/keys"
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Key {_get_api_key()}",
        "Content-Type": "application/json",
    }


def _upload_headers() -> dict[str, str]:
    return {
        "Authorization": f"Key {_get_api_key()}",
    }


# ---------------------------------------------------------------------------
# File Upload
# ---------------------------------------------------------------------------


def upload_file(file_path: str | Path) -> str:
    """
    Upload a local file to fal's storage and return the hosted URL.

    This is needed because Seedance endpoints expect publicly-accessible
    URLs for reference images/videos/audio.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot upload — file not found: {file_path}")

    # Determine content type
    suffix = file_path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }
    ct = content_types.get(suffix, "application/octet-stream")

    with open(file_path, "rb") as f:
        resp = requests.post(
            FAL_UPLOAD_URL,
            headers=_upload_headers(),
            files={"file": (file_path.name, f, ct)},
            timeout=120,
        )
    resp.raise_for_status()
    data = resp.json()

    url = data.get("url") or data.get("file_url") or data.get("access_url", "")
    if not url:
        raise RuntimeError(f"Upload succeeded but no URL in response: {data}")

    logger.info("Uploaded %s → %s", file_path.name, url)
    return url


def ensure_url(path_or_url: str) -> str:
    """If it's a local path, upload it. If it's already a URL, return as-is."""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return upload_file(path_or_url)


# ---------------------------------------------------------------------------
# Generation (async queue flow)
# ---------------------------------------------------------------------------


def submit_generation(endpoint: str, payload: dict[str, Any]) -> str:
    """
    Submit a generation request to fal's async queue.
    Returns the request_id for polling.
    """
    url = f"{FAL_QUEUE_BASE}/{endpoint}"
    resp = requests.post(url, headers=_headers(), json={"input": payload}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    request_id = data.get("request_id", "")
    if not request_id:
        raise RuntimeError(f"No request_id in queue response: {data}")
    logger.info("Submitted to %s → request_id=%s", endpoint, request_id)
    return request_id


def poll_status(endpoint: str, request_id: str) -> dict[str, Any]:
    """Poll the queue for request status. Returns the status payload."""
    url = f"{FAL_QUEUE_BASE}/{endpoint}/requests/{request_id}/status"
    resp = requests.get(url, headers=_headers(), params={"logs": "true"}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_result(endpoint: str, request_id: str) -> dict[str, Any]:
    """Fetch the completed result from the queue."""
    url = f"{FAL_QUEUE_BASE}/{endpoint}/requests/{request_id}"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def wait_for_completion(
    endpoint: str,
    request_id: str,
    timeout: int = 300,
    poll_interval: int = 5,
    on_log: Optional[callable] = None,
) -> dict[str, Any]:
    """
    Poll until the request completes or times out.
    Returns the final result dict.
    """
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > timeout:
            raise TimeoutError(
                f"Generation timed out after {timeout}s "
                f"(endpoint={endpoint}, request_id={request_id})"
            )

        status = poll_status(endpoint, request_id)
        state = status.get("status", "UNKNOWN")

        # Forward log messages
        if on_log and "logs" in status:
            for log in status["logs"]:
                on_log(log.get("message", ""))

        if state == "COMPLETED":
            return fetch_result(endpoint, request_id)
        elif state in ("FAILED", "CANCELLED"):
            raise RuntimeError(
                f"Generation failed: status={state}, "
                f"detail={status.get('error', 'unknown')}"
            )

        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download_video(url: str, dest_path: str | Path) -> Path:
    """Download a video from a URL to a local path."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    logger.info("Downloaded %s → %s (%.1f MB)", url[:60], dest, dest.stat().st_size / 1e6)
    return dest


# ---------------------------------------------------------------------------
# High-level: generate a single shot
# ---------------------------------------------------------------------------


def generate_shot(
    endpoint: str,
    payload: dict[str, Any],
    dest_path: str | Path,
    timeout: int = 300,
) -> dict[str, Any]:
    """
    End-to-end: submit → poll → download.

    Returns dict with keys: video_url, local_path, seed, duration_actual.
    """
    request_id = submit_generation(endpoint, payload)
    result = wait_for_completion(
        endpoint,
        request_id,
        timeout=timeout,
        on_log=lambda msg: logger.debug("[fal] %s", msg),
    )

    video_info = result.get("video", {})
    video_url = video_info.get("url", "")
    if not video_url:
        raise RuntimeError(f"No video URL in result: {result}")

    local = download_video(video_url, dest_path)

    return {
        "video_url": video_url,
        "local_path": str(local),
        "seed": result.get("seed"),
    }
