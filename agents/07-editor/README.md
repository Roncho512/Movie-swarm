# Agent 07: Editor

Video and audio assembly agent for the AI Movie Production Swarm. Takes selected video clips and audio assets from the Sound Designer, assembles them into a rough cut via FFmpeg.

## Setup

```bash
cd agents/07-editor
brew install ffmpeg   # if not already installed
```

No Python dependencies beyond the standard library.

## Usage

### Probe clip inventory

```bash
python3 -m src.cli probe ../../productions/the-last-marker
```

### Concatenate video only (no audio mix)

```bash
python3 -m src.cli concat ../../productions/the-last-marker
```

### Full rough cut with audio mix

```bash
python3 -m src.cli assemble ../../productions/the-last-marker --mix-file mix-scenes-1-2.json
```

## Mix File Format

The mix file is a JSON file that defines audio layers. Each layer specifies:

```json
{
  "layers": [
    {
      "asset_id": "engine-healthy",
      "source_path": "audio/sfx/engine-source.wav",
      "layer_type": "sfx",
      "timeline_start": 4.0,
      "volume": 0.6,
      "fade_in": 3.0,
      "fade_out": 0.0,
      "trim_start": 10.0,
      "trim_end": 45.0
    }
  ]
}
```

- `source_path`: Relative to the production directory
- `timeline_start`: When in the assembled timeline this audio begins (seconds)
- `volume`: 0.0–1.0
- `trim_start` / `trim_end`: Trim the source file to a specific segment
- `fade_in` / `fade_out`: Fade durations in seconds

## Output

```
productions/the-last-marker/edit/
├── rough-cut-v1.mp4           # The assembled rough cut
├── edit-decision-list.json    # What went where (clips + audio layers)
└── assembly-log.txt           # Command log
```

## Integration Points

- **Upstream**: Selected clips from human review; audio assets from Sound Designer
- **Downstream**: QA agent reviews the rough cut for continuity issues
- **Orchestrator**: EDL feeds back for tracking and iteration
