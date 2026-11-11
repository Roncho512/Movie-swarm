# Agent 06: Sound Designer

The studio Sound Designer and Composer that the Director calls live in `movie_swarm/sound.py`, command `spot`. After Ron approves picture lock, they write a cue sheet timed to the cut. The Composer reads `audio/score-brief.json`. Placeholder stems are rendered when ffmpeg is installed. A paid call waits on the generation gate. Ron approves a `sound` gate before color and mix. The commands below are the older prompt library. The Director's dry-run still uses them. A run without `--dry-run` is refused.

Audio generation agent for the AI Movie Production Swarm. Generates dialogue, sound effects, ambient audio, and musical score via ElevenLabs. Reads the shot list's `sound_notes` to determine what audio is needed per shot, generates assets, and outputs a structured audio manifest for the Editor agent.

## Setup

```bash
cd agents/06-sound-designer
pip3 install -r requirements.txt
export ELEVENLABS_API_KEY="your-key-from-elevenlabs.io"
```

Get your API key from [elevenlabs.io](https://elevenlabs.io) → Developers → API Keys.

## Usage

Prompts are read from the production, at `audio/sound-prompts.json`. This program does not keep a film's prompts. A dry run writes the manifest and does not call ElevenLabs. A run without `--dry-run` is refused. This build has no live audio client, and a paid call also has to pass the generation gate.

```bash
python3 -m src.cli sfx path/to/shot-list.json ./output --dry-run
python3 -m src.cli sfx path/to/shot-list.json ./output --library path/to/audio/sound-prompts.json --dry-run
```

The Last Marker prompts now live in `productions/the-last-marker/audio/sound-prompts.json`. That file is production data. It is not part of this program.

## Output

A dry run writes `audio-manifest.json` in the output folder. The `production_id` comes from the prompt file, or from the shot list when the prompt file does not name one.
