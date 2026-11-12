# Movie Swarm

Movie Swarm turns a screenplay into a finished short film. Specialized helpers, called agents, do the steps. Ron is the executive producer. He reviews the work and decides what is allowed to spend money.

New to a film, or coming back after a long gap? Read [START-HERE.md](START-HERE.md).

## Current status

Phase 0 is on main. It merged on 2026-11-10 in [pull request 1](https://github.com/Roncho512/Movie-swarm/pull/1), merge `c369689`. Phase 0 is the shared checklist, the run record, the review gates, and the $500 cap.

Phase 1 is on main. It merged on 2026-11-10 in [pull request 3](https://github.com/Roncho512/Movie-swarm/pull/3), merge `da9d54a`. The Line Producer watches the budget, the schedule, the credits, and the gates. The Director reads a screenplay and writes a treatment, which is the plan for the film before anyone generates a shot. Ron approved the Last Marker treatment gate. The $500 stage split is locked on run phase-1. Spent so far: $0.00 of $500.00.

Phase 2 is on main. It merged on 2026-11-10 in [pull request 4](https://github.com/Roncho512/Movie-swarm/pull/4) and [pull request 5](https://github.com/Roncho512/Movie-swarm/pull/5), merge `f6f52d4`. The storyboard is one beat per shot: 41 shots, plus the three scene 3 shots Ron added, 44 in all. Ron approved the previs gate. The note is "Approve the storyboard previs gate." No images were generated.

Phase 3 is on main. It merged on 2026-11-10 in [pull request 6](https://github.com/Roncho512/Movie-swarm/pull/6), merge `1355ad4`. The studio can quote any production, put locked prop phrases into a prompt, and refuse a paid call until Ron approves a gate called `generation`. A gate is a switch that makes a stage wait for Ron. That build does not call a provider. The generation gate on The Last Marker is still closed. Spent so far: $0.00 of $500.00.

Phase 4 is on main. It merged on 2026-11-11 in [pull request 7](https://github.com/Roncho512/Movie-swarm/pull/7), merge `c0de548`. After generation, every take is reviewed before it can be cut. A take is one generated clip or frame for a shot. The Dailies Reviewer circles a take that passes, sends a bad one back as a retake, or rejects a file that is missing. The proof is Harbor Night, under `tests/fixtures/`, plus tiny frames made in the tests. Harbor Night is a synthetic production, not The Last Marker. The review does not call a paid model. A retake is an estimate against the fix-loop line, and nothing is charged. The editor waits until Ron approves the `dailies` gate. Making The Last Marker is still the last phase.

Phase 5 is on main. It merged on 2026-11-11 in [pull request 8](https://github.com/Roncho512/Movie-swarm/pull/8), merge `683e4c5`. The Editor assembles the circled takes into a rough cut. An edit decision list is the cut: which take, where it starts and ends, and how it joins the next shot. JSON is the source of truth. A CMX3600 file is a reading copy of the same cut. The editor trims toward the runtime in the production brief and does not invent a shot. A shot with no circled take is a blocker sent back to dailies or generation. Locked props are checked across adjacent cuts. When ffmpeg is installed, a small preview is rendered. When it is not, the edit decision list is still written. Ron approves an `edit` gate before sound. That approval is picture lock. The proof is Harbor Night plus tiny synthetic clips. Nothing was spent. The Last Marker was not cut.

Phase 6 is on main. It merged on 2026-11-11 in [pull request 9](https://github.com/Roncho512/Movie-swarm/pull/9), merge `8d0de69`. After picture lock, the Sound Designer and the Composer spot a cue sheet onto the cut: dialogue, sound effects, foley, ambience, and music. Each cue has a start and end, the shots it belongs to, a prompt, and a source of generated, library, or silence. Music follows `audio/score-brief.json` when the production has one, including the shots that brief leaves silent. A cue has to sit inside the cut. An effect tied to a shot is flagged when it lands outside a short sync tolerance. A prop sound is flagged when that prop is not in the shot. The plan is priced from the rate card against the Sound line. That card has no audio rate, so the price is marked unknown. A paid call waits on the generation gate. When ffmpeg is installed, placeholder stems and a temp mix are rendered. When it is not, the cue sheet is still written. Ron approves a `sound` gate before color and mix. The proof is Harbor Night plus tiny synthetic audio. Nothing was spent. The Last Marker was not spotted.

Phase 7 is on main. It merged on 2026-11-11 in [pull request 10](https://github.com/Roncho512/Movie-swarm/pull/10), merge `82fdbf5`. After the edit gate and the sound gate are both approved, the Colorist grades the locked picture and the Re-recording Mixer mixes the stems. A grade plan is the color: one base grade for the whole cut, plus one adjustment per scene, read from `look/look.json` and from `look/grade.json` when the production has one. A mix plan is the sound: a level for each stem, dialogue in front, music and effects ducked under dialogue, and a fade at each scene change. Loudness is checked against EBU R128, or against `audio/mix-targets.json` when the production sets its own target. EBU R128 is a published delivery standard: -23.0 LUFS, true peak no higher than -1.0 dBTP. The rate card has no color or mix price, so that estimate is marked unknown and is not stored as zero. When ffmpeg is installed, it renders a low-resolution graded preview, the mix, and a married preview of picture plus sound. When it is not, the plans are still written. Ron approves a `color-mix` gate before final delivery. The proof is Harbor Night plus tiny synthetic video and audio. Nothing was spent. The Last Marker was not graded or mixed.

Phase 8 is on main. It merged on 2026-11-11 in [pull request 11](https://github.com/Roncho512/Movie-swarm/pull/11), merge `3fa56c0`. The Post Supervisor reads `delivery/delivery-spec.json` from the production folder and writes a delivery package: a master file, the web or social variants the spec asks for, a poster frame, and captions timed from the dialogue cues. QC checks duration, resolution, frame rate, loudness, black frames, frozen frames, and caption timing. The report is JSON plus a short Markdown table. A delivery manifest lists the files, a SHA-256 checksum for each one that was written, the film spend against the $500 cap, the stage split, and every gate record. The package folder follows `MOVIE_SWARM_ASSET_ROOT` or `config/assets.json`. No drive path is hard-coded. Ron approves a `delivery` gate to mark the film delivered. One command, `scripts/studio.py`, walks Harbor Night from the treatment through that package and stops at each gate. A test harness can approve those gates. The command line cannot. The generation gate stays closed. Nothing was spent. The Last Marker was not delivered.

Phase 8.5 wires the provider clients. A provider is the company that makes the picture, the sound, or the text. Anthropic is the text provider. fal is the picture provider. ElevenLabs is the sound provider. A real call is sent only when all four of these are true: the generation gate is approved, the estimate fits the remaining money on that stage line and under the $500 cap, the key for that provider is in the environment, and the command was given `--live`. Offline stays the default. A test shot is one picture call for one shot. The command is on the Line Producer. It was not run live. The rate card still has no price for audio, color, or delivery, and no fal address for Gemini Omni or Kling, so those calls are refused. Spent so far: $0.00 of $500.00. The Last Marker was not generated.

Phase 8.6 adds six prep roles, on top of the Phase 8.5 branch. The Assistant Director writes a shooting schedule and a call sheet from the shot list and the scenes, and flags stunt beats. The Gaffer writes a lighting plan from the camera package. The Key Grip writes camera support and rigging from that plan and the shot list. The Costume Designer and Makeup and Hair lock per-character specs the way the Prop Master locks props. The Script Supervisor, the dailies review, and the edit check those locks for drift. The VFX Supervisor writes a breakdown and turnover notes for the editor and the colorist, then reviews the VFX shots after dailies. No new gate was added. The new roles bill against lines that are already in the locked split. The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Phase 8.7 adds Title and Graphic Design, on top of the Phase 8.6 branch. The role reads the treatment, the screenplay, the brief, the style bible, and the director's notes, and writes that research down before it designs anything. The brand guide is built only from the research. Titles, title cards, end credits, subtitle styling, a designed poster, and the collateral are built only after the guide is approved. The Art Director still owns the in-film look. Subtitle timing stays with the Post Supervisor. A graphics gate starts closed. The role bills to the Art line. The locked $500 split did not change. The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Phase 8.8 adds one budget per film and the Trailer Editor, on top of the Phase 8.7 branch. The budget lives in `budget.json` in the production folder. One calculator, `tools/budget-calculator/index.html`, shows the whole film, including the trailer when it is on. A film with no budget file keeps the $500 cap and the locked split. Going past the budget still pauses and writes an approval request. Ron can approve that overage without editing the budget. The Trailer Editor is role 20. It runs only when the budget turns the trailer on, it cuts from approved takes, and it bills to Marketing and Distribution. A trailer gate starts closed. The film can deliver without it. The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Phase 8.5, Phase 8.6, Phase 8.7, and Phase 8.8 merged to main on 2026-11-12 in [pull request 12](https://github.com/Roncho512/Movie-swarm/pull/12), merge `67a60f2`.

Phase 8.9 is the first real key test, on its own branch, not merged. The commands in `scripts/` load a repo-root `.env` and do not override variables already set in the shell. They do not print the values. A test shot takes `--model` or `--tier`. The order is the flag, then the tier flag, then the film's budget tier, then the routing file. The picture tiers in that file match the budget rate card. Gemini Omni 1.2 Flash stays the good tier and stays planned, with no fal address. A live call for a model with no endpoint is refused and lists the wired models. It does not switch models. A dry run prints the model, the tier, the provider, the resolution, the duration, the estimated cost, and the money left, and says nothing was sent. The same summary is printed before a `--live` call. `scripts/doctor.py` checks the machine without spending. The guide is [START-HERE.md](START-HERE.md). The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Film facts stay in the production folder. The engine does not know that this film's exhaust is on the right, that the watch is on the left wrist, that the bike is a 1965, that the story is 1967, or that the look is Sergio Leone. Those sentences live in `productions/the-last-marker/`. A different film uses its own files. The pilot sound prompts moved out of the sound program and into `productions/the-last-marker/audio/sound-prompts.json`.

The continuity check on the old pilot shot list found 17 missing locks. Each one is the Triumph shown without the locked exhaust phrase. The new storyboard states the locks. No money was spent.

Older pilot clips of scenes 1 and 2 are still in the production folder. They are not a finished film.

## Run it locally

From the repo root. The longer setup, including the virtual environment and `scripts/doctor.py`, is in [START-HERE.md](START-HERE.md).

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pytest tests -q
python3 scripts/validate-schema.py --production productions/the-last-marker
```

See where The Last Marker stands:

```bash
python3 scripts/line-producer.py --production productions/the-last-marker --run phase-1 status
```

Draft again from the screenplay. This does not approve anything. The draft stays offline unless you pass `--live`. `--offline` is the same default, written out.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline intake
```

Answer the Director. Open `productions/the-last-marker/treatment/questions.json`. Type each answer in the `answer` field. Leave a field as `null` if you are not ready. Then:

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline answer \
  --answers productions/the-last-marker/treatment/questions.json
```

You can also send a separate answers file:

```json
{
  "round": 1,
  "answers": [
    {"id": "q-intent", "answer": "Lock it."}
  ]
}
```

Approve the treatment after you have read `treatment/treatment.md`. This is the only way the treatment becomes approved. It also locks the stage split, which is how the $500 is divided across jobs.

```bash
python3 scripts/line-producer.py --production productions/the-last-marker --run phase-1 approve-gate \
  --stage treatment --decision approved --by ron --note "Lock the treatment and the split."
```

Reject it the same way, with `--decision rejected`. You can put the same fields in a JSON file and pass `--file` instead of the flags.

Write the phase 2 package. These calls do not spend money. They pause until the treatment gate is approved. They do not approve the previs gate.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent prop-master --crew-command lock --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent costume-designer --crew-command lock --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent makeup-hair --crew-command lock --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent cinematographer --crew-command package --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent cinematographer --crew-command boards --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent gaffer --crew-command plan --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent key-grip --crew-command plan --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent stunt-coordinator --crew-command breakdown --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent assistant-director --crew-command schedule --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent vfx-supervisor --crew-command breakdown --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent script-supervisor --crew-command check --estimate 0
```

Wardrobe definitions, when the production has them, live in `wardrobe/costume-definitions.json`. Makeup and hair live in `makeup/makeup-definitions.json`. VFX notes live in `vfx/vfx-needs.json`. A production with none of those files still gets a lock or a breakdown, and the role does not invent a garment, an effect, or a shot.

Approve the package after you have read the files under `props/`, `wardrobe/`, `makeup/`, `continuity/`, `camera/`, `storyboard/`, `lighting/`, `grip/`, `schedule/`, `stunts/`, and `vfx/`.

```bash
python3 scripts/line-producer.py --production productions/the-last-marker --run phase-1 approve-gate \
  --stage previs --decision approved --by ron --note "The phase 2 package can go forward."
```

A picture call does not run until you have approved the treatment, the previs package, and that stage. This example only prices shots with the older production estimator. It does not generate video.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 dispatch \
  --agent production --crew-command estimate --estimate 0 \
  --shot-list productions/the-last-marker/shot-lists/shot-list.json
```

Ask for a generation plan. A generation plan is a dry-run quote: the generator, the clip length, the takes allowed, and the price, set against the locked split. It does not spend, and it does not need the generation gate. This phase proved the command on Harbor Night. It did not write a plan for The Last Marker.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 dispatch \
  --agent production --crew-command plan --estimate 0 \
  --output-dir path/to/a-folder
```

A generate call is the paid path. It pauses until you approve the generation gate. Without `--live`, it still does not call a provider. With `--live`, it can call, and it sends every shot that passes the checks. Use the test shot below when you want exactly one call.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage generation --decision approved --by ron --note "A paid generation may be prepared."
```

Review the takes before the edit. A takes manifest is a JSON file that lists each generated clip or frame and the shot it belongs to. The checklist is `schemas/takes-manifest.schema.json`. This command does not call a vision model and does not spend. If a text file sits beside a frame and has the same name plus `.txt`, that text is the picture description. Tests pass a fake description instead. A required phrase that never appears is a retake. A missing file is a reject.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent dailies --crew-command review --estimate 0 \
  --takes path/to/takes-manifest.json
```

Read `dailies/dailies-report.md`. The VFX review reads that report and the breakdown:

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent vfx-supervisor --crew-command review --estimate 0
```

Then approve the circled takes. Until you do, the editor does not run. The VFX review does not add a gate.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage dailies --decision approved --by ron --note "The circled takes can be cut."
```

Assemble the circled takes. This does not spend. It also waits until you have approved the treatment, the previs package, and the editor's own gate. The shot order comes from the storyboard. A production can set transitions and the runtime tolerance in `edit/editing-style.json`. The default join is a cut.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent editor --crew-command assemble --estimate 0
```

Read `edit/rough-cut.md`. The checklist is `edit/rough-cut.json`. The reading copy is `edit/assembly.edl`. A clean cut also writes `edit/picture-lock.json`. That file is not locked until you approve the edit gate. Sound does not run until you do.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage edit --decision approved --by ron --note "Picture lock."
```

Spot sound and score onto that cut. This does not spend. It also waits until you have approved the treatment, the previs package, and the sound designer's own gate. Prompts come from `audio/sound-prompts.json`. Music comes from `audio/score-brief.json` when that file exists. A prop can carry a sound in the prop file. The cue plays only in shots that show the prop.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent sound-designer --crew-command spot --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent composer --crew-command spot --estimate 0
```

Read `sound/cue-sheet.md`. The checklist is `sound/cue-sheet.json`. When ffmpeg is installed, placeholder stems land in `sound/stems/`. A generate call is the paid path. It pauses until you approve the generation gate. Without `--live`, it does not call ElevenLabs. The rate card has no audio price, so a live sound call also needs `--price-override` and your approval of that one amount.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage sound --decision approved --by ron --note "Color and mix can start."
```

Grade the locked picture and mix the stems. Both calls wait until the edit gate and the sound gate are approved. They do not spend. The grade is read from `look/look.json`. Scene adjustments, a LUT, and the consistency tolerance come from `look/grade.json` when that file exists. A LUT is a color lookup table, a file the production can supply. The mix is read from `sound/cue-sheet.json` and the stems. Loudness uses EBU R128 unless `audio/mix-targets.json` sets another target.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent colorist --crew-command grade --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent mixer --crew-command mix --estimate 0
```

Read `color/grade-plan.md` and `color/mix-plan.md`. The checklists are `color/grade-plan.json` and `color/mix-plan.json`. When ffmpeg is installed, the graded picture is `color/graded-preview.mp4`, the mix is `color/mix.wav`, and the married preview is `color/married-preview.mp4`. Final delivery does not run until you approve the color-mix gate.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage color-mix --decision approved --by ron --note "Final delivery can start."
```

Package the locked cut. This does not spend. The sizes, the variants, the poster shot, and the caption mode come from `delivery/delivery-spec.json`. When that file leaves a field out, the plan uses a cited platform default and says so. Captions are built from the dialogue cues. When ffmpeg is installed, it renders the master, the variants, and the poster. When it is not, the plan and the caption sidecars are still written. QC then checks each file. The manifest is the package list.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent post-supervisor --crew-command deliver --estimate 0
```

Read `delivery/delivery-plan.md`, `delivery/qc-report.md`, and `delivery/delivery-manifest.md`. Approve the delivery gate to mark the film delivered.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage delivery --decision approved --by ron --note "The film is delivered."
```

The same commands work from the agent folders as `python3 -m src.cli`, with the same flags.

## How to make a film with the studio

This is the path from a treatment to a delivered file. A gate is a switch that makes a stage wait for Ron. The studio command stops at the first closed gate. Approve that gate, then run the command again. It does not approve anything by itself, and it does not spend.

Practice on Harbor Night. It is the synthetic fixture under `tests/fixtures/harbor-night`. Copy it if you do not want to write into the fixture:

```bash
cp -a tests/fixtures/harbor-night /tmp/harbor-night
python3 scripts/studio.py --production /tmp/harbor-night --run studio-1
```

The first run stops at the treatment gate. Nothing after that is written yet. Approve the gate, then run the same command again:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run studio-1 approve-gate \
  --stage treatment --decision approved --by ron --note "Lock the treatment and the split."
python3 scripts/studio.py --production /tmp/harbor-night --run studio-1
```

Keep going. Each run stops at the next closed gate and tells you the name. The order is:

1. `treatment`. Read `treatment/treatment.md`. Approving it locks the $500 split.
2. `previs`. The prop lock, wardrobe, makeup, the continuity check, the camera package, the storyboard, the lighting plan, the grip plan, the shooting schedule, the action breakdown, the VFX breakdown, and the title research and draft brand guide are written first. Then you approve them.
3. `graphics`. Read `graphics/brand-guide.md`. Approving this gate lets the titles, the credits, the key art, and the collateral be specced.
4. `production`. This lets the generation quote be written. It does not open a paid call.
5. `dailies`. If the production has no takes manifest, the offline run writes synthetic placeholder clips and says so in `takes/placeholder.txt`. Those are not generated pictures. A real takes file is left alone. The VFX review is written with the dailies report.
6. `editor`. This lets the circled takes be cut. Title and credit overlays are in the reading copy when the graphics package exists.
7. `edit`. That approval is picture lock. Read `edit/rough-cut.md` first.
8. `sound-designer`. This lets the cue sheet be spotted.
9. `sound`. Read `sound/cue-sheet.md`. Color and mix wait on this approval.
10. `color-mix`. The grade and the mix are written first. Read `color/grade-plan.md` and `color/mix-plan.md`.
11. `delivery`. The package is written first. The manifest lists graphics files when they are present. The frame-grab poster stays `poster.png`. The designed poster is `key-art-poster.png`. Read the QC report and the manifest. Approving this gate marks the film delivered.

The generation gate is not in that list. Leave it closed until you are ready to pay for pictures. The studio command never passes `--live`. Harbor Night's offline run spends $0.00.

A real production is the same two commands, with that film's folder instead of `/tmp/harbor-night`. If it has no treatment yet, draft one first with `scripts/director.py` and the `intake` command, answer the questions, and then start the studio command. Do not run this path on The Last Marker until the first-film phase. Its approved previs stays where it is.

The delivery spec is `delivery/delivery-spec.json` in the production folder. Harbor Night's spec asks for a small H.264 master, a 16:9 web file, a 9:16 center crop, sidecar captions, and a poster from shot `s01-sh01`. A different film puts its own sizes in that file. The package is written under `delivery/` inside the production folder unless you set a drive. Set `MOVIE_SWARM_ASSET_ROOT`, or set `asset_root` in `config/assets.json`. The code does not name a drive.

When ffmpeg is installed, the package can include `master.mp4` (or a ProRes master when the spec asks and the encoder exists), the variant files, `poster.png`, `captions.srt`, and `captions.vtt`. When ffmpeg is missing, those picture files are skipped and the plan, the captions, the QC report, and the manifest are still written.

Tests can call `run_studio(..., auto_approve=True)`. That is a test harness. It records the approver as `test-auto-approve`, not as Ron, and it still leaves the generation gate closed. `scripts/studio.py` and the Director's `studio` command do not pass that flag. Do not use it on a real film.

## One live test shot

A test shot is one picture call for one shot. It does not send anything unless you pass `--live`. The commands in `scripts/` load `.env` from the repo root. A variable already set in the shell wins. The values are not printed. `.env.example` lists the names with empty values. `.env` is ignored by git. Doctor says whether each key is present. It prints yes or no.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run studio-1 test-shot \
  --shot s01-sh01 --model seedance-2.0-fast
```

That prints the quote and does not call a provider. Seedance 2.0 fast at 720p is the cheapest picture model with a fal address. `--tier better` names the same model. To send the one call, all of these have to be true:

1. You approved the generation gate on that run.
2. The estimate fits the money left on the Production line ($270 in the locked split) and under the $500 cap.
3. `FAL_KEY` is set in the environment.
4. You pass `--live`.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run studio-1 --live test-shot \
  --shot s01-sh01 --model seedance-2.0-fast
```

The same quote is printed before that call. The good tier, and the preview purpose in the routing file, is still Gemini Omni 1.2 Flash. The rate card has its price and does not have a fal address for it, so a live call for it is refused and lists the wired models. It does not switch to another model. Seedance 2.0 and Seedance 2.0 fast are the picture models with a fal address. Do not pass `--live` until you mean to spend.

The estimate is written on the ledger before the call. The provider's own price, when it reports one, replaces that estimate after the call. If the rate card has no price, the call is refused. `--price-override 0.25` writes an approval request for that one amount. The call waits until you approve the request. It does not invent a price.

Run the same command again and it uses the saved file. It does not call the provider again and it does not charge again. A failure leaves the run waiting at the current stage. It does not skip ahead.

Text calls use `ANTHROPIC_API_KEY`. Sound calls use `ELEVENLABS_API_KEY`. The Director stays offline unless you pass `--live` on `scripts/director.py`. The rate card has no text price and no audio price, so those live calls need a price override. Downloaded files go under `MOVIE_SWARM_ASSET_ROOT` when that is set, otherwise under `asset_root` in `config/assets.json`, otherwise in the production folder. `asset_root` is still null. No drive path is written in the code.

## What the checks do

`python3 -m pytest tests -q` runs the shared checks. They cover the Phase 0 foundation, the Phase 1 rules, the Phase 2 package, the Phase 3 quote, the Phase 4 dailies review, the Phase 5 edit, the Phase 6 cue sheet, the Phase 7 grade and mix, the Phase 8 delivery package, and the Phase 8.5 provider gate: the cap, approvals, the treatment checklist, each screenplay format, the question round trip, a crew call that must pass the Line Producer first, locked props, a continuity check, a camera package, storyboards, an action breakdown, a dry-run generation plan, the generation gate, a prompt that keeps a locked phrase, a circled take, a forbidden prop phrase, a missing file, a shot-list mismatch, the dailies report checklist, the dailies gate in front of the editor, storyboard order, a missing-coverage blocker, a runtime trim, the edit decision list checklist, a locked prop that breaks across a cut, the edit gate in front of sound, cues inside the cut, a sync tolerance flag, a prop sound outside the frame, a paid sound call refused while the generation gate is closed, the Sound line on the rate card, a grade read from the look, a scene grade stated once, a color mismatch between adjacent shots, dialogue ducking, a loudness miss, the color-mix gate in front of final delivery, a delivery spec read from the production, caption timing, a QC pass, a forced QC fail, a manifest with checksums and spend, the delivery gate, a studio run that stops at each gate unless a test harness approves them, an offline default, a closed generation gate, a missing key, an over-budget call, an unknown price, a ledger estimate and a reported actual, a re-run that does not charge again, a retry and a timeout, a key that never appears in the saved output, a shooting schedule, a lighting plan, a grip plan, locked wardrobe, locked makeup, a VFX breakdown, wardrobe and makeup drift, a studio run that still stops at each gate, research before the brand guide, an approved guide before any graphic, a guide rule that traces to research, a TITLE CARD picked up from the screenplay, end credits taken from the Line Producer record, graphics listed on the delivery manifest, and the frame-grab poster left as poster.png. The provider tests use a fake HTTP transport. They do not open a network connection. Phase 8.9 checks the `.env` loader, the test-shot model and tier, the quote printed before a call, the doctor report, and the readable treatment written before the treatment gate. One fixture is The Last Marker. Another is Harbor Night, a tiny second film, so the engine is not proven only on this one. Phase 3 through Phase 8.5 picture, sound, delivery, and provider checks use Harbor Night. The provider checks do not call The Last Marker.

Three older agents have their own checks, because each one uses a folder named `src`:

```bash
python3 -m pytest agents/05-production/tests -q
python3 -m pytest agents/06-sound-designer/tests -q
python3 -m pytest agents/08-qa/tests -q
```

`python3 scripts/validate-schema.py --production productions/the-last-marker` checks every JSON file in the production against its checklist. A checklist is a schema: a list of required fields. Files that fail are named. A few older pilot files are on a known-mismatch list. They are reported and do not fail the run. A new file that fails does stop the command.

GitHub runs these checks on every push and every pull request. See `.github/workflows/ci.yml`.

## Settings

Environment variables, by name only. Do not commit a key.

| Name | Used for |
|---|---|
| `ANTHROPIC_API_KEY` | Text calls for the Director and the Line Producer. Read only when you pass `--live`. The value is never written down. `scripts/` loads it from `.env` when the shell has not set it. |
| `MOVIE_SWARM_ASSET_ROOT` | Optional folder for downloaded media and the delivery package. Overrides the file below. |
| `FAL_KEY` | Picture calls on fal. Read only when you pass `--live`. |
| `ELEVENLABS_API_KEY` | Sound calls on ElevenLabs. Read only when you pass `--live`. The key needs the Voices: Read permission for the voice list. |

Config files in `config/`:

| File | What it controls |
|---|---|
| `gates.json` | The $500 film cap, and one on/off switch per stage. On means Ron reviews that stage. Every switch starts on. |
| `model-routing.json` | Which model each role uses. Change the file, not the code. |
| `assets.json` | Where finished media lives. `null` keeps files in the production folder. |

## Sample data

The sample film is The Last Marker, in `productions/the-last-marker/`.

| File | What it is |
|---|---|
| `screenplay/Pilot_-_the_last_marker_screenplay.md` | The shooting script. |
| `production-brief.json` | Ron's locked choices: $500, Baja California, 1967, the Leone look, the two hero props. Exhaust on the right. Watch on the left wrist. |
| `treatment/treatment.md` | The approved treatment. |
| `treatment/treatment.json` | The same treatment in the form the checks can read. Status: approved. |
| `treatment/questions.json` | Round 1, closed. Ron's answers are in the file. |
| `runs/phase-1/` | The run record. Treatment gate approved. Previs gate approved. Generation gate not approved. Stage split locked. Spent $0.00 of $500.00. |
| `props/prop-definitions.json` | The locked attributes for this film, written as production data. |
| `props/hero-props.json` | The same lock, after the Prop Master copies it. |
| `look/look.json` | This film's lenses, framing, and lighting. |
| `camera/camera-package.json` | The Cinematographer's package, copied from that look. |
| `storyboard/` | One beat per shot, the look stated once, and an animatic. No images were generated. Shots that show the featured watch are listed, each with one sentence on why. Scene 3 also has the empty canteen, the circling buzzards, and the hard cut from a buzzard's face to his eyes. |
| `continuity/continuity-check.json` | Drift findings. The old pilot shot list is missing the locked exhaust phrase. |
| `stunts/action-breakdown.json` | The treatment's two action beats, broken into shots. |
| `audio/sound-prompts.json` | The pilot sound prompts. The sound program reads this file. It does not keep a copy. |

Hero props for this film are the 1965 Triumph TR6SC and the Breitling Top Time. Ron locked the exhaust on the right and the watch on the left wrist. Those sentences are in the production files above. They are not in the studio code.

## Where to read more

- [ARCHITECTURE.md](ARCHITECTURE.md) — how the pieces fit, and what each coded role reads and writes.
- [ROADMAP.md](ROADMAP.md) — phases, gates, and what is next.
- [DECISIONS.md](DECISIONS.md) — choices already made.
- [CONTRIBUTING.md](CONTRIBUTING.md) — how a pull request should read, and the doc rule.
- [docs/perfect-treatment.md](docs/perfect-treatment.md) — what a good treatment contains, with a short Last Marker example for each field.
- [docs/treatment-template.md](docs/treatment-template.md) — a blank treatment you can fill in.
