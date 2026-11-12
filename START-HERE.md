# Start here

This is the page to open when a film is about to start, even if the last one was months ago. Ron is the executive producer. The crew does the work. Ron reviews it and decides what may spend money.

The worked example below uses Harbor Night, the synthetic film in `tests/fixtures/harbor-night`. Copy it first so the fixture stays as it is. Your own film uses the same commands with your folder in place of `/tmp/harbor-night`.

```bash
cp -a tests/fixtures/harbor-night /tmp/harbor-night
```

A stop from `scripts/studio.py` exits with status 2. That means the studio is waiting on a gate. It is not a crash. Read the file it names, then approve the gate, then run the studio again.

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

Doctor prints the Python version, whether the requirements import, whether ffmpeg is on the path, whether `.env` is there, and whether each key is set. It prints yes or no. It does not print a key, and it does not use the network. `python3 scripts/doctor.py --ping` asks Anthropic and ElevenLabs with a read-only request and prints the HTTP status. fal is not checked that way. This repo has no free fal auth check. That line says it needs a paid test shot.

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

Offline is the default. A real call needs all four of these: the generation gate approved, the estimate inside the line and the film budget, the key in the environment, and `--live` on the command.

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

Finished media uses `MOVIE_SWARM_ASSET_ROOT` when that variable is set. Otherwise it uses `asset_root` in `config/assets.json`. That value is null today, so the package stays in the production folder under `delivery/`.

The package holds the master, the variants the delivery spec asked for, a poster frame, captions, the QC report, and `delivery/delivery-manifest.json` with a SHA-256 checksum for each file that was written. When a trailer was cut, the package also has `delivery/marketing/` and a short usage sheet. Posting anything stays with Ron.

## 8. If something stops

- Studio exit 2: a gate is waiting. Read the file in the status, approve it, run the studio again.
- "No budget.json": the film is on the $500 cap. Write one with the calculator or the budget command.
- A spend pauses: open the request file, or run `status`, then `decide`.
- A trailer command says the trailer is off: set `trailer_on` to true in `budget.json` when you want one.
- "The trailer is off" is a skip, not a failure. Delivery still runs.
- A live call says a key is missing: set that name in `.env` or in the shell. Do not put the value in the repo. Doctor says whether each name is set.
- A live picture call says no endpoint is configured: that model is unwired. Pass `--model seedance-2.0-fast` or `--tier better` for the cheapest wired picture model. The message lists the choices.
- A live call says the rate is unknown: the rate card has no verified price. Pass `--price-override` only for that one call, and approve the request it writes.
- A failed call left an estimate on the ledger and produced nothing: `python3 scripts/line-producer.py --production /tmp/harbor-night --run guide-1 release --entry spend-014 --by ron --note "Nothing was produced."` The original entry stays. The running total goes back down.
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
