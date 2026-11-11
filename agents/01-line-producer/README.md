# Line Producer

The Line Producer reports to Ron. Ron is the executive producer. This folder used to be the executive producer agent. That job is Ron's.

The program watches the budget, the schedule, the credits, and the gates for one run. It uses the Phase 0 run state for the stage, the status, and the running total. The ledger and Ron's decisions sit beside it.

## Commands

From the repo root:

```bash
python3 scripts/line-producer.py --production productions/the-last-marker --run phase-1 status
```

Other commands: `start`, `spend`, `approve-gate`, `decide`, `credit`. Pass `--file` when the decision is a JSON file. Nothing in this command waits for a typed answer.

## What it will not do

It will not write the story. It will not approve a spend that breaks the $500 cap or a locked stage ceiling unless Ron's yes is recorded. It will not hide a retake outside the cap. It will not let the editor run while the dailies gate is closed. It will not let sound run while the edit gate is closed. That gate is picture lock. It will not let color and mix run while the edit gate or the sound gate is closed. It will not let final delivery run while the color-mix gate is closed.
