# Film credits for the working copy

Filing recommendation: keep this note with the archived film copy. The file the build reads belongs in the working film folder, outside this repo, at `credits/film-credits.json`.

`film-credits.example.json` is the credits Ron named on 2026-11-13 (D196, D198). It is an example for the archive. The graphics build does not read an example. It reads `credits/film-credits.json` in the production folder it was pointed at.

Copy the example onto the working film and name the copy `credits/film-credits.json`. For The Last Marker that folder is `PER-Films/the-last-marker` (the films root plus `the-last-marker`). Fields:

- `version`: `1.0.0`
- `production_company.name`: Man's Epic Productions
- `production_company.site`: mansepic.com
- `billing`: Director Ronaldo M., Writer Roncho, Producer R. Edwin Merrill III.
- `cast`: one object, `role` Miguel Vega, `name` Teodoro Abasolo. The build prints the name as the character. This is an official credited name (D198).
- `crew`: Director of Photography Enzo Callegaris, Editor Halina Wierzbicka, Music Aurelio Benvenga, Production Design Rodrigo Llanes Ortuño, Art Director Massimo Ferlandi, Costumes Graziella Fontecchio, Sound Bogdan Przybyłek, Makeup Pilar Arreguín. These are the official credited names (D198). Keep the diacritics in Ortuño, Przybyłek, and Arreguín.

Do not add a watch or a brand line (D38).

Agent credits stay on the Line Producer record. When this file is present, the build lists those agent lines under "Made with Movie-swarm crew" and does not put them in the billing block (D197, proposed).

Approved key art is a separate file, `graphics/brand/key-art-poster.png`, in the same working film folder. The build references that file. It does not draw a stand-in (D197, proposed).
