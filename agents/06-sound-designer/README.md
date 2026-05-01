# Agent 06: Sound Designer

Audio generation agent for the AI Movie Production Swarm. Generates dialogue, sound effects, ambient audio, and musical score via ElevenLabs. Reads the shot list's `sound_notes` to determine what audio is needed per shot, generates assets, and outputs a structured audio manifest for the Editor agent.

## Setup

```bash
cd agents/06-sound-designer
pip3 install -r requirements.txt
export ELEVENLABS_API_KEY="your-key-from-elevenlabs.io"
```

Get your API key from [elevenlabs.io](https://elevenlabs.io) → Developers → API Keys.

## Usage

### Search for a voice (for dialogue)

```bash
python3 -m src.cli voices "mexican male"
```

### Generate sound effects (dry run)

```bash
python3 -m src.cli sfx ../../productions/the-last-marker/shot-lists/shot-list.json ./output --dry-run
```

### Generate specific SFX

```bash
python3 -m src.cli sfx ../../productions/the-last-marker/shot-lists/shot-list.json ./output --assets engine-healthy engine-death desert-wind-light
```

### Generate all SFX

```bash
python3 -m src.cli sfx ../../productions/the-last-marker/shot-lists/shot-list.json ./output
```

### Generate dialogue

```bash
python3 -m src.cli dialogue ../../productions/the-last-marker/shot-lists/shot-list.json ./output --voice-id YOUR_VOICE_ID
```

### Generate closing guitar music

```bash
python3 -m src.cli music ../../productions/the-last-marker/shot-lists/shot-list.json ./output
```

### Generate everything at once

```bash
python3 -m src.cli all ../../productions/the-last-marker/shot-lists/shot-list.json ./output --voice-id YOUR_VOICE_ID
```

## Audio Assets for The Last Marker

### Sound Effects (13 assets)
- **Engine states**: healthy cruise, skip/misfire, sputtering death, kick-start fail, kick-start catch, rough idle
- **Environment**: desert wind (light), desert silence
- **Foley**: tire on hardpan, pebble spray, boot on kick lever, cooling metal ticking, spark plug pull

### Dialogue (1 asset)
- "Primero llegas. Despues compites." — the only spoken line in the film

### Music (1 asset)
- Closing nylon-string guitar — three notes, Mexican folk phrase, played twice with silence between

## Output Structure

```
output/
├── sfx/
│   ├── engine-healthy.mp3
│   ├── engine-skip.mp3
│   ├── engine-death.mp3
│   └── ...
├── dialogue/
│   └── vega-primero-llegas.mp3
├── music/
│   └── closing-guitar.mp3
└── audio-manifest.json
```

## Integration Points

- **Upstream**: Shot list (sound_notes) from Cinematographer; clip metadata from Production
- **Downstream**: Editor agent uses audio-manifest.json to layer audio over video clips
- **Orchestrator**: Generation log feeds back for cost tracking

## Estimated Cost

~$8-16 total for The Last Marker (13 SFX + 1 dialogue + 1 music track).
