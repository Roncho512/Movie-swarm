# Title and Graphic Design

Research the film's graphic identity, write a brand guide from that research, then spec the titles, the credits, the subtitle style, the key art, and the collateral. The Art Director still owns the in-film look.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent title-graphic-design --crew-command research --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent title-graphic-design --crew-command guide --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent title-graphic-design --crew-command build --estimate 0
```

`research` writes `graphics/research.json`. `guide` writes `graphics/brand-guide.json` and will not run without that research. `build` writes the graphic specs and will not run until the brand guide is approved at the graphics gate.

The estimate is checked against the art director allocation from the locked split. It is not charged. Offline is the default.
