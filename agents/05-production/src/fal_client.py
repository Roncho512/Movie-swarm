"""
fal_client.py — Wrapper around fal.ai for Seedance 2.0.

File uploads and shot generation use the fal_client SDK (pip package
fal-client). The queue helpers below talk to the REST API with requests.
Handles:

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


def _engine():
    """Shared queue rules. Imported here so this package can still start on its own.

    The production command is launched from ``agents/05-production``. That
    process does not have the repo root on its path until a queue call needs it.
    """
    import sys

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from movie_swarm.duration import clip_lengths, request_value
    from movie_swarm.providers import (
        _fal_queue_url,
        _fal_result_url,
        _fal_status_url,
        _provider_error_message,
    )
    from movie_swarm.rates import RateCardError, load_rate_card
    from movie_swarm.redact import redact

    return {
        "clip_lengths": clip_lengths,
        "request_value": request_value,
        "fal_queue_url": _fal_queue_url,
        "fal_result_url": _fal_result_url,
        "fal_status_url": _fal_status_url,
        "provider_error_message": _provider_error_message,
        "RateCardError": RateCardError,
        "load_rate_card": load_rate_card,
        "redact": redact,
    }

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
    """Upload a local file to fal storage via the fal-client SDK."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot upload - file not found: {file_path}")
    import fal_client as _fal
    url = _fal.upload_file(file_path)
    logger.info("Uploaded %s -> %s", file_path.name, url)
    return url

def ensure_url(path_or_url: str) -> str:
    """If it's a local path, upload it. If it's already a URL, return as-is."""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return upload_file(path_or_url)


# ---------------------------------------------------------------------------
# Generation (async queue flow)
# ---------------------------------------------------------------------------


def _endpoint_text(endpoint: str) -> str:
    return endpoint.value if hasattr(endpoint, "value") else str(endpoint)


def _duration_row(endpoint: str) -> dict | None:
    """The rate row whose duration rule applies to this fal endpoint."""
    engine = _engine()
    text = _endpoint_text(endpoint).strip().strip("/")
    try:
        card = engine["load_rate_card"]()
    except engine["RateCardError"]:
        return None
    for item in card.get("generators") or []:
        if isinstance(item, dict) and item.get("endpoint") == text:
            return item
    by_model = card.get("by_model") or {}
    if text.startswith("bytedance/seedance-2.0/fast/"):
        return by_model.get("seedance-2.0-fast")
    if text.startswith("bytedance/seedance-2.0/"):
        return by_model.get("seedance-2.0")
    return None


