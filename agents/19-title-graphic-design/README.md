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

At the graphics gate Ron reads that draft. Today the reading copy is `graphics/brand-guide.md`. A visual brand guide PDF is planned for the same review (D191, Ron, 2026-11-13). This role does not write that PDF yet. When Ron gives the go, the PDF shows color swatches with hex codes, a rendered specimen of each proposed face (title, credits, subtitles, and marketing) with the type rules for size, casing, tracking, hierarchy, and safe area, the text rules and the credit-block rules on the page, imagery of each film's locked hero props (for example a vehicle or a watch) consistent with the locked specs and the featured-product placement rules, and at least one proposed scene or key-art frame. Laying out the PDF is offline. An image that needs paid generation uses the art director line and generation approval. The props and the placement rules come from the production folder. The engine stays generic (D30).

A title card stores the words on screen apart from any design direction on the cue. Credits use the face the active design-reference pack names for that role. The engine does not force a category (D194, D196). When the film folder has `credits/film-credits.json`, the build uses those names for the end credits and the billing block, and it keeps the Line Producer names in a separate studio-crew section. A fictional placeholder is printed on the line. Key art references `graphics/brand/key-art-poster.png` and is not drawn as a stand-in (D197, proposed). A featured object in the brief is carried into the guide and the key art as a story placement, not as a sale.

The estimate is checked against the art director allocation from the locked split. It is not charged. Offline is the default.
