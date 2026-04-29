# 07. Editor (Assembly Agent)

Assembles everything into the final film.

## Role

- Take selected clips and audio assets
- Assemble the timeline according to the shot list order and transition notes
- Apply pacing directives from the scene manifest
- Color grade for consistency across clips
- Apply Veo upscaling for final output resolution
- Export in multiple formats

## Inputs

- Shot list (`shot-list.schema.json`) — sequence, transitions, pacing
- Clip metadata (`clip-metadata.schema.json`) — selected clips
- Audio manifest (`audio-manifest.schema.json`) — all audio layers
- Scene manifest (`scene-manifest.schema.json`) — editorial rhythm notes

## Outputs

- Assembled timeline
- Color-graded final cut
- Multiple format exports in `edit/export/`
- Quality report

## Primary Tools

- FFmpeg (programmatic editing, clip assembly, format conversion)
- Veo upscaling (enhance to 1080p or 4K)

## Secondary Tools

- DaVinci Resolve (color grading, professional output)
- CapCut (quick assembly, caption generation)

## Status

- [ ] Skill file written
- [ ] FFmpeg assembly script written
- [ ] Color grade workflow defined
- [ ] Export formats defined

## Build Order

Build in Phase 2, after clips and audio exist.
