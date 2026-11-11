"""The Dailies Reviewer hook.

A later phase watches the real frames. This one only records the locked
phrases that review would check. It does not call a model and it does not
open a picture.
"""

from __future__ import annotations

from movie_swarm.continuity import expected_phrases


def review_dailies(
    *,
    shot_id: str,
    prompt: str,
    props_in_frame,
    lock: dict | None,
    clip_ref: str | None = None,
) -> dict:
    """Return the stub a post-generation check calls. ``watched`` stays false."""
    phrases = expected_phrases(prompt, props_in_frame, lock)
    return {
        "status": "stub",
        "reviewer": "dailies",
        "shot_id": shot_id,
        "watched": False,
        "clip_ref": clip_ref,
        "phrases": phrases,
        "note": (
            "The Dailies Reviewer did not watch a frame and did not call a model. "
            "A later phase checks these phrases on the picture."
        ),
    }
