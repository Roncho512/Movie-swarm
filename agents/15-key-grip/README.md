# Key Grip

Write the camera support and the rigging for each shot. Support follows the shot list. Rigging follows the gaffer.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent key-grip --crew-command plan --estimate 0
```

The estimate is checked against the cinematographer allocation from the locked split. It is not charged. Offline is the default.
