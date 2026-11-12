"""Model calls for the Director and the Line Producer.

The model name comes from ``config/model-routing.json``. The API key is read
from the environment when a real call is made. Tests pass a fake transport
and never need a key.

No temperature is sent. Current Claude models reject it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from movie_swarm.models import resolve_model
from movie_swarm.redact import redact


class LLMError(Exception):
    """The model call did not return usable text."""


class WritingQuote(LLMError):
    """``--live`` printed a writing quote and did not send the call."""


class ModelReply(str):
    """The model text, plus whether the provider stopped at the output cap.

    It is a string, so existing callers can keep using it as text. ``stop_reason``
    is the provider's value. ``output_tokens`` is the reported count.
    """

    def __new__(
        cls,
        text: str,
        *,
        stop_reason: str | None = None,
        output_tokens: int | None = None,
        max_tokens: int | None = None,
    ):
        reply = str.__new__(cls, text)
        reply.stop_reason = stop_reason
        reply.output_tokens = output_tokens
        reply.max_tokens = max_tokens
        return reply


class LLMClient:
    """One completion. ``role`` and ``purpose`` pick the model from config."""

    def __init__(self, transport):
        self.transport = transport

    def complete(
        self,
        *,
        role: str,
        purpose: str,
        system: str,
        user: str,
        max_tokens: int = 4000,
    ) -> str:
        chosen = resolve_model(role, purpose=purpose)
        model = chosen.get("model")
        if not model:
            raise LLMError(
                f"No model is configured for {role} / {purpose}. "
                "Set one in config/model-routing.json."
            )
        return self.transport.complete(
            model=model,
            system=system,
            user=user,
            max_tokens=max_tokens,
        )


class AnthropicTransport:
    """Claude messages API. Reads ``ANTHROPIC_API_KEY`` at call time."""

    url = "https://api.anthropic.com/v1/messages"

    def complete(self, *, model: str, system: str, user: str, max_tokens: int) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set.")
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = redact(exc.read().decode("utf-8", errors="replace")[:500])
            raise LLMError(f"The model call failed ({exc.code}). {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"The model call could not connect. {redact(str(exc.reason))}") from exc

        parts = []
        for block in body.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
        text = "\n".join(parts).strip()
        if not text:
            raise LLMError("The model returned no text.")
        return text


def client_from_environment() -> LLMClient | None:
    """A real client when the API key is set. Otherwise None (use the offline path)."""
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return None
    return LLMClient(AnthropicTransport())
