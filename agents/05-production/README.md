# 05. Production (Video Generation Agent)

The workhorse. Executes video generation and validates results.

## Role

- Take each shot from the shot list
- Assemble the reference images specified by the Cinematographer
- Execute the generation call on the routed tool
- Validate the clip against character refs, style bible, and continuity notes
- Flag clips that need regeneration
- Track costs per clip and per production
- Manage the generation queue and retries

## Inputs

- Shot list (`shot-list.schema.json`)
- Visual style bible (`visual-style-bible.schema.json`) — for validation
- Reference image files

## Outputs

- `clip-metadata.schema.json`
- Raw video clips in `clips/raw/`
- Selected clips in `clips/selected/`
- Upscaled clips in `clips/upscaled/`

## Primary Tools

- Google Flow / Veo 3.1 (dialogue, realism, native audio)
- Veo 3.1 Lite (iteration at zero credits)

## Secondary Tools

- Seedance 2.0 via fal.ai API (multi-shot action, up to 15 seconds)
- Runway (multi-model routing)

## Status

- [ ] Skill file written
- [ ] Google Flow workflow documented
- [ ] Veo generation tested
- [ ] Clip validation logic implemented
- [ ] Cost tracking implemented

## Build Order

Build in Phase 2, after shot list exists. Most manual phase in the pilot.
