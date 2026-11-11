# Movie Swarm

Movie Swarm turns a screenplay into a finished short film. Specialized helpers, called agents, do the steps. Ron is the executive producer. He reviews the work and decides what is allowed to spend money.

## Current status

Phase 0 is on main. It merged on 2026-11-10 in [pull request 1](https://github.com/Roncho512/Movie-swarm/pull/1), merge `c369689`. Phase 0 is the shared checklist, the run record, the review gates, and the $500 cap.

Phase 1 is on main. It merged on 2026-11-10 in [pull request 3](https://github.com/Roncho512/Movie-swarm/pull/3), merge `da9d54a`. The Line Producer watches the budget, the schedule, the credits, and the gates. The Director reads a screenplay and writes a treatment, which is the plan for the film before anyone generates a shot. Ron approved the Last Marker treatment gate. The $500 stage split is locked on run phase-1. Spent so far: $0.00 of $500.00.

Phase 2 is on main. It merged on 2026-11-10 in [pull request 4](https://github.com/Roncho512/Movie-swarm/pull/4) and [pull request 5](https://github.com/Roncho512/Movie-swarm/pull/5), merge `f6f52d4`. The storyboard is one beat per shot: 41 shots, plus the three scene 3 shots Ron added, 44 in all. Ron approved the previs gate. The note is "Approve the storyboard previs gate." No images were generated.

Phase 3 is on main. It merged on 2026-11-10 in [pull request 6](https://github.com/Roncho512/Movie-swarm/pull/6), merge `1355ad4`. The studio can quote any production, put locked prop phrases into a prompt, and refuse a paid call until Ron approves a gate called `generation`. A gate is a switch that makes a stage wait for Ron. That build does not call a provider. The generation gate on The Last Marker is still closed. Spent so far: $0.00 of $500.00.

Phase 4 is in review. After generation, every take is reviewed before it can be cut. A take is one generated clip or frame for a shot. The Dailies Reviewer circles a take that passes, sends a bad one back as a retake, or rejects a file that is missing. The proof is Harbor Night, under `tests/fixtures/`, plus tiny frames made in the tests. Harbor Night is a synthetic production, not The Last Marker. The review does not call a paid model. A retake is an estimate against the fix-loop line, and nothing is charged. The editor waits until Ron approves the `dailies` gate. Making The Last Marker is still the last phase.

Phase 5 is in review. It is built on the Phase 4 branch, which is not merged. Ron merges Phase 4 first. The Editor assembles the circled takes into a rough cut. An edit decision list is the cut: which take, where it starts and ends, and how it joins the next shot. JSON is the source of truth. A CMX3600 file is a reading copy of the same cut. The editor trims toward the runtime in the production brief and does not invent a shot. A shot with no circled take is a blocker sent back to dailies or generation. Locked props are checked across adjacent cuts. When ffmpeg is installed, a small preview is rendered. When it is not, the edit decision list is still written. Ron approves a new `edit` gate before sound. That approval is picture lock. The proof is Harbor Night plus tiny synthetic clips. Nothing was spent. The Last Marker was not cut.

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

The same commands work from the agent folders as `python3 -m src.cli`, with the same flags.

## What the checks do

`python3 -m pytest tests -q` runs the shared checks. They cover the Phase 0 foundation, the Phase 1 rules, the Phase 2 package, the Phase 3 quote, the Phase 4 dailies review, and the Phase 5 edit: the cap, approvals, the treatment checklist, each screenplay format, the question round trip, a crew call that must pass the Line Producer first, locked props, a continuity check, a camera package, storyboards, an action breakdown, a dry-run generation plan, the generation gate, a prompt that keeps a locked phrase, a circled take, a forbidden prop phrase, a missing file, a shot-list mismatch, the dailies report checklist, the dailies gate in front of the editor, storyboard order, a missing-coverage blocker, a runtime trim, the edit decision list checklist, a locked prop that breaks across a cut, and the edit gate in front of sound. One fixture is The Last Marker. Another is Harbor Night, a tiny second film, so the engine is not proven only on this one. Phase 3, Phase 4, and Phase 5 picture checks use Harbor Night.

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
