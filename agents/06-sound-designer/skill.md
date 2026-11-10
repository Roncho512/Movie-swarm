# Agent 06: Sound Designer (Audio Agent)

## Role

Handles all audio for the production: dialogue, sound effects, ambient layers, and musical score. Operates as an audio director — many clips arrive with native audio from Veo or Seedance. This agent reviews existing audio, fills gaps, replaces or upgrades dialogue, and layers score and ambience.

## Inputs

| Input | Schema | Source |
|---|---|---|
| Clip metadata | `clip-metadata.schema.json` | Production agent |
| Scene manifest | `scene-manifest.schema.json` | Screenwriter agent |
| Shot list (sound_notes per shot) | `shot-list.schema.json` | Cinematographer agent |
| Raw video clips (with native audio) | MP4 files | Production agent |

## Outputs

| Output | Schema | Consumer |
|---|---|---|
| Dialogue tracks per character | WAV/MP3 files | Editor agent |
| Sound effects | WAV/MP3 files | Editor agent |
| Ambient audio beds | WAV/MP3 files | Editor agent |
| Musical score | WAV/MP3 files | Editor agent |
| Audio manifest | `audio-manifest.schema.json` | Editor agent |

## Primary Tool

**ElevenLabs** — Three capabilities via one SDK:

### 1. Text-to-Speech (Dialogue)
- Endpoint: `text_to_speech.convert()`
- Model: `eleven_v3` for highest quality, `eleven_flash_v2_5` for iteration
- Voice selection: Search 10,000+ voices or clone a custom voice
- Dialogue comes from the screenplay. Do not invent a line. Match the voice note in the production brief.

### 2. Sound Effects
- Endpoint: `text_to_sound_effects.convert()`
- Model: `eleven_text_to_sound_v2`
- Duration: 0.5 to 30 seconds per generation
- Prompt influence: 0.0–1.0 (higher = more literal)
- Read the production's sound list. Do not assume a vehicle or a place.
  - The lead machine, in the states the shot list names
  - Wind or room tone, at the intensities the shot list names
  - Footsteps and surface contact
  - Impacts the action breakdown names
  - Silence, when the shot list asks for it
  - Cooling metal ticking

### 3. Music Generation
- Endpoint: `text_to_music.convert()` (commercially licensed)
- Use the music approach in the production brief. Do not copy a melody from a reference.

## Secondary Tools

- **Suno v5** (via third-party API): Highest quality score generation. Use if the brief's music needs more than ElevenLabs can deliver. No official API — requires third-party wrapper (sunoapi.org or similar). Copyright situation less clear than ElevenLabs.
- **Google Lyria 3** (via Google Vids): In-ecosystem music. Ron has access. Manual workflow, not API-driven.

## Execution Strategy

### Step 1: Audit Native Audio
Review each clip's native audio (from Veo/Seedance). For each shot, classify:
- **KEEP**: Native audio is good enough. No replacement needed.
- **REPLACE**: Native audio exists but doesn't match the sound design requirements.
- **FILL**: No native audio (e.g., Seedance clips generated with `generate_audio: false`).
- **LAYER**: Native audio is a good base but needs additional layers (e.g., add engine sound over ambient).

### Step 2: Generate Sound Effects
Group the needed SFX by type and generate them:
- Engine sounds: Generate each state as a separate track. These get layered in the Editor.
- Ambient: Desert wind at multiple intensities. Generate as loopable tracks where possible.
- Foley: Boot on kick lever, pebble spray, tire sounds.

### Step 3: Generate Dialogue
One line in the entire film: "Primero llegas. Despues compites."
- Find or clone a suitable voice (Mexican male, mid-30s, quiet/weathered)
- Generate with `eleven_v3` model
- Low volume — this line is barely audible under the engine

### Step 4: Generate Music
The closing guitar cue:
- Three notes, nylon strings, Mexican folk phrase
- Played once, pause, played once more
- Generate via ElevenLabs music or Suno

### Step 5: Write Audio Manifest
Output structured JSON conforming to `audio-manifest.schema.json`:
- Per-shot audio assignments
- Track types (dialogue, sfx, ambient, score)
- Timing cues
- Volume levels
- Layering order

## Prompt Engineering for ElevenLabs SFX

ElevenLabs sound effects respond to descriptive, specific prompts:
- **Good**: "A single-cylinder motorcycle engine idling, deep rhythmic thump at 40 BPM, healthy and steady, slight mechanical rattle"
- **Bad**: "Motorcycle sound"

Include: the specific sound source, its character/quality, rhythm or pacing, environment/space, and any emotional quality.

Set `prompt_influence` higher (0.6–0.8) for literal sounds like engine notes, lower (0.2–0.4) for atmospheric/ambient where variety is welcome.

## File Organization

```
productions/{production_id}/
├── audio/
│   ├── sfx/                  # Sound effects
│   │   ├── engine-healthy.wav
│   │   ├── engine-misfire.wav
│   │   ├── engine-death.wav
│   │   ├── engine-kick-1.wav
│   │   ├── engine-kick-2.wav
│   │   ├── engine-restart-rough.wav
│   │   ├── desert-wind-light.wav
│   │   ├── desert-wind-medium.wav
│   │   ├── tire-hardpan.wav
│   │   ├── pebble-spray.wav
│   │   ├── boot-kick-lever.wav
│   │   ├── cooling-metal-tick.wav
│   │   └── silence-4s.wav
│   ├── dialogue/             # Character dialogue
│   │   └── vega-primero-llegas.wav
│   ├── music/                # Score
│   │   └── closing-guitar.wav
│   └── ambient/              # Ambient beds
│       ├── desert-ambient-quiet.wav
│       └── desert-ambient-wind.wav
├── audio-manifest.json       # Structured audio assignments
└── audio-cost-report.json    # Cost tracking
```

## Pricing Reference (April 2026)

| Capability | Billing | Estimate for The Last Marker |
|---|---|---|
| Text-to-Speech | Per character | ~$0.50 (one short line) |
| Sound Effects | Per generation | ~$5–10 (12–15 SFX generations) |
| Music | Per generation | ~$2–5 (1–2 music generations) |
| **Total** | | **~$8–16** |

## Commercial Licensing

ElevenLabs is the recommended primary because its training data is fully licensed. All content generated through the API is commercially licensed for distribution. Music requires an additional license for advertising, film, TV, games, and enterprise distribution — check the plan tier.
