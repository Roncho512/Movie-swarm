# VFX Supervisor

Flag shots that need VFX. Write the task, the method, and the risk, and the turnover for the editor and the colorist. Review those shots again in dailies.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent vfx-supervisor --crew-command breakdown --estimate 0
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent vfx-supervisor --crew-command review --estimate 0
```

`breakdown` is the pre-production list. `review` reads the dailies report. Neither one opens a gate.

The estimate is checked against the editor allocation from the locked split. It is not charged. Offline is the default.
