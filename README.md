# AI Movie Production Swarm

Nine specialized AI agents. One orchestrated pipeline. Script to screen.

## What This Is

A production system that takes a screenplay and produces a complete short film using AI generation tools. Each stage of film production — writing, visual design, shot planning, video generation, sound design, editing, quality assurance, and fix coordination — is handled by a dedicated agent with defined inputs, outputs, and tool access.

The architecture is modeled on a prior software Build Swarm that produced ~43,000 lines of code. Same pattern: fan-out tasks to specialists, fan-in results, validate, loop if needed.

Optimized around Google Flow (Veo 3.1), ChatGPT Pro (Images 2.0), Claude API (orchestration and QA), ElevenLabs (audio), and Seedance 2.0 via fal.ai (multi-shot video).

Target: short-form content, 3–15 minutes. Feature-length is not yet viable.

## Repository Structure

```
movie-swarm/
├── agents/
│   ├── 01-executive-producer/  # Orchestrator — sequences agents, manages state
│   ├── 02-screenwriter/        # Script parsing → scene manifest + character bible
│   ├── 03-art-director/        # Visual language — character refs, style bible
│   ├── 04-cinematographer/     # Shot planning — shot lists, generation prompts, tool routing
│   ├── 05-production/          # Video generation — Seedance/Veo clip execution
│   ├── 06-sound-designer/      # Audio — dialogue, SFX, ambience, score
│   ├── 07-editor/              # FFmpeg assembly — timeline, audio mix, export
│   ├── 08-qa/                  # Continuity review — Claude vision analysis
│   └── 09-fix-loop/            # QA-driven regeneration — route fixes, track iterations
├── schemas/                    # JSON schemas for all agent handoffs
├── movie_swarm/                # Shared checks, run record, gates, model map
├── config/                     # Review gates, budget cap, models, asset root
├── productions/                # One directory per film project
│   └── the-last-marker/        # Pilot production (in progress)
├── orchestration/              # Pipeline runner (planned)
├── scripts/                    # validate-schema.py and other utilities
└── docs/                       # Architecture brief, build guide
```

## Pipeline Flow

```
Screenplay → [Screenwriter] → Scene Manifest
                                    ↓
Style Brief → [Art Director] → Visual Style Bible + Character Refs
                                    ↓
              [Cinematographer] → Shot List + Generation Prompts
                                    ↓
              [Production] → Video Clips + Native Audio
                                    ↓
              [Sound Designer] → Dialogue + SFX + Ambience + Score
                                    ↓
              [Editor] → Rough Cut → Final Export
                                    ↓
              [QA] → Continuity Report
                                    ↓
              [Fix Loop] → Modified Prompts → Regenerate → Reassemble → Re-review
                                    ↓
              [QA] → Approved or Loop (max 3 iterations)
```

## Agent Status

| # | Agent | Skill File | Code | Tested |
|---|---|---|---|---|
| 01 | Executive Producer | ✅ | — | — |
| 02 | Screenwriter | ✅ | — | — |
| 03 | Art Director | ✅ | — | — |
| 04 | Cinematographer | ✅ | — | — |
| 05 | Production | ✅ | ✅ | ✅ |
| 06 | Sound Designer | ✅ | ✅ | ✅ |
| 07 | Editor | ✅ | ✅ | — |
| 08 | QA | ✅ | ✅ | ✅ |
| 09 | Fix Loop | ✅ | ✅ | — |

A checkmark means the file is in the repo. **Code** means that agent has a program (`src/`). **Tested** means that program has automated tests. Skill-only agents are written instructions: a skill file, and no program yet.

## Schemas

Every agent handoff is defined by a JSON schema.

| Schema | Producer | Consumer(s) |
|---|---|---|
| `production-brief` | Human / Signal | Executive Producer |
| `scene-manifest` | Screenwriter | All downstream agents |
| `visual-style-bible` | Art Director | Cinematographer, Production, QA |
| `shot-list` | Cinematographer | Production, Editor |
| `clip-metadata` | Production | Editor, QA |
| `audio-manifest` | Sound Designer | Editor |
| `continuity-report` | QA | Fix Loop → Production |

Run state, review gates, model routing, and the asset root have their own checklists too (`run-state`, `gate-config`, `model-routing`, `asset-config`).

## How the foundation works

Agents hand work to each other as JSON files. Each kind of file has a checklist in `schemas/`. The shared library checks a file before it is accepted. If a required piece is missing, the handoff stops. The message names the file, the checklist, and what is wrong.

Each production run can keep a status file. It records the current stage, whether the run is waiting, which files it has produced, and how much money has been spent against the film's cap.

Human review is a switch per stage in `config/gates.json`. Every switch starts on, so a person reviews every stage. The film budget cap is in the same file and starts at $500. Changing a switch or the cap is an edit to that file.

`config/model-routing.json` records which generator each role uses, so a later change is a config edit. The programs still call the generators they call today. An `overrides` list is there for a later per-scene or per-shot choice. It is empty.

Finished video can live on an external drive. Set `MOVIE_SWARM_ASSET_ROOT`, or set `asset_root` in `config/assets.json`. Until one of those is set, files stay in the production folder inside this repo. Nothing is moved.

Check the pilot's files:

```bash
python3 scripts/validate-schema.py --production productions/the-last-marker
```

The scene manifest, the shot list, and the visual style bible match their checklists. The audio manifest, the clip metadata, and the two QA reports were saved in an older shape. They are listed in `config/known-schema-mismatches.json`, so the audit reports them and exits successfully. Any other file that fails its checklist stops the command with an error.

## Current Production: The Last Marker

3-minute pilot. Baja California desert, 1967. A solo motorcycle racer on a vintage Triumph, shot in 16mm Ektachrome style.

**Status:** Scenes 1–2 complete through QA. Fix loop generated. Awaiting clip regeneration for lighting and continuity fixes, then reassembly and re-review.

**Production assets:**
- 27 reference images (character, vehicle, environment, props)
- 22-shot shot list with generation prompts
- 6 selected clips (scenes 1–2)
- Audio assets (engine, ambience, dialogue, score)
- Rough cut v1 assembled
- QA report v2 with 4 findings (1 critical, 1 major)
- Fix plan v1 with modified prompts

## Tool Stack

| Category | Primary | Secondary |
|---|---|---|
| Orchestration | Claude API | GPT-5.5 API |
| Image generation | ChatGPT Images 2.0 | Nano Banana Pro (Google Flow) |
| Video generation | Google Veo 3.1 | Seedance 2.0 (fal.ai) |
| Audio | ElevenLabs | Suno v5, Google Lyria 3 |
| Assembly | FFmpeg | DaVinci Resolve |
| QA | Claude API (vision) | GPT-5.5 (vision) |

## Cost Per 15-Minute Short

$150–$460 estimated, depending on generation quality tiers and iteration count. Ron's existing Google Flow and ChatGPT Pro subscriptions absorb significant cost.

## Setup

Install the shared foundation and the agent dependencies from the repo root:

```bash
pip3 install -r requirements.txt
python3 -m pytest tests -q
python3 scripts/validate-schema.py --production productions/the-last-marker
```

Each agent with code also runs independently from its directory:

```bash
cd agents/08-qa
pip3 install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
python3 -m src.cli review ../../productions/the-last-marker
```

See individual agent READMEs for specific setup instructions.
