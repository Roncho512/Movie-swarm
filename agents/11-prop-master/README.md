# Prop Master

The Prop Master locks the hero props a production already defined. Definitions live in `props/prop-definitions.json` when the production has them. Otherwise the lock uses the approved treatment and the brief, and it does not invent a side.

```bash
python3 scripts/director.py --production productions/the-last-marker --run first-film-1 --offline dispatch \
  --agent prop-master --crew-command lock --estimate 0
```

The estimate is checked against the art director allocation from the locked split. It is not charged.
