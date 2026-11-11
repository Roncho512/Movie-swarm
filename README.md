# Movie Swarm

Movie Swarm turns a screenplay into a finished short film. Specialized helpers, called agents, do the steps. Ron is the executive producer. He reviews the work and decides what is allowed to spend money.

## Current status

Phase 0 is on main. It merged on 2026-11-10 in [pull request 1](https://github.com/Roncho512/Movie-swarm/pull/1), merge `c369689`. Phase 0 is the shared checklist, the run record, the review gates, and the $500 cap.

Phase 1 is on main. It merged on 2026-11-10 in [pull request 3](https://github.com/Roncho512/Movie-swarm/pull/3), merge `da9d54a`. The Line Producer watches the budget, the schedule, the credits, and the gates. The Director reads a screenplay and writes a treatment, which is the plan for the film before anyone generates a shot. Ron approved the Last Marker treatment gate. The $500 stage split is locked on run phase-1. Spent so far: $0.00 of $500.00.

Phase 2 is on main. It merged on 2026-11-10 in [pull request 4](https://github.com/Roncho512/Movie-swarm/pull/4) and [pull request 5](https://github.com/Roncho512/Movie-swarm/pull/5), merge `f6f52d4`. The storyboard is one beat per shot: 41 shots, plus the three scene 3 shots Ron added, 44 in all. Ron approved the previs gate. The note is "Approve the storyboard previs gate." No images were generated.

Phase 3 is on main. It merged on 2026-11-10 in [pull request 6](https://github.com/Roncho512/Movie-swarm/pull/6), merge `1355ad4`. The studio can quote any production, put locked prop phrases into a prompt, and refuse a paid call until Ron approves a gate called `generation`. A gate is a switch that makes a stage wait for Ron. That build does not call a provider. The generation gate on The Last Marker is still closed. Spent so far: $0.00 of $500.00.

Phase 4 is on main. It merged on 2026-11-11 in [pull request 7](https://github.com/Roncho512/Movie-swarm/pull/7), merge `c0de548`. After generation, every take is reviewed before it can be cut. A take is one generated clip or frame for a shot. The Dailies Reviewer circles a take that passes, sends a bad one back as a retake, or rejects a file that is missing. The proof is Harbor Night, under `tests/fixtures/`, plus tiny frames made in the tests. Harbor Night is a synthetic production, not The Last Marker. The review does not call a paid model. A retake is an estimate against the fix-loop line, and nothing is charged. The editor waits until Ron approves the `dailies` gate. Making The Last Marker is still the last phase.

Phase 5 is on main. It merged on 2026-11-11 in [pull request 8](https://github.com/Roncho512/Movie-swarm/pull/8), merge `683e4c5`. The Editor assembles the circled takes into a rough cut. An edit decision list is the cut: which take, where it starts and ends, and how it joins the next shot. JSON is the source of truth. A CMX3600 file is a reading copy of the same cut. The editor trims toward the runtime in the production brief and does not invent a shot. A shot with no circled take is a blocker sent back to dailies or generation. Locked props are checked across adjacent cuts. When ffmpeg is installed, a small preview is rendered. When it is not, the edit decision list is still written. Ron approves an `edit` gate before sound. That approval is picture lock. The proof is Harbor Night plus tiny synthetic clips. Nothing was spent. The Last Marker was not cut.

Phase 6 is on main. It merged on 2026-11-11 in [pull request 9](https://github.com/Roncho512/Movie-swarm/pull/9), merge `8d0de69`. After picture lock, the Sound Designer and the Composer spot a cue sheet onto the cut: dialogue, sound effects, foley, ambience, and music. Each cue has a start and end, the shots it belongs to, a prompt, and a source of generated, library, or silence. Music follows `audio/score-brief.json` when the production has one, including the shots that brief leaves silent. A cue has to sit inside the cut. An effect tied to a shot is flagged when it lands outside a short sync tolerance. A prop sound is flagged when that prop is not in the shot. The plan is priced from the rate card against the Sound line. That card has no audio rate, so the price is marked unknown. A paid call waits on the generation gate. When ffmpeg is installed, placeholder stems and a temp mix are rendered. When it is not, the cue sheet is still written. Ron approves a `sound` gate before color and mix. The proof is Harbor Night plus tiny synthetic audio. Nothing was spent. The Last Marker was not spotted.

Phase 7 is in review. After the edit gate and the sound gate are both approved, the Colorist grades the locked picture and the Re-recording Mixer mixes the stems. A grade plan is the color: one base grade for the whole cut, plus one adjustment per scene, read from `look/look.json` and from `look/grade.json` when the production has one. A mix plan is the sound: a level for each stem, dialogue in front, music and effects ducked under dialogue, and a fade at each scene change. Loudness is checked against EBU R128, or against `audio/mix-targets.json` when the production sets its own target. EBU R128 is a published delivery standard: -23.0 LUFS, true peak no higher than -1.0 dBTP. The rate card has no color or mix price, so that estimate is marked unknown and is not stored as zero. When ffmpeg is installed, it renders a low-resolution graded preview, the mix, and a married preview of picture plus sound. When it is not, the plans are still written. Ron approves a `color-mix` gate before final delivery. The proof is Harbor Night plus tiny synthetic video and audio. Nothing was spent. The Last Marker was not graded or mixed.

Film facts stay in the production folder. The engine does not know that this film's exhaust is on the right, that the watch is on the left wrist, that the bike is a 1965, that the story is 1967, or that the look is Sergio Leone. Those sentences live in `productions/the-last-marker/`. A different film uses its own files. The pilot sound prompts moved out of the sound program and into `productions/the-last-marker/audio/sound-prompts.json`.

The continuity check on the old pilot shot list found 17 missing locks. Each one is the Triumph shown without the locked exhaust phrase. The new storyboard states the locks. No money was spent.

Older pilot clips of scenes 1 and 2 are still in the production folder. They are not a finished film.

## Run it locally

From the repo root:

```bash
pip3 install -r requirements.txt
python3 -m pytest tests -q
python3 scripts/validate-schema.py --production productions/the-last-marker
```

See where The Last Marker stands:

```bash
python3 scripts/line-producer.py --production productions/the-last-marker --run phase-1 status
```

Draft again from the screenplay. This does not approve anything. `--offline` skips the model even if a key is set.

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
  --agent cinematographer --crew-command package --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent cinematographer --crew-command boards --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent script-supervisor --crew-command check --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent stunt-coordinator --crew-command breakdown --estimate 0
```

Approve the package after you have read the files under `props/`, `continuity/`, `camera/`, `storyboard/`, and `stunts/`.

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

A generate call is the paid path. It pauses until you approve the generation gate. Even after that approval, this build's client does not call a provider.

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

Read `dailies/dailies-report.md`. Then approve the circled takes. Until you do, the editor does not run.

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

Read `sound/cue-sheet.md`. The checklist is `sound/cue-sheet.json`. When ffmpeg is installed, placeholder stems land in `sound/stems/`. A generate call is the paid path. It pauses until you approve the generation gate. This build's client does not call a provider.

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

The same commands work from the agent folders as `python3 -m src.cli`, with the same flags.

## What the checks do

`python3 -m pytest tests -q` runs the shared checks. They cover the Phase 0 foundation, the Phase 1 rules, the Phase 2 package, the Phase 3 quote, the Phase 4 dailies review, the Phase 5 edit, the Phase 6 cue sheet, and the Phase 7 grade and mix: the cap, approvals, the treatment checklist, each screenplay format, the question round trip, a crew call that must pass the Line Producer first, locked props, a continuity check, a camera package, storyboards, an action breakdown, a dry-run generation plan, the generation gate, a prompt that keeps a locked phrase, a circled take, a forbidden prop phrase, a missing file, a shot-list mismatch, the dailies report checklist, the dailies gate in front of the editor, storyboard order, a missing-coverage blocker, a runtime trim, the edit decision list checklist, a locked prop that breaks across a cut, the edit gate in front of sound, cues inside the cut, a sync tolerance flag, a prop sound outside the frame, a paid sound call refused while the generation gate is closed, the Sound line on the rate card, a grade read from the look, a scene grade stated once, a color mismatch between adjacent shots, dialogue ducking, a loudness miss, and the color-mix gate in front of final delivery. One fixture is The Last Marker. Another is Harbor Night, a tiny second film, so the engine is not proven only on this one. Phase 3, Phase 4, Phase 5, Phase 6, and Phase 7 picture and sound checks use Harbor Night.

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
| `ANTHROPIC_API_KEY` | The Director and the Line Producer, when you want a real model. Without it, the draft is offline and labeled that way. |
| `MOVIE_SWARM_ASSET_ROOT` | Optional folder for finished media. Overrides the file below. |
| `FAL_KEY` | The production agent, when it really generates video. This phase does not do that. |
| `ELEVENLABS_API_KEY` | The sound agent, when it really generates audio. This phase does not do that. |

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
