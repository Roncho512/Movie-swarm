Archived copy. The working film lives in the films folder; see START-HERE.

# The Last Marker

Pilot production. 3-minute short film. AI Studio proof of concept.

The first film starts from the top. D41 is lifted for this folder only. The live treatment is a draft. Run `first-film-1` is waiting at the treatment gate. Spent $0.00.

## Start from the top

Intake refuses to draft again when `treatment/treatment.json` says approved. The message is: the treatment is already approved, and the Director will not write over Ron's approval. It also refuses when the current question round already has answers. Those records are in `archive/`. See `archive/README.md`.

The live files are inputs, not an approved gate:

- The screenplay is `screenplay/Pilot_-_the_last_marker_screenplay.md`. The story year is 1967. The Triumph stays a 1965.
- Prop locks are `props/prop-definitions.json` and `props/hero-props.json`. Exhaust is on the right. The watch is on the left wrist.
- The look is `look/look.json`. The style bible is `visual-style-bible.json`.
- Ron's locked answers are in `treatment/inputs.json`. Theme, tone, and references are locked. Miguel wants to finish the race, but water and life matter more. Withhold whether the canyon really has water. The action beats are approved.

Intake reads `treatment/inputs.json`, merges those facts into the draft, and leaves the gate closed. `budget.json` is the quote. The trailer is on, contingency is 10 percent, and the picture tier is better. Those three are proposed, Ron to confirm. Best is the upgrade.

From the repo root, with the machine's Python (the key-test venv is one example):

```bash
python3 scripts/studio.py --production productions/the-last-marker --run first-film-1
python3 scripts/line-producer.py --production productions/the-last-marker --run first-film-1 budget
```

Exit status 2 means the studio is waiting. Read `treatment/treatment.md`, then approve the treatment gate when the draft is right. This folder's offline run already stopped there. Nothing was spent.

## Concept

A solo motorcycle racer crosses the Baja desert in 1967. His bike is failing. He is lost. He finds a trail marker left by a rider who came before him. The marker points two directions. He has to choose.

Three minutes. Almost no dialogue. Pure visual storytelling.

## Key Specs

| | |
|---|---|
| **Runtime** | 3 minutes |
| **Scenes** | 4 |
| **Dialogue** | 1 line (5 words, Spanish) |
| **Aspect Ratio** | 2.39:1 Anamorphic |
| **Visual Style** | 16mm Ektachrome, 1967 |
| **Cuts** | ~18-22 |

## Characters

- **Miguel Vega** — 30, Mexican, ranch hand from outside Tecate. Rides a 1965 Triumph TR6SC Trophy.

## Key Props

- **Breitling Top Time** — Black reverse panda dial, worn brown leather rally strap. Visible in 3 shots across 3 scenes (4 seconds total, 2.2% of runtime).

## Directory Structure

```
the-last-marker/
├── screenplay/            # Source screenplay (markdown)
├── scene-manifest/        # Structured scene manifest (JSON)
├── visual-assets/
│   ├── character-refs/    # Miguel Vega reference sheets
│   ├── environment-refs/  # Desert landscapes at 4 light conditions
│   ├── prop-refs/         # Breitling Top Time reference
│   └── style-frames/     # Overall visual style reference
├── shot-lists/            # Shot list with generation prompts (JSON)
├── clips/
│   ├── raw/              # All generated clips
│   ├── selected/         # Best clip per shot
│   └── upscaled/         # 4K upscaled versions
├── audio/
│   ├── dialogue/         # "Primero llegas. Despues compites."
│   ├── sfx/              # Engine sounds, mechanical sounds
│   ├── ambience/         # Desert wind, sand, silence
│   ├── score/            # Guitar phrase
│   └── mix/              # Final mixed audio
├── edit/
│   ├── assembly/         # Timeline assembly files
│   ├── color-grade/      # Color graded versions
│   └── export/           # Final exports
└── qa-reports/           # Continuity reports
```

## Pipeline Status

- [x] Screenplay written
- [ ] Scene manifest generated
- [ ] Production brief created
- [ ] Character refs generated
- [ ] Vehicle refs generated
- [ ] Prop refs generated
- [ ] Environment refs generated
- [ ] Style bible completed
- [ ] Shot list created
- [ ] Clips generated
- [ ] Audio produced
- [ ] Assembly completed
- [ ] QA passed
- [ ] Final export
