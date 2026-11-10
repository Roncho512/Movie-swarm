# Build Guide: Zero to Movie

Step-by-step instructions for building the AI Movie Production Swarm and producing the first film.

## Prerequisites

- GitHub account with Git LFS enabled
- Google Flow account (AI Pro or Ultra)
- ChatGPT Pro account
- Claude API access (Anthropic)
- ElevenLabs account
- Optional: Suno v5, Runway, fal.ai (Seedance 2.0)

---

## Phase 1: Foundation (Sessions 1-3)

### Session 1: Repository Setup

**Goal:** Repo on GitHub, directory structure in place, schemas committed.

1. Create a new private repository on GitHub called `movie-swarm`
2. Clone it locally
3. Copy the contents of this repo skeleton into it
4. Initialize Git LFS:
   ```bash
   git lfs install
   git lfs track "*.mp4" "*.webm" "*.mov" "*.wav" "*.mp3" "*.png" "*.jpg" "*.jpeg" "*.tiff" "*.webp"
   ```
5. Commit and push:
   ```bash
   git add .
   git commit -m "Initial repo structure: agents, schemas, production skeleton"
   git push origin main
   ```

**Deliverable:** Live GitHub repo with full structure.

### Session 2: Schema Review and Refinement

**Goal:** Validate that the seven JSON schemas capture everything needed for The Last Marker.

1. Walk through each schema against the screenplay:
   - Does `scene-manifest.schema.json` have fields for every type of note in the screenplay? (color, sound, production, editorial)
   - Does `shot-list.schema.json` support all the shot types in the script? (extreme wide, detail, POV, tracking)
   - Does `audio-manifest.schema.json` handle the engine sound as a first-class layer?
   - Does `clip-metadata.schema.json` track prop visibility validation?
2. Refine schemas based on gaps found
3. Commit updates

**Deliverable:** Validated schemas that cover The Last Marker end-to-end.

### Session 3: Production Brief for The Last Marker

**Goal:** Create the first real data file — the production brief JSON for The Last Marker.

1. Populate `production-brief.schema.json` with data from the screenplay
2. Save to `productions/the-last-marker/production-brief.json`
3. This becomes the input to the Screenwriter agent

**Deliverable:** Machine-readable production brief for the pilot.

---

## Phase 2: First Two Agents (Sessions 4-6)

### Session 4: Screenwriter Agent — Skill File

**Goal:** Build the Screenwriter agent that parses the screenplay into a scene manifest.

1. Write the skill file (`agents/02-screenwriter/skill.md`):
   - System prompt defining the agent's role
   - Input schema reference
   - Output schema reference
   - Parsing rules (how to extract scenes, dialogue, color notes, etc.)
2. Test: Feed the The Last Marker screenplay → get back a scene manifest JSON
3. Validate output against `scene-manifest.schema.json`
4. Save the validated manifest to `productions/the-last-marker/scene-manifest/`

**Deliverable:** Scene manifest JSON for The Last Marker. Every downstream agent can now start.

### Session 5: Art Director Agent — Skill File

**Goal:** Build the Art Director agent and generate initial reference assets.

1. Write the skill file (`agents/03-art-director/skill.md`):
   - System prompt defining the visual design role
   - Input: scene manifest + production brief
   - Output: visual style bible + reference images
   - Generation prompt templates for ChatGPT Images 2.0
   - Generation prompt templates for Nano Banana Pro (Flow)
2. Generate Miguel Vega character reference sheet:
   - Front, profile, 3/4, full body (8 images via Images 2.0)
   - Save to `visual-assets/character-refs/`
3. Generate Triumph TR6SC reference sheet
4. Generate Breitling Top Time reference
5. Generate 4 environment style frames (amber, bronze, rose, blue dusk)

**Deliverable:** Visual style bible JSON + all reference images committed to repo.

### Session 6: Test the Handoff

**Goal:** Verify that the Screenwriter → Art Director handoff works cleanly.

1. Start from the production brief
2. Run through Screenwriter → scene manifest
3. Feed scene manifest to Art Director → style bible + refs
4. Review: Does the style bible contain everything the Cinematographer will need?
5. Document any schema gaps or handoff friction
6. Commit fixes

**Deliverable:** Proven two-agent pipeline. Foundation is solid.

---

## Phase 3: Shot Planning and Production (Sessions 7-10)

### Session 7: Cinematographer Agent — Skill File

**Goal:** Build the agent that creates shot lists with generation prompts.

1. Write the skill file (`agents/04-cinematographer/skill.md`)
2. Feed: scene manifest + visual style bible
3. Get back: shot list JSON with ~20 shots, each with:
   - Generation prompt
   - Tool routing (Veo 3.1, Veo Lite, etc.)
   - Reference assets to include
   - Continuity notes
