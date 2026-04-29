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

## Versioning

Every schema instance carries a `version` field (semver). When an agent regenerates its output (e.g., Art Director updates a character ref), the version increments and downstream agents can detect the change.

## Validation

Agents should validate their inputs before processing and their outputs before handing off. A script for validation against these schemas is in `/scripts/validate-schema.py` (planned).
