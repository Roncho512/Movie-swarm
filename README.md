# AI Movie Production Swarm

Eight specialized AI agents. One orchestrated pipeline. Script to screen.

## What This Is

A production system that takes a screenplay and produces a complete short film using AI generation tools. Each stage of film production — writing, visual design, shot planning, video generation, sound design, editing, and quality assurance — is handled by a dedicated agent with defined inputs, outputs, and tool access.

The system is designed for short-form content (3-15 minutes) and optimized around Google Flow (Veo 3.1), ChatGPT Pro (Images 2.0), Claude API (orchestration), and ElevenLabs (audio).

## Repository Structure

```
movie-swarm/
├── agents/                     # Agent definitions (skill files, prompts, tools)
│   ├── 01-executive-producer/  # Orchestrator — sequences all agents, manages state
│   ├── 02-screenwriter/        # Script parsing → scene manifest + character bible
│   ├── 03-art-director/        # Visual language — character refs, style bible
│   ├── 04-cinematographer/     # Shot planning — shot lists, tool routing, prompts
│   ├── 05-production/          # Video generation — clip execution, validation
│   ├── 06-sound-designer/      # Audio — dialogue, SFX, ambience, score
│   ├── 07-editor/              # Assembly — timeline, color grade, export
│   └── 08-qa/                  # Continuity review — consistency, sync, narrative
├── schemas/                    # JSON schemas for all agent handoffs
├── productions/                # One directory per film project
│   └── the-last-marker/        # Pilot production
├── orchestration/              # Pipeline runner, state management, retry logic
├── scripts/                    # Utility scripts (FFmpeg wrappers, file ops, etc.)
└── docs/                       # Architecture brief, guides, decision log
```

## Pipeline Flow

```
Screenplay → [Screenwriter] → Scene Manifest + Character Bible
                                      ↓
Style Brief → [Art Director] → Visual Style Bible + Character Refs + Environment Refs
                                      ↓
              [Cinematographer] → Shot List + Generation Prompts + Tool Routing
                                      ↓
              [Production] → Raw Video Clips + Native Audio + Clip Metadata
                                      ↓
              [Sound Designer] → Dialogue + SFX + Ambience + Score
                                      ↓
              [Editor] → Assembled Timeline → Color Grade → Final Export
                                      ↓
              [QA] → Continuity Report → Fix Requests → Loop or Approve
```

## Schemas

Every agent handoff is defined by a JSON schema. Agents produce and consume structured data. No free-form handoffs.

| Schema | Producer | Consumer(s) |
|---|---|---|
| `scene-manifest.schema.json` | Screenwriter | All downstream agents |
| `visual-style-bible.schema.json` | Art Director | Cinematographer, Production, QA |
| `shot-list.schema.json` | Cinematographer | Production, Editor |
| `clip-metadata.schema.json` | Production | Editor, QA |
| `audio-manifest.schema.json` | Sound Designer | Editor |
| `continuity-report.schema.json` | QA | Executive Producer (orchestrator) |
| `production-brief.schema.json` | External (human or Signal platform) | Executive Producer |

## Current Production

**The Last Marker** — 3-minute pilot. Baja desert, 1966. Solo motorcycle racer. 16mm Ektachrome visual style. See `productions/the-last-marker/`.

## Tools

| Category | Primary | Secondary |
|---|---|---|
| Image Generation | ChatGPT Images 2.0, Nano Banana Pro (Flow) | Midjourney |
| Video Generation | Google Veo 3.1 (Flow) | Seedance 2.0 (fal.ai), Runway Gen-4.5 |
| Audio / Voice | ElevenLabs | Suno v5, Google Lyria 3 |
| Orchestration | Claude API | GPT-5.5 API |
| Editing | FFmpeg | DaVinci Resolve, CapCut |

## Status

- [x] Architecture brief (v2.0)
- [x] Pilot screenplay (The Last Marker)
- [x] Repository structure
- [x] Handoff schemas defined
- [ ] Screenwriter agent skill file
- [ ] Art Director agent skill file
- [ ] Cinematographer agent skill file
- [ ] Production agent skill file
- [ ] Sound Designer agent skill file
- [ ] Editor agent skill file
- [ ] QA agent skill file
- [ ] Orchestrator agent skill file
- [ ] The Last Marker — scene manifest generated
- [ ] The Last Marker — character refs generated
- [ ] The Last Marker — clips generated
- [ ] The Last Marker — assembled cut
- [ ] The Last Marker — final export

---

*Confidential | Ron Merrill*