4. Validate against `shot-list.schema.json`

**Deliverable:** Complete shot list for The Last Marker.

### Sessions 8-9: Production — Generate Clips

**Goal:** Generate all video clips. This is the most hands-on phase.

1. Start with Veo 3.1 Lite for storyboard validation:
   - Generate low-cost versions of every shot
   - Check composition, framing, character appearance
   - Flag shots that need prompt revision
2. Revise prompts based on Lite results
3. Generate final clips on Veo 3.1 (or Veo 3.1 Fast):
   - Include reference images
   - Validate each clip against style bible
4. For each clip, log metadata in `clip-metadata.json`
5. Select best clip per shot → move to `clips/selected/`

**Deliverable:** ~20 selected video clips with metadata.

### Session 10: Production Agent — Skill File

**Goal:** Codify the generation and validation workflow into the Production agent.

1. Write the skill file based on what you learned in Sessions 8-9
2. Document the Google Flow workflow step by step
3. Build the clip validation checklist
4. Implement cost tracking

**Deliverable:** Production agent skill file. The manual process is now documented and repeatable.

---

## Phase 4: Audio, Assembly, QA (Sessions 11-14)

### Session 11: Sound Designer Agent

**Goal:** Produce all audio assets.

1. Write the skill file (`agents/06-sound-designer/skill.md`)
2. Review native audio from Veo clips — keep/replace/augment decisions
3. Generate:
   - Triumph engine sound (5 states: healthy, faltering, dying, restarting, rough)
   - Desert ambience (wind, sand, silence, cooling metal)
   - Dialogue: "Primero llegas. Despues compites." via ElevenLabs
   - Guitar phrase: 3 notes, nylon string, Mexican folk via Suno v5
4. Produce audio manifest JSON

**Deliverable:** All audio assets + audio manifest.

### Session 12: Editor Agent

**Goal:** Assemble the film.

1. Write the skill file (`agents/07-editor/skill.md`)
2. Write FFmpeg assembly script:
   - Read shot list for sequence and transitions
   - Read clip metadata for file paths
   - Read audio manifest for layered audio
   - Concatenate, crossfade, mix
3. Assemble first rough cut
4. Apply color grading for cross-clip consistency
5. Apply Veo upscaling for final resolution
6. Export

**Deliverable:** First assembled cut of The Last Marker.

### Session 13: QA Agent

**Goal:** Review the cut and produce a continuity report.

1. Write the skill file (`agents/08-qa/skill.md`)
2. Extract key frames from the assembled cut
3. Run Claude visual analysis:
   - Character consistency across shots
   - Vehicle consistency
   - Prop visibility (Top Time in 3 shots)
   - Lighting progression
   - Style adherence
4. Run GPT-5.5 vision as second reviewer
5. Merge findings into continuity report JSON

**Deliverable:** Continuity report with scored categories and fix requests.

### Session 14: Fix Loop

**Goal:** Address QA findings and produce the final cut.

1. Route fix requests to responsible agents:
   - Production: regenerate flagged clips
   - Sound Designer: fix audio issues
   - Editor: re-cut with fixed assets
2. Re-run QA
3. Repeat until approved or max iterations reached
4. Export final cut

**Deliverable:** QA-approved final export of The Last Marker.

---

## Phase 5: Orchestrator (Session 15+)

### Session 15: Executive Producer Agent

**Goal:** Automate the pipeline you've now run manually.

1. Write the skill file (`agents/01-line-producer/skill.md`)
2. Implement:
   - Production brief parsing
   - Agent sequencing
   - State management (which agents have run, what outputs exist)
   - QA loop routing
   - Cost aggregation
3. Test: Give it a new production brief → does it sequence everything correctly?

**Deliverable:** Working orchestrator. The pipeline is now automated with human checkpoints.

---

## After the Pilot

Once The Last Marker is complete:

1. **Retrospective:** Document what worked, what broke, what took longest
2. **Schema updates:** Fix any gaps found during production
3. **Second production:** Pick a different genre/style to stress-test the pipeline
4. **Signal integration:** Connect Signal Intelligence Platform output → production brief input
5. **Cost optimization:** Review generation costs, identify where Lite/Fast tiers save money
6. **Catalog structure:** Define how multiple productions share the same repo

---

## Working Across Sessions

This project spans multiple chat sessions. To maintain continuity:

1. **Always commit to GitHub** at the end of each session
2. **Update the production README checklist** as tasks complete
3. **Reference specific file paths** when picking up work (e.g., "let's work on `agents/02-screenwriter/skill.md`")
4. **The schemas are the source of truth** — if there's a question about what data an agent needs, the schema has the answer

The repo is the shared memory between sessions. Keep it current.
