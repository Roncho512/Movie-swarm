# Agent 07: Editor (Assembly Agent)

## Role

Assembles all video clips and audio assets into a final timeline. Handles clip concatenation, audio layering, transitions, and export. Uses FFmpeg for all programmatic editing.

## Inputs

| Input | Source |
|---|---|
| Selected video clips | `clips/selected/` (one MP4 per shot, named by shot_id) |
| Audio manifest | `audio/audio-manifest.json` from Sound Designer |
| SFX, dialogue, music files | `audio/sfx/`, `audio/dialogue/`, `audio/music/` |
| Shot list | `shot-lists/shot-list.json` from Cinematographer |

## Outputs

| Output | Consumer |
|---|---|
| Assembled rough cut (MP4) | QA agent, human review |
| Edit decision list (JSON) | QA agent, Orchestrator |

## Primary Tool

**FFmpeg** — All editing is done programmatically via FFmpeg commands:
- `ffmpeg -f concat` for clip assembly
- Audio mixing via `amix` and `amerge` filters
- Crossfade transitions via `xfade` filter
- Volume adjustment via `volume` filter
- Final export to H.264 MP4

## Assembly Strategy

### Step 1: Concatenate Video
Join selected clips in sequence order. Two approaches:
- **Hard cut**: Simple concat demuxer. No transition between shots.
- **Crossfade**: Use xfade filter for dissolves between scenes (not between shots within a scene).

Take the transition from the treatment. If the treatment does not name one, hard-cut within a scene.

### Step 2: Strip or Mute Native Audio
Native audio from Veo/Seedance clips varies in quality. For a controlled mix:
- Strip native audio from all clips
- Replace entirely with the Sound Designer's audio assets
- This gives full control over the sound design

### Step 3: Layer Audio
Build the audio mix in layers, bottom to top:
1. **Ambient bed** (desert wind, silence) — continuous, low volume
2. **Engine sound** (from Freesound source recording) — primary sound, follows the narrative arc
3. **Foley** (tire, pebbles, boot, cooling metal) — spot effects at specific moments
4. **Dialogue** — very low volume, one line only
5. **Music** (closing guitar) — final shot only

### Step 4: Export
- Codec: H.264 (libx264)
- Audio: AAC
- Resolution: Match source clips
- Container: MP4

## Engine Sound Slicing

The Freesound source file `218352__photomonster__motorcycle_nsumax_1954_engine.wav` contains a full engine cycle. The Editor slices it by timestamp into the states needed:
- Healthy cruise segment → loop for Scene 1
- Struggling/misfire segment → Scene 1 end, Scene 2 start
- Death segment → Scene 2 engine death moment

Timestamp identification is done by the human operator, then passed to the assembly script.

## File Organization

```
productions/{production_id}/
├── edit/
│   ├── rough-cut-v1.mp4       # Assembled output
│   ├── edit-decision-list.json # What went where
│   └── assembly-log.txt        # FFmpeg command log
```
