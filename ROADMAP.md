# Roadmap

Status as of 2026-11-12.

## Where things stand

Phase 0 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/1, merge commit c369689. Phase 1 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/3, merge commit da9d54a. The treatment validates, the question round is closed, nothing can spend past a gate or the cap without a recorded approval, and the Director reaches crew only through the Line Producer. Ron approved the treatment gate and the $500 split is locked. Spent: $0.00 of $500.00.

Phase 2 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/4 and PR https://github.com/Roncho512/Movie-swarm/pull/5, merge commit f6f52d4. The previs package is written. The storyboard is one beat per shot: 41 shots, plus the three scene 3 shots, 44 in all. Ron approved the previs gate with the note "Approve the storyboard previs gate." No images were generated. Spent: $0.00 of $500.00.

Ron then changed direction. Build the studio first. Make the film later. Phase 3 merged to main on 2026-11-10 via PR https://github.com/Roncho512/Movie-swarm/pull/6, merge commit 1355ad4. The generation studio quotes any production, routes the cheap picture model, puts locked phrases on the prompt, and stops a paid call until Ron approves the generation gate. It was proven on Harbor Night. It did not write a generation plan for The Last Marker, and it did not generate a frame. The pilot sound prompts live in that film's folder, which was engine cleanup, not a film run. Spent: $0.00 of $500.00.

Phase 4 merged to main on 2026-11-11 via PR https://github.com/Roncho512/Movie-swarm/pull/7, merge commit c0de548. The Dailies Reviewer watches each generated take and writes a circle, retake, or reject. A takes manifest lists the files. The report is JSON plus a readable table. A retake carries a prompt fix and an estimate against the fix-loop line. Nothing is spent. The editor waits until Ron approves the dailies gate. The proof is Harbor Night and tiny synthetic frames. The Last Marker is not reviewed in this phase. Spent: $0.00 of $500.00.

Phase 5 merged to main on 2026-11-11 via PR https://github.com/Roncho512/Movie-swarm/pull/8, merge commit 683e4c5. The Editor cuts the circled takes into an edit decision list, trims toward the production brief, and flags a shot with no circled take. A locked prop is checked across adjacent cuts. ffmpeg renders a low-resolution preview when it is installed. The edit decision list is written either way. Ron approves an edit gate before sound. That approval is picture lock. The proof is Harbor Night and tiny synthetic clips. The Last Marker is not cut. Spent: $0.00 of $500.00.

Phase 6 merged to main on 2026-11-11 via PR https://github.com/Roncho512/Movie-swarm/pull/9, merge commit 8d0de69. The Sound Designer and the Composer spot a cue sheet onto the locked cut. Music follows the production's score brief, including where that brief asks for silence. Cues stay inside the cut. An effect outside the sync tolerance is flagged. A prop sound outside the frame is flagged. The quote uses the rate card and the Sound line. The card has no audio rate, so the price is marked unknown. A paid call waits on the generation gate. ffmpeg renders placeholder stems when it is installed. The cue sheet is written either way. Ron approves a sound gate before color and mix. The proof is Harbor Night and tiny synthetic audio. The Last Marker is not spotted. Spent: $0.00 of $500.00.

Phase 7 merged to main on 2026-11-11 via PR https://github.com/Roncho512/Movie-swarm/pull/10, merge commit 82fdbf5. The Colorist writes a grade plan from the production's look, with one base grade and one adjustment per scene. The Re-recording Mixer writes a mix plan from the cue sheet and the stems: levels, dialogue ducking, fades at scene changes, and a loudness target. The target is EBU R128 unless the production sets its own. The rate card has no color or mix price, so the estimate is unknown. ffmpeg renders a graded preview, the mix, and a married picture-and-sound preview when it is installed. The plans are written either way. Both calls wait until Ron has approved the edit gate and the sound gate. Ron approves a color-mix gate before final delivery. The proof is Harbor Night and tiny synthetic video and audio. The Last Marker is not graded or mixed. Spent: $0.00 of $500.00.

Phase 8 merged to main on 2026-11-11 via PR https://github.com/Roncho512/Movie-swarm/pull/11, merge commit 3fa56c0. The Post Supervisor reads the production's delivery spec and writes a master, the variants that spec asks for, a poster frame, and captions from the dialogue cues. QC checks duration, resolution, frame rate, loudness, black frames, frozen frames, and caption timing. The manifest lists files, SHA-256 checksums, spend against the $500 cap, the stage split, and every gate record. The package folder is a setting. Ron approves a delivery gate to mark the film delivered. `scripts/studio.py` walks Harbor Night from the treatment through that package and stops at each gate. A test harness can approve the gates. The command line cannot. The generation gate stays closed. The Last Marker is not delivered. Spent: $0.00 of $500.00.

Phase 8.5 is in review. The provider clients can call Anthropic, fal, and ElevenLabs. A call is sent only when the generation gate is approved, the estimate fits the stage line and the $500 cap, the key is in the environment, and `--live` is passed. Offline stays the default. The test shot command prepares exactly one picture call and records it. It was not run live. The rate card still has no audio, color, or delivery price, and no fal address for Gemini Omni or Kling. Spent: $0.00 of $500.00.

