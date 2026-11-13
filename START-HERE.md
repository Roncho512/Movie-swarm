# Start here

This is the page to open when a film is about to start, even if the last one was months ago. Ron is the executive producer. The crew does the work. Ron reviews it and decides what may spend money.

The worked example below uses Harbor Night, the synthetic film in `tests/fixtures/harbor-night`. Copy it first so the fixture stays as it is. Your own film uses the same commands with your folder in place of `/tmp/harbor-night`.

```bash
cp -a tests/fixtures/harbor-night /tmp/harbor-night
```

A stop from `scripts/studio.py` exits with status 2. That means the studio is waiting on a gate. It is not a crash. Read the file it names, then approve the gate, then run the studio again.

## Where films live

The studio repo holds the engine. A film's working files live in their own folder outside the repo, under the films root. Set `MOVIE_SWARM_FILMS_ROOT` in `.env`, or in the shell. When that name is empty, the commands use `MOVIE_SWARM_ASSET_ROOT` (the shell, `.env`, or `config/assets.json`). A non-interactive shell does not read `~/.zshrc`. Doctor names which setting it used and whether the folder exists. It does not print the path. Do not commit a real path.

A production name is that folder plus the name. `--production the-last-marker` is the working folder for that film. An absolute path is used as given, including a folder outside this repo. A relative path is used as given. It is not moved into this repo.

`productions/the-last-marker` in this repo is an archived copy. The working film is the one in the films folder. Copy it out with:

```bash
python3 scripts/export-film.py --from productions/the-last-marker --to /path/to/films/the-last-marker
```

That copies the folder, writes a checksum list, checks it, and does not delete the source. A later phase can remove the archived copy after that export is confirmed. Start a new film with:

```bash
python3 scripts/new-film.py my-film
python3 scripts/new-film.py my-film --total 500
python3 scripts/new-film.py my-film --git
```

The new folder is created in the films root. `--total` sets the budget. Omit it and `budget.json` keeps the calculator default and says the total was not asked. `--git` runs `git init` in that folder. It does not add a remote and it does not push. Harbor Night stays in `tests/fixtures/` as the example.

## Making The Last Marker

The working film is the folder named `the-last-marker` in the films root. Story facts stay in that folder. This page does not repeat them.

Prior approvals from the archived copy are in that film's `archive/`. The live treatment is a draft, so intake can write it again. Intake reads `treatment/inputs.json` and does not approve the gate. If a treatment is already approved, intake stops. Do not draft again. Read `treatment/treatment.md`.

From the repo root, with the films root set:

```bash
python3 scripts/studio.py --production the-last-marker --run first-film-1
python3 scripts/line-producer.py --production the-last-marker --run first-film-1 budget
```

The same commands can take the absolute path of the film folder instead of the name. On the key-test machine the same commands can use `/tmp/movie-swarm-venv/bin/python` in place of `python3`. Exit status 2 means the run is waiting at the treatment gate. Read `treatment/treatment.md` in the film folder. The quote comes from `budget.json`. The steps that belong only to this film are in that folder's `README.md`. The archived copy in this repo is not the working film.

## Draft the treatment with Claude

Offline is still the default. A live Director draft is three commands from the repo root, with the films root set and `ANTHROPIC_API_KEY` in `.env` or the shell. The first command prints a quote and sends nothing. It does not replace `treatment/treatment.md`. Read the model, the input-token estimate, the max output tokens, and the worst-case dollars.

```bash
python3 scripts/director.py --production the-last-marker --run first-film-1 --live intake
```

Intake makes two text calls once it is allowed to send: the Director's draft on Claude Sonnet 5.5, then the Line Producer's question wording on Claude Haiku 5.5. The quote you just read is the draft. The question call is smaller. Approve one ceiling that covers both. `$1.00` is inside the director line on this film's `budget.json` and covers a treatment draft plus that question pass. The generation gate stays closed.

```bash
python3 scripts/line-producer.py --production the-last-marker --run first-film-1 approve-writing \
  --by Ron --max-usd 1.00 --note "Treatment draft for first-film-1."
```

Run the same intake again. This one sends the calls.

```bash
python3 scripts/director.py --production the-last-marker --run first-film-1 --live intake
```

Read `treatment/treatment.md`. The treatment stays a draft. The draft call sends the screenplay, up to 120,000 characters, plus `treatment/inputs.json` and the prop locks when the film has them. The quote counts that whole prompt. On the archived copy, a 23,300-character screenplay plus those files is about $0.1042 worst case for the Sonnet draft and about $0.0011 for the Haiku question pass. The $1.00 ceiling still covers both. If the model draft does not match the checklist, the offline draft is kept, the note lists the schema errors, and it says the call cost was booked. The raw reply is under `runs/<run>/rejected-draft-<hash>.txt`.