def queue_payload(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """The JSON body for one queue submit.

    The fields sit at the top. Seedance duration is rounded up to a length
    the model accepts. ``auto`` is left as fal documents it.
    """
    body = dict(payload)
    duration = body.get("duration")
    if duration in (None, ""):
        return body
    if isinstance(duration, str) and duration.strip().lower() == "auto":
        return body
    row = _duration_row(endpoint)
    if row is None:
        return body
    engine = _engine()
    lengths, _notes = engine["clip_lengths"](duration, row)
    if len(lengths) != 1:
        label = row.get("label") or row.get("model") or "This model"
        raise ValueError(
            f"This shot is longer than one {label} call accepts. Nothing was sent."
        )
    body["duration"] = engine["request_value"](lengths[0], row)
    return body


def _reject_error_body(data: dict) -> None:
    problem = _engine()["provider_error_message"](data)
    if problem:
        raise RuntimeError(
            f"The provider rejected the request. {problem} Nothing was produced."
        )


def _object(data: Any) -> dict:
    if not isinstance(data, dict):
        raise RuntimeError("The provider response was not a JSON object.")
    return data


def submit_generation(endpoint: str, payload: dict[str, Any], *, session=None) -> dict[str, Any]:
    """Submit a generation request to fal's async queue.

    Returns ``request_id``, ``status_url``, and ``response_url``. The body is
    the input fields themselves. Pass ``session`` in tests so nothing is sent.
    """
    http = session or requests
    ep = _endpoint_text(endpoint)
    body = queue_payload(ep, payload)
    url = f"{FAL_QUEUE_BASE}/{ep}"
    resp = http.post(url, headers=_headers(), json=body, timeout=30)
    resp.raise_for_status()
    data = _object(resp.json())
    _reject_error_body(data)
    request_id = str(data.get("request_id") or "")
    if not request_id:
        raise RuntimeError("No request_id in queue response. Nothing was produced.")
    logger.info("Submitted to %s", ep)
    engine = _engine()
    return {
        "request_id": request_id,
        "status_url": engine["fal_queue_url"](data.get("status_url")) or engine["fal_status_url"](ep, request_id),
        "response_url": engine["fal_queue_url"](data.get("response_url")) or engine["fal_result_url"](ep, request_id),
    }


def poll_status(
    endpoint: str,
    request_id: str,
    *,
    status_url: str | None = None,
    session=None,
) -> dict[str, Any]:
    """Poll the queue for request status. Returns the status payload.

    Uses ``status_url`` when the submit response returned one. Otherwise the
    URL is the owner and the app, the first two path segments, not the full
    endpoint.
    """
    http = session or requests
    ep = _endpoint_text(endpoint)
    engine = _engine()
    url = engine["fal_queue_url"](status_url) or engine["fal_status_url"](ep, request_id)
    resp = http.get(url, headers=_headers(), params={"logs": "true"}, timeout=15)
    resp.raise_for_status()
    data = _object(resp.json())
    state = str(data.get("status") or "")
    if state not in {"IN_QUEUE", "IN_PROGRESS", "COMPLETED"}:
        _reject_error_body(data)
    return data


def fetch_result(
    endpoint: str,
    request_id: str,
    *,
    response_url: str | None = None,
    session=None,
) -> dict[str, Any]:
    """Fetch the completed result from the queue."""
    http = session or requests
    ep = _endpoint_text(endpoint)
    engine = _engine()
    url = engine["fal_queue_url"](response_url) or engine["fal_result_url"](ep, request_id)
    resp = http.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = _object(resp.json())
    _reject_error_body(data)
    return data


def wait_for_completion(
    endpoint: str,
    request_id: str,
    timeout: int = 300,
    poll_interval: int = 5,
    on_log: Optional[callable] = None,
    *,
    status_url: str | None = None,
    response_url: str | None = None,
    session=None,
    sleeper=None,
    clock=None,
) -> dict[str, Any]:
    """
    Poll until the request completes or times out.
    Returns the final result dict.
    """
    pause = sleeper or time.sleep
    now = clock or time.monotonic
    start = now()
    current_status = status_url
    current_result = response_url
    while True:
        if now() - start > timeout:
            raise TimeoutError(
                f"Generation timed out after {timeout}s "
                f"(endpoint={endpoint})"
            )

        status = poll_status(endpoint, request_id, status_url=current_status, session=session)
        newer = _engine()["fal_queue_url"](status.get("response_url"))
        if newer:
            current_result = newer
        state = status.get("status", "UNKNOWN")

        if on_log and "logs" in status:
            redact = _engine()["redact"]
            for log in status["logs"]:
                on_log(redact(log.get("message", "")))

        if state == "COMPLETED":
            return fetch_result(
                endpoint,
                request_id,
                response_url=current_result,
                session=session,
            )
        if state in ("FAILED", "ERROR", "CANCELLED"):
            problem = _engine()["provider_error_message"](status) or _engine()["redact"](str(state))
            raise RuntimeError(
                f"The provider rejected the request. {problem} Nothing was produced."
            )

        pause(poll_interval)


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
    End-to-end: submit, poll, download using the fal-client SDK.
    Returns dict with keys: video_url, local_path, seed.
    """
    import fal_client as _fal

    ep = endpoint.value if hasattr(endpoint, "value") else endpoint
    logger.info("Calling fal_client.subscribe(%s)", ep)

    def on_update(update):
        if hasattr(update, "logs") and update.logs:
            for log in update.logs:
                msg = log.get("message", "") if isinstance(log, dict) else str(log)
                logger.debug("[fal] %s", msg)

    result = _fal.subscribe(ep, arguments=payload, with_logs=True, on_queue_update=on_update)

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
