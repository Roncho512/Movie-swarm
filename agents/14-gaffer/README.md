# Gaffer

Write a lighting plan for each scene from the camera package and the look. Key, fill, practicals, time of day, color temperature, and contrast ratio stay the production's words.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent gaffer --crew-command plan --estimate 0
```

The estimate is checked against the cinematographer allocation from the locked split. It is not charged. Offline is the default.
