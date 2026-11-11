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

# The cue sheet can be written while this gate is closed.
# Color and mix wait until Ron approves it.
SOUND_STAGE = "sound"

# The grade and the mix can be written while this gate is closed.
# Final delivery waits until Ron approves it.
COLOR_MIX_STAGE = "color-mix"

# The package can be written while this gate is closed.
# Ron's approval marks the film delivered.
DELIVERY_STAGE = "delivery"

# The Composer bills against the Sound line, which is the sound-designer allocation.
SOUND_BILLING = {
    "composer": "sound-designer",
}

# Color bills against the editor allocation. The mix bills against the Sound line.
# The dollar amounts stay the split already locked. No new bucket is added.
COLOR_MIX_BILLING = {
    "colorist": "editor",
    "mixer": "sound-designer",
}

# Delivery bills against the editor allocation. No new line is added.
DELIVERY_BILLING = {
    "post-supervisor": "editor",
}

# A dailies call is an estimate. It is checked against the fix-loop ceiling and not charged.
# The dollar amount stays the split already locked. No new bucket is added.
DAILIES_BILLING = {
    "dailies": "fix-loop",
}

# The Composer spots music onto the locked cut. The cue sheet is the review,
# so this call does not wait on the sound gate.
SOUND_CREW = ("composer",)

# The Colorist and the Mixer write the plans Ron reads at the color-mix gate.
# The call waits for picture lock and the sound gate. It does not wait on color-mix.
COLOR_MIX_CREW = ("colorist", "mixer")

# The Post Supervisor writes the package Ron reads at the delivery gate.
# The call waits for the color-mix gate. It does not wait on the delivery gate.
DELIVERY_CREW = ("post-supervisor",)

CALLABLE = PICTURE_CREW + PHASE2_CREW + DAILIES_CREW + SOUND_CREW + COLOR_MIX_CREW + DELIVERY_CREW

PREP_STAGES = (
    "director",
    "line-producer",
)
