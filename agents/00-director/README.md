# Director

The Director turns a screenplay into a treatment and asks Ron what is still open. A treatment is the plan for the film: intent, look, people, scene beats, and a proposed split of the budget.

The Director does not approve the plan. Ron does, through the Line Producer.

## Commands

From the repo root:

```bash
python3 scripts/director.py --production productions/the-last-marker --run first-film-1 --offline intake
python3 scripts/director.py --production productions/the-last-marker --run first-film-1 --offline answer \
  --answers productions/the-last-marker/treatment/questions.json
python3 scripts/director.py --production productions/the-last-marker --run first-film-1 reconform --request <hash>
```

`reconform` reads a response already stored in `runs/<run>/provider-cache.json`. It does not call a model and it does not book money. A live intake sends the screenplay up to 120,000 characters, and it sends `treatment/inputs.json` and the prop locks when the film has them. The offline draft does not call a model, and it does not read the prop locks.

`dispatch` calls the phase 2 roles, production, sound, the composer, the editor, QA, the fix loop, the Dailies Reviewer, the Colorist, the Re-recording Mixer, or the Post Supervisor. The Line Producer checks the gate and the cap first. A picture call waits until Ron approves the previs gate. A plan prices the work and does not spend. A generate call also waits for the generation gate. A dailies review writes a circle, retake, or reject and does not spend. The editor's assemble command waits until Ron approves the dailies gate, then writes the cut and does not spend. Sound and the composer wait until Ron approves the edit gate. That approval is picture lock. Their spot command writes a cue sheet and does not spend. The Colorist and the Mixer wait until Ron approves both the edit gate and the sound gate. Their commands write a grade plan and a mix plan and do not spend. The Post Supervisor waits until Ron approves the color-mix gate, then writes the delivery package and does not spend. Ron approves the delivery gate to mark the film delivered. `studio` walks that path and stops at each gate. It does not approve a gate and it does not pass `--live`. A generation is bought only when `--live` is passed and the generation gate, the key, and a known price all allow it.

Inputs can be Markdown, Fountain, PDF, or Word, or a partial treatment, or both. The guide for a finished treatment is `docs/perfect-treatment.md`.
