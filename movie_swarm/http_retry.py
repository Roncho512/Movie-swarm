"""HTTP with a timeout, a few retries, and no secrets in the error text.

The transport is injectable so tests can answer without a network call.
A timeout on a request that might already have been accepted is not retried
unless the caller says the request is safe to send again (a GET).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from movie_swarm.redact import redact


class HttpTimeout(Exception):
    """The provider did not answer before the timeout."""


class HttpConnectionError(Exception):
    """The provider could not be reached. The request was not accepted."""


class HttpStatusError(Exception):
    """The provider answered with an error status."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.retryable = status in {429, 500, 502, 503, 504}


@dataclass
class HttpResult:
    status: int
    body: bytes
    headers: dict = field(default_factory=dict)


DEFAULT_BACKOFF = (0.5, 1.0, 2.0)


def send_with_retry(
    transport,
    *,
    method: str,
    url: str,
    headers: dict | None,
    body,
    timeout: float,
    attempts: int = 3,
    sleeper=time.sleep,
    backoff: tuple[float, ...] = DEFAULT_BACKOFF,
    retry_timeout: bool = False,
) -> HttpResult:
    """Send one HTTP request. Retry a connection error or a 429/5xx.

    ``retry_timeout`` is for a GET. A POST that times out is not sent again
    by this helper, because the provider may already have accepted it.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = transport(method, url, dict(headers or {}), body, timeout)
        except TimeoutError as exc:
            message = redact(str(exc) or "The provider did not answer before the timeout.")
            if not retry_timeout or attempt == attempts:
                raise HttpTimeout(message) from exc
            last_error = HttpTimeout(message)
        except ConnectionError as exc:
            message = redact(str(exc) or "The provider could not be reached.")
            if attempt == attempts:
                raise HttpConnectionError(message) from exc
            last_error = HttpConnectionError(message)
        else:
            if result.status < 400:
                return result
            detail = _snippet(result.body)
            message = redact(f"The provider returned {result.status}. {detail}".strip())
            error = HttpStatusError(result.status, message)
            if not error.retryable or attempt == attempts:
                raise error
            last_error = error
        delay = backoff[min(attempt - 1, len(backoff) - 1)]
        sleeper(delay)
    if last_error is None:
        raise HttpConnectionError("The provider could not be reached.")
    raise last_error


def _snippet(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace")[:180]
    return redact(text).replace("\n", " ").strip()


class UrllibTransport:
    """The real transport. It uses the standard library. Tests do not use it.

    Errors name the status or the kind of failure. They do not include
    request headers, so a key in a header cannot leak through this path.
    """

    def __call__(self, method, url, headers, body, timeout) -> HttpResult:
        data = None
        hdrs = {str(key): str(value) for key, value in (headers or {}).items()}
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        elif isinstance(body, bytes):
            data = body
        request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                status = getattr(response, "status", None) or response.getcode()
                return HttpResult(int(status), payload, {})
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            return HttpResult(int(exc.code), payload, {})
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).casefold():
                raise TimeoutError("The provider did not answer before the timeout.") from exc
            raise ConnectionError("The provider could not be reached.") from exc
