# Roadmap

Status as of 2026-11-11.

## Where things stand

Phase 0 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/1, merge commit c369689. Phase 1 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/3, merge commit da9d54a. The treatment validates, the question round is closed, nothing can spend past a gate or the cap without a recorded approval, and the Director reaches crew only through the Line Producer. Ron approved the treatment gate and the $500 split is locked. Spent: $0.00 of $500.00.

Phase 2 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/4 and PR https://github.com/Roncho512/Movie-swarm/pull/5, merge commit f6f52d4. The previs package is written. The storyboard is one beat per shot: 41 shots, plus the three scene 3 shots, 44 in all. Ron approved the previs gate with the note "Approve the storyboard previs gate." No images were generated. Spent: $0.00 of $500.00.

Ron then changed direction. Build the studio first. Make the film later. Phase 3 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/6, merge commit 1355ad4. The generation studio quotes any production, routes the cheap picture model, puts locked phrases on the prompt, and stops a paid call until Ron approves the generation gate. It was proven on Harbor Night. It did not write a generation plan for The Last Marker, and it did not generate a frame. The pilot sound prompts live in that film's folder, which was engine cleanup, not a film run. Spent: $0.00 of $500.00.

Phase 4 is in review. The Dailies Reviewer watches each generated take and writes a circle, retake, or reject. A takes manifest lists the files. The report is JSON plus a readable table. A retake carries a prompt fix and an estimate against the fix-loop line. Nothing is spent. The editor waits until Ron approves the dailies gate. The proof is Harbor Night and tiny synthetic frames. The Last Marker is not reviewed in this phase.

Phase 5 is in review. It is built on the Phase 4 branch, which Ron has not merged. He merges Phase 4 first. The Editor cuts the circled takes into an edit decision list, trims toward the production brief, and flags a shot with no circled take. A locked prop is checked across adjacent cuts. ffmpeg renders a low-resolution preview when it is installed. The edit decision list is written either way. Ron approves an edit gate before sound. That approval is picture lock. The proof is Harbor Night and tiny synthetic clips. The Last Marker is not cut. Spent: $0.00 of $500.00.

## Phases

Each studio phase is proven on a synthetic fixture. The Last Marker is not the proof. Its approved previs waits for the last phase.

| Phase | What it covers | Status |
|---|---|---|
| 0 | Cleanup and foundation: shared handoff checks, run state, gates, the $500 cap, model routing, asset root, CI | Done, merged 2026-11-10, PR #1, merge c3696890 |
| 1 | Line Producer and Director core, with treatment intake | Done, merged 2026-11-10, PR #3, merge da9d54a |
| 2 | Prevent bad shots: Script Supervisor, Production Designer/Prop Master with locked hero-prop specs, camera package, storyboards/animatic, Stunt and Action Coordinator | Done, merged 2026-11-10, PRs #4 and #5, merge f6f52d4 |
| 3 | Generation studio: quote any production, route the cheap picture model, stop a paid call until Ron approves the generation gate, put locked phrases into the prompt | Done, merged 2026-11-10, PR #6, merge 1355ad4. Proven on Harbor Night. No pictures were generated. Spent $0.00 of $500.00. |
| 4 | Dailies review: circle, retake, or reject each take against locked phrases, the shot list, the look, and local technical checks. A gate blocks the editor until Ron approves the circled takes. | In review. Proven on Harbor Night and synthetic frames. No paid call. Spent $0.00 of $500.00. |
| 5 | Edit and assembly: an edit decision list from circled takes, in storyboard order, trimmed toward the brief. Missing coverage goes back to dailies or generation. A picture-lock gate blocks sound. | In review. Proven on Harbor Night and synthetic clips. No paid call. Spent $0.00 of $500.00. |
| 6 | Sound and score, using the production's sound prompts. Proven on a synthetic fixture. Sound waits until Ron approves picture lock. | Not started |
| 7 | Color and mix. Proven on a synthetic fixture. | Not started |
| 8 | Final delivery: a finished file, still proven on a synthetic fixture. | Not started |
| 9 | First film: the finished studio makes The Last Marker from its approved previs. | Not started |

## Gates

Every stage switch in `config/gates.json` is on, including the generation gate and the dailies gate. Ron reviews each stage until that part of the crew is reliable. The end goal is smaller: Ron approves the look, and Ron approves the final cut. Turning a switch off is an edit to the config file, done later on purpose. It is not a code change.

On run phase-1, Ron approved the treatment gate. That locked the $500 split. Ron approved the previs gate on 2026-11-10. The generation gate is not approved. A plan can be quoted without it. A paid call cannot. The dailies gate is not approved. The editor cannot run until it is. The edit gate is not approved. Sound cannot run until Ron locks picture. Other stage switches stay on.

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
- D41 — Build the studio first. Make The Last Marker in the last phase, from the approved previs.

## Open decisions

- The folder path on the Ron Workspace drive. The switch exists. The path is not set.
- The older video program still calls Seedance, and QA still calls its current Claude model. The generation pipeline quotes Gemini Omni 1.2 Flash and does not call it. Connecting a live client is a later step, after Ron approves the generation gate.

Phase 1 records technical choices D15 through D22. Phase 2 records D31 through D37. Phase 3 records D42 through D46. Phase 4 records D47 through D51. Phase 5 records D52 through D57. They are proposals from the build, pending Ron's approval at merge. They are not closed.

## What comes next

Ron reviews Phase 4 and Phase 5. Phase 4 is not merged. Phase 5 sits on that branch, so he merges Phase 4 first. He can accept or reject D47 through D51, and D52 through D57. Merging does not approve a paid run, the dailies gate, or the edit gate on The Last Marker. The generation gate stays closed until he approves it on a run. The next studio phase is sound and score, proven on a fixture, still without making The Last Marker. Sound waits until he approves picture lock.