The same request sent again is free. The provider cache replays it. This prompt is not the one that was paid, so a new intake will not match that call. To conform a saved reply without paying again, pass its request hash from `runs/first-film-1/provider-cache.json`. The first 12 characters are enough when they match one call. This command does not call the model.

The Opus final pass on `first-film-1` filled its 8,000 output tokens and the reply was cut off. That call is the cache entry whose ledger row is `spend-005`. Run this from the repo root. Replace `<hash>` with that entry's request hash. The command closes the cut-off JSON, drops the unfinished field, fills anything still required from the current draft, and writes the treatment. It does not call the model and it does not book.

If the treatment is already approved and `draft_note` still says the final model pass failed and the earlier draft was kept, the same command is the fix. It reads the cache, checks that the reply still conforms, and then removes that stale sentence. It does not replace the approved scenes, the logline, the stage split, or the approval block. The treatment gate stays approved. The approval stays valid because the Line Producer's gate decision is the record, and this command does not rewrite `status` or `approval`. `--redo previs` does not touch the treatment. Run reconform first, then the previs redo below.

```bash
python3 scripts/director.py --production the-last-marker --run first-film-1 reconform --request <hash>
```

A confirmation such as `Lock.` keeps the drafted text. The final pass allows 16,000 output tokens. If a reply fills that cap, the command says the final pass hit the output limit. A reply that still cannot be read is saved at `runs/<run>/rejected-final-<hash>.txt`.

Picture and audio calls still wait until you approve the generation gate.

## Set up the machine

Do this once on the machine that will run the film.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
python3 scripts/doctor.py
```

Fill the three names in `.env`. The commands in `scripts/` load that file. A variable already set in the shell is left as it is. The values are not printed. Do not commit `.env`.

`MOVIE_SWARM_ASSET_ROOT` is optional. Set it in `.env` when finished media should leave the production folder. `MOVIE_SWARM_FILMS_ROOT` is the folder that holds each film. When the films root is empty, a production name uses the asset root. A non-interactive shell does not read `~/.zshrc`, so a path that lives only there is invisible to these commands. Leave the asset root empty to keep finished files in the production folder. Doctor does not print the path.

Doctor prints the Python version, whether the requirements import, whether ffmpeg is on the path, whether `.env` is there, and whether each key is set. It prints yes or no. It does not print a key, and it does not use the network. It also says where the asset root came from, and where the films root came from: the shell, `.env`, or `config/assets.json`, and whether that folder exists. `python3 scripts/doctor.py --ping` asks Anthropic and ElevenLabs with a read-only request and prints the HTTP status. fal is not checked that way. This repo has no free fal auth check. That line says it needs a paid test shot. `python3 scripts/doctor.py --production the-last-marker` checks that the film folder is there and does not print the path.

## 1. Open the film agent

Open the Grok Bot film agent. Its name is PER.INN.FILM, and it answers to Reel. Start the discussion there. This repo does not start that chat for you.

## 2. Bring the script

For a new film, make a folder and point intake at the script. This writes a draft treatment and a question file. It does not approve anything.

```bash
mkdir -p /tmp/new-film/screenplay
cp tests/fixtures/harbor-night/screenplay/harbor-night.md /tmp/new-film/screenplay/harbor-night.md
python3 scripts/director.py --production /tmp/new-film --run guide-1 --offline intake \
  --screenplay /tmp/new-film/screenplay/harbor-night.md
```

Intake writes `treatment/treatment.md` and `treatment/questions.json`. Read the markdown, then answer the questions in `treatment/questions.json`, in the `answer` field. The treatment gate comes later. Approving that gate does not create the markdown. Then:

```bash
python3 scripts/director.py --production /tmp/new-film --run guide-1 --offline answer \
  --answers /tmp/new-film/treatment/questions.json
```

Harbor Night already has an approved treatment, so the worked example below does not run intake on that copy. Intake refuses to overwrite an approved treatment.

## 3. Set the budget

Open the one calculator. From the repo root:

```bash
python3 -m http.server 8000
```

Then open [http://127.0.0.1:8000/tools/budget-calculator/index.html](http://127.0.0.1:8000/tools/budget-calculator/index.html). You can also open `tools/budget-calculator/index.html` straight from the file browser. There is no build step, and there is no second calculator for the trailer. The trailer is a line on this screen.

Set the film's total, the contingency percent, the tier for each stage, and whether the trailer is on. Ten percent contingency and, when the trailer is on, ten percent for Marketing and Distribution are the suggested starting numbers. Export `budget.json` and save it into the production folder as `budget.json`.

The same file can be written from the command line. This example keeps the familiar $500 lines, with the trailer off and no contingency:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night budget --write --total 500 --trailer off --contingency 0
```

