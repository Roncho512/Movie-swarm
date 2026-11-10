# The Last Marker

Pilot production. 3-minute short film. AI Studio proof of concept.

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
