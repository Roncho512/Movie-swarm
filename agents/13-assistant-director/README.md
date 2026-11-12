# Assistant Director

Break the shot list into a shooting schedule and a call sheet. Group by location and setup. Flag stunt beats. Hand the file to production.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent assistant-director --crew-command schedule --estimate 0
```

The estimate is checked against the line producer allocation from the locked split. It is not charged. Offline is the default.
