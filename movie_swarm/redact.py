"""Strip provider keys out of text before it is printed, saved, or raised.

The values are read from the environment at the moment of redaction. The
names of the variables are not secrets. The values are.
"""

from __future__ import annotations

import os


KEY_NAMES = ("ANTHROPIC_API_KEY", "FAL_KEY", "ELEVENLABS_API_KEY")


def secret_values() -> list[str]:
    """Key values currently in the environment. Short strings are left alone.

    A value shorter than 8 characters is not stripped. Replacing a tiny
    string would punch holes in ordinary words. Real provider keys are longer.
    """
    found = []
    for name in KEY_NAMES:
        value = os.environ.get(name, "").strip()
        if len(value) >= 8 and value not in found:
            found.append(value)
    return found


def redact(text: str) -> str:
    """Return ``text`` with any current key value replaced by ``[redacted]``."""
    if not text:
        return ""
    cleaned = str(text)
    for value in secret_values():
        cleaned = cleaned.replace(value, "[redacted]")
    return cleaned
