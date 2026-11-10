# Movie Swarm

Movie Swarm turns a screenplay into a finished short film. Specialized helpers, called agents, do the steps. Ron is the executive producer. He reviews the work and decides what is allowed to spend money.

## Current status

Phase 0 is on main. It merged on 2026-11-10 in [pull request 1](https://github.com/Roncho512/Movie-swarm/pull/1), merge `c3696890`. Phase 0 is the shared checklist, the run record, the review gates, and the $500 cap.

Phase 1 adds two roles. The Line Producer watches the budget, the schedule, the credits, and the gates. The Director reads a screenplay and writes a treatment, which is the plan for the film before anyone generates a shot. The Director asks Ron questions in a file. Ron answers in a file. The Director cannot approve its own work.

The Last Marker has a draft treatment. It is not approved. Spent so far on this run: $0.00 of $500.00. The film is set in 1967. The Triumph stays a 1965.

Older pilot files are still in the production folder. Scenes 1 and 2 were cut and reviewed before this phase. Those clips are not a finished film.

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

A crew call does not run until you have approved the treatment and that stage. This example only prices shots. It does not generate video. It will pause until those gates are approved.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 dispatch \
  --agent production --crew-command estimate --estimate 0 \
  --shot-list productions/the-last-marker/shot-lists/shot-list.json
```

The same commands work from the agent folders as `python3 -m src.cli`, with the same flags.

## What the checks do

`python3 -m pytest tests -q` runs the shared checks. They cover the Phase 0 foundation and the Phase 1 rules: the cap, approvals, the treatment checklist, each screenplay format, the question round trip, and a crew call that must pass the Line Producer first.

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
| `production-brief.json` | Ron's locked choices: $500, Baja California, 1967, the Leone look, the two hero props. Sidedness is still open. |
| `treatment/treatment.md` | The readable draft. Not approved. |
| `treatment/treatment.json` | The same draft in the form the checks can read. |
| `treatment/questions.json` | Eight questions for Ron. Answers are empty. |
| `runs/phase-1/` | The run record. Stage: treatment. Waiting on Ron. |

Hero props are the 1965 Triumph TR6SC and the Breitling Top Time. The screenplay currently says the exhaust is on the right and the watch is on the left wrist. Ron has not locked either side.

## Where to read more

- [ARCHITECTURE.md](ARCHITECTURE.md) — how the pieces fit, and what each coded role reads and writes.
- [ROADMAP.md](ROADMAP.md) — phases, gates, and what is next.
- [DECISIONS.md](DECISIONS.md) — choices already made.
- [CONTRIBUTING.md](CONTRIBUTING.md) — how a pull request should read, and the doc rule.
- [docs/perfect-treatment.md](docs/perfect-treatment.md) — what a good treatment contains, with a short Last Marker example for each field.
- [docs/treatment-template.md](docs/treatment-template.md) — a blank treatment you can fill in.
