# Agent 05: Production

Video generation agent for the AI Movie Production Swarm. Reads a shot list from the Cinematographer, generates video clips via Seedance 2.0 on fal.ai, validates outputs, and produces structured clip metadata for the Editor and QA agents.

## Setup

```bash
cd agents/05-production
pip install -r requirements.txt
export FAL_KEY="your-fal-api-key"
```

Get your API key from [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys).

FFmpeg is optional but recommended for clip validation:
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg
```

## Usage

### Cost estimate (no API calls)

```bash
python -m src.cli estimate ../../productions/the-last-marker/shot-list.json
```

Shows per-shot cost breakdown for both preview and final passes.

### Dry run (shows payloads without calling fal)

```bash
python -m src.cli run ../../productions/the-last-marker/shot-list.json ./output --dry-run
```

### Preview pass (fast tier, 480p — cheap iteration)

```bash
python -m src.cli run ../../productions/the-last-marker/shot-list.json ./output --pass preview
```

### Final pass (standard tier, 720p)

```bash
python -m src.cli run ../../productions/the-last-marker/shot-list.json ./output --pass final
```

### Generate specific shots only

```bash
python -m src.cli run shot-list.json ./output --pass final --shots s01-sh01 s03-sh02
```

### Upload reference images to fal storage

```bash
python -m src.cli upload ../../productions/the-last-marker/visual-assets/character-refs/miguel-front.png
```

Returns a URL you can use in the shot list's `reference_assets`.

## Output Structure

```
output/
├── clips/
│   ├── preview/              # 480p fast-tier clips
│   │   ├── s01-sh01_preview.mp4
│   │   └── ...
│   └── final/                # 720p standard-tier clips
│       ├── s01-sh01.mp4
│       └── ...
├── clip-metadata.json        # Conforms to clip-metadata.schema.json
├── cost-report.json          # Per-call cost tracking
├── preview-summary.txt       # Human-readable preview pass results
└── final-summary.txt         # Human-readable final pass results
```

## How It Works

1. **Loads** the shot list JSON (from Cinematographer)
2. **Selects endpoint** per shot based on reference assets:
   - Has image/video/audio refs → `reference-to-video`
   - Has a start frame → `image-to-video`
   - Text only → `text-to-video`
3. **Builds payload** with proper `@Image1` syntax for reference binding
4. **Submits** to fal.ai async queue
5. **Polls** until completion (exponential backoff on failure, up to 3 retries)
6. **Downloads** the generated MP4
7. **Validates** via ffprobe (duration, streams, file size)
8. **Writes** clip metadata, cost report, and summary

## Two-Pass Strategy

The agent runs in two passes to keep costs down:

- **Preview pass** (~$0.12/sec at 480p fast): Quick iteration to check composition and prompt accuracy. Review these before committing to final generation.
- **Final pass** (~$0.30/sec at 720p standard): Full quality for the edit. Only run this on shots that passed preview review.

For a 3-minute short with ~22 shots averaging 8 seconds each:
- Preview: ~$21
- Final: ~$53
- Total: ~$74

## Shot List Format

The agent reads shot lists conforming to `schemas/shot-list.schema.json`. Key fields per shot:

```json
{
  "shot_id": "s01-sh01",
  "scene_number": 1,
  "shot_number": 1,
  "sequence_position": 1,
  "generation_prompt": "Extreme wide shot of Baja desert...",
  "target_duration_seconds": 8,
  "aspect_ratio": "16:9",
  "tool_routing": {
    "primary_tool": "seedance-2.0",
    "rationale": "Landscape establishing shot, no character refs needed"
  },
  "reference_assets": {
    "character_refs": ["https://fal-storage.../miguel-front.png"],
    "environment_refs": [],
    "audio_refs": [],
    "video_refs": [],
    "start_frame": null,
    "end_frame": null
  }
}
```

## Integration Points

- **Upstream:** Cinematographer agent produces the shot list
- **Downstream:** Editor agent consumes clips + `clip-metadata.json`; QA agent reviews clips against style bible
- **Orchestrator:** Cost report feeds back to the Executive Producer for budget tracking
