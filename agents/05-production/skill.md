# Agent 05: Production (Video Generation Agent)

## Role

The workhorse of the pipeline. Takes the Cinematographer's shot list and executes video generation calls via Seedance 2.0 on fal.ai. Validates each clip against character references and the visual style bible. Manages retries, cost tracking, and outputs structured clip metadata.

## Inputs

| Input | Schema | Source |
|---|---|---|
| Shot list | `shot-list.schema.json` | Cinematographer agent |
| Character reference images | URLs or local paths | Art Director agent |
| Environment reference images | URLs or local paths | Art Director agent |
| Visual style bible | `visual-style-bible.schema.json` | Art Director agent |

## Outputs

| Output | Schema | Consumer |
|---|---|---|
| Raw video clips (MP4 with native audio) | Files on disk | Editor agent |
| Clip metadata | `clip-metadata.schema.json` | Editor agent, QA agent |
| Cost report | Inline JSON | Orchestrator |

## Primary Tool

**Seedance 2.0 via fal.ai** — Three endpoints:

- `bytedance/seedance-2.0/text-to-video` — Pure text prompt, no reference assets. Use for establishing shots, landscapes, abstract sequences.
- `bytedance/seedance-2.0/image-to-video` — Single reference image animated into video. Use for character-driven shots with one subject.
- `bytedance/seedance-2.0/reference-to-video` — Up to 9 images + 3 videos + 3 audio files as references. Use for multi-character scenes, style transfer, lip-sync, and any shot requiring character consistency anchoring.

Fast-tier variants (`bytedance/seedance-2.0/fast/*`) are available at ~20% lower cost with slightly reduced quality. Use for iteration/preview passes.

## Execution Strategy

### Two-Pass Generation

1. **Preview pass (fast tier):** Generate every shot on the fast tier at 480p. Review for composition, framing, character accuracy, and prompt alignment. This is cheap (~$1.21/10s clip at 480p fast). Flag shots that need prompt revision.

2. **Final pass (standard tier):** Generate approved shots at 720p standard. Include all reference assets. Enable audio generation. This is the quality output (~$3.03/10s clip at 720p standard).

### Endpoint Selection Logic

The Cinematographer's `tool_routing` field specifies the intended endpoint per shot, but the Production agent makes the final call based on:

- **Has character reference images?** → `reference-to-video` (anchors identity)
- **Has a single starting frame?** → `image-to-video` (animate from key frame)
- **Text-only, no references needed?** → `text-to-video` (landscapes, establishing)
- **Has audio reference for lip-sync?** → `reference-to-video` with `audio_urls`

### Reference Asset Rules

- Character references: Use `@Image1`, `@Image2` etc. in the prompt to bind reference images to subjects.
- Maximum 12 total reference files across all modalities per call.
- Upload reference images to fal's file storage first, then use returned URLs.
- For multi-character scenes, assign one reference image per character and reference them by position in the prompt.

### Retry and Validation

- If a clip fails generation, retry up to 3 times with exponential backoff.
- After generation, validate:
  - File exists and is playable MP4
  - Duration matches requested duration (±1 second)
  - Resolution matches requested resolution
  - If audio was requested, audio track is present
- If validation fails after retries, log the failure and move to the next shot. Don't block the pipeline.

### Cost Tracking

Log every API call with:
- Endpoint used
- Tier (standard/fast)
- Resolution
- Duration requested vs. actual
- Cost per call (calculated from fal.ai pricing)
- Cumulative cost for the production

### Pricing Reference (April 2026)

| Tier | Resolution | Text-to-Video | Image-to-Video | Reference-to-Video |
|---|---|---|---|---|
| Standard | 720p | $0.3034/sec | $0.3024/sec | $0.3024/sec |
| Fast | 720p | $0.2419/sec | $0.2419/sec | $0.2419/sec |
| Standard | 480p | ~$0.15/sec | ~$0.15/sec | ~$0.15/sec |
| Fast | 480p | ~$0.12/sec | ~$0.12/sec | ~$0.12/sec |

Reference-to-video with video inputs gets a 0.6x price multiplier.

## Prompt Engineering for Seedance

Seedance wants cinematic direction, not image-generation keywords. Structure prompts as:

1. **Subject and action first** — who, doing what
2. **Camera movement second** — tracking, dolly, static, handheld
3. **Sound/audio cues third** — what should be heard
4. **Cuts and timing** — "Cut scene to...", "At 5 seconds..."

Use `@Image1` etc. to reference inputs. Wrap dialogue in double quotes: `The man said: "Remember this moment."`

Do NOT use comma-separated tag lists or quality boosters. The model responds to narrative structure.

## File Organization

```
productions/{production_id}/
├── clips/
│   ├── preview/          # Fast-tier 480p preview clips
│   │   ├── s01-sh01_preview.mp4
│   │   └── ...
│   ├── final/            # Standard-tier 720p final clips
│   │   ├── s01-sh01.mp4
│   │   └── ...
│   └── rejected/         # Failed or replaced clips (kept for reference)
├── clip-metadata.json    # Structured metadata per clip-metadata.schema.json
└── cost-report.json      # Running cost log
```
