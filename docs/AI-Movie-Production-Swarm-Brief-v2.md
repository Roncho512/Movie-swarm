AI Movie Production Swarm  |  Architecture Brief v2.0  |  April 2026

# ARCHITECTURE BRIEF

## **AI Movie Production Swarm**

*Eight specialized agents. One orchestrated pipeline. Script to screen.*

UPDATED APRIL 29, 2026

*Incorporates GPT-5.5, Google Flow, Seedance 2.0, Veo 3.1, and current tool landscape.*

Prepared for: **Ron Merrill**

Version: **2.0**

Date: **April 29, 2026**

Classification: **Internal / Working Draft**

---

# What Changed Since v1.0 (April 2 to April 29, 2026)

The AI video and audio landscape shifted materially in the last four weeks. This section summarizes the changes that affect the swarm architecture, tool selection, and cost model.

> **Key takeaway:** The tools got cheaper, the quality got better, and several agent handoffs we planned to build manually are now handled natively by platforms Ron already has access to (Google Flow and ChatGPT Pro).

## GPT-5.5 and ChatGPT Images 2.0 (April 21-24, 2026)

- **GPT-5.5** is better at multi-step planning, tool use, and self-verification. Directly improves orchestrator and agent logic quality.

- **Images 2.0** is OpenAI's first image model with thinking capabilities. It generates up to eight images per prompt, renders text accurately, maintains facial likeness across edits, and runs up to 4x faster than prior models. Outputs at up to 2K resolution.

- **Impact on swarm:** Images 2.0 becomes a primary tool for the Art Director agent. Multi-image per prompt means character reference sheets (front, profile, 3/4, full body) can be generated in fewer calls. Text rendering improvement removes a key limitation for on-screen graphics.

## Google Flow Redesign (February-April 2026)

- **Unified workspace:** Google merged Whisk and ImageFX into Flow. Nano Banana Pro is now built into the core experience. You generate high-fidelity images and instantly use them as ingredients for Veo 3.1 video generations without leaving the platform.

- **Free tier expanded:** All Google accounts get 10 free Veo 3.1 clips per month via Google Vids. Flow provides 50 daily AI credits (roughly 12 videos per day). Google AI Ultra subscribers get up to 1,000 Veo generations per month.

- **Veo 3.1 family:** Now three tiers (Veo 3.1, Veo 3.1 Fast, Veo 3.1 Lite), all with native audio generation. A new upscaling capability enhances any video to 1080p or 4K.

- **Impact on swarm:** Flow becomes the primary execution environment for visual design and production. The Art Director and Production agents can operate largely within Flow, using Nano Banana for reference images and Veo 3.1 for video clips in a single integrated workflow. Ron already has a Flow account.

## Seedance 2.0 (February 2026, API access April 2026)

- **New entrant from ByteDance.** Currently ranked number one on the Artificial Analysis Video Arena leaderboard for both text-to-video and image-to-video, ahead of Kling 3.0, Sora 2, and Veo 3.

- **Multimodal input:** Accepts up to 9 reference images, 3 video clips, and 3 audio files in a single generation pass. Generates audio and video jointly in one architecture, not layered separately.

- **Multi-shot generation:** Produces sequences of connected shots with consistent characters, lighting, and style in one pass. Clips up to 15 seconds at up to 2K resolution with dual-channel stereo audio.

- **Copyright concern:** Disney, Paramount, and US senators have raised IP infringement issues. ByteDance has acknowledged the concerns and committed to safeguards. Monitor before making it a primary tool.

- **Impact on swarm:** If the copyright situation stabilizes, Seedance 2.0 could collapse several agent handoffs into fewer API calls. Its multi-shot capability with reference locking is the closest thing to a Production agent in a box. Available via third-party APIs (fal.ai, Atlas Cloud) at $0.08 to $0.15 per second.

## Runway Multi-Model Platform

- **Model marketplace:** Runway now hosts Gen-4.5, Seedance 2.0, Kling 3.0, Nano Banana 2, Veo 3.1, Sora 2 Pro, and more inside one interface with custom workflow chaining.

- **Runway Characters:** Real-time intelligent avatars that can talk and be directed. Potential application for dialogue-heavy scenes.

- **Impact on swarm:** Runway could serve as a secondary execution layer where the Production agent routes specific shot types to the best model, all within one platform and billing system.

## Audio and Music Tools

- **Suno v5:** Now the quality benchmark for AI music. Vocals are realistic enough to fool listeners. Effective for full score generation.

- **ElevenLabs:** Launched ElevenMusic standalone app in April 2026, unifying voice, music, and sound effects. Company valued at $11 billion. Music model trained on licensed data, making it the safest option for commercial use.

