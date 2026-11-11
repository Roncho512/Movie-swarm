# Director

The Director turns a screenplay into a treatment and asks Ron what is still open. A treatment is the plan for the film: intent, look, people, scene beats, and a proposed split of the budget.

The Director does not approve the plan. Ron does, through the Line Producer.

## Commands

From the repo root:

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline intake
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline answer \
  --answers productions/the-last-marker/treatment/questions.json
```

`dispatch` calls the phase 2 roles, production, sound, the composer, the editor, QA, the fix loop, or the Dailies Reviewer. The Line Producer checks the gate and the cap first. A picture call waits until Ron approves the previs gate. A plan prices the work and does not spend. A generate call also waits for the generation gate. A dailies review writes a circle, retake, or reject and does not spend. The editor's assemble command waits until Ron approves the dailies gate, then writes the cut and does not spend. Sound and the composer wait until Ron approves the edit gate. That approval is picture lock. Their spot command writes a cue sheet and does not spend. Color and mix wait until Ron approves the sound gate. This build does not buy a generation.

Inputs can be Markdown, Fountain, PDF, or Word, or a partial treatment, or both. The guide for a finished treatment is `docs/perfect-treatment.md`.
