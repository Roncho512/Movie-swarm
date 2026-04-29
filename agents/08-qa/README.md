# 08. Continuity / QA Agent

Reviews the assembled cut and drives the fix loop.

## Role

- Watch the assembled cut
- Compare every shot against character refs, style bible, and scene manifest
- Check audio sync and quality
- Check narrative coherence and pacing
- Score the cut across multiple dimensions
- Produce a continuity report with specific fix requests routed to the responsible agent
- The Orchestrator uses this report to drive the feedback loop

## Inputs

- Assembled cut (from Editor)
- Scene manifest (`scene-manifest.schema.json`)
- Visual style bible (`visual-style-bible.schema.json`)
- Character / vehicle / prop reference images

## Outputs

- `continuity-report.schema.json`

## Primary Tools

- Claude API (visual analysis, frame-by-frame comparison)
- GPT-5.5 vision (second-pass review, self-verification)

## Dual-Model Review

Two-model QA catches more issues than either alone:
1. Claude reviews first, produces initial report
2. GPT-5.5 reviews independently, adds findings
3. Reports merge into final continuity report

## Status

- [ ] Skill file written
- [ ] Review checklist defined
- [ ] Frame extraction script written
- [ ] Dual-model review workflow tested

## Build Order

Build in Phase 2, after an assembled cut exists.
