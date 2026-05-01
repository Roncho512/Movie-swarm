# Agent 08: Continuity / QA Agent

## Role

Reviews assembled cuts for continuity errors, visual inconsistencies, audio sync issues, and narrative gaps. Acts as the final quality gate before a cut is approved. Sends structured revision requests back to the Orchestrator for routing to the appropriate specialist agent.

## Inputs

| Input | Source |
|---|---|
| Assembled rough cut (MP4) | Editor agent |
| Edit decision list (JSON) | Editor agent |
| Shot list | Cinematographer agent |
| Visual style bible | Art Director agent |
| Character reference sheets | Art Director agent |
| Scene manifest | Screenwriter agent |
| Audio manifest | Sound Designer agent |

## Outputs

| Output | Consumer |
|---|---|
| QA report (JSON) | Orchestrator, human review |
| Frame extractions (PNG) | Attached to QA report for evidence |
| Approval or rejection | Orchestrator |

## Primary Tools

**Claude API** — Visual analysis, frame-by-frame comparison, structured reasoning about continuity. Extracts frames from the cut, analyzes them against character references and style bible, and produces a structured report.

**FFmpeg** — Frame extraction at specific timestamps for analysis.

## Review Checklist

The QA agent evaluates the cut across seven dimensions:

### 1. Visual Continuity
- Character appearance consistent across shots (clothing, hair, skin tone, build)
- Vehicle/prop consistency (motorcycle color, damage state, dust level)
- Lighting continuity between adjacent shots (color temperature, direction, intensity)
- Environment consistency (same desert, same vegetation, same terrain)

### 2. Temporal Continuity
- Time of day progression makes sense (sun position, light color)
- No impossible jumps (sunset to midday between adjacent shots)
- Shadow direction consistent within a scene

### 3. Spatial Continuity
- Screen direction maintained (rider moving left-to-right stays left-to-right)
- 180-degree rule not violated between shots in a scene
- Background landmarks consistent between shots of the same location

### 4. Audio Continuity
- Engine sound state matches visual (running when riding, dead when stopped)
- Ambient sound consistent within a scene
- No abrupt audio jumps between shots
- Dialogue (if any) audible and timed correctly

### 5. Narrative Continuity
- Scene order matches screenplay intent
- Key story beats are present (engine dies, diagnosis, restart)
- Emotional arc tracks (confidence → trouble → determination)
- Pacing serves the story (not too fast, not too slow)

### 6. Technical Quality
- Resolution consistent across shots
- No visible artifacts, glitches, or generation failures
- Frame rate consistent
- Aspect ratio consistent
- No black frames or flash frames at cuts

### 7. Style Adherence
- Film grain / vintage aesthetic consistent
- Color palette matches style bible
- Camera language matches cinematographer's shot list (wide, medium, close-up)
- Overall look matches the reference period (1960s Baja)

## Execution Strategy

### Step 1: Extract Frames
Extract key frames from the cut at:
- First frame of each shot
- Last frame of each shot
- Mid-point of each shot
- Any moment where a cut or transition occurs

This gives 3-4 frames per shot for analysis.

### Step 2: Analyze Each Frame
For each extracted frame, evaluate against the checklist. Use Claude's vision capability to compare frames against character references and the style bible.

### Step 3: Cross-Shot Comparison
Compare adjacent shot pairs for continuity breaks:
- Last frame of shot N vs. first frame of shot N+1
- Check for screen direction, lighting, and character state mismatches

### Step 4: Audio Review
Analyze the audio track for:
- Sync with visual events
- Volume consistency
- Appropriate silence/sound transitions

### Step 5: Generate Report
Produce a structured QA report with:
- Per-shot findings
- Cross-shot continuity issues
- Severity ratings (critical, major, minor, note)
- Specific fix recommendations
- Overall approval/rejection

## Severity Ratings

- **Critical**: Breaks immersion immediately. Must fix before release. (e.g., character changes appearance between shots, motorcycle is different color)
- **Major**: Noticeable on careful viewing. Should fix. (e.g., lighting direction reverses, desert type changes)
- **Minor**: Only noticeable if looking for it. Fix if time allows. (e.g., dust level on motorcycle slightly different, grain intensity varies)
- **Note**: Not a problem, just an observation for future reference. (e.g., this shot has slightly warmer color temperature than adjacent shots)

## Report Format

```json
{
  "production_id": "the-last-marker",
  "cut_reviewed": "rough-cut-v1.mp4",
  "review_date": "2026-05-01T...",
  "overall_verdict": "revise",
  "overall_notes": "...",
  "findings": [
    {
      "finding_id": "F001",
      "severity": "major",
      "category": "visual_continuity",
      "shots_affected": ["s01-sh02", "s01-sh03"],
      "timestamp": "25.0s",
      "description": "Desert landscape changes from Sonoran (cactus) to Mojave (scrubland) at the sh02→sh03 cut.",
      "evidence_frames": ["frames/s01-sh02-end.png", "frames/s01-sh03-start.png"],
      "recommendation": "Regenerate s01-sh03 with Baja desert environment reference.",
      "assigned_to": "production"
    }
  ],
  "shot_grades": {
    "s01-sh01": {"grade": "A", "notes": "Strong opening. Vintage look solid."},
    "s01-sh02": {"grade": "B+", "notes": "Good tracking. Slight dust inconsistency."}
  },
  "statistics": {
    "total_findings": 5,
    "critical": 0,
    "major": 2,
    "minor": 2,
    "notes": 1
  }
}
```

## File Organization

```
productions/{production_id}/
├── qa-reports/
│   ├── qa-report-v1.json      # Structured findings
│   ├── qa-summary-v1.txt      # Human-readable summary
│   └── frames/                # Extracted evidence frames
│       ├── s01-sh01-start.png
│       ├── s01-sh01-mid.png
│       ├── s01-sh01-end.png
│       └── ...
```