- **Google Lyria 3:** Integrated into Google Vids for custom music generation. Available to Google AI Pro and Ultra subscribers.

- **Impact on swarm:** The Sound Designer agent now has three strong options. ElevenLabs is the recommended primary for dialogue and commercially safe music. Suno v5 for highest quality score generation. Google Lyria 3 for music that stays inside the Flow/Vids ecosystem.

---

# Platform Strategy: Ron's Accounts

Ron has active accounts on Google Flow (Google AI Pro/Ultra) and ChatGPT Pro. This shapes which tools the swarm prioritizes.

> **Design principle:** Build the swarm around platforms Ron already pays for. Use third-party tools only where Flow and ChatGPT Pro have clear gaps.

| **Agent** | **Primary Platform** | **Secondary / Fallback** |
| --- | --- | --- |
| Executive Producer | Claude API (orchestration logic) | GPT-5.5 API for complex planning |
| Screenwriter | Claude API or ChatGPT Pro (script generation) | N/A |
| Art Director | ChatGPT Images 2.0 (character refs, concept art) + Google Flow / Nano Banana Pro | Midjourney for stylized concepts |
| Cinematographer | Claude API (cinematic shot planning) | N/A |
| Production | Google Flow / Veo 3.1 (dialogue, realism, native audio) | Seedance 2.0 via API (multi-shot, action); Runway (model routing) |
| Sound Designer | ElevenLabs (dialogue, commercially safe music) | Suno v5 (score quality); Google Lyria 3 (in-ecosystem) |
| Editor | FFmpeg (programmatic assembly) | DaVinci Resolve; Veo upscaler (4K) |
| Continuity / QA | Claude API (visual analysis, frame comparison) | GPT-5.5 vision for second-pass review |

**Why this split works:** Google Flow handles the visual pipeline (image generation to video production) in a single workspace with native audio. ChatGPT Pro handles the thinking-intensive work (character reference sheets via Images 2.0, script generation, complex planning). Claude handles orchestration and QA where structured reasoning and tool-calling are strongest. Each platform plays to its strength.

---

# Updated Pipeline Overview

The eight-agent architecture from v1.0 remains intact. The changes are in tool assignments and handoff simplification.

| **#** | **Agent** | **Function** | **What Changed in v2.0** |
| --- | --- | --- | --- |
| 01 | Executive Producer | Orchestrator. Receives brief, sequences all agents, manages state. | GPT-5.5 available for complex planning steps. Better self-verification. |
| 02 | Screenwriter | Produces production-ready screenplay with structured scene manifest. | No material change. Claude or ChatGPT Pro both work. |
| 03 | Art Director | Establishes visual language. Character refs, environments, style bible. | Images 2.0 generates 8 images per prompt with facial consistency. Nano Banana in Flow for video-ready refs. |
| 04 | Cinematographer | Translates scenes into shot lists. Routes each shot to optimal tool. | Now routes across Veo 3.1 (three tiers), Seedance 2.0, and Runway multi-model. |
| 05 | Production | Executes video generation. Manages queue, validates consistency. | Google Flow is primary. Seedance multi-shot reduces per-clip generation count. Native audio on Veo and Seedance. |
| 06 | Sound Designer | Dialogue, SFX, ambient audio, musical score. | Less custom work needed. Veo/Seedance include native audio. ElevenLabs unified platform. Lyria 3 for in-ecosystem music. |
| 07 | Editor | Assembles timeline. Pacing, transitions, color grade, export. | Veo upscaling to 4K now available. CapCut integration possible via Seedance. |
| 08 | Continuity / QA | Reviews cut for consistency, sync, narrative gaps. | GPT-5.5 vision capability adds a second-pass reviewer alongside Claude. |

**Feedback loop:** Unchanged from v1.0. QA agent sends continuity report to Orchestrator, which routes fixes to the appropriate specialist. Loop continues until QA approves or maximum iterations reached.

---

# Updated Agent Specifications

## 01. Executive Producer (Orchestrator Agent)

Master controller. Receives the initial brief and sequences every downstream agent. Manages state, tracks progress, handles retries, and assembles the final deliverable.

| | |
| --- | --- |
| **Inputs** | Script or concept, style/genre/tone brief, director reference (optional), target runtime |
| **Outputs** | Scene breakdown manifest, agent task queue, progress state, final assembled film |
| **Primary Tools** | Claude API (orchestration logic, structured tool-calling); GPT-5.5 API (complex multi-step planning) |
| **Pattern** | Same pattern as the Privagent Build Swarm orchestrator. Fan-out tasks to specialists, fan-in results, validate, loop if needed. |

