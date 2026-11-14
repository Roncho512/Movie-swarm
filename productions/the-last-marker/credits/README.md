# Film credits for the working copy

Filing recommendation: keep this note with the archived film copy. The file the build reads belongs in the working film folder, outside this repo, at `credits/film-credits.json`.

`film-credits.example.json` is the credits Ron approved on 2026-11-13 (D196). It is an example for the archive. The graphics build does not read an example. It reads `credits/film-credits.json` in the production folder it was pointed at.

Copy the example onto the working film and name the copy `credits/film-credits.json`. For The Last Marker that folder is `PER-Films/the-last-marker` (the films root plus `the-last-marker`). Fields:

- `version`: `1.0.0`
- `production_company.name`: Man's Epic Productions
- `production_company.site`: mansepic.com
- `billing`: Director Ronaldo M., Writer Roncho, Producer R. Edwin Merrill III. These lines are not placeholders.
- `cast`: one object, `role` Miguel Vega, `name` Teodoro Abasolo, `fictional_placeholder` true. The build prints the name as the character.
- `crew`: the eight placeholder lines in the example, each with `fictional_placeholder` true. Keep the diacritics in Ortuño, Przybyłek, and Arreguín.

A true `fictional_placeholder` is printed as FICTIONAL PLACEHOLDER on the end credits and on the billing block. Leave the flag off the company and the billing names. Do not add a watch or a brand line (D38).

Agent credits stay on the Line Producer record. When this file is present, the build lists those agent lines under "Made with Movie-swarm crew" and does not put them in the billing block (D197, proposed).

Approved key art is a separate file, `graphics/brand/key-art-poster.png`, in the same working film folder. The build references that file. It does not draw a stand-in (D197, proposed).