Leave off `--contingency` and the file uses 10. Pass `--trailer on` when you want the marketing line. The other lines scale down so the total still equals the budget. A film with no `budget.json` stays on today's $500 cap and the locked split.

The report shows the budget, the estimate, the spend, the contingency left, and under or over for each line. Pass `--run` when a run is open so the spend is included.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 budget
```

## 4. Walk the gates

Start the run, then let the studio stop at each gate. Approve only after you have read the file.

Harbor Night's copy has `treatment/treatment.json` and no markdown yet. Starting the run, or the first studio stop, writes `treatment/treatment.md` from that JSON. Read the markdown, then approve the treatment gate. The approval does not create the file.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 start
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 status
python3 scripts/studio.py --production /tmp/harbor-night --run guide-1
```

Every approval uses the same command. Change the stage and the note.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 approve-gate \
  --stage treatment --decision approved --by ron --note "The treatment can proceed."
```

| Gate | What Ron reads | What the approval means |
|---|---|---|
| treatment | `treatment/treatment.md` | The plan is accepted and the stage lines lock. |
| previs | Props, wardrobe, makeup, continuity, camera, storyboard, schedule, light, grip, stunts, VFX, and the title research. | The package can go forward. |
| graphics | `graphics/brand-guide.md` | Titles, credits, and key art may be built. This stop comes after previs. |
| production | The generation plan under `generation/`. | The quote may be written. This is not a paid call. |
| dailies | `dailies/dailies-report.md` | Circled takes may be cut. |
| editor | The same report, before assembly. | The editor may assemble. |
| edit | `edit/rough-cut.md` | Picture lock. Sound waits on this. |
| sound-designer | The locked cut. | Sound may spot the cue sheet. |
| sound | `sound/cue-sheet.md` | Color and mix may start. |
| color-mix | `color/grade-plan.md` and `color/mix-plan.md` | The package may be written. |
| delivery | `delivery/delivery-manifest.md` and the QC report. | The film is delivered. |
| trailer | `marketing/trailer-plan.md`, when the trailer is on. | The trailer is accepted. The film can deliver without this approval. |
| generation | The quote. | A paid call is allowed. Leave this closed until you mean to spend. |

The generation gate stays closed through the studio walk. The command, for the day you want it open, is:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 approve-gate \
  --stage generation --decision approved --by ron --note "One test shot."
```

After each approval, run `scripts/studio.py` again with the same `--production` and `--run`.

To regenerate previs on a run that is already past the treatment gate and still waiting on previs, use `--redo previs`. For the first film, from the repo root, with the films root set:

```bash
python3 scripts/studio.py --production the-last-marker --run first-film-1 --redo previs
```

That command is offline. It rewrites the prop lock, wardrobe, makeup, continuity check, camera package, storyboard, lighting plan, grip plan, schedule, action breakdown, VFX breakdown, and the title research and draft brand guide. It does not approve the previs gate and it does not spend. If that gate is already approved, the command refuses and leaves the files and the gate alone. `--live` is refused. A run that dies in the boards does not approve the gate and does not leave a half-written storyboard. Run the same command again. The locks from the failed attempt are overwritten. Nothing has to be deleted first. A hero prop can list `parts` in `props/prop-definitions.json` so a shot that names a part is tagged. It can also list `generic_nouns` for ordinary words that are not the name. `config/kind-nouns.json` holds kind-level nouns, used only when the film has exactly one lock of that kind. A film replaces a kind by writing `props/kind-nouns.json`. `config/absence-phrases.json` lists phrases that name a prop without putting it in the frame, such as "left the X" or "walks away from the X". A film replaces a list in `props/absence-phrases.json`. A phrase that could go either way is listed for review and is not guessed. A prop is not carried into a close-up of a different object, or into a fade, a hold, black, or a title. When one person rides a vehicle and that vehicle passes the camera, the shot includes that person. Shot lengths default to 1–12 seconds unless the screenplay names a length. Time left after those limits is spread across shots in the same scene that still have room. If that scene has no room left, the leftover time goes to shots in other scenes that do, and the pacing note names which scene took it. `storyboard/pacing-limits.json` can set `min_shot_seconds` and `max_shot_seconds`.