## 02. Screenwriter (Script Agent)

Takes raw concept or draft script and produces a production-ready screenplay with scene headers, action lines, dialogue, and technical notes.

| | |
| --- | --- |
| **Inputs** | Concept/logline or raw script, genre and tone directives, target runtime, character descriptions |
| **Outputs** | Formatted screenplay, scene manifest (JSON), character bible, dialogue extraction per scene |
| **Primary Tools** | Claude API or ChatGPT Pro (writing, formatting, scene parsing) |
| **Pattern** | If given a raw concept, generates full screenplay. If given an existing script, parses and structures it. Always outputs machine-readable scene manifest alongside human-readable script. |

## 03. Art Director (Visual Design Agent)

Establishes the entire visual language of the film. This agent is the consistency anchor. Every downstream visual agent references this output.

| | |
| --- | --- |
| **Inputs** | Scene manifest, style/genre brief, director reference, character bible from Screenwriter |
| **Outputs** | Character reference sheets (8-10 images per character, multi-angle), environment concept art, color palette and lighting guide, visual style bible |
| **Primary Tools** | ChatGPT Images 2.0 (hero character frames, up to 8 images per prompt with facial consistency, 2K resolution, accurate text rendering); Google Flow / Nano Banana Pro (video-ready reference images that feed directly into Veo) |
| **Secondary** | Midjourney (stylized concept art and mood boards) |
| **v2.0 Change** | Images 2.0 dramatically reduces call count for character sheets. Its thinking capability lets it plan compositions before generating. Nano Banana integration in Flow means reference images are instantly available for video generation without file transfer. |

## 04. Cinematographer (Shot Planning Agent)

Translates each scene into a precise shot list with camera angles, movements, framing, and transitions. Routes each shot to the optimal video generation tool.

| | |
| --- | --- |
| **Inputs** | Scene manifest, visual style bible, character reference sheets, genre conventions |
| **Outputs** | Shot list per scene (with camera specs), video generation prompts per shot, tool routing map, transition notes |
| **Primary Tools** | Claude API (cinematic knowledge, tool capability matrix) |
| **v2.0 Change** | Tool routing matrix is now richer. Routes dialogue scenes to Veo 3.1 (native audio). Routes multi-shot action sequences to Seedance 2.0 (multi-reference, joint audio-video). Routes stylized/artistic shots to Runway Gen-4.5. Routes budget/iteration shots to Veo 3.1 Lite (zero credits in Flow). |

## 05. Production (Video Generation Agent)

The workhorse. Executes video generation calls, validates clips against character references, and manages retries.

| | |
| --- | --- |
| **Inputs** | Shot list with prompts, character reference images, visual style bible, tool routing from Cinematographer |
| **Outputs** | Raw video clips per shot (with native audio where applicable), clip metadata, consistency validation results, re-generation flags |
| **Primary Tools** | Google Flow / Veo 3.1 (dialogue scenes, realism, native audio, 8-second clips at 1080p, extendable); Veo 3.1 Lite (rapid iteration at zero credit cost in Flow) |
| **Secondary** | Seedance 2.0 via API (multi-shot action, up to 15 seconds, 12 reference assets per call, joint audio-video); Runway (multi-model routing for specialized shots) |
| **v2.0 Change** | Native audio on Veo and Seedance means many clips arrive with synchronized sound, reducing work for the Sound Designer. Veo upscaling adds 4K output. Seedance multi-shot generation can produce connected sequences with consistent characters in one pass, reducing the stitch-and-validate cycle. |

## 06. Sound Designer (Audio Agent)

Handles all audio: dialogue, sound effects, ambient layers, and musical score. Workload reduced from v1.0 because Veo and Seedance now generate native audio.

| | |
| --- | --- |
| **Inputs** | Dialogue extraction per scene, scene mood/tone notes, visual clips with native audio (for gap analysis), genre conventions |
| **Outputs** | Dialogue tracks per character, supplemental sound effects, ambient audio beds, musical score, audio timing manifest |
| **Primary Tools** | ElevenLabs (dialogue voices, voice cloning, commercially licensed music generation, sound effects); Suno v5 (highest-quality score and song generation) |
| **Secondary** | Google Lyria 3 (in-ecosystem music, available in Google Vids for Pro/Ultra subscribers); Cartesia (voice matching) |
| **v2.0 Change** | This agent now operates more as an audio director than a from-scratch producer. Many clips arrive with native audio from Veo or Seedance. The agent reviews, fills gaps, replaces or upgrades dialogue where needed, and layers score. ElevenLabs unification of voice, music, and SFX under one platform simplifies the toolchain. For commercial distribution, ElevenLabs is preferred because its training data is fully licensed. |

