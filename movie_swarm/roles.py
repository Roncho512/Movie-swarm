"""Role names shared by the Line Producer and the Director.

``GATED_CREW`` are the coded agents the Director may call. A call to one of
them waits until Ron has approved the treatment and that stage.

``PREP_STAGES`` can record a small model cost while they prepare the work
Ron reviews. They still cannot pass the film cap or a locked stage allocation.
"""

from __future__ import annotations


# Picture calls. Each one has its own gate, and it also waits for the previs gate.
PICTURE_CREW = (
    "production",
    "sound-designer",
    "editor",
    "qa",
    "fix-loop",
)

# The old name. A spend on one of these still waits for that stage's gate.
GATED_CREW = PICTURE_CREW

# Phase 2 writes the package Ron reviews at the previs gate.
# The call does not require that gate to be open already. The files are the review.
PHASE2_CREW = (
    "script-supervisor",
    "prop-master",
    "cinematographer",
    "stunt-coordinator",
)

# Which locked ceiling a phase 2 estimate is checked against.
# The dollar amounts stay the split Ron already locked. No new bucket is added.
PHASE2_BILLING = {
    "script-supervisor": "screenwriter",
    "prop-master": "art-director",
    "cinematographer": "cinematographer",
    "stunt-coordinator": "production",
}

PREVIS_STAGE = "previs"

# A paid image, video, or audio call waits here even after the stage gate is open.
GENERATION_STAGE = "generation"

# The Dailies Reviewer writes the report Ron reads. The editor waits on this gate.
DAILIES_CREW = ("dailies",)
DAILIES_STAGE = "dailies"

# Picture lock. The editor writes the cut while this gate is closed.
# Sound waits until Ron approves it.
EDIT_STAGE = "edit"

# A dailies call is an estimate. It is checked against the fix-loop ceiling and not charged.
# The dollar amount stays the split already locked. No new bucket is added.
DAILIES_BILLING = {
    "dailies": "fix-loop",
}

CALLABLE = PICTURE_CREW + PHASE2_CREW + DAILIES_CREW

PREP_STAGES = (
    "director",
    "line-producer",
)
