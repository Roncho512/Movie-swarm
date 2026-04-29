# 06. Sound Designer (Audio Agent)

All audio: dialogue, SFX, ambience, score.

## Role

- Review native audio from video clips (keep, replace, or augment)
- Generate dialogue tracks for spoken lines
- Generate or source sound effects
- Create ambient sound beds per scene
- Generate musical score elements
- Produce the audio manifest with time-coded placement for the Editor

## Inputs

- Scene manifest (`scene-manifest.schema.json`) — dialogue extractions, sound notes
- Clip metadata (`clip-metadata.schema.json`) — native audio status
- Raw video clips (to evaluate native audio quality)

## Outputs

- `audio-manifest.schema.json`
- Audio files in `audio/` subdirectories

## Primary Tools

- ElevenLabs (dialogue, voice cloning, commercially licensed music, SFX)
- Suno v5 (highest quality score and song generation)

## Secondary Tools

- Google Lyria 3 (in-ecosystem music via Google Vids)
- Cartesia (voice matching)

## Key Requirements for The Last Marker

- Triumph single-cylinder engine as the dominant sound (healthy → faltering → dead → restarting → rough)
- Desert silence: wind, sand on rock, cooling metal ticks
- One line of Spanish dialogue ("Primero llegas. Despues compites.") mixed under engine sound
- Nylon string guitar: three-note Mexican folk phrase, played twice, enters at 2:56
- No music until the final 4 seconds

## Status

- [ ] Skill file written
- [ ] ElevenLabs voice profile created for Miguel Vega
- [ ] Engine sound design approach tested
- [ ] Ambient desert sound tested
- [ ] Guitar phrase generated

## Build Order

Build in Phase 2, after clips exist.
