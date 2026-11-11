# Schemas

Every agent handoff in the pipeline is defined by a JSON schema. No free-form handoffs. If data flows between agents, it flows through a schema.

## Why This Matters

When you're debugging why Shot 14 has the wrong lighting, you need to trace the data backward: Editor received clip metadata → Production generated against a shot list prompt → Cinematographer wrote that prompt based on the scene manifest → Screenwriter parsed that from the screenplay. Schemas make every link in that chain inspectable and validatable.

## Schema Map

```
                    ┌─────────────────────┐
                    │  production-brief    │  (Human / Signal Platform → Orchestrator)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   scene-manifest     │  (Screenwriter → All Agents)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ visual-style-bible   │  (Art Director → Cinematographer, Production, QA)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     shot-list        │  (Cinematographer → Production, Editor)
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
   ┌──────────▼──────┐  ┌─────▼──────┐  ┌──────▼──────────┐
   │  clip-metadata   │  │audio-manif.│  │continuity-report│
   │ (Prod → Ed, QA)  │  │(Sound→Ed)  │  │  (QA → Orch)    │
   └─────────────────┘  └────────────┘  └─────────────────┘
```

## Files

| Schema | Description |
|---|---|
| `production-brief.schema.json` | Entry point. Everything the orchestrator needs to start. |
| `scene-manifest.schema.json` | The central document. Structured screenplay with every scene, shot suggestion, dialogue extraction, color note, and sound note indexed. |
| `visual-style-bible.schema.json` | Visual consistency anchor. Character refs, environment refs, prop refs, color system, lighting rules. |
| `shot-list.schema.json` | Every shot in the film with generation prompts, tool routing, reference assets, and continuity notes. |
| `clip-metadata.schema.json` | Every generated clip with technical specs, validation results, cost tracking, and selection status. |
| `audio-manifest.schema.json` | All audio assets organized by layer: dialogue, SFX, ambience, score, engine sound. Time-coded for assembly. |
| `sound-prompts.schema.json` | The prompts a production asks the sound program to generate. The program does not keep its own copy. |
| `takes-manifest.schema.json` | Generated takes for one production. Each take names a shot and a clip or frame file. |
| `dailies-report.schema.json` | Circle, retake, or reject for each take, plus the retake list and its estimate. |
| `edit-decision-list.schema.json` | The Editor's cut. Ordered circled takes, source in and out, transitions, and scene markers. JSON is the source of truth. |
| `cue-sheet.schema.json` | The Sound Designer and the Composer's cues, timed to the locked cut. |
| `score-brief.schema.json` | One production's music plan: tempo, instrumentation, motifs, and the shots that stay silent. |
| `grade.schema.json` | One production's grade: scene and shot adjustments, an optional LUT, and the consistency tolerance. |
| `grade-plan.schema.json` | The Colorist's grade. A base for the whole cut, and one adjustment per scene. |
| `mix-targets.schema.json` | One production's stem levels and loudness target. Optional. EBU R128 is the default. |
| `mix-plan.schema.json` | The Re-recording Mixer's levels, dialogue ducking, scene fades, and loudness check. |
| `delivery-spec.schema.json` | One production's delivery request: master size, variants, poster shot, captions, and QC tolerances. |
| `delivery-plan.schema.json` | The Post Supervisor's plan. Sizes come from the spec, or from a cited platform default. |
| `qc-report.schema.json` | Pass, fail, or skipped for each delivery check. |
| `delivery-manifest.schema.json` | Files, SHA-256 checksums, spend against the cap, the stage split, and every gate record. |
| `continuity-report.schema.json` | QA findings with issue routing. Drives the feedback loop. |
| `run-state.schema.json` | One production run: stage, status, artifacts, and spend against the cap. |
| `gate-config.schema.json` | Review switches and the film budget cap. |
| `model-routing.schema.json` | Which generator each role uses, plus optional per-shot overrides. |
| `asset-config.schema.json` | Where finished media lives. Null keeps the current in-repo paths. |
| `treatment.schema.json` | The Director's plan. Draft until the Line Producer records Ron's approval. |
| `director-questions.schema.json` | One round of questions for Ron. Answers live in the file. |
| `line-producer-record.schema.json` | Ledger, stage split, credits, schedule, and Ron's decisions for one run. |
| `hero-props.schema.json` | Locked hero props. The attributes are whatever the production defined. |
| `continuity-check.schema.json` | Script Supervisor findings before a shot is generated. |
| `look.schema.json` | The look one production chose: lenses, framing, lighting, palette. |
| `camera-package.schema.json` | The Cinematographer's package, copied from that look. |
| `storyboard.schema.json` | Board prompts and an animatic plan. Images can be left ungenerated. |
| `action-breakdown.schema.json` | Shot-by-shot action breakdown from the treatment's beats. |
| `costume-lock.schema.json` | Locked wardrobe: garment, color, condition, and the change by scene. |
| `makeup-lock.schema.json` | Locked makeup, hair, and effects, including the change by scene. |
| `lighting-plan.schema.json` | The Gaffer's plan. Unstated values stay `not named`. |
| `grip-plan.schema.json` | Camera support and rigging for each shot. |
| `shooting-schedule.schema.json` | The Assistant Director's call sheet. |
| `vfx-needs.schema.json` | One production's list of effects. |
| `vfx-breakdown.schema.json` | Task, method, risk, and turnover for the editor and the colorist. |
| `vfx-review.schema.json` | The VFX read of the dailies. |

## Versioning

Every schema instance carries a `version` field (semver). When an agent regenerates its output (e.g., Art Director updates a character ref), the version increments and downstream agents can detect the change.

## Validation

Agents should validate their inputs before processing and their outputs before handing off.

```bash
python3 scripts/validate-schema.py productions/the-last-marker/shot-lists/shot-list.json
python3 scripts/validate-schema.py --production productions/the-last-marker
```

From Python:

```python
from movie_swarm.validate import validate_file

result = validate_file("productions/the-last-marker/shot-lists/shot-list.json")
if not result.ok:
    raise SystemExit(result.text())
```

`movie_swarm.handoff.read_handoff` and `write_handoff` use the same check. An invalid file raises `HandoffError` and is not written.
