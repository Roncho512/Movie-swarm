# Design reference packs

Filing recommendation: keep this folder with the other engine config, next to `config/design-references/*.json`. Do not move a pack into a film folder. A film selects a pack by the words in its own genre, tone, and look.

These files are offline research for Title and Graphic Design. The role reads them when it writes `graphics/research.json`. It does not call a model and it does not open a network connection. A pack applies when its match says `always`, or when one of its terms appears in that production's genre, tone, world, look name, look summary, or brief decisions. A story year narrows a pack only when the pack sets a year span.

Everything a pack adds to a brand guide is a designer proposal. Ron approves or rejects it at the graphics gate. The guide stays a draft until then. A credits face is the one the matched pack names for that role. The engine does not force that face into one category. The western pack is version 2.0.0 (D196, Ron, 2026-11-13). It names Caprasimo for credits, Fraunces as the glyph fallback, Alfa Slab One for subheads and section labels, and Old Standard TT for body, billing, and burned-in subtitles. Rye and Sancreek are mockup stand-ins for the painted pulp capitals. The pack also carries the burned-in subtitle spec and the player-file face. Noto Sans is only that player face.
