# Makeup and Hair

Lock makeup, hair, and effects the production already defined. Dirt, sweat, wounds, and aging stay the production's words.

```bash
python3 scripts/director.py --production productions/the-last-marker --run phase-1 --offline dispatch \
  --agent makeup-hair --crew-command lock --estimate 0
```

The estimate is checked against the art director allocation from the locked split. It is not charged. Offline is the default.