Phase 8.6 sits on that branch and is not merged. Six prep roles join the previs package: Assistant Director, Gaffer, Key Grip, Costume Designer, Makeup and Hair, and VFX Supervisor. Wardrobe and makeup are locked and checked the way props are. The VFX breakdown is written before the production gate. The VFX review is written with the dailies. No new gate was added. The locked $500 split did not change. The proof is Harbor Night. The Last Marker folder was not changed. Spent: $0.00 of $500.00.

Phase 8.7 sits on the Phase 8.6 branch and is not merged. Title and Graphic Design researches the film's graphic identity, writes a brand guide from that research, and then specs titles, title cards, end credits, subtitle styling, a designed poster, and collateral. The Art Director still owns the in-film look. A graphics gate starts closed. The role bills to the Art line. The locked $500 split did not change. The proof is Harbor Night. The Last Marker folder was not changed. Spent: $0.00 of $500.00.

Phase 8.8 sits on the Phase 8.7 branch and is not merged. Each film can carry its own budget. One calculator shows the whole film, trailer included. A film with no budget file keeps the $500 cap and the locked split. An overage still pauses for Ron, and his approval is recorded without editing the budget. The Trailer Editor cuts a teaser and a trailer from approved takes when the budget turns the trailer on, and bills it to Marketing and Distribution. A trailer gate starts closed. The film can deliver without it. The proof is Harbor Night. The Last Marker folder was not changed. Spent: $0.00 of $500.00. Merge order, when Ron is ready: 8.5, then 8.6, then 8.7, then 8.8.

## Phases

Each studio phase is proven on a synthetic fixture. The Last Marker is not the proof. Its approved previs waits for the last phase.

| Phase | What it covers | Status |
|---|---|---|
| 0 | Cleanup and foundation: shared handoff checks, run state, gates, the $500 cap, model routing, asset root, CI | Done, merged 2026-11-10, PR #1, merge c3696890 |
| 1 | Line Producer and Director core, with treatment intake | Done, merged 2026-11-10, PR #3, merge da9d54a |
| 2 | Prevent bad shots: Script Supervisor, Production Designer/Prop Master with locked hero-prop specs, camera package, storyboards/animatic, Stunt and Action Coordinator | Done, merged 2026-11-10, PRs #4 and #5, merge f6f52d4 |
| 3 | Generation studio: quote any production, route the cheap picture model, stop a paid call until Ron approves the generation gate, put locked phrases into the prompt | Done, merged 2026-11-10, PR #6, merge 1355ad4. Proven on Harbor Night. No pictures were generated. Spent $0.00 of $500.00. |
| 4 | Dailies review: circle, retake, or reject each take against locked phrases, the shot list, the look, and local technical checks. A gate blocks the editor until Ron approves the circled takes. | Done, merged 2026-11-11, PR #7, merge c0de548. Proven on Harbor Night and synthetic frames. No paid call. Spent $0.00 of $500.00. |
| 5 | Edit and assembly: an edit decision list from circled takes, in storyboard order, trimmed toward the brief. Missing coverage goes back to dailies or generation. A picture-lock gate blocks sound. | Done, merged 2026-11-11, PR #8, merge 683e4c5. Proven on Harbor Night and synthetic clips. No paid call. Spent $0.00 of $500.00. |
| 6 | Sound and score: a cue sheet on the locked cut, with dialogue, effects, foley, ambience, and music. Sync and prop-sound checks. A sound gate blocks color and mix. | Done, merged 2026-11-11, PR #9, merge 8d0de69. Proven on Harbor Night and synthetic audio. No paid call. Spent $0.00 of $500.00. |
| 7 | Color and mix: a grade plan from the production's look, a mix plan from the cue sheet, loudness against a cited target, and a color-mix gate before final delivery. | Done, merged 2026-11-11, PR #10, merge 82fdbf5. Proven on Harbor Night and synthetic video and audio. No paid call. Spent $0.00 of $500.00. |
| 8 | Final delivery: a master, variants, a poster, captions, QC, and a manifest, plus an offline studio run that stops at each gate. | Done, merged 2026-11-11, PR #11, merge 3fa56c0. Proven on Harbor Night and synthetic media. No paid call. Spent $0.00 of $500.00. |
| 8.5 | Provider wiring: real HTTP clients for Anthropic, fal, and ElevenLabs, behind the generation gate, the stage line, the key, and `--live`. Offline stays the default. One test-shot command. | In review. Proven on Harbor Night with a fake HTTP transport. No live call. Spent $0.00 of $500.00. |
| 8.6 | Crew the previs package was missing: Assistant Director, Gaffer, Key Grip, Costume Designer, Makeup and Hair, and VFX Supervisor. Wardrobe and makeup are checked like props. VFX is broken down before production and reviewed with the dailies. No new gate. No new budget line. | In review, stacked on Phase 8.5. Proven on Harbor Night. No live call. Spent $0.00 of $500.00. The Last Marker folder was not changed. |
| 8.7 | Title and Graphic Design. Research, then a brand guide, then titles, title cards, end credits, subtitle styling, key art, and collateral. A graphics gate starts closed. No new budget line. | On branch, awaiting Ron's merge. Stacked on Phase 8.6. Proven on Harbor Night. No live call. Spent $0.00 of $500.00. The Last Marker folder was not changed. |
| 8.8 | One budget per film, one calculator, a soft overage with approval, and the Trailer Editor. The trailer is optional, uses approved takes, and bills to Marketing and Distribution. | On branch, awaiting Ron's merge. Stacked on Phase 8.7. Merge order: 8.5, 8.6, 8.7, 8.8. Proven on Harbor Night. No live call. Spent $0.00 of $500.00. The Last Marker folder was not changed. |
| 9 | First film: the finished studio makes The Last Marker from its approved previs. | Not started |

