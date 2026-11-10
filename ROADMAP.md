Status as of 2026-11-10.

## Where things stand

Phase 0 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/1, merge commit c369689. Phase 1 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/3, merge commit da9d54a. The treatment validates, the question round is closed, nothing can spend past a gate or the cap without a recorded approval, and the Director reaches crew only through the Line Producer. Ron approved the treatment gate and the $500 split is locked. Spent: $0.00 of $500.00.

Phase 2's done-when is met. The previs package is written, the storyboard is one beat per shot, and Ron approved the previs gate on 2026-11-10 with the note "Approve the storyboard previs gate." That approval is the board at commit 48d84b0, plus the status recorded on this branch. No images were generated. Spent: $0.00 of $500.00. Phase 2 is waiting for Ron to merge it. The old pilot shot list still has 17 missing exhaust-side statements. Those are the earlier pilot, not this storyboard.

## Phases

| Phase | What it covers | Status |
|---|---|---|
| 0 | Cleanup and foundation: shared handoff checks, run state, gates, the $500 cap, model routing, asset root, CI | Done, merged 2026-11-10, PR #1, merge c3696890 |
| 1 | Line Producer and Director core, with treatment intake | Done, merged 2026-11-10, PR #3, merge da9d54a |
| 2 | Prevent bad shots: Script Supervisor, Production Designer/Prop Master with locked hero-prop specs, camera package, storyboards/animatic, Stunt and Action Coordinator | Building, awaiting merge |
| 3 | Catch bad shots: coverage and multiple takes, Dailies Reviewer watching full video, Assistant Editor | Not started |
| 4 | Editor upgrade and Colorist | Not started |
| 5 | Sound: Composer, Foley and Ambience, generalized Sound Designer, Re-recording Mixer | Not started |
| 6 | QA on the full cut, Test Audience, Post Supervisor replacing Fix Loop | Not started |
| 7 | Finish The Last Marker end to end with zero exhaust-side/watch-wrist mismatches, then relax the middle gates | Not started |

## Gates

Every stage switch in `config/gates.json` is on. Ron reviews each stage until that part of the crew is reliable. The end goal is smaller: Ron approves the look, and Ron approves the final cut. Turning a switch off is an edit to the config file, done later on purpose. It is not a code change.

On run phase-1, Ron approved the treatment gate. That locked the $500 split. Ron approved the previs gate on 2026-11-10. A picture call still waits for its own stage gate. Other stage switches stay on.

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
- D28 — The proposed $500 split is the one Ron wants.
- D29 — Ron approved the treatment gate. The split is locked on the run.
- D30 — Film facts stay in the production folder. The engine does not hard-code a film's props, years, or look.
- D38 — The Last Marker is a subtle placement for the Breitling Top Time. Not an ad.
- D39 — Scene 3 gains the empty canteen, circling buzzards, and a hard cut from a buzzard's face to his eyes.
- D40 — Ron approved the storyboard previs gate.

## Open decisions

- The folder path on the Ron Workspace drive. The switch exists. The path is not set.
- When the video program and the QA program switch to the models in D6. The direction is decided. The code still calls today's models.
- Whether to move the pilot sound library out of `agents/06-sound-designer/src/pipeline.py`. D30 says a film's prompts belong in the production folder. That list is still in the sound program. This phase did not rewrite it.

Phase 1 records technical choices D15 through D22. Phase 2 records D31 through D37. They are proposals from the build, pending Ron's approval at merge. They are not closed.

## What comes next

Ron merges Phase 2 when he is ready. He can also accept or reject D31 through D37. After the merge, Phase 3 starts the roles that catch a bad shot after it exists: coverage, extra takes, a Dailies Reviewer, and an Assistant Editor.
