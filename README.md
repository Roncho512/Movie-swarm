# Movie Swarm

Movie Swarm turns a screenplay into a finished short film. Specialized helpers, called agents, do the steps. Ron is the executive producer. He reviews the work and decides what is allowed to spend money.

New to a film, or coming back after a long gap? Read [START-HERE.md](START-HERE.md).

## Current status

Phase 0 is on main. It merged on 2026-11-10 in [pull request 1](https://github.com/Roncho512/Movie-swarm/pull/1), merge `c369689`. Phase 0 is the shared checklist, the run record, the review gates, and the $500 cap.

Phase 1 is on main. It merged on 2026-11-10 in [pull request 3](https://github.com/Roncho512/Movie-swarm/pull/3), merge `da9d54a`. The Line Producer watches the budget, the schedule, the credits, and the gates. The Director reads a screenplay and writes a treatment, which is the plan for the film before anyone generates a shot. Ron approved the Last Marker treatment gate on run phase-1. That record is in `productions/the-last-marker/archive/`. The live run is `first-film-1`, and the treatment is a draft. Spent so far: $0.00 of $500.00.

Phase 2 is on main. It merged on 2026-11-10 in [pull request 4](https://github.com/Roncho512/Movie-swarm/pull/4) and [pull request 5](https://github.com/Roncho512/Movie-swarm/pull/5), merge `f6f52d4`. The storyboard is one beat per shot: 41 shots, plus the three scene 3 shots Ron added, 44 in all. Ron approved the previs gate. The note is "Approve the storyboard previs gate." No images were generated.

Phase 3 is on main. It merged on 2026-11-10 in [pull request 6](https://github.com/Roncho512/Movie-swarm/pull/6), merge `1355ad4`. The studio can quote any production, put locked prop phrases into a prompt, and refuse a paid call until Ron approves a gate called `generation`. A gate is a switch that makes a stage wait for Ron. That build does not call a provider. The generation gate on The Last Marker is still closed. Spent so far: $0.00 of $500.00.

Phase 4 is on main. It merged on 2026-11-11 in [pull request 7](https://github.com/Roncho512/Movie-swarm/pull/7), merge `c0de548`. After generation, every take is reviewed before it can be cut. A take is one generated clip or frame for a shot. The Dailies Reviewer circles a take that passes, sends a bad one back as a retake, or rejects a file that is missing. The proof is Harbor Night, under `tests/fixtures/`, plus tiny frames made in the tests. Harbor Night is a synthetic production, not The Last Marker. The review does not call a paid model. A retake is an estimate against the fix-loop line, and nothing is charged. The editor waits until Ron approves the `dailies` gate. Making The Last Marker is still the last phase.

Phase 5 is on main. It merged on 2026-11-11 in [pull request 8](https://github.com/Roncho512/Movie-swarm/pull/8), merge `683e4c5`. The Editor assembles the circled takes into a rough cut. An edit decision list is the cut: which take, where it starts and ends, and how it joins the next shot. JSON is the source of truth. A CMX3600 file is a reading copy of the same cut. The editor trims toward the runtime in the production brief and does not invent a shot. A shot with no circled take is a blocker sent back to dailies or generation. Locked props are checked across adjacent cuts. When ffmpeg is installed, a small preview is rendered. When it is not, the edit decision list is still written. Ron approves an `edit` gate before sound. That approval is picture lock. The proof is Harbor Night plus tiny synthetic clips. Nothing was spent. The Last Marker was not cut.

Phase 6 is on main. It merged on 2026-11-11 in [pull request 9](https://github.com/Roncho512/Movie-swarm/pull/9), merge `8d0de69`. After picture lock, the Sound Designer and the Composer spot a cue sheet onto the cut: dialogue, sound effects, foley, ambience, and music. Each cue has a start and end, the shots it belongs to, a prompt, and a source of generated, library, or silence. Music follows `audio/score-brief.json` when the production has one, including the shots that brief leaves silent. A cue has to sit inside the cut. An effect tied to a shot is flagged when it lands outside a short sync tolerance. A prop sound is flagged when that prop is not in the shot. The plan is priced from the rate card against the Sound line. That card has no audio rate, so the price is marked unknown. A paid call waits on the generation gate. When ffmpeg is installed, placeholder stems and a temp mix are rendered. When it is not, the cue sheet is still written. Ron approves a `sound` gate before color and mix. The proof is Harbor Night plus tiny synthetic audio. Nothing was spent. The Last Marker was not spotted.

Phase 7 is on main. It merged on 2026-11-11 in [pull request 10](https://github.com/Roncho512/Movie-swarm/pull/10), merge `82fdbf5`. After the edit gate and the sound gate are both approved, the Colorist grades the locked picture and the Re-recording Mixer mixes the stems. A grade plan is the color: one base grade for the whole cut, plus one adjustment per scene, read from `look/look.json` and from `look/grade.json` when the production has one. A mix plan is the sound: a level for each stem, dialogue in front, music and effects ducked under dialogue, and a fade at each scene change. Loudness is checked against EBU R128, or against `audio/mix-targets.json` when the production sets its own target. EBU R128 is a published delivery standard: -23.0 LUFS, true peak no higher than -1.0 dBTP. The rate card has no color or mix price, so that estimate is marked unknown and is not stored as zero. When ffmpeg is installed, it renders a low-resolution graded preview, the mix, and a married preview of picture plus sound. When it is not, the plans are still written. Ron approves a `color-mix` gate before final delivery. The proof is Harbor Night plus tiny synthetic video and audio. Nothing was spent. The Last Marker was not graded or mixed.

Phase 8 is on main. It merged on 2026-11-11 in [pull request 11](https://github.com/Roncho512/Movie-swarm/pull/11), merge `3fa56c0`. The Post Supervisor reads `delivery/delivery-spec.json` from the production folder and writes a delivery package: a master file, the web or social variants the spec asks for, a poster frame, and captions timed from the dialogue cues. QC checks duration, resolution, frame rate, loudness, black frames, frozen frames, and caption timing. The report is JSON plus a short Markdown table. A delivery manifest lists the files, a SHA-256 checksum for each one that was written, the film spend against the $500 cap, the stage split, and every gate record. The package folder follows `MOVIE_SWARM_ASSET_ROOT` or `config/assets.json`. No drive path is hard-coded. Ron approves a `delivery` gate to mark the film delivered. One command, `scripts/studio.py`, walks Harbor Night from the treatment through that package and stops at each gate. A test harness can approve those gates. The command line cannot. The generation gate stays closed. Nothing was spent. The Last Marker was not delivered.

Phase 8.5 wires the provider clients. A provider is the company that makes the picture, the sound, or the text. Anthropic is the text provider. fal is the picture provider. ElevenLabs is the sound provider. A real call is sent only when all four of these are true: the generation gate is approved, the estimate fits the remaining money on that stage line and under the $500 cap, the key for that provider is in the environment, and the command was given `--live`. Offline stays the default. A test shot is one picture call for one shot. The command is on the Line Producer. It was not run live. The rate card still has no price for audio, color, or delivery, and no fal address for Gemini Omni or Kling, so those calls are refused. Spent so far: $0.00 of $500.00. The Last Marker was not generated.

Phase 8.6 adds six prep roles, on top of the Phase 8.5 branch. The Assistant Director writes a shooting schedule and a call sheet from the shot list and the scenes, and flags stunt beats. The Gaffer writes a lighting plan from the camera package. The Key Grip writes camera support and rigging from that plan and the shot list. The Costume Designer and Makeup and Hair lock per-character specs the way the Prop Master locks props. The Script Supervisor, the dailies review, and the edit check those locks for drift. The VFX Supervisor writes a breakdown and turnover notes for the editor and the colorist, then reviews the VFX shots after dailies. No new gate was added. The new roles bill against lines that are already in the locked split. The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Phase 8.7 adds Title and Graphic Design, on top of the Phase 8.6 branch. The role reads the treatment, the screenplay, the brief, the style bible, and the director's notes, and writes that research down before it designs anything. The brand guide is built only from the research. Titles, title cards, end credits, subtitle styling, a designed poster, and the collateral are built only after the guide is approved. The Art Director still owns the in-film look. Subtitle timing stays with the Post Supervisor. A graphics gate starts closed. The role bills to the Art line. The locked $500 split did not change. The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Phase 8.8 adds one budget per film and the Trailer Editor, on top of the Phase 8.7 branch. The budget lives in `budget.json` in the production folder. One calculator, `tools/budget-calculator/index.html`, shows the whole film, including the trailer when it is on. A film with no budget file keeps the $500 cap and the locked split. Going past the budget still pauses and writes an approval request. Ron can approve that overage without editing the budget. The Trailer Editor is role 20. It runs only when the budget turns the trailer on, it cuts from approved takes, and it bills to Marketing and Distribution. A trailer gate starts closed. The film can deliver without it. The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Phase 8.5, Phase 8.6, Phase 8.7, and Phase 8.8 merged to main on 2026-11-12 in [pull request 12](https://github.com/Roncho512/Movie-swarm/pull/12), merge `67a60f2`.

Phase 8.9 is on main. It merged on 2026-11-12 in [pull request 13](https://github.com/Roncho512/Movie-swarm/pull/13), merge `607eea4`. The commands in `scripts/` load a repo-root `.env` and do not override variables already set in the shell. They do not print the values. A test shot takes `--model` or `--tier`. The order is the flag, then the tier flag, then the film's budget tier, then the routing file. The picture tiers in that file match the budget rate card. Gemini Omni 1.2 Flash stays the good tier and stays planned, with no fal address. A live call for a model with no endpoint is refused and lists the wired models. It does not switch models. A dry run prints the model, the tier, the provider, the resolution, the duration, the estimated cost, and the money left, and says nothing was sent. The same summary is printed before a `--live` call. `scripts/doctor.py` checks the machine without spending. The guide is [START-HERE.md](START-HERE.md). The proof is Harbor Night. Nothing was spent. The Last Marker folder was not changed.

Phase 8.10 is on main. It merged on 2026-11-12 in [pull request 14](https://github.com/Roncho512/Movie-swarm/pull/14), merge `8578f4d`. The queue body is the input fields themselves. Status and result reads use the URLs the submit response returns. A shot is rounded up to a length the model accepts, and the estimate uses that length. The cheapest Seedance 2.0 fast shot is 4 seconds at 720p, $0.9676. A call that fails validation, and produces nothing, releases the booked estimate and leaves the original ledger row in place. `release --entry` does the same thing by hand. No paid call was made in that phase. The proof is Harbor Night. The Last Marker folder was not changed.

Phase 8.11 is on main. It merged on 2026-11-12 in [pull request 15](https://github.com/Roncho512/Movie-swarm/pull/15), merge `c98ef2f`. A Seedance job can take a few minutes, so a fal picture call now waits 10 minutes by default. The pauses start at 5 seconds and grow to 15. A short progress line prints about every 30 seconds. `--wait` sets a different wait for one test shot. A timeout still leaves the estimate booked, and a re-run checks the same request. The older fal queue helpers post the input fields at the top and use the URLs fal returns. Doctor says whether the asset root came from the shell, from `.env`, or from `config/assets.json`, and whether that folder exists. It does not print the path. When fal does not report a dollar amount, the ledger marks `actual_source` as `estimate`, and status says that part of the spend is still the estimate. No paid call was made in that phase. The proof is Harbor Night. The Last Marker folder was not changed.

The first film is underway. Ron said on 2026-11-12 to do The Last Marker from the top. D41 is lifted for that film only. The working film lives in the films folder, outside this repo (D129). `productions/the-last-marker` is an archived copy. The earlier treatment and previs approvals are in that copy's `archive/`. The live treatment is a draft. Run `first-film-1` stops at the treatment gate. `budget.json` is the quote. Spent on this step: $0.00. No live call was made.

Phase 8.12 gives Claude writing calls their own approval, separate from the generation gate (D130). `--live` on a text call prints a quote and sends nothing until Ron records that approval for the run. The quote names the model, an input-token estimate, the max output tokens, and the worst-case dollars. Picture and audio calls still wait on the generation gate. The rate card now has Anthropic's published text prices, read on 2026-11-12. After a live text call, the ledger books the reported token counts times those prices. It merged on 2026-11-12 in [pull request 17](https://github.com/Roncho512/Movie-swarm/pull/17), merge `41bd177`. The proof is Harbor Night with a fake transport. The archived film folder was not changed. No live call was made in that phase.

Phase 8.13 fixes the live treatment draft (D136). The paid draft on run `first-film-1` was sent the first 12,000 characters of the screenplay and none of the locked files, then the reply was thrown away. The note still said no model was called. A live draft now sends the screenplay up to 120,000 characters. When a file is longer than that, the prompt and the draft note say it was cut. `treatment/inputs.json`, `props/hero-props.json`, `props/prop-definitions.json`, and a spec file under `props/<name>/` are included when the film has them. The offline draft does not read those prop files and does not change. The model is told the required treatment keys, taken from the schema, and told not to re-ask a locked fact. `theme` and `emotional_intent` are folded into `theme_and_emotional_intent`. `tone` and `genre` are folded into `tone_and_genre`. A version that is not semver becomes `0.1.0`. A blank deliverable is filled from the offline draft. A required field that is still empty is filled from that draft and checked again. The offline draft is kept only when the reply is still not valid. That note lists the schema errors, says the call cost was booked, and does not say that no model was called. The raw reply is saved at `runs/<run>/rejected-draft-<hash>.txt`. Running the same request again is still free, because the provider cache replays it. This prompt is not the one that was paid, so that replay will not match. `reconform --request <hash>` reads the saved response and does not call the model. It merged on 2026-11-12 in [pull request 18](https://github.com/Roncho512/Movie-swarm/pull/18), merge `fc259e2`. The proof uses a fake model. No live call was made in that phase.

Phase 8.14 fixes the final treatment pass (D141). On run `first-film-1` the Opus pass was allowed 8,000 output tokens, used all of them, and the reply stopped inside the last notes field. The parse failed, the earlier draft was kept, and the answer merge wrote a confirmation over the drafted tone and pasted a withheld answer onto more than one scene. The final pass now allows 16,000 tokens. It may return the whole treatment or only the fields it changed. If the provider stops because the reply filled the cap, the draft note and the command output say so. A reply that still cannot be read is saved at `runs/<run>/rejected-final-<hash>.txt`. `reconform --request <hash>` also reads a final-pass reply. It closes a JSON object that was cut off, drops the unfinished field, fills anything still required from the current draft, and writes the treatment. It does not call a model and it does not book. An approved treatment is left alone. Answers already stored are not wiped. A confirmation such as `Lock.` keeps the drafted text and the note says that field was locked. A leading `That's all:` is not copied into the treatment. A withheld fact is written once, on the last scene. The writing quote estimates input tokens as the character count divided by 3, plus 25 percent, plus 200 tokens, rounded up, and the ceiling check uses that worst case. For the recorded prompts that quote is at least what was booked. The proof uses fakes. No live call was made in that phase. It merged on 2026-11-12 in [pull request 19](https://github.com/Roncho512/Movie-swarm/pull/19), merge `2d0fe4e`.

Phase 8.15 fixes the previs package (D147). A character lock matches a surname, a first name, a screenplay cue, and any alias on the lock. A shot is tagged with the people and the hero props its text shows, including a prop part named on the lock. A long wardrobe paragraph matches its short garment facts, or a `wardrobe lock: <id>` line, and a contradicting phrase still fails. The storyboard section is "Hero prop moments". A shot that shows a hero prop says so in the continuity note, and its prompt carries that prop's locked spec and reference-image paths. A confirmation is not a stunt beat, and a note is not a stunt shot. Time of day is read from the scene heading, and "moments later" and "continuous" keep the previous time. A sun line is not copied into the practicals. An older `shot-lists/shot-list.json` is marked superseded when the storyboard list is the one generation uses. It is kept, it is not checked for drift, and it is not sent to generation. Shot lengths stay between 1 and 12 seconds unless the screenplay names a hold, and the boards say when a length moved. Graphics research reads a year from the logline and from the world. The shooting schedule lists the hero props and writes each safety line as a full sentence. After `reconform` succeeds, a stale "the final model pass failed" sentence is replaced with the repair history. `scripts/studio.py --redo previs` regenerates that package offline and refuses when the previs gate is already approved. The proof is Harbor Night and synthetic shots. No live call was made. Spent: $0.00 of $500.00. It merged on 2026-11-12 in [pull request 20](https://github.com/Roncho512/Movie-swarm/pull/20), merge `b0e77dd`.

Phase 8.16 follows that previs pass (D155). A pronoun inherits the only locked character in the scene, or the most recent shot that named exactly one, and the wardrobe and makeup lines then ride on the prompt. If the pronoun could mean more than one person, the shot is listed for review and is not guessed. A lock can list `generic_nouns`. Ordinary nouns for a kind live in `config/kind-nouns.json`, and a film replaces a kind in `props/kind-nouns.json`. Those nouns match only when exactly one locked prop has that kind. A shot that continues the previous shot's action can carry that one prop forward, and the board says so. A placement line describes the story. The engine will not write "product shot", "advert", "sponsor", "commercial", or the same words inside a negation. Generated previs text is scanned, and a banned phrase fails the continuity check. "The detail stays readable." is added only when the brief asks for a legible detail. It is a focus instruction. "Fifteen minutes of day left" is not a time-of-day change against a pre-dusk heading. "At dawn" and "night falls" still are. Every stunt beat is on the schedule's safety list, with the full safety sentence. When the 1–12 second limits leave a scene short, the remainder fills other shots in that scene that still have room. If they do not, the boards say so. `reconform --request <hash>` on an already approved treatment removes a stale "the final model pass failed" sentence from the draft note. It does not call a model, and it does not change the approved scenes, the approval block, or the gate. The proof is Harbor Night and synthetic shots. No live call was made. Spent: $0.00 of $500.00.

Phase 8.16.1 puts the people matcher back on the storyboard (D164). A locked person who is not already on the shot is matched with the same word-boundary check as the catalog. It merged on 2026-11-13 in [pull request 22](https://github.com/Roncho512/Movie-swarm/pull/22), merge `067c1df`. No live call was made.

Phase 8.17 follows that previs pass (D165, Ron, 12 Nov 2026). A phrase such as "left the X", "leaves the X behind", "walks away from the X", "without the X", or "looks back at the X" does not put the prop in the shot. Those phrases live in `config/absence-phrases.json`, and a film can replace a list in `props/absence-phrases.json`. If a phrase could still show the prop, the shot is listed for review and is not guessed. A prop carried from the previous shot stops at a close-up, an insert, or an extreme close-up of some other object, and it stops when the shot's subject is something else. A line that is only sound, a fade, a hold, black, or a title does not carry a prop, and the board says it needs review. If the previous shot only mentioned the prop in an absence phrase, there is nothing to carry. When a vehicle passes the camera and exactly one person in the scene rides it, that person is tagged and the wardrobe line follows. If the rider is not one clear person, the shot is listed for review. When a scene's shots are all at the 12 second cap, any leftover time is spread across shots in other scenes that still have room, and the pacing note names the scene that absorbed it. If no shot anywhere has room, the boards still say so. The proof is Harbor Night and synthetic shots, including the Mina Cole yard scene. No live call was made. Spent: $0.00 of $500.00. It merged on 2026-11-13 in [pull request 23](https://github.com/Roncho512/Movie-swarm/pull/23), merge `10467c0`.

Phase 8.17.1 is a hotfix on that pass (D171, Ron, 12 Nov 2026). The continuity check uses the storyboard's prop tags, or the same absence phrases, and does not treat a bare name as the prop in frame (D172, proposed). "Has left the X", "had left", and "has abandoned" are absence, including when an alias is "the X" and the sentence ends. Only the ambiguous list, such as "left the X in", "on", "running", or "there", is a review (D173, proposed). Ride language anywhere in the scene, including an earlier shot and the scene description, and forms such as "on a vehicle", "rides", and "riding", names the one rider when that vehicle passes. A shot-size line such as "LOW ANGLE." is not the subject. If the rider is not one person, the shot is listed for review (D174, proposed). The proof is Harbor Night and the synthetic Mina Cole yard scene. No live call was made. Spent: $0.00 of $500.00. It merged on 2026-11-13 in [pull request 24](https://github.com/Roncho512/Movie-swarm/pull/24), merge `3d89bee`.

Phase 8.17.2 is a hotfix on that pass (D175, Ron, 2026-11-13). A perfect-tense absence with nothing after the object is clear. The end of the clause, punctuation, or a conjunction that starts the next clause counts as nothing. Those conjunctions live in `closed_clause` inside `config/absence-phrases.json`, and a film replaces that key in `props/absence-phrases.json` along with the phrase lists (D176, proposed). A continuation in the same clause, such as "in", "on", "running", or "there", is still a review. The storyboard review and the frame classifier read that same file. The proof is Harbor Night and a synthetic yard paragraph in the shape of a departure shot. No live call was made. Spent: $0.00 of $500.00. It merged on 2026-11-13 in [pull request 25](https://github.com/Roncho512/Movie-swarm/pull/25), merge `23670b7`.

Phase 8.17.3 is a hotfix on that pass (D178, Ron, 2026-11-13). A trace a part leaves behind does not count as the prop being named. A label immediately followed by a trace noun, with a space or a hyphen, is that trace. "Tire tracks", "prints", "ruts", and "skid marks" are traces. "The front tire spins", "he kicks the tire", and "the tire is flat" still name the prop. Those nouns live in `trace_nouns` inside `config/absence-phrases.json`. A film adds nouns in `props/absence-phrases.json` and the shared nouns stay (D179, proposed). The storyboard review, the frame classifier, and the continuity check read that same file. The proof is Harbor Night and a synthetic yard paragraph in the shape of a departure shot. No live call was made. Spent: $0.00 of $500.00. It merged on 2026-11-13 in [pull request 26](https://github.com/Roncho512/Movie-swarm/pull/26), merge `290940f`.

Phase 8.17.4 is a hotfix on that pass (D180, Ron, 2026-11-13). A trace does not stop a prop that was in the previous shot of the same scene from carrying. The trace does not name the prop, and it is not an absence. Carry without a shared verb applies only when the shot has a trace of that prop (D182), and the other stop rules still pass: no absence phrase, not a close-up or insert of another object, not a different subject, and not only sound, a fade, a hold, black, or a title. Otherwise again, another, still, or a shared action verb is still required. A trace that opens the shot is not a different subject (D181, proposed). After a clear absence, a later trace does not bring the prop back. The storyboard review, the frame classifier, and the continuity check still share that decision: the classifier says the trace is unnamed, the board carries the tag and says so, and the check follows the tag. The proof is Harbor Night and synthetic yard lines. No live call was made. Spent: $0.00 of $500.00. It merged on 2026-11-13 in [pull request 27](https://github.com/Roncho512/Movie-swarm/pull/27), merge `691e0dc`.

Phase 8.18 is the graphics gate pass (D183, Ron, 2026-11-13). A TITLE CARD's displayed words are the title or the card copy. Background and typography on the cue are design direction, and a phrase such as a named typography style is carried into the research and the guide. When a brief has a featured object, the placement rules reach the research, the brand guide, and the key art, and the guide does not present that object as something for sale. The role also reads offline packs in `config/design-references/`. A pack applies when the production's own genre, tone, or look uses its terms, or when the pack is marked always. Suggestions are labeled `DESIGNER PROPOSAL` and cite a reference. Facts from the production documents are labeled `SOURCED FROM PRODUCTION DOCS`. Credits use the face the active design-reference pack names for that role (D194). The sans-serif credits clause in D183 is superseded. The engine does not force a category. The guide can propose a title face, a credits face, subtitle and marketing faces, a custom title lettering description, layout, a safe area, and hex values. The custom lettering is not a built font. The guide stays a draft until Ron approves the graphics gate. No model is called and no network research runs on this path. A live research mode is planned (D192, Ron, 2026-11-13) and stays off. It is not built in this phase. The proof is Harbor Night plus a synthetic card, a synthetic featured object, and a look whose name matches the checked-in pack. The archived film folder was not changed. No live call was made. Spent: $0.00 of $500.00. This phase is on branch `phase-8.18-graphics-designer`. There is no pull request. Ron opens that himself.

Ron approved the graphics gate on the external brand guide v4 on 2026-11-13 at 10:40 PM CT (D196). The western design-reference pack is now 2.0.0. Credits are Caprasimo, with Fraunces for the glyphs Ł ł Ń ń. Subheads and section labels are Alfa Slab One. Body, billing, and burned-in subtitles are Old Standard TT. The title direction is painted pulp capitals. Rye and Sancreek are mockup stand-ins, and the final is hand-drawn later. Burned-in subtitles are Old Standard TT Bold, sentence case, bone #E8DCC8 with a 1 px charcoal edge, bottom-centre inside the 2.39:1 picture, at most two lines. Noto Sans is only for player-rendered SRT and VTT files. The palette keeps blue dusk #4A5D7A, adds cool dusk blue #6B7F96 and dust #BFAE93, and holds #14110E black for print. End credits and the billing block come from `credits/film-credits.json` in the film folder when that file is present. Placeholder names are marked FICTIONAL PLACEHOLDER. Agent credits stay in a separate "Made with Movie-swarm crew" section (D197, proposed). The archive keeps an example of the credits file and does not keep the live file. Approved key art is `graphics/brand/key-art-poster.png` in the working film folder. The build references that file and does not draw a stand-in (D197, proposed). No image was generated. Spent on this step: $0.00. This work is on branch `graphics-v4-design-pack`. There is no pull request. Ron opens that himself.

Reference images on a Seedance picture call are proposed (D198). When a shot has photographs the model can take, and the rate row names reference-to-video, the call uses that endpoint instead of text-to-video. The order is character face, then location, then prop, then the shot's own `reference_images`, one image per subject before a second from the same subject, capped at 9. Faces come from a locked `characters/character-lock.json`, or from `reference_images` on a locked costume entry when the character lock has none. Places come from a locked `locations/location-lock.json`, matched to the shot's setting. Props come from the locked hero-prop file. Paths are relative to the film folder. A live call uploads them with the fal client and sends the URLs. A missing file is logged and skipped. A dry run lists the files and uses fal's published reference price. It does not upload and it does not open a network connection. Fast image references are $0.2419 per second at 720p, the same as fast text-to-video. Seedance 2.0 image references are $0.3024 per second. A shot with nothing to send stays on text-to-video. The engine does not name a film (D30). No live call was made. This is proposed. Ron has not accepted it.

A later phase is planned and not started (D184, Ron, 2026-11-13). A Script Supervisor and 1st AD pass would draft a machine-readable scene and shot breakdown and stop for Ron before previs. The human-readable script and treatment stay as they are. No code for that pass is in this phase. The number 8.19 on the roadmap is a filing choice (D190, proposed).

Two further phases are planned and not started. A visual brand guide PDF (D191, Ron, 2026-11-13) is what Ron reviews at the graphics gate once he gives the go: color swatches with hex codes, rendered font specimens and type rules, text and credit-block rules, hero-prop imagery that follows the locked specs and the placement rules, and at least one scene or key-art frame. Paid images use the art director line and generation approval. The PDF layout is offline. The engine stays generic (D30). For The Last Marker, Ron's Grok Bot designer teammate, Beautiful 3, is producing the first such PDF by hand as the reference example. Drafts of that guide were produced outside this repo. Ron approved the graphics gate on v4 (D196, Ron, 2026-11-13). The PDF is not added here (D195, proposed). A live designer research mode (D192, Ron, 2026-11-13) lets the studio designer research the film's period, genre, posters, fonts, and colors, with citations, and write a reference pack for Ron to approve. It is a metered paid step on the art director line, behind gate approval, and it is never on by default. Today the designer still reads the offline packs from Phase 8.18 (D186). The roadmap files these as 8.20 and 8.21. With 8.19, those numbers are not a start order. No code for either pass is in this change.

Film facts stay in the production folder. The engine does not know that this film's exhaust is on the right, that the watch is on the left wrist, that the bike is a 1965, that the story is 1967, or that the look is Techniscope 35mm (2-perf, 2.39:1) in a Leone-style sun-blasted grainy spaghetti western, pushed harder (D193). Those sentences live in the film folder. A different film uses its own files. The pilot sound prompts moved out of the sound program and into the film's `audio/sound-prompts.json`. The archived copy still has that file.

The continuity check on the old pilot shot list found 17 missing locks. Each one is the Triumph shown without the locked exhaust phrase. The new storyboard states the locks. No money was spent.

Older pilot clips of scenes 1 and 2 are still in the production folder. They are not a finished film.

## Run it locally

From the repo root. The longer setup, including the virtual environment and `scripts/doctor.py`, is in [START-HERE.md](START-HERE.md).

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pytest tests -q
python3 scripts/validate-schema.py --production productions/the-last-marker
```

That last command checks the archived copy in this repo. The working film is checked the same way with `--production the-last-marker` once `MOVIE_SWARM_FILMS_ROOT` is set, or with the absolute path of the film folder.

See where the working film stands:

```bash
python3 scripts/line-producer.py --production the-last-marker --run first-film-1 status
python3 scripts/line-producer.py --production the-last-marker --run first-film-1 budget
```

Draft again from the screenplay. This does not approve anything. The live treatment is already a draft, so intake is allowed. It reads `treatment/inputs.json` and `budget.json`, and it replaces the draft. If the treatment were still approved, intake would stop and tell you not to draft again. The draft stays offline unless you pass `--live`. `--offline` is the same default, written out.

```bash
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline intake
```

Answer the Director. Open `treatment/questions.json` in the film folder. Type each answer in the `answer` field. Leave a field as `null` if you are not ready. Then:

```bash
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline answer \
  --answers treatment/questions.json
```

You can also send a separate answers file:

```json
{
  "round": 1,
  "answers": [
    {"id": "q-intent", "answer": "Lock it."}
  ]
}
```

Approve the treatment after you have read `treatment/treatment.md`. This is the only way the treatment becomes approved. It also locks the stage split, which is how the $500 is divided across jobs.

```bash
python3 scripts/line-producer.py --production the-last-marker --run first-film-1 approve-gate \
  --stage treatment --decision approved --by ron --note "Lock the treatment and the split."
```

Reject it the same way, with `--decision rejected`. You can put the same fields in a JSON file and pass `--file` instead of the flags.

Write the phase 2 package. These calls do not spend money. They pause until the treatment gate is approved. They do not approve the previs gate.

```bash
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent prop-master --crew-command lock --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent costume-designer --crew-command lock --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent makeup-hair --crew-command lock --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent cinematographer --crew-command package --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent cinematographer --crew-command boards --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent gaffer --crew-command plan --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent key-grip --crew-command plan --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent stunt-coordinator --crew-command breakdown --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent assistant-director --crew-command schedule --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent vfx-supervisor --crew-command breakdown --estimate 0
python3 scripts/director.py --production the-last-marker --run first-film-1 --offline dispatch \
  --agent script-supervisor --crew-command check --estimate 0
```

Wardrobe definitions, when the production has them, live in `wardrobe/costume-definitions.json`. Makeup and hair live in `makeup/makeup-definitions.json`. VFX notes live in `vfx/vfx-needs.json`. A production with none of those files still gets a lock or a breakdown, and the role does not invent a garment, an effect, or a shot.

Approve the package after you have read the files under `props/`, `wardrobe/`, `makeup/`, `continuity/`, `camera/`, `storyboard/`, `lighting/`, `grip/`, `schedule/`, `stunts/`, and `vfx/`.

```bash
python3 scripts/line-producer.py --production the-last-marker --run first-film-1 approve-gate \
  --stage previs --decision approved --by ron --note "The phase 2 package can go forward."
```

A picture call does not run until you have approved the treatment, the previs package, and that stage. This example only prices shots with the older production estimator. It does not generate video.

```bash
python3 scripts/director.py --production the-last-marker --run first-film-1 dispatch \
  --agent production --crew-command estimate --estimate 0 \
  --shot-list shot-lists/shot-list.json
```

Ask for a generation plan. A generation plan is a dry-run quote: the generator, the clip length, the takes allowed, and the price, set against the locked split. It does not spend, and it does not need the generation gate. This phase proved the command on Harbor Night. It did not write a plan for The Last Marker.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 dispatch \
  --agent production --crew-command plan --estimate 0 \
  --output-dir path/to/a-folder
```

A generate call is the paid path. It pauses until you approve the generation gate. Without `--live`, it still does not call a provider. With `--live`, it can call, and it sends every shot that passes the checks. Use the test shot below when you want exactly one call.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage generation --decision approved --by ron --note "A paid generation may be prepared."
```

Review the takes before the edit. A takes manifest is a JSON file that lists each generated clip or frame and the shot it belongs to. The checklist is `schemas/takes-manifest.schema.json`. This command does not call a vision model and does not spend. If a text file sits beside a frame and has the same name plus `.txt`, that text is the picture description. Tests pass a fake description instead. A required phrase that never appears is a retake. A missing file is a reject.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent dailies --crew-command review --estimate 0 \
  --takes path/to/takes-manifest.json
```

Read `dailies/dailies-report.md`. The VFX review reads that report and the breakdown:

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent vfx-supervisor --crew-command review --estimate 0
```

Then approve the circled takes. Until you do, the editor does not run. The VFX review does not add a gate.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage dailies --decision approved --by ron --note "The circled takes can be cut."
```

Assemble the circled takes. This does not spend. It also waits until you have approved the treatment, the previs package, and the editor's own gate. The shot order comes from the storyboard. A production can set transitions and the runtime tolerance in `edit/editing-style.json`. The default join is a cut.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent editor --crew-command assemble --estimate 0
```

Read `edit/rough-cut.md`. The checklist is `edit/rough-cut.json`. The reading copy is `edit/assembly.edl`. A clean cut also writes `edit/picture-lock.json`. That file is not locked until you approve the edit gate. Sound does not run until you do.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage edit --decision approved --by ron --note "Picture lock."
```

Spot sound and score onto that cut. This does not spend. It also waits until you have approved the treatment, the previs package, and the sound designer's own gate. Prompts come from `audio/sound-prompts.json`. Music comes from `audio/score-brief.json` when that file exists. A prop can carry a sound in the prop file. The cue plays only in shots that show the prop.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent sound-designer --crew-command spot --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent composer --crew-command spot --estimate 0
```

Read `sound/cue-sheet.md`. The checklist is `sound/cue-sheet.json`. When ffmpeg is installed, placeholder stems land in `sound/stems/`. A generate call is the paid path. It pauses until you approve the generation gate. Without `--live`, it does not call ElevenLabs. The rate card has no audio price, so a live sound call also needs `--price-override` and your approval of that one amount.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage sound --decision approved --by ron --note "Color and mix can start."
```

Grade the locked picture and mix the stems. Both calls wait until the edit gate and the sound gate are approved. They do not spend. The grade is read from `look/look.json`. Scene adjustments, a LUT, and the consistency tolerance come from `look/grade.json` when that file exists. A LUT is a color lookup table, a file the production can supply. The mix is read from `sound/cue-sheet.json` and the stems. Loudness uses EBU R128 unless `audio/mix-targets.json` sets another target.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent colorist --crew-command grade --estimate 0
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent mixer --crew-command mix --estimate 0
```

Read `color/grade-plan.md` and `color/mix-plan.md`. The checklists are `color/grade-plan.json` and `color/mix-plan.json`. When ffmpeg is installed, the graded picture is `color/graded-preview.mp4`, the mix is `color/mix.wav`, and the married preview is `color/married-preview.mp4`. Final delivery does not run until you approve the color-mix gate.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage color-mix --decision approved --by ron --note "Final delivery can start."
```

Package the locked cut. This does not spend. The sizes, the variants, the poster shot, and the caption mode come from `delivery/delivery-spec.json`. When that file leaves a field out, the plan uses a cited platform default and says so. Captions are built from the dialogue cues. When ffmpeg is installed, it renders the master, the variants, and the poster. When it is not, the plan and the caption sidecars are still written. QC then checks each file. The manifest is the package list.

```bash
python3 scripts/director.py --production path/to/a-production --run phase-1 --offline dispatch \
  --agent post-supervisor --crew-command deliver --estimate 0
```

Read `delivery/delivery-plan.md`, `delivery/qc-report.md`, and `delivery/delivery-manifest.md`. Approve the delivery gate to mark the film delivered.

```bash
python3 scripts/line-producer.py --production path/to/a-production --run phase-1 approve-gate \
  --stage delivery --decision approved --by ron --note "The film is delivered."
```

The same commands work from the agent folders as `python3 -m src.cli`, with the same flags.

## How to make a film with the studio

This is the path from a treatment to a delivered file. A gate is a switch that makes a stage wait for Ron. The studio command stops at the first closed gate. Approve that gate, then run the command again. It does not approve anything by itself, and it does not spend.

Practice on Harbor Night. It is the synthetic fixture under `tests/fixtures/harbor-night`. Copy it if you do not want to write into the fixture:

```bash
cp -a tests/fixtures/harbor-night /tmp/harbor-night
python3 scripts/studio.py --production /tmp/harbor-night --run studio-1
```

The first run stops at the treatment gate. Nothing after that is written yet. Approve the gate, then run the same command again:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run studio-1 approve-gate \
  --stage treatment --decision approved --by ron --note "Lock the treatment and the split."
python3 scripts/studio.py --production /tmp/harbor-night --run studio-1
```

Keep going. Each run stops at the next closed gate and tells you the name. The order is:

1. `treatment`. Read `treatment/treatment.md`. Approving it locks the $500 split.
2. `previs`. The prop lock, wardrobe, makeup, the continuity check, the camera package, the storyboard, the lighting plan, the grip plan, the shooting schedule, the action breakdown, the VFX breakdown, and the title research and draft brand guide are written first. Then you approve them.
3. `graphics`. Read `graphics/brand-guide.md`. Ron approved the external brand guide v4 (D196, Ron, 2026-11-13). A visual brand guide PDF is planned for this same review (D191) and is not in this repo. When it is built, this gate shows that PDF: color swatches with hex codes, rendered font specimens and type rules, text and credit-block rules, hero-prop imagery that follows the locked specs and the placement rules, and at least one scene or key-art frame. Approving this gate lets the titles, the credits, the key art, and the collateral be specced.
4. `production`. This lets the generation quote be written. It does not open a paid call.
5. `dailies`. If the production has no takes manifest, the offline run writes synthetic placeholder clips and says so in `takes/placeholder.txt`. Those are not generated pictures. A real takes file is left alone. The VFX review is written with the dailies report.
6. `editor`. This lets the circled takes be cut. Title and credit overlays are in the reading copy when the graphics package exists.
7. `edit`. That approval is picture lock. Read `edit/rough-cut.md` first.
8. `sound-designer`. This lets the cue sheet be spotted.
9. `sound`. Read `sound/cue-sheet.md`. Color and mix wait on this approval.
10. `color-mix`. The grade and the mix are written first. Read `color/grade-plan.md` and `color/mix-plan.md`.
11. `delivery`. The package is written first. The manifest lists graphics files when they are present. The frame-grab poster stays `poster.png`. The designed poster is `key-art-poster.png`. Read the QC report and the manifest. Approving this gate marks the film delivered.

The generation gate is not in that list. Leave it closed until you are ready to pay for pictures. The studio command never passes `--live`. Harbor Night's offline run spends $0.00.

To regenerate previs when the treatment is already approved and the previs gate is still closed:

```bash
python3 scripts/studio.py --production the-last-marker --run first-film-1 --redo previs
```

The same flag works on any production folder. It is offline. It does not approve the gate. If the previs gate is already approved, the command stops and leaves the files and the gate as they are.

A real production is the same two commands, with that film's folder instead of `/tmp/harbor-night`. If it has no treatment yet, draft one first with `scripts/director.py` and the `intake` command, answer the questions, and then start the studio command. Do not run this path on The Last Marker until the first-film phase. Its approved previs stays where it is.

The delivery spec is `delivery/delivery-spec.json` in the production folder. Harbor Night's spec asks for a small H.264 master, a 16:9 web file, a 9:16 center crop, sidecar captions, and a poster from shot `s01-sh01`. A different film puts its own sizes in that file. The package is written under `delivery/` inside the production folder unless you set a drive. Set `MOVIE_SWARM_ASSET_ROOT`, or set `asset_root` in `config/assets.json`. The code does not name a drive.

When ffmpeg is installed, the package can include `master.mp4` (or a ProRes master when the spec asks and the encoder exists), the variant files, `poster.png`, `captions.srt`, and `captions.vtt`. When ffmpeg is missing, those picture files are skipped and the plan, the captions, the QC report, and the manifest are still written.

Tests can call `run_studio(..., auto_approve=True)`. That is a test harness. It records the approver as `test-auto-approve`, not as Ron, and it still leaves the generation gate closed. `scripts/studio.py` and the Director's `studio` command do not pass that flag. Do not use it on a real film.

## One live test shot

A test shot is one picture call for one shot. It does not send anything unless you pass `--live`. The commands in `scripts/` load `.env` from the repo root. A variable already set in the shell wins. The values are not printed. `.env.example` lists the names with empty values. `.env` is ignored by git. Doctor says whether each key is present. It prints yes or no.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run studio-1 test-shot \
  --shot s01-sh01 --model seedance-2.0-fast
```

That prints the quote and does not call a provider. The cheapest real Seedance 2.0 fast shot is 4 seconds at 720p, $0.9676. Harbor Night's first shot is 2.087 seconds, so the dry run says `duration 2.087 seconds (sent as 4 seconds), estimated cost $0.9676.` `--tier better` names the same model. When that shot has reference images and the model has a reference-to-video endpoint, the same dry run names that endpoint, the price per second, and the files that would be sent, character face first, then the location, then the prop, then the shot's own images. Fast image references stay $0.2419 per second, so a 4 second fast shot is still $0.9676. Seedance 2.0 image references are $0.3024 per second, so a 4 second shot is $1.2096. The dry run does not upload the files. A shot with no image that can be sent keeps the text-to-video quote and does not add that list. To send the one call, all of these have to be true:

1. You approved the generation gate on that run.
2. The estimate fits the money left on the Production line ($270 in the locked split) and under the $500 cap.
3. `FAL_KEY` is set in the environment.
4. You pass `--live`.

A text call does not use that gate. Offline is still the default. `--live` prints the model, the input-token estimate, the max output tokens, and the worst-case dollars, then stops. The treatment file stays as it is. Ron records a ceiling with `approve-writing`. The next `--live` sends the call when that worst case fits the ceiling, the stage line, and the film cap. The commands for the first film are in [START-HERE.md](START-HERE.md).

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run studio-1 --live test-shot \
  --shot s01-sh01 --model seedance-2.0-fast
```

The same quote is printed before that call. A Seedance job can take a few minutes. The command waits 10 minutes by default, pauses 5 seconds and then up to 15, and prints a short progress line about every 30 seconds. `--wait 900` waits 900 seconds for this one shot. The numbers are in `config/providers.json`. The good tier, and the preview purpose in the routing file, is still Gemini Omni 1.2 Flash. The rate card has its price and does not have a fal address for it, so a live call for it is refused and lists the wired models. It does not switch to another model. Seedance 2.0 and Seedance 2.0 fast are the picture models with a fal address. Do not pass `--live` until you mean to spend.

The estimate is written on the ledger before the call. The provider's own price, when it reports one, replaces that estimate after the call, and the row is marked `actual_source: provider`. If fal does not report a dollar amount, the booked amount stays the estimate and the row is marked `actual_source: estimate`. Status says that part of the spend is still the estimate. If the rate card has no price, the call is refused. `--price-override 0.25` writes an approval request for that one amount. The call waits until you approve the request. It does not invent a price.

Run the same command again after a finished call and it uses the saved file. It does not call the provider again and it does not charge again. A failure leaves the run waiting at the current stage. It does not skip ahead. A validation failure releases the booked estimate. The original row stays, and a release row takes the same amount off the running total. If the wait ends first, the estimate stays booked and the message says the provider did not finish before the poll limit. Run the same test shot again. It checks that same request and does not send a new one. Release that row by hand only when you know nothing was produced:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run studio-1 release \
  --entry spend-001 --by ron --note "Nothing was produced."
```

Text calls use `ANTHROPIC_API_KEY`. Sound calls use `ELEVENLABS_API_KEY`. The Director stays offline unless you pass `--live` on `scripts/director.py`. Claude Haiku 5.5, Claude Sonnet 5.5, and Claude Opus 5.5 have published prices on the rate card. A text call whose model id is not priced is refused. The rate card still has no audio price, so a live sound call needs a price override. After a text call, the booked amount is the reported input and output tokens times the rate card, and the ledger says `actual_source: usage`. If those token counts are missing, the booked amount stays the quote and the ledger says `actual_source: estimate`. Downloaded files go under `MOVIE_SWARM_ASSET_ROOT` when that is set, otherwise under `asset_root` in `config/assets.json`, otherwise in the production folder. Put the path in `.env` when the shell does not set it. Doctor names the source and whether the folder exists. It does not print the path. `asset_root` is still null. No drive path is written in the code.

## What the checks do

`python3 -m pytest tests -q` runs the shared checks. They cover the Phase 0 foundation, the Phase 1 rules, the Phase 2 package, the Phase 3 quote, the Phase 4 dailies review, the Phase 5 edit, the Phase 6 cue sheet, the Phase 7 grade and mix, the Phase 8 delivery package, and the Phase 8.5 provider gate: the cap, approvals, the treatment checklist, each screenplay format, the question round trip, a crew call that must pass the Line Producer first, locked props, a continuity check, a camera package, storyboards, an action breakdown, a dry-run generation plan, the generation gate, a prompt that keeps a locked phrase, a circled take, a forbidden prop phrase, a missing file, a shot-list mismatch, the dailies report checklist, the dailies gate in front of the editor, storyboard order, a missing-coverage blocker, a runtime trim, the edit decision list checklist, a locked prop that breaks across a cut, the edit gate in front of sound, cues inside the cut, a sync tolerance flag, a prop sound outside the frame, a paid sound call refused while the generation gate is closed, the Sound line on the rate card, a grade read from the look, a scene grade stated once, a color mismatch between adjacent shots, dialogue ducking, a loudness miss, the color-mix gate in front of final delivery, a delivery spec read from the production, caption timing, a QC pass, a forced QC fail, a manifest with checksums and spend, the delivery gate, a studio run that stops at each gate unless a test harness approves them, an offline default, a closed generation gate, a missing key, an over-budget call, an unknown price, a ledger estimate and a reported actual, a re-run that does not charge again, a retry and a timeout, a key that never appears in the saved output, a shooting schedule, a lighting plan, a grip plan, locked wardrobe, locked makeup, a VFX breakdown, wardrobe and makeup drift, a studio run that still stops at each gate, research before the brand guide, an approved guide before any graphic, a guide rule that traces to research, a TITLE CARD picked up from the screenplay, end credits taken from the Line Producer record, graphics listed on the delivery manifest, and the frame-grab poster left as poster.png. The provider tests use a fake HTTP transport. They do not open a network connection. Phase 8.9 checks the `.env` loader, the test-shot model and tier, the quote printed before a call, the doctor report, and the readable treatment written before the treatment gate. Phase 8.10 checks the fal queue body, the status URL from the submit response, the rounded duration, the budget using that same length, and a release that keeps the original ledger row. Phase 8.11 checks the ten-minute fal wait, the rising pauses, the progress line, `--wait`, the older fal client's queue body and URLs, the asset-root source line, and a ledger row marked `estimate` when no dollars were reported. Phase 8.12 checks a writing quote that sends nothing, a text call that proceeds while the generation gate is closed, picture and audio calls that still stop, the film cap and the stage line, and a ledger row booked from the reported token counts. Phase 8.13 checks a full screenplay in the draft prompt, locked inputs and prop files in that prompt, the four schema mistakes conformed into a valid draft, a fallback note that says the call was booked, a rejected reply saved under the run, and a writing quote that grows with the input. One fixture is The Last Marker. Another is Harbor Night, a tiny second film, so the engine is not proven only on this one. Phase 3 through Phase 8.5 picture, sound, delivery, and provider checks use Harbor Night. The provider checks do not call The Last Marker. Phase 8.18 checks a title card whose direction is not the card text, a featured-object rule that is not written as a sale, a design-reference pack that stays a proposal, and a credits face that must be a sans-serif.

Three older agents have their own checks, because each one uses a folder named `src`:

```bash
python3 -m pytest agents/05-production/tests -q
python3 -m pytest agents/06-sound-designer/tests -q
python3 -m pytest agents/08-qa/tests -q
```

`python3 scripts/validate-schema.py --production productions/the-last-marker` checks the archived copy. `python3 scripts/validate-schema.py --production the-last-marker` checks the working film when the films root is set. A path outside this repo works the same way. The command checks every JSON file in the production against its checklist. A checklist is a schema: a list of required fields. Files that fail are named. A few older pilot files are on a known-mismatch list. They are reported and do not fail the run, including when that folder has been copied out of the repo. A new file that fails does stop the command.

GitHub runs these checks on every push and every pull request. See `.github/workflows/ci.yml`.

## Settings

Environment variables, by name only. Do not commit a key.

| Name | Used for |
|---|---|
| `ANTHROPIC_API_KEY` | Text calls for the Director and the Line Producer. Read only when you pass `--live`. The value is never written down. `scripts/` loads it from `.env` when the shell has not set it. |
| `MOVIE_SWARM_ASSET_ROOT` | Optional folder for downloaded media and the delivery package. Overrides the file below. Put it in `.env` when the shell does not set it. A non-interactive shell does not read `~/.zshrc`. Doctor names the source and whether the folder exists. It does not print the path. |
| `FAL_KEY` | Picture calls on fal. Read only when you pass `--live`. |
| `ELEVENLABS_API_KEY` | Sound calls on ElevenLabs. Read only when you pass `--live`. The key needs the Voices: Read permission for the voice list. |

Config files in `config/`:

| File | What it controls |
|---|---|
| `gates.json` | The $500 film cap, and one on/off switch per stage. On means Ron reviews that stage. Every switch starts on. |
| `model-routing.json` | Which model each role uses. Change the file, not the code. |
| `providers.json` | How long a fal picture call waits, and how the pauses between status checks grow. `--wait` on a test shot replaces the wait for that one call. |
| `assets.json` | Where finished media lives, and the films root when `films_root` is set. `null` keeps media in the production folder. |

## Sample data

The archived copy of the first film is The Last Marker, in `productions/the-last-marker/`. The working film lives in the films folder. Harbor Night, under `tests/fixtures/`, is the in-repo example.

| File | What it is |
|---|---|
| `screenplay/Pilot_-_the_last_marker_screenplay.md` | The shooting script. |
| `production-brief.json` | Ron's locked choices: $500, Baja California, 1967, the Leone look, the two hero props. Exhaust on the right. Watch on the left wrist. |
| `budget.json` | The film budget. Total $500. Trailer on, 10 percent contingency, picture tier better. Trailer, contingency, and the tier are proposed. |
| `treatment/treatment.md` | The live treatment. Status: draft. Not an approved gate. |
| `treatment/treatment.json` | The same treatment in the form the checks can read. Status: draft. |
| `treatment/inputs.json` | Ron's locked creative answers. Intake reads this. It does not approve the gate. |
| `treatment/questions.json` | Round 1, open. Answers are empty so intake can draft again. |
| `runs/first-film-1/` | The live run. Waiting at the treatment gate. No gate on this run is approved. Spent $0.00. |
| `archive/` | The earlier run `phase-1`, the approved treatment, the closed question round, and the approved storyboard. |
| `props/prop-definitions.json` | The locked attributes for this film, written as production data. |
| `props/hero-props.json` | The same lock, after the Prop Master copies it. |
| `look/look.json` | This film's lenses, framing, and lighting. |
| `camera/camera-package.json` | The Cinematographer's package, copied from that look. |
| `storyboard/` | One beat per shot, the look stated once, and an animatic. No images were generated. The live file is a draft. The approved copy is in `archive/`. Scene 3 also has the empty canteen, the circling buzzards, and the hard cut from a buzzard's face to his eyes. |
| `continuity/continuity-check.json` | Drift findings. The old pilot shot list is missing the locked exhaust phrase. |
| `stunts/action-breakdown.json` | The treatment's two action beats, broken into shots. |
| `audio/sound-prompts.json` | The pilot sound prompts. The sound program reads this file. It does not keep a copy. |

Hero props for this film are the 1965 Triumph and the watch. Ron locked the exhaust on the right and the watch on the left wrist. Those sentences are in the production files above. They are not in the studio code.

## Where to read more

- [ARCHITECTURE.md](ARCHITECTURE.md) — how the pieces fit, and what each coded role reads and writes.
- [ROADMAP.md](ROADMAP.md) — phases, gates, and what is next.
- [DECISIONS.md](DECISIONS.md) — choices already made.
- [CONTRIBUTING.md](CONTRIBUTING.md) — how a pull request should read, and the doc rule.
- [docs/perfect-treatment.md](docs/perfect-treatment.md) — what a good treatment contains, with a short Last Marker example for each field.
- [docs/treatment-template.md](docs/treatment-template.md) — a blank treatment you can fill in.