When the trailer is on, turn it on in `budget.json` before picture lock. After the color-mix gate, the studio writes the research, the spoiler guard, the Director's sign-off, the plan, and the cut. You can also call the steps yourself:

```bash
python3 scripts/director.py --production /tmp/harbor-night --run guide-1 --offline dispatch \
  --agent trailer-editor --crew-command research --estimate 0
python3 scripts/director.py --production /tmp/harbor-night --run guide-1 --offline dispatch \
  --agent trailer-editor --crew-command guard --estimate 0
python3 scripts/director.py --production /tmp/harbor-night --run guide-1 --offline dispatch \
  --agent trailer-editor --crew-command sign --estimate 0
python3 scripts/director.py --production /tmp/harbor-night --run guide-1 --offline dispatch \
  --agent trailer-editor --crew-command plan --estimate 0
python3 scripts/director.py --production /tmp/harbor-night --run guide-1 --offline dispatch \
  --agent trailer-editor --crew-command cut --estimate 0
```

If the trailer is off, that dispatch prints that nothing was written, and the film still delivers.

## 5. API keys

The names are in `.env.example`. Copy it to `.env` on your machine and fill the values there. Do not commit `.env`. The repo stores empty names only.

| Name | Used for |
|---|---|
| `ANTHROPIC_API_KEY` | Text calls. Read only when you pass `--live`. |
| `FAL_KEY` | Picture calls on fal. Read only when you pass `--live`. |
| `ELEVENLABS_API_KEY` | Sound calls. Read only when you pass `--live`. The key needs the Voices: Read permission. The voice list uses it. |

A live call that needs a missing key stops and says which name is unset. Nothing is sent.

## 6. Live calls and overages

Offline is the default. A picture or audio call needs all four of these: the generation gate approved, the estimate inside the line and the film budget, the key in the environment, and `--live` on the command. A text call uses the writing approval instead of the generation gate. The commands for a live treatment draft are in the section Draft the treatment with Claude.

One picture call, for one shot, with nothing sent. The cheapest real Seedance 2.0 fast shot is 4 seconds at 720p. A shorter board is rounded up to 4 seconds, and the estimate uses that length. Harbor Night's first shot is 2.087 seconds, so the dry run says it is sent as 4 seconds and estimates $0.9676. The dry run prints the model, the tier, the provider, the resolution, the duration, the estimated cost, and the money still left. It says nothing was sent.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 test-shot \
  --shot s01-sh01 --model seedance-2.0-fast
```

The dry-run line for that shot is:

```text
Shot s01-sh01: model seedance-2.0-fast, tier better, provider fal.ai, resolution 720p, duration 2.087 seconds (sent as 4 seconds), estimated cost $0.9676.
Production line remaining: $270.00. Film remaining: $500.00.
```

That shot exists after the studio has written the storyboard. `--tier better` names the same model. Read the estimate. Add `--live` only after you have approved the generation gate and you mean to spend:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 --live test-shot \
  --shot s01-sh01 --model seedance-2.0-fast
```

A Seedance job can take a few minutes. The first live fast shot took about four minutes at fal. The command waits 10 minutes by default. While it waits it prints a short line about every 30 seconds: the elapsed time, the fal status such as `IN_QUEUE` or `IN_PROGRESS`, and the queue position when fal sends one. The first pause is 5 seconds. The pause then grows to 15 seconds. The numbers live in `config/providers.json`. To wait a different length on this one call, pass `--wait` with the seconds:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 --live test-shot \
  --shot s01-sh01 --model seedance-2.0-fast --wait 900
```

If the wait ends before fal finishes, the command says the provider did not finish before the poll limit. The estimate stays booked. Nothing is sent again. Run the same command once more. It checks that same request and does not start a new one.

A test shot with no `--model` and no `--tier` uses the film's budget tier, then the routing default. The good tier is Gemini Omni 1.2 Flash. That model is planned and has no fal address, so a live call for it is refused and the message lists the wired models and the flag. It does not switch models on its own.

Going past a line, or past the film budget, pauses the spend and writes `runs/<run-id>/requests/req-001.json`. The status names the request. This records a $20 director spend, then pauses the next dollar, then approves it. The approval does not edit `budget.json`.

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 spend \
  --stage director --amount 20 --description "draft" --kind generation
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 spend \
  --stage director --amount 1 --description "one more pass" --kind generation
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 decide \
  --request req-001 --decision approved --by ron --note "Allow it."
```

