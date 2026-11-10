Status as of 2026-11-10.

## Where things stand

Phase 0 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/1, merge commit c3696890. Phase 1 is in progress. The Director's first question round is answered. The revised Last Marker treatment is still a draft. Ron has not approved the treatment gate.

## Phases

| Phase | What it covers | Status |
|---|---|---|
| 0 | Cleanup and foundation: shared handoff checks, run state, gates, the $500 cap, model routing, asset root, CI | Done, merged 2026-11-10, PR #1, merge c3696890 |
| 1 | Line Producer and Director core, with treatment intake | Building |
| 2 | Prevent bad shots: Script Supervisor, Production Designer/Prop Master with locked hero-prop specs, camera package, storyboards/animatic, Stunt and Action Coordinator | Not started |
| 3 | Catch bad shots: coverage and multiple takes, Dailies Reviewer watching full video, Assistant Editor | Not started |
| 4 | Editor upgrade and Colorist | Not started |
| 5 | Sound: Composer, Foley and Ambience, generalized Sound Designer, Re-recording Mixer | Not started |
| 6 | QA on the full cut, Test Audience, Post Supervisor replacing Fix Loop | Not started |
| 7 | Finish The Last Marker end to end with zero exhaust-side/watch-wrist mismatches, then relax the middle gates | Not started |

## Gates

Every stage switch in `config/gates.json` is on. Ron reviews each stage until that part of the crew is reliable. The end goal is smaller: Ron approves the look, and Ron approves the final cut. Turning a switch off is an edit to the config file, done later on purpose. It is not a code change.

The treatment gate is the one in front of Ron now. Approving it locks the proposed split of the $500. Crew calls stay paused until that gate, and the gate for that crew stage, are approved.

## Closed decisions

These are made. The write-up is in [DECISIONS.md](DECISIONS.md).

- D1 — Ron is the executive producer. The old agent slot is the Line Producer.
- D2 — The Director has creative say, inside a stage budget.
- D3 — A human gate after every stage, until the crew is dialed in.
- D4 — The output is a finished video.
- D5 — $500 cap, retakes included. The split is proposed at the treatment and approved by Ron.
- D6 — Cost-conscious models. Cheap models for admin. Gemini for the picture plan and for watching dailies. Claude for the Director and the writing. Seedance and Kling as alternates.
- D7 — The Last Marker stays the test film.
- D8 — Sergio Leone look, Morricone-spirited score, no copied melody.
- D9 — Finished files belong on Ron's external drive. Working files stay on the run machine.
- D10 — The story year is 1967. The Triumph is a 1965.
- D11 — Hero props get locked specs and are checked before and after generation.
- D12 — Add a Stunt and Action Coordinator.
- D13 — Scripts become treatments through questions with Ron. A template says what is required.
- D14 — Living docs update in the same pull request as the code.
- D23 — The Last Marker theme, tone, and references stay as drafted.
- D24 — Miguel chooses life over winning.
- D25 — Withhold whether the canyon has water.
- D26 — The kick and spark-plug beats stay.
- D27 — Exhaust on the right. Watch on the left wrist.
- D28 — The proposed $500 split is the one Ron wants. The treatment gate still has to lock it.

## Open decisions

- The folder path on the Ron Workspace drive. The switch exists. The path is not set.
- When the video program and the QA program switch to the models in D6. The direction is decided. The code still calls today's models.

Phase 1 also records technical choices D15 through D22. They are proposals from the build, pending Ron's approval at merge. They are not closed.

## What comes next

Ron reads the revised `productions/the-last-marker/treatment/treatment.md` and approves or rejects the treatment gate. That approval is what locks the $500 split in the Line Producer's books. After that, Phase 2 starts the roles that stop a bad shot before it is generated: the Script Supervisor, the Prop Master with locked hero-prop specs, the camera package, storyboards, and the Stunt and Action Coordinator.
