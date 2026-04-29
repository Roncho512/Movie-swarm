# 01. Executive Producer (Orchestrator Agent)

Master controller. Receives the production brief and sequences every downstream agent.

## Role

- Parse the production brief
- Sequence agent execution: Screenwriter → Art Director → Cinematographer → Production → Sound Designer → Editor → QA
- Manage state across the pipeline
- Handle the QA feedback loop: route fix requests to the correct agent, re-run affected stages, re-submit to QA
- Track costs and generation counts
- Assemble the final deliverable

## Inputs

- `production-brief.schema.json`

## Outputs

- Agent task queue (internal state)
- Progress tracking
- Final assembled production package

## Primary Tools

- Claude API (orchestration logic, structured tool-calling)
- GPT-5.5 API (complex multi-step planning, fallback)

## Pattern

Fan-out tasks to specialists, fan-in results, validate, loop if needed. Same pattern as the Privagent Build Swarm orchestrator.

## Status

- [ ] Skill file written
- [ ] State management defined
- [ ] Retry logic implemented
- [ ] Cost tracking implemented
- [ ] Integration tested

## Build Order

Build this agent LAST. Run the pipeline manually first to understand real friction points.
