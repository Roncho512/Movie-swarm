# Stunt and Action Coordinator

This role reads `action_and_stunt_beats` on the approved treatment and writes one shot per sentence. The safety line is the same for every film: separate shots, one movement each, no real impact, no real fall, no real fire.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent stunt-coordinator --crew-command breakdown --estimate 0
```

The estimate is checked against the production allocation. It is not charged. A beat that is not physically possible is marked, not staged as real.
