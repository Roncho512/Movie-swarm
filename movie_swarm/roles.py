"""Role names shared by the Line Producer and the Director.

``GATED_CREW`` are the coded agents the Director may call. A call to one of
them waits until Ron has approved the treatment and that stage.

``PREP_STAGES`` can record a small model cost while they prepare the work
Ron reviews. They still cannot pass the film cap or a locked stage allocation.
"""

from __future__ import annotations


GATED_CREW = (
    "production",
    "sound-designer",
    "editor",
    "qa",
    "fix-loop",
)

PREP_STAGES = (
    "director",
    "line-producer",
)