## Gates

Every stage switch in `config/gates.json` is on, including the generation gate, the dailies gate, the edit gate, the sound gate, the color-mix gate, the delivery gate, the graphics gate, and the trailer gate. The trailer gate does not block delivery. Ron reviews each stage until that part of the crew is reliable. The end goal is smaller: Ron approves the look, and Ron approves the final cut. Turning a switch off is an edit to the config file, done later on purpose. It is not a code change.

On run phase-1, Ron approved the treatment gate. That locked the $500 split. Ron approved the previs gate on 2026-11-10. The generation gate is not approved. A plan can be quoted without it. A paid call cannot. The dailies gate is not approved. The editor cannot run until it is. The edit gate is not approved. Sound cannot run until Ron locks picture. The sound gate is not approved. Color and mix cannot run until he approves both picture lock and the cue sheet. The color-mix gate is not approved. Final delivery cannot run until he approves the grade and the mix. The delivery gate is not approved. The film is not delivered until he approves the package. Other stage switches stay on.

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
- The older video program still calls Seedance, and QA still calls its current Claude model. The generation pipeline quotes Gemini Omni 1.2 Flash. A live call for that model is refused because the rate card has no fal address for it. Connecting that address is still open, and it still waits on Ron's generation-gate approval and `--live`.
- Audio, color, and delivery have no published price in this repo. A live call for one of them is refused unless Ron approves a one-call price override.

Phase 1 records technical choices D15 through D22. Phase 2 records D31 through D37. Phase 3 records D42 through D46. Phase 4 records D47 through D51. Phase 5 records D52 through D57. Phase 6 records D58 through D63. Phase 7 records D64 through D70. Phase 8 records D71 through D79. Phase 8.5 records D80 through D86. Phase 8.6 records D87 through D93. Phase 8.7 records D94 through D98. Phase 8.8 records D99 through D108. D99 through D102 were decided by Ron on the 2026-11-11 call. D103 through D108 are proposals from the build. Ron has not accepted or rejected the proposals in a decision entry. They are not closed.

## What comes next

Ron reviews Phase 8.5, Phase 8.6, Phase 8.7, and Phase 8.8. The merge order is 8.5, then 8.6, then 8.7, then 8.8. Phases 4 through 8 are merged. He can accept or reject D47 through D98, and D103 through D108. D99 through D102 are the budget and trailer choices from the 2026-11-11 call. Merging does not approve a paid run, the dailies gate, the edit gate, the sound gate, the color-mix gate, the delivery gate, the graphics gate, or the trailer gate on The Last Marker. The generation gate stays closed until he approves it on a run. `--live` was not used. Phase 8.6 did not add a gate. Phase 8.7 added a graphics gate that starts closed. Phase 8.8 added a trailer gate that starts closed and does not block delivery. A film with no budget file keeps the locked split.

The next phase is the first film. The Last Marker is made from its approved previs, still inside the $500 cap. Before that run can leave the machine, these are still open:

- Ron's keys, in the environment only: `ANTHROPIC_API_KEY`, `FAL_KEY`, and `ELEVENLABS_API_KEY`. No key is stored in the repo.
- A delivery spec at `productions/the-last-marker/delivery/delivery-spec.json`: master codec and size, which variants he wants (16:9, 9:16, 1:1), the poster shot, and sidecar or burned-in captions. The studio does not invent those for the film.
- Ron's approval of the generation gate on that run. Until he does, no paid picture or audio call is made.
- The first live test shot, one shot, after he has read the estimate. The command is `scripts/line-producer.py` `test-shot`. It was not run.
- A published price for audio, color, and delivery. This repo does not contain one, so those calls stay unknown until Ron approves a one-call override or a cited rate is added.
- A fal address for Gemini Omni 1.2 Flash and for Kling. The rate card has their picture prices and no endpoint, so a live call for them is refused. Seedance 2.0 and Seedance 2.0 fast are the picture models with a fal address.
- The folder on the Ron Workspace drive, if the package should be written there. Set `MOVIE_SWARM_ASSET_ROOT` or `asset_root` in `config/assets.json`. The path is still unset. `asset_root` is null.
