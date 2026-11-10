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
