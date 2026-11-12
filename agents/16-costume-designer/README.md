# Costume Designer

Lock wardrobe the production already defined: garment, color, condition, and the change in each scene. Do not add a garment.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent costume-designer --crew-command lock --estimate 0
```

The estimate is checked against the art director allocation from the locked split. It is not charged. Offline is the default.