## 07. Editor (Assembly Agent)

Assembles all video clips and audio into the final timeline. Handles pacing, transitions, color grading, and export.

| | |
| --- | --- |
| **Inputs** | Selected video clips per shot, audio stems, shot list with transition notes, pacing directives |
| **Outputs** | Assembled timeline, color-graded final cut, multiple format exports, quality report |
| **Primary Tools** | FFmpeg (programmatic editing, clip assembly, format conversion); Veo upscaling (enhance to 1080p or 4K) |
| **Secondary** | DaVinci Resolve (color grading, professional output); CapCut (quick assembly, caption generation) |
| **v2.0 Change** | Veo upscaling capability is new. Any clip, whether AI-generated or traditional, can now be enhanced to 4K resolution. This removes a previous quality ceiling. |

## 08. Continuity / QA Agent

Reviews the assembled cut for continuity errors, visual inconsistencies, audio sync issues, and narrative gaps.

| | |
| --- | --- |
| **Inputs** | Assembled cut, character reference sheets, scene manifest, visual style bible |
| **Outputs** | Continuity report, re-generation requests, edit revision notes, final approval or rejection |
| **Primary Tools** | Claude API (visual analysis, frame-by-frame comparison); GPT-5.5 (vision capability for second-pass review, self-verification) |
| **v2.0 Change** | GPT-5.5 adds a second reviewer with strong vision capability and improved self-verification. Two-model QA (Claude + GPT-5.5) catches more inconsistencies than either alone. |

---

# Updated Tool Stack (April 2026)

## Image Generation

| **Tool** | **Access** | **Best For** |
| --- | --- | --- |
| ChatGPT Images 2.0 | ChatGPT Pro (Ron has) | Character reference sheets (8 per prompt), concept art, text-heavy graphics. Thinking capability plans compositions. 2K resolution. |
| Nano Banana Pro | Google Flow (Ron has) | Video-ready reference images. Direct integration with Veo for image-to-video. High fidelity, instant use as video ingredients. |
| Midjourney | Subscription | Stylized concept art, mood boards, environment design. Optional. |

## Video Generation

| **Tool** | **Access** | **Best For** |
| --- | --- | --- |
| Google Veo 3.1 | Google Flow (Ron has) | PRIMARY. Dialogue scenes, realism, native audio. 8-second extendable clips at 1080p. Three tiers (quality, fast, lite). Upscaling to 4K. |
| Veo 3.1 Lite | Google Flow (zero credits) | Rapid iteration and exploration. Same speed as Fast at less than half the cost. Use for storyboard validation before committing to full-quality generation. |
| Seedance 2.0 | Third-party API (fal.ai) | Multi-shot action sequences. 12 reference assets per call. Joint audio-video. Up to 15 seconds. Number one on video benchmarks. Watch copyright situation. |
| Runway Gen-4.5 | Runway subscription | Cinematic hero shots, stylized sequences. Also hosts Kling 3.0, Sora 2, and other models for routing flexibility. |

## Audio, Voice, and Music

| **Tool** | **Access** | **Best For** |
| --- | --- | --- |
| ElevenLabs | Subscription/API | PRIMARY for dialogue. Voice cloning, emotional performance, 70+ languages. Also: commercially licensed music generation and SFX. Safest for commercial distribution. |
| Suno v5 | Subscription | Highest quality AI music. Realistic vocals, proper song structure. Best for hero score and soundtrack generation. |
| Google Lyria 3 | Google Vids (Ron has) | In-ecosystem music. Custom soundtracks, 30 seconds to 3 minutes. Stays inside the Google toolchain. |
| Veo/Seedance native audio | Included in video generation | Ambient sound, environmental audio, and lip-synced dialogue generated jointly with video. Reduces Sound Designer workload. |

## Orchestration and Intelligence

| **Tool** | **Access** | **Best For** |
| --- | --- | --- |
| Claude API | Anthropic API | Orchestration logic, structured tool-calling, visual analysis, QA review. Best for the reasoning backbone of the swarm. |
| GPT-5.5 | ChatGPT Pro / API | Complex multi-step planning, self-verification, vision-based QA. Second reviewer for continuity checks. |

---

# Updated Cost Estimates

## Per 15-Minute Short Film

| **Category** | **v1.0 Estimate** | **v2.0 Estimate** |
| --- | --- | --- |
| Video generation | $150 - $400 | $100 - $300 |
| Voice and dialogue | $25 - $50 | $15 - $40 |
| Music and score | $10 - $30 | $10 - $25 |
| Image generation | $15 - $40 | $5 - $20 |
| AI orchestration (Claude, GPT) | $20 - $50 | $20 - $50 |
| Post-production / upscaling | $0 - $35 | $0 - $25 |
| **Total** | **$220 - $605** | **$150 - $460** |

