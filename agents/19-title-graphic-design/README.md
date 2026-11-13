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

`research` writes `graphics/research.json`. It reads the production documents and any offline pack in `config/design-references/` whose terms the production's own genre, tone, or look already uses. A pack suggestion is labeled a designer proposal. `guide` writes `graphics/brand-guide.json` from that research and will not run without it. The guide stays a draft. `build` writes the graphic specs and will not run until Ron approves the brand guide at the graphics gate.

A title card stores the words on screen apart from any design direction on the cue. Credits use a sans-serif. A featured object in the brief is carried into the guide and the key art as a story placement, not as a sale.

The estimate is checked against the art director allocation from the locked split. It is not charged. Offline is the default.
