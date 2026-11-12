# Trailer Editor

Cut a teaser and a trailer from approved takes, after picture lock. The trailer is optional. A film that leaves it off delivers without one.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent trailer-editor --crew-command research --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent trailer-editor --crew-command guard --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent trailer-editor --crew-command sign --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent trailer-editor --crew-command plan --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent trailer-editor --crew-command cut --estimate 0
```

`research` writes `marketing/trailer-research.json`. `guard` will not run without that research. `sign` is the Director's sign-off on the spoiler guard. `plan` will not run without research and that sign-off. `cut` will not run without a plan.

The estimate is checked against the Marketing and Distribution line. It is not charged to the Editor. Offline is the default. This role runs only when the film's budget turns the trailer on.