**Why costs dropped:** Veo 3.1 Lite at zero credits for iteration. Veo 3.1 Fast price reduction (April 7). Native audio reduces separate audio generation calls. Images 2.0 generates multiple images per prompt. Ron's existing subscriptions (Flow, ChatGPT Pro) absorb significant cost that would otherwise be pay-per-call.

---

# Updated Limitations (April 2026)

- **Clip duration:** Veo generates 8-second clips (extendable). Seedance generates up to 15 seconds. Sora 2 reaches 20-25 seconds. Still requires stitching for anything longer, but the clips are getting longer.

- **Character consistency:** Now a baseline capability across all major platforms. Seedance and Kling both lock faces, clothing, and style across shots. Still degrades over very long sequences (100+ shots). The Art Director agent's reference anchoring remains critical.

- **Complex physics:** Improved but not solved. Seedance 2.0 handles multi-subject collisions and contact dynamics better than anything prior. Water and cloth still imperfect.

- **Text rendering:** Dramatically improved. ChatGPT Images 2.0 renders dense, accurate text including non-Latin scripts. On-screen titles, signs, and credits are now feasible.

- **Feature length:** Still not viable for 90-minute films. Multi-shot generation (Seedance) helps with scene-level coherence, but maintaining narrative, visual, and audio consistency across an entire feature requires more development. Target: 3 to 15 minutes for MVP.

- **Copyright:** New and significant concern. Seedance 2.0 faces active legal challenges. ElevenLabs is the only audio platform with fully licensed training data. For any commercially distributed content, verify the licensing status of every generation tool in the pipeline.

---

# Updated MVP Implementation Plan

## Phase 1: Proof of Concept (3-Minute Short)

Build inside Ron's existing platforms. Manual orchestration. Target: produce a single 3-minute short film from a concept input within two weeks.

- Use ChatGPT Images 2.0 to generate character reference sheets (front, profile, 3/4, full body) in 1-2 prompts per character
- Feed references into Google Flow. Generate Nano Banana hero frames, then Veo 3.1 video clips with native audio
- Use ElevenLabs for dialogue replacement where Veo native audio is insufficient
- Assemble in FFmpeg or CapCut. Apply Veo upscaling for final output
- Measure: cost per minute, generation time, consistency score, audio quality

## Phase 2: Full Pipeline (5-Minute Short)

Add orchestration layer and remaining agents. Automated pipeline with human checkpoints.

- Build the Orchestrator agent using Claude API with the same swarm pattern as Privagent Build Swarm
- Add Cinematographer agent with tool routing across Veo 3.1 tiers, Seedance 2.0, and Runway
- Add Sound Designer agent backed by ElevenLabs (dialogue + SFX) and Suno v5 (score)
- Add QA agent with dual-model review (Claude + GPT-5.5 vision)
- Test end-to-end automated pipeline. Measure intervention rate

## Phase 3: Scale and Integrate (15-Minute Short)

Connect the Movie Swarm to Signal Intelligence Platform for demand-driven production. This is where the combined system begins generating revenue.

- Stress-test character consistency over 100+ shots
- Implement cost tracking and budget management per project
- Develop style templates for repeatable production across genres
- Connect Signal platform output (high-demand stories) directly to Movie Swarm input (production brief)
- Publish proof-of-concept shorts to YouTube. Measure audience response against Signal predictions
- Use audience data as pitch material for optioning or selling production rights

---

# Next Steps

- Run a Phase 1 test inside Google Flow this week. Pick a simple concept (narration-driven, stylized), generate character refs in ChatGPT Images 2.0, produce clips in Flow with Veo 3.1, assemble manually. Prove the basic pipeline works.

- Test Seedance 2.0 via fal.ai on one multi-shot action sequence. Compare quality and consistency against Veo 3.1 for the same scene. Evaluate copyright risk.

- Define the JSON handoff schemas between agents: scene manifest, shot list, clip metadata, audio manifest. Same discipline as the Build Swarm spec files.

- Build the Screenwriter and Art Director agents first. These produce the foundation all other agents depend on.

- Brief Paul on the updated architecture. The Unified Spec Compiler pattern from the Build Swarm applies directly to agent skill files for the Movie Swarm.

- Select a test concept for the combined Signal-to-Swarm pipeline. Something with a known fan community and measurable engagement, so audience response can be tracked.

---

*Confidential  |  Ron Merrill*
