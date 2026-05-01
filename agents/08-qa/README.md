# Agent 08: Continuity / QA

Quality assurance agent for the AI Movie Production Swarm. Extracts frames from assembled cuts, sends them to Claude for visual analysis, and produces structured QA reports with continuity findings and shot grades.

## Setup

```bash
cd agents/08-qa
pip3 install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
```

Requires FFmpeg for frame extraction (already installed if you built the Editor agent).

## Usage

### Extract frames only (no API call, for manual review)

```bash
python3 -m src.cli frames ../../productions/the-last-marker
open ../../productions/the-last-marker/qa-reports/frames/
```

Extracts start/mid/end frames for each shot. Review them yourself without spending API credits.

### Full QA review (Claude vision analysis)

```bash
python3 -m src.cli review ../../productions/the-last-marker
```

Extracts frames, sends them to Claude with the shot list context, and generates a structured QA report. Costs ~$0.10-0.20 per review depending on frame count.

### Review a specific cut

```bash
python3 -m src.cli review ../../productions/the-last-marker --cut rough-cut-v2.mp4
```

## Output

```
productions/the-last-marker/qa-reports/
├── qa-report-v1.json      # Structured findings (machine-readable)
├── qa-summary-v1.txt      # Human-readable summary
└── frames/                # Extracted evidence frames
    ├── s01-sh01-start.png
    ├── s01-sh01-mid.png
    ├── s01-sh01-end.png
    ├── s01-sh02-start.png
    └── ...
```

## Review Dimensions

The agent evaluates across seven categories:
1. Visual continuity (character, vehicle, environment)
2. Temporal continuity (time of day, lighting)
3. Spatial continuity (screen direction, 180-degree rule)
4. Audio continuity (engine state matches visual)
5. Narrative continuity (story beats, emotional arc)
6. Technical quality (artifacts, resolution, frame rate)
7. Style adherence (vintage film look, color palette, period accuracy)

## Severity Ratings

- **Critical**: Must fix. Breaks immersion immediately.
- **Major**: Should fix. Noticeable on careful viewing.
- **Minor**: Fix if time allows. Only noticeable if looking.
- **Note**: Observation for future reference.

## Integration Points

- **Upstream**: Rough cut from Editor; style bible from Art Director; shot list from Cinematographer
- **Downstream**: QA report routes back to Orchestrator, which assigns fixes to the appropriate agent
- **Feedback loop**: QA → Orchestrator → Production/Editor → QA (iterate until approved)