The second spend exits with status 2 while it waits. Retakes and a tier change can use the contingency reserve after the line is spent. Anything past the reserve waits for the same kind of approval. Nothing is spent past the budget without that record.

To change a tier when the line and the contingency can hold it:

```bash
python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 budget --upgrade production=better
```

## 7. Where the film goes

Finished media uses `MOVIE_SWARM_ASSET_ROOT` when that variable is set. Put the path in `.env` when the shell does not set it. Otherwise it uses `asset_root` in `config/assets.json`. That value is null today, so the package stays in the production folder under `delivery/`. Doctor names the source and whether the folder exists. It does not print the path.

The package holds the master, the variants the delivery spec asked for, a poster frame, captions, the QC report, and `delivery/delivery-manifest.json` with a SHA-256 checksum for each file that was written. When a trailer was cut, the package also has `delivery/marketing/` and a short usage sheet. Posting anything stays with Ron.

## 8. If something stops

- Studio exit 2: a gate is waiting. Read the file in the status, approve it, run the studio again.
- "No budget.json": the film is on the $500 cap. Write one with the calculator or the budget command.
- A spend pauses: open the request file, or run `status`, then `decide`.
- A trailer command says the trailer is off: set `trailer_on` to true in `budget.json` when you want one.
- "The trailer is off" is a skip, not a failure. Delivery still runs.
- A live call says a key is missing: set that name in `.env` or in the shell. Do not put the value in the repo. Doctor says whether each name is set.
- A live picture call says no endpoint is configured: that model is unwired. Pass `--model seedance-2.0-fast` or `--tier better` for the cheapest wired picture model. The message lists the choices.
- A live picture or sound call says the rate is unknown: the rate card has no verified price for that model. Pass `--price-override` only for that one call, and approve the request it writes. A text model with a null price is refused. Claude Haiku 5.5, Claude Sonnet 5.5, and Claude Opus 5.5 are priced.
- A live text call prints a writing quote and stops: record `approve-writing` for that run, then run the same command again. The generation gate can stay closed.
- A failed call left an estimate on the ledger and produced nothing: `python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 release --entry spend-014 --by ron --note "Nothing was produced."` The original entry stays. The running total goes back down.
- A live picture call says the provider did not finish before the poll limit: fal is still working. The estimate stays booked. Run the same test shot again. It checks the same request and does not send a new one. Pass `--wait` with more seconds if you want a longer wait on that call.
- Status says part of the spend is still the estimate: fal did not report a dollar amount. That part of the ledger is the quote, not a measured charge.
- Intake says the treatment is already approved: do not draft again. Read `treatment/treatment.md`.

## What each role does

The Director is role 00. Ron talks to the Director. The Director writes the treatment and calls the crew through the Line Producer.

| Role | Who | What they do |
|---|---|---|
| 01 | Line Producer | Budget, schedule, credits, gates, and the ledger. |
| 02 | Screenwriter | The writing skill. The treatment is the document the rest of the crew reads. |
| 03 | Art Director | The in-film look. |
| 04 | Cinematographer | Camera package and storyboard. |
| 05 | Production | The picture quote, and the paid picture call when you allow it. |
| 06 | Sound Designer | The cue sheet: dialogue, effects, and ambience. |
| 07 | Editor | Assembles circled takes. Does not bill for the trailer. |
| 08 | QA | Reviews the cut and, when a trailer exists, the cards and the spoiler guard. |
| 09 | Fix loop | Sends a failed check back for another pass. |
| 10 | Script Supervisor | Checks locked props, wardrobe, and makeup before a shot is made. |
| 11 | Prop Master | Locks the hero props. |
| 12 | Stunt and Action Coordinator | Turns action beats into shots. |
| 13 | Assistant Director | Shooting schedule and call sheet. |
| 14 | Gaffer | Lighting plan. |
| 15 | Key Grip | Camera support and rigging. |
| 16 | Costume Designer | Locks wardrobe. |
| 17 | Makeup and Hair | Locks makeup, hair, and effects. |
| 18 | VFX Supervisor | Breakdown before production, and a read of the VFX shots after dailies. |
| 19 | Title and Graphic Design | Research, the brand guide, titles, credits, and key art. |
| 20 | Trailer Editor | Teaser and trailer from approved takes, after picture lock, and only when the budget turns the trailer on. |

The Dailies Reviewer, the Composer, the Colorist, the Re-recording Mixer, and the Post Supervisor are part of the studio walk. They are not numbered 01 to 20. Their gates are dailies, sound, color-mix, and delivery.
