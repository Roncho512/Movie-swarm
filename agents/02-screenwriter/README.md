# 02. Screenwriter (Script Agent)

Parses screenplay into machine-readable scene manifest.

## Role

- If given a concept: generate a full screenplay
- If given a screenplay (like The Last Marker): parse and structure it
- Output a machine-readable scene manifest that every downstream agent consumes
- Extract dialogue per scene for the Sound Designer
- Build the character bible
- Tag production notes, color notes, sound notes per scene

## Inputs

- Production brief (`production-brief.schema.json`)
- Raw screenplay (markdown or docx)

## Outputs

- `scene-manifest.schema.json` — the central data structure
- Formatted screenplay (if generated)
- Character bible (embedded in scene manifest)

## Primary Tools

- Claude API or ChatGPT Pro (writing, formatting, scene parsing)

## Key Requirement

The scene manifest must be comprehensive enough that an agent which has NEVER read the original screenplay can still do its job. Every color note, every sound note, every production direction, every prop mention must be captured in structured fields.

## Status

- [ ] Skill file written
- [ ] Scene manifest output validated against schema
- [ ] Tested with The Last Marker screenplay

## Build Order

Build FIRST (alongside Art Director). This agent's output is the foundation for everything.
