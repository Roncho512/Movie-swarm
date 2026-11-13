# Decisions

Choices that are already made. Each entry has the context, the decision, what follows from it, and who decided.

## D1 — Ron is the executive producer

- Date: 2026-11-10
- Context: The repo had an Executive Producer agent that was meant to run the whole pipeline. A person needs to own the film.
- Decision: Ron is the human executive producer. The old agent slot becomes the Line Producer. It owns the budget, the schedule, the credits, the gates, and the run state. It reports to Ron.
- Consequences: The folder is `agents/01-line-producer/`. Creative calls are not its job. Approval commands live on the Line Producer, not on the Director.
- Who decided: Ron

## D2 — The Director calls the crew

- Date: 2026-11-10
- Context: The film needs one role with creative say, able to ask specialists for work at the moment a choice comes up.
- Decision: A Director agent has full creative say. It may call any crew role at a decision point, under a per-stage spend allocation. More spend goes through the Line Producer, which means Ron while the crew is still being dialed in.
- Consequences: There is no separate executive-producer agent making the creative calls. A crew call is refused until the Line Producer allows it.
- Who decided: Ron

## D3 — A gate after every stage

- Date: 2026-11-10
- Context: The crew is new. Bad work should stop before the next stage spends money.
- Decision: A human review gate after every stage until the crew is dialed in. The end goal is Ron approving only the look and the final cut. Gates are config switches.
- Consequences: `config/gates.json` starts with every switch on. Turning one off is a config edit, later, when that stage is trusted.
- Who decided: Ron

## D4 — The output is a finished video

- Date: 2026-11-10
- Context: The pipeline could stop at a shot list, a rough cut, or a pile of clips.
- Decision: The output of a production is a finished video.
- Consequences: Stages exist to reach that file. A treatment, a shot list, or a rough cut is not the end.
- Who decided: Ron

## D5 — Five hundred dollars, retakes included

- Date: 2026-11-10
- Context: Generation can quietly overrun if each retake is treated as extra.
- Decision: The spend cap is $500 per film, total. Retakes are included. The Director proposes the per-stage split at the treatment gate. Ron approves it.
- Consequences: The Line Producer copies $500 onto the run. It refuses a spend that would pass the cap or a locked stage ceiling, and writes a request. Ron can approve that one spend. The cap number stays $500 so the overage stays visible.
- Who decided: Ron

## D6 — Spend the cheap model where the work is cheap

- Date: 2026-11-10
- Context: A film burns money on the picture, not on bookkeeping. Some jobs need a model that can watch video and hear audio.
- Decision: Use a cost-conscious model per role. Cheap models for admin. Gemini Omni 1.2 Flash for final video, with cheap previews. Gemini for dailies and QA, because it watches picture with sound. Claude Sonnet and Claude Opus for the Director and for writing. Seedance and Kling as alternates the Director can route.
- Consequences: The Line Producer and the question list use Claude Haiku 5.5. The Director drafts on Claude Sonnet 5.5 and does the final treatment pass on Claude Opus 5.5. The video and QA programs have not switched yet. They still call Seedance and the QA program's current Claude model. The routing file says so.
- Who decided: proposed by Reel (PER.INN.FILM), approved by Ron

## D7 — The Last Marker is the test film

- Date: 2026-11-10
- Context: The pipeline needs one film to prove each phase, not a new story every time.
- Decision: The Last Marker stays the test production through every phase.
- Consequences: New checks and new roles are tried on this production first. Its files stay in `productions/the-last-marker/`. D41 keeps it as the film the finished studio will make, and proves the studio phases on Harbor Night before that.
- Who decided: Ron

## D8 — A Leone western, without copying a score

- Date: 2026-11-10
- Context: The film needs a locked look before art direction and camera start inventing one.
- Decision: The reference look is a Sergio Leone spaghetti western. Extreme wides against extreme close-ups. Locked 2.39:1. Long holds, then sharp cuts. A warm, grainy 1960s film look. A mostly still camera with slow push-ins. A score in the spirit of Ennio Morricone, without copying any melody.
- Consequences: The production brief and the draft treatment carry this look. The lookbook says what to take, not "make it like the reference" with nothing else.
- Who decided: The look specifics were proposed by Reel and approved as direction by Ron.

## D9 — Finished files live on Ron's drive

- Date: 2026-11-10
- Context: A finished film should not depend on the machine that happened to render it.
- Decision: Finished videos and approved assets live on Ron's "Ron Workspace" external drive, copied at the end of each run. Working files stay on the run machine. The asset root is configurable.
- Consequences: `config/assets.json` and `MOVIE_SWARM_ASSET_ROOT` choose the folder. Nothing is copied yet. Nothing in the repo is deleted to make room.
- Who decided: Ron

## D10 — 1967 on screen, a 1965 Triumph

- Date: 2026-11-10
- Context: The pilot papers said 1966. Ron chose the story year. The bike's model year is a different fact.
- Decision: The Last Marker is set in 1967. The Triumph remains a 1965 model.
- Consequences: Period lines in the production notes, the screenplay, the prompts, the style bible, and the art-director skill say 1967. The schema's generic example year was left alone. It is not this film.
- Who decided: Ron

## D11 — Lock the hero props, then check them twice

- Date: 2026-11-10
- Context: The May pilot drifted. The exhaust side and the watch wrist did not stay put.
- Decision: Hero props get locked specs, with multi-angle reference images. A Script Supervisor checks them before generation. A Dailies Reviewer checks them after, on the real frames.
- Consequences: The treatment has a slot for the locked spec and for those images. The Script Supervisor is the before-generation check. D27 locked this film's sidedness. D30 says the checker reads the production's prop file and does not hard-code it. D47 is the frame check this decision named. Phase 3 left that check as a stub.
- Who decided: Ron

## D12 — A stunt and action role

- Date: 2026-11-10
- Context: Action beats were being invented inside other jobs. Kicks, plugs, and falls need an owner.
- Decision: Add a Stunt and Action Coordinator role.
- Consequences: The treatment has a place for action beats. The role reads those beats and writes a shot breakdown. It does not invent a beat.
- Who decided: Ron

## D13 — A treatment, built by questions

- Date: 2026-11-10
- Context: A screenplay is not yet a plan the crew can share. Ron should not have to invent the missing intent inside a chat that cannot be resumed.
- Decision: The Director converts scripts into treatments by rounds of questions with Ron. A Perfect Treatment template says which fields are required and which are optional.
- Consequences: The checklist is `schemas/treatment.schema.json`. The guide is `docs/perfect-treatment.md`. The blank form is `docs/treatment-template.md`. Questions and answers are files.
- Who decided: Ron

## D14 — Docs travel with the code

- Date: 2026-11-10
- Context: A pull request that changes behavior and leaves the map stale makes the next session guess.
- Decision: Repo work is built by Cursor cloud agents as pull requests. The living docs are updated in the same pull request as the code they describe.
- Consequences: The living docs are `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, and `DECISIONS.md`, plus `CONTRIBUTING.md` for the rule itself. `docs/` is for supporting material. See [CONTRIBUTING.md](CONTRIBUTING.md).
- Who decided: Ron

## D15 — The ledger sits beside the run state

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: Phase 0 already stores the stage, the status, and the running total in `run-state.json`. The Line Producer also needs a ledger, a stage split, credits, and Ron's decisions.
- Decision: Keep the Phase 0 run state as it is. Store the rest in `line-producer.json` next to it.
- Consequences: Both files are checked against their own schemas. The running total changes only when a spend is booked.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D16 — No prompt that waits

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: A Grok Bot will show gates and questions in chat. A command that stops and waits for a keypress cannot be resumed from another machine.
- Decision: Every question, answer, approval, and rejection is a file or a command flag.
- Consequences: `questions.json` holds the round. Ron fills answers there, or sends an answers file. Gates and spend requests work the same way.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D17 — The Director cannot self-approve

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: A model can write `"status": "approved"` into a draft. That must not count.
- Decision: Only the Line Producer's approve-gate command can mark a treatment approved. The Director rewrites any self-approval back to draft before it saves.
- Consequences: The committed Last Marker treatment is a draft. The approval record says it is pending.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D18 — An offline draft is labeled

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: The build machine had no Anthropic API key. A silent fake model would look like a real draft.
- Decision: With no key, or with `--offline`, the Director writes a deterministic draft from the screenplay and the brief. The file says `offline-deterministic`.
- Consequences: The Last Marker draft in the repo was made this way. It is still a real checklist-valid draft. It is not a model pass. A later run with a key can redraft. Tests use a fake client and do not need a key.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D19 — A crew call is checked, and this phase does not spend

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: The Director must be able to reach today's coded agents. A first version should not buy video.
- Decision: Production, sound, the editor, QA, and the fix loop are called only through the Line Producer. The call checks the treatment gate, that stage's gate, the film cap, and the stage ceiling. This phase runs a price estimate or a dry run. A dry run does not book the estimate as spent. Editor, QA, and the fix loop are named and routed, and their picture-touching commands are not executed.
- Consequences: An over-cap estimate pauses and writes a request. Approving that request does not add dollars. It allows the checked call. A real spend is a separate Line Producer command, and it still cannot pass a closed gate or a ceiling without Ron's recorded yes.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D20 — Which Claude model, and where the key lives

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: D6 names the cost policy. The code needs exact model ids and one place to read the key.
- Decision: Admin and question bookkeeping use `claude-haiku-5-5`. The treatment draft uses `claude-sonnet-5-5`. The final treatment pass uses `claude-opus-5-5`. The key is read from `ANTHROPIC_API_KEY`. Tests pass a fake response and never read a key.
- Consequences: The names live in `config/model-routing.json`. Changing them is a config edit. The key is never written into the repo.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D21 — Four screenplay formats

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: Ron may hand over a script as Markdown, Fountain, PDF, or Word, or as a partial treatment, or as both.
- Decision: The intake reads all four, plus a partial treatment JSON or a worksheet that uses labels such as `Logline:`. When both are given, the partial treatment wins where Ron already wrote a value, and the screenplay fills the scene beats.
- Consequences: PDF needs `pypdf`. Word needs `python-docx`. Both are in `requirements.txt`.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D22 — Who may spend before a review

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: The Director's own model cost is the work Ron is about to review. Blocking that cost on the Director's own gate would mean Ron must approve the Director before a draft exists.
- Decision: The Director and the Line Producer may record their own small costs against the film cap before their review gates. The five crew agents may not be called, and may not be charged, until the treatment gate and that stage's gate are approved.
- Consequences: A production spend on a new run pauses with a gate request. A two-dollar Director bookkeeping line does not, unless it would break the cap or a locked stage ceiling.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D23 — Theme, tone, and references for The Last Marker

- Date: 2026-11-10
- Context: The Director's first question round asked Ron to lock or replace the draft theme, the tone, and the lookbook.
- Decision: Lock all three as drafted. Theme: "Arrive first. Winning can wait." Feeling: the rider feels small, the engine death is a shock, then quiet relief at the choice to live. Tone: sparse, tense, and sun-bleached, a Sergio Leone spaghetti western played as a quiet desert survival story. Genre: western. References: the Leone framing already in the lookbook, and a score in the spirit of Ennio Morricone with no copied melody.
- Consequences: Those fields stay in the revised treatment. Round 1 does not replace them with new wording.
- Who decided: Ron

## D24 — Miguel chooses life over winning

- Date: 2026-11-10
- Context: The draft had no locked arc for Miguel Vega.
- Decision: He wants to finish the race, but in the end water (life) is more important. He chooses life over winning.
- Consequences: That sentence is his arc in the treatment.
- Who decided: Ron

## D25 — Withhold the canyon water

- Date: 2026-11-10
- Context: The Director asked what the audience should not know yet.
- Decision: Withhold whether the canyon really has water.
- Consequences: That withhold is written on the canyon scene and on the scene where he chooses. The film does not show him finding the water.
- Who decided: Ron

## D26 — The action beats stay

- Date: 2026-11-10
- Context: The draft named three kicks on the Triumph and a stone tap on the cracked spark plug.
- Decision: Yes, those beats.
- Consequences: The treatment keeps those two beats. No new stunt was added in this round.
- Who decided: Ron

## D27 — Exhaust on the right, watch on the left wrist

- Date: 2026-11-10
- Context: The May pilot drifted on exhaust side and watch wrist. The screenplay already said right and left. Ron had not locked them.
- Decision: Lock the Triumph exhaust on the right side. Lock the Breitling Top Time on the left wrist.
- Consequences: Both hero props in the treatment carry that sidedness. The multi-angle reference slot is still empty. Later roles still have to check the locks before and after generation.
- Who decided: Ron

## D28 — The $500 split Ron wants

- Status: The number choice stands. The "gate still open" part is superseded by D29.
- Date: 2026-11-10
- Context: The draft proposed a split of the $500 cap. The numbers add up to $500.
- Decision: The proposed split is approved as written. Director $20, line producer $5, screenwriter $5, art director $25, cinematographer $10, production $270, sound $55, editor $15, QA $45, fix loop $50, treatment $0.
- Consequences: The numbers stay on the treatment. Retakes use the same buckets and the same cap. D29 is what locks them into the run.
- Who decided: Ron

## D29 — The treatment gate is approved

- Date: 2026-11-10
- Context: Ron read the revised treatment and said, "Approve the treatment and lock the split."
- Decision: Approve the Last Marker treatment gate. Lock the $500 stage split from D28 into run phase-1.
- Consequences: `treatment.json` status is approved, version 1.0.0, approval by Ron, with that note. The Line Producer record shows the stage allocations as approved. Spent so far is $0.00 of $500.00. Other stage gates stay on.
- Who decided: Ron

## D30 — Film facts stay in the production folder

- Date: 2026-11-10
- Context: The exhaust side, the watch wrist, the bike's model year, the story year, and the Leone look are facts about The Last Marker. If the studio code knows them, the next film inherits them.
- Decision: Nothing film-specific may be hard-coded in the studio code, the agents, the schemas, or the defaults. Those facts belong only under `productions/the-last-marker/`. The Prop Master and the Script Supervisor read whatever hero props and locked attributes a production defines. The Cinematographer builds a camera package from the production's chosen look. A different film can use another look with no code change.
- Consequences: Phase 2 reads `props/prop-definitions.json` and `look/look.json` from the production. Tests include Harbor Night, a second tiny production with a scarf and a documentary look. The shared treatment draft no longer invents this film's props, theme, or tone. D45 moves the pilot sound prompts into the production folder.
- Who decided: Ron

## D31 — One previs gate for the phase 2 package

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: Phase 2 writes several files. Ron needs one place to review them before a picture call can spend.
- Decision: Add one gate, `previs`, in `config/gates.json`. It starts on. It covers the prop lock, the continuity check, the camera package, the storyboard, and the action breakdown. The drafts can be written while the gate is closed. A picture call cannot.
- Consequences: Run phase-1 is waiting on that gate. The locked dollar split did not gain a new bucket.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D32 — Phase 2 estimates use the locked ceilings

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: The $500 split is already locked. The new roles were not given their own dollars.
- Decision: A phase 2 call is a dry run. The estimate is checked and not charged. The Script Supervisor is checked against the screenwriter ceiling ($5). The Prop Master is checked against the art director ceiling ($25). The Cinematographer is checked against its own ceiling ($10). The Stunt and Action Coordinator is checked against the production ceiling ($270).
- Consequences: A $0 document pass fits. A larger estimate pauses on that ceiling, the same way a picture estimate does. The split Ron locked is unchanged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D33 — Continuity uses the production's phrases

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: The checker has to flag a prop that switches or vanishes, without knowing what the prop is.
- Decision: Each locked attribute can list required phrases and forbidden phrases. A forbidden phrase in a scene or a shot is a contradiction. A shot that shows the prop and never states a required phrase is a missing lock. Scenes are not flagged merely for omitting the phrase. Negative prompts are not scanned, so a "do not show" line is not treated as the picture.
- Consequences: The Last Marker definitions name the exhaust phrases and the wrist phrases. The old pilot shot list has 17 missing exhaust-side statements and no contradictions. The new storyboard states the required phrases.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D34 — The camera package copies the look file

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: Lenses, framing, and lighting have to come from the film, not from a default look in the code.
- Decision: If `look/look.json` exists, the camera package copies its lenses, framing, lighting, and palette. If it does not, the package quotes the treatment and the brief and leaves the lens list empty, with a note that none were named.
- Consequences: The Last Marker package matches its look file. Harbor Night's package matches the documentary look. A model reply that names a look the documents do not contain is discarded.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D35 — Storyboard images are not generated by default

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: Boards need prompts now. They do not need a paid image call.
- Decision: The storyboard stores a prompt and an animatic duration for each shot. `image_generation` is `not-run` unless the caller passes an image client. Tests pass a fake client. There is no image API and no network call on the default path. Board prompts stay on the offline pass even when a language-model key is set, so a model cannot drop a locked phrase.
- Consequences: `storyboard/storyboard.json` has 13 boards for The Last Marker and no image files.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D36 — Model names for the new roles

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: D6 says cheap models for admin and Claude for writing. The new roles need exact ids.
- Decision: The Script Supervisor and the Prop Master use `claude-haiku-5-5`. The Cinematographer and the Stunt and Action Coordinator use `claude-sonnet-5-5`. The names are in `config/model-routing.json`. A model reply that changes a locked prop is discarded.
- Consequences: With no `ANTHROPIC_API_KEY`, or with `--offline`, the files are labeled `offline-deterministic` and still name the model they would have used. The key is never written into the repo.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D37 — Phase 2 files are registered on the existing run

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: The locked split lives on run phase-1. A new run would not have that split unless it was copied.
- Decision: The phase 2 calls use run phase-1. They add dry-run ledger lines at $0 and set the stage to previs, waiting for review. They do not clear the treatment approval.
- Consequences: The run record lists the new files. Spent stays $0.00 of $500.00. Approving previs does not change the split.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D38 — The Last Marker is a subtle watch placement

- Date: 2026-11-10
- Context: Ron reviewed the storyboard and gave a new creative direction. The watch in the script is not a background detail.
- Decision: The film is subtly about the specific Breitling in the script: a Breitling Top Time, black reverse panda dial, worn brown leather rally strap, on the left wrist. It is a very subtle product-placement piece for the buyer who would wear that watch. The dial is legible in a few key close-ups tied to time, the race, and choosing water over finishing. It is never ad-like. No logo-forward hero spins. No dialogue names the brand unless the script already does.
- Consequences: The production brief can carry an optional featured-product section. Only The Last Marker fills one in. The boards name the shots that show the watch and why. The engine stays generic, per D30. A film with no featured product gets no placement section.
- Who decided: Ron

## D39 — Three danger shots in scene 3

- Date: 2026-11-10
- Context: Ron reviewed the storyboard. Scene 3 did not yet show how much danger the rider is in, and it did not pay off the word on the marker.
- Decision: Add three shots to scene 3 of The Last Marker. Early, after he walks away from the bike, the last drop falls from an empty canteen, so the AGUA arrow pays it off. After he crests the rise, buzzards circle in the distant sky. Just before he spots the cairn, an imposing close-up of a buzzard's face and beak hard-cuts, in a Sergio Leone way, against a tight close-up of his eyes. The shots orient the viewer, add drama, and recall that look.
- Consequences: The beats are in the screenplay and in the approved treatment for scene 3. The storyboard is rebuilt from those files. The engine does not name the canteen, the birds, or this film's look. The animatic stays near three minutes by keeping the new shots inside scene 3's time.
- Who decided: Ron

## D40 — The storyboard previs gate is approved

- Date: 2026-11-10
- Context: Ron read the storyboard, including the scene 3 danger shots, and said, "Approve the storyboard previs gate."
- Decision: Approve the previs gate for The Last Marker. The approval covers the storyboard at commit 48d84b0. The storyboard status is approved, with that note. No images are generated.
- Consequences: Run phase-1 records Ron's yes on the previs gate. Picture calls still wait for their own stage gates, and a paid call also waits for the generation gate. Spent stays $0.00 of $500.00. This does not merge the branch.
- Who decided: Ron

## D41 — Build the studio first

- Date: 2026-11-10
- Context: Ron changed direction after the previs gate was approved. The approved boards can wait. The studio should be proven before anyone generates The Last Marker.
- Decision: Build the studio, and make the film later. New picture tools are proven on Harbor Night, or on another synthetic fixture. Do not write a generation plan for The Last Marker in this phase. The last phase is the first film: the finished studio makes The Last Marker from its approved previs.
- Consequences: Phase 3 does not edit that production except to move the pilot sound prompts into its folder. That move is engine cleanup from D30. No images and no video are generated. Spent stays $0.00 of $500.00.
- Who decided: Ron

## D42 — A generation gate before any paid call

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: The treatment gate, the stage gate, and the previs gate already stop a crew call. A paid provider call needs its own yes, so a quote can be written while the money stays locked.
- Decision: Add a gate named `generation` in `config/gates.json`. It starts on. A plan or an estimate does not need it. A generate call does. The older production and sound programs refuse a live call in this build, because no live client is connected.
- Consequences: Ron's yes is a Line Producer approval of the generation gate. This phase does not approve it. The default client returns not-sent and does not open a network connection. Tests use a fake client.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D43 — The quote uses published rates

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: A price has to come from a published page, and the same estimator has to work for any production.
- Decision: `config/generation-rates.json` holds the per-second rates read on 2026-11-10. Gemini Omni 1.2 Flash is $0.07 per second at 720p (Google, 2026-11-05). Seedance 2.0 is $0.3034 per second at 720p, and the fast tier is $0.2419 (fal.ai, read 2026-11-10). Kling 4.0 with no input video is $0.157 per second at 720p (Kling's API pricing, read 2026-11-10). The plan marks every line that is an assumption. A model that is not on the card is not given a price.
- Consequences: The default quote uses Omni for the preview and the final, because that is the cheap picture model. Seedance and Kling are priced only when a routing override names them. Stills and sound stay at $0 on this card, and the plan says why. The retake reserve is one extra preview of every priced shot. The fix-loop reserve is the locked allocation, not a new price.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D44 — Locked phrases go into the prompt

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: D11 says a prop is checked before generation and again on the frames. The frames do not exist yet.
- Decision: When a locked prop is in the shot, the prompt gains a required phrase before it can be sent. A forbidden phrase blocks the call. The phrases come from the production's prop file. After the client returns, `review_dailies` records those phrases. It does not watch a frame and it does not call a model.
- Consequences: Harbor Night's scarf phrase is added in the tests. The generation step records the phrases and does not watch a frame. D47 is the review that watches the picture.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D45 — Sound prompts live in the production folder

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: D30 left the pilot sound prompts inside the sound program. A film's prompts are film facts.
- Decision: The sound program loads `audio/sound-prompts.json` from the production. The Last Marker prompts moved to `productions/the-last-marker/audio/sound-prompts.json`. A production with no file gets an empty library. A live audio call is refused in this build.
- Consequences: The sound program no longer names a film. This closes the loose end in D30.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D46 — The quote reads the cheap model, and the old program stays put

- Status: pending Ron's approval at merge
- Date: 2026-11-10
- Context: D6 names Gemini Omni 1.2 Flash for the picture, with Seedance and Kling as alternates. The older production program still calls Seedance.
- Decision: `config/model-routing.json` keeps `production.model` as `seedance-2.0`, because that is what the older program calls. The preview and final purposes are `gemini-omni-1.2-flash`. The generation pipeline reads those purposes. It does not call the model.
- Consequences: A routing override can point one shot at Seedance or Kling, and the quote uses that row on the rate card. No provider is called.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D47 — A takes manifest in, a dailies report out

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D11 says the frames are checked after generation. Phase 3 recorded the phrases and did not open a picture. The editor should not cut a take Ron has not circled.
- Decision: The Dailies Reviewer reads a production folder and a takes manifest. The checklist is `schemas/takes-manifest.schema.json`. Each take names a shot id and a clip or frame file. The review writes `dailies/dailies-report.json`, checked against `dailies-report.schema.json`, and a Markdown table. Each shot has a best take, a verdict, and reasons. The verdict is circle, retake, or reject.
- Consequences: The Director calls it with `dailies` / `review`. The call waits for the treatment and the previs gate. It does not spend. Tests prove it on Harbor Night. The Last Marker is not reviewed.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D48 — The four checks read the production's files

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: A review that hard-codes a prop, a side, or a look would leak one film into the next. D30 already forbids that.
- Decision: Continuity reuses the locked required and forbidden phrases. The shot list says which props are in frame, so a missing prop is still checked. Shot match asks the description for the shot-list framing word and for a subject word, and compares clip duration when a duration was read. The tolerance is half a second or 20 percent of the shot length, whichever is larger. Look match asks the description for a phrase from `look/look.json`. The description comes from a vision client the caller passes. Tests pass a fake client. With no client, a text file beside the frame is the description. If neither is there, the description is empty. No model is called.
- Consequences: A forbidden phrase is a retake. A required phrase that never appears is a retake. A framing or subject miss is a retake. A look file that is absent skips the look check. The engine does not name a film's props or look.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D49 — Technical checks are local, and optional

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: Some failures do not need a model. A missing file is one. A black or frozen clip is another. The build machine may not have ffmpeg.
- Decision: A missing or empty file is a reject, and the vision client is not called. When ffprobe is installed it reads duration, size, and frame rate. When ffmpeg is installed, a black stretch of half a second or more is a retake. A frozen clip is a retake only when the shot list asked for camera movement. A static hold is not treated as a freeze. A still frame is not scanned for duration, black, or freeze. If the tools are missing, or cannot read the file, those checks are skipped and the file check still stands.
- Consequences: The review runs on a machine without ffmpeg. Tests cover the skip, and they cover a black clip and a frozen moving shot when ffmpeg is installed.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D50 — The dailies gate blocks the editor

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D3 says a person reviews each stage until the crew is trusted. Circled takes should not reach the cut on the reviewer's own say.
- Decision: Add a gate named `dailies` in `config/gates.json`. It starts on. The review can be written while the gate is closed. Ron approves it with the existing approve-gate command. The editor call waits for that approval, after the treatment, the previs gate, and the editor's own gate.
- Consequences: This phase does not approve the gate. Approving it does not spend money and does not run the edit. The editor command is still only routed.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D51 — A retake is an estimate against the fix-loop line

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D5 says retakes count against the $500 cap. D43 priced a retake reserve as one extra preview and kept the fix-loop figure as the locked allocation. The review must not spend, and it must not offer a retake list the line cannot hold.
- Decision: Each shot whose best take is a retake is estimated as one preview, using the same rate card as the generation quote. The sum is compared with the locked fix-loop allocation, minus what that stage has already spent. The prompt fix is text for the next production generate call. It names the locked phrases to state, the forbidden phrases to drop, and the shot-list framing and subject when those failed. The report routes that text to `production generate`. This phase does not call generate.
- Consequences: If the estimate fits, the report says so and charges nothing. If it is over the line, or there is no locked fix-loop line, the list is kept and marked not cleared to spend. Nothing is charged. A missing file is a reject, not a prompt retake. Spent on the proof stays $0.00.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D52 — The cut is an edit decision list

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D50 left the editor routed and not run. Circled takes need a cut Ron can read before sound.
- Decision: The Editor reads the dailies report, the storyboard order, and the scene structure. It writes `edit/rough-cut.json`, checked against `edit-decision-list.schema.json`, plus `edit/rough-cut.md` and a CMX3600 reading copy at `edit/assembly.edl`. JSON is the source of truth. Each event names the shot, the circled take, source in and out, duration, and a transition. The default transition is a cut. A dissolve or a fade is used when the storyboard frame or `edit/editing-style.json` asks for one. Scene markers come from the scene manifest, then the treatment.
- Consequences: The Director calls `editor` / `assemble`. The call still waits for the treatment, the previs gate, the editor's own gate, and the dailies gate. It does not spend. Tests prove it on Harbor Night. The Last Marker is not cut.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D53 — Trim toward the brief, and do not invent a shot

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: A rough cut has to land near the runtime the production asked for. The editor must not add a shot the storyboard does not have.
- Decision: The target runtime is `target_runtime_seconds` on the production brief, then on the scene manifest, then the sum of the treatment's scene durations. A cut that runs long is shortened across the circled shots, down to half a second when the shot is longer than that. A cut that runs short is reported and not padded. The tolerance is `runtime_tolerance_seconds` in `edit/editing-style.json` when that file sets one, otherwise one second or ten percent of the target, whichever is larger. The report states the over or the under.
- Consequences: Storyboard order wins over the shot list. Durations on the board win over a different number on the shot list. The editor does not add a shot to fill time.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D54 — A shot with no circled take is a blocker

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D47 circles a take before it can be cut. A gap in coverage should not be filled by the editor.
- Decision: A storyboard shot with no circled take is left out of the timeline. The edit decision list records a missing-coverage blocker. A retake is routed to generation. A reject, or a shot dailies never reviewed, is routed to dailies. The detail says the shot was not invented.
- Consequences: The cut is not ready for picture lock while a blocker remains. Nothing is charged. This phase does not call generate.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D55 — Locked props are checked across adjacent cuts

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D11 and D48 check a prop inside one shot. A cut can still break the lock between two shots that both show it.
- Decision: For each adjacent pair in the cut, the editor runs the same locked-phrase check the Prop Master and the Script Supervisor use. The text is the shot description plus the dailies notes for the circled take. A forbidden phrase on either side, or a required phrase that one shot states and the next does not, is a continuity flag. The shot stays in the cut. The flag blocks picture lock.
- Consequences: A prop that is not in both shots is not compared. The engine does not name a film's props. The phrases come from the production's prop file.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D56 — The preview is local, and optional

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: Ron needs a picture of the cut, and the build machine may not have ffmpeg. D6 keeps the editor cheap.
- Decision: When ffmpeg is installed, the editor renders `edit/rough-cut.mp4` at 160 by 90. Cuts are concatenated. A dissolve or a fade uses a short crossfade. When ffmpeg is missing, or a source file is missing, the preview is skipped and the edit decision list is still written. The assembly model stays ffmpeg. A notes purpose names Claude Haiku 5.5. This build does not call it.
- Consequences: No key is read. Spent on the proof stays $0.00. The preview is not picture lock.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D57 — Picture lock is a gate, and sound waits

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D3 says a person reviews each stage. Phase 6 is sound. It should not start on a cut Ron has not locked.
- Decision: Add a gate named `edit` in `config/gates.json`. It starts on. The editor can write the cut while the gate is closed, because that cut is what Ron reads. A clean cut also writes `edit/picture-lock.json` with `picture_lock` still false. Ron approves the edit gate with the existing approve-gate command. That approval is picture lock. The sound designer waits for it, after the treatment, the previs gate, and the sound designer's own gate.
- Consequences: This phase does not approve the gate. Approving it does not spend money and does not generate sound. A cut with a blocker, a continuity flag, or a runtime outside the tolerance does not write the picture-lock file. Sound still waits until Ron approves the gate.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D58 — The cue sheet is spotted after picture lock

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D57 left sound waiting on the edit gate. The sound program had a prompt list. It did not time cues to a cut.
- Decision: The Sound Designer and the Composer read the picture-lock cut, `audio/sound-prompts.json`, and `audio/score-brief.json` when the production has them. They write `sound/cue-sheet.json`, checked against `cue-sheet.schema.json`, plus `sound/cue-sheet.md`. Each cue has a type (dialogue, sfx, foley, ambience, or music), a start and end on the cut, the shot ids it belongs to, a prompt, and a source (generated, library, or silence). The Director calls `sound-designer` or `composer` with `spot`. The call waits for the treatment, the previs gate, the sound designer's gate, and the edit gate. It does not wait for the sound gate, because the sheet is what Ron reads. Spotting is computed in code. The admin model is Claude Haiku 5.5. This build does not call it.
- Consequences: Tests prove it on Harbor Night. The Last Marker is not spotted. Nothing is spent.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D59 — Sync is checked, and a miss is a flag

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: A cue that starts before the cut, runs past the end, or sits on a shot the cut does not have would drift out of picture lock.
- Decision: Every placed cue must lie inside the cut. A cue that names a shot the cut does not have is not placed, and the sheet records a missing-shot flag. An effect or a foley cue tied to a shot must start and end within 0.5 seconds of that shot, unless the production sets `sync_tolerance_seconds` on the sound prompts or the score brief. A miss stays on the sheet and blocks ready-for-approval. The cue is not deleted and the shot is not invented.
- Consequences: A clean sheet can be ready for Ron. A flagged sheet is still written. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D60 — A prop sound plays only while that prop is in frame

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D11 locks props in the production folder. A sound that belongs to a prop should stay with the shots that show it.
- Decision: A production can put a sound prompt on a prop, or set `prop_id` on a sound prompt. The cue is checked against the shot list. If the prop is not in that shot, the sheet records a prop-sound flag. The phrases and the prop ids come from the production. The engine does not name them.
- Consequences: The flag blocks ready-for-approval. The cue stays on the sheet so Ron can see it. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D61 — Music follows the score brief, including silence

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D8 describes one film's score. That description is a film fact and does not belong in the spotting code.
- Decision: Music cues are read from `audio/score-brief.json`: tempo, instrumentation, motifs, and the shots where the brief asks for silence. A silence entry wins over a motif on the same shot. A production with no brief gets no invented score. A music prompt in `audio/sound-prompts.json` is spotted onto its assigned shots. On a shot the brief marks silent, that prompt is not placed over the silence.
- Consequences: Harbor Night's brief, when a test writes one, is the proof. The engine does not contain a film's tempo, motif, or instrumentation.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D62 — Sound is priced from the rate card, and a paid call waits

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D43 prices picture from `config/generation-rates.json`. That card has no audio rate. D44 stops a paid picture call until the generation gate is open. Sound should not invent a price or spend.
- Decision: The cue sheet prices generated cues with the same rate card. A model with no row is marked unknown. The unknown estimate is not stored as zero. The total is set against the locked `sound-designer` allocation, which is the Sound line. A model that does have a published row is quoted from that row, including its source. Library and silence cues are not charged. The `generate` command waits on the generation gate. A closed gate does not call the client. The client in this build does not open a network connection. A dispatch estimate that would pass the Sound line pauses before the sheet is written. The Composer's estimate uses that same Sound line.
- Consequences: Spent on the proof stays $0.00. The picture quote is unchanged. It still does not invent an audio price.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D63 — The sound gate sits in front of color and mix

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D3 says a person reviews each stage. Phase 7 is color and mix. It should not start on a cue sheet Ron has not approved.
- Decision: Add a gate named `sound` in `config/gates.json`. It starts on. The cue sheet can be written while the gate is closed. Ron approves it with the existing approve-gate command. Color and mix wait on that approval. This phase does not build color or mix, and it does not approve the gate.
- Consequences: Approving the gate does not spend money and does not generate audio. A flagged sheet can still be approved by Ron. The sheet does not approve itself. `sound_approved` stays false.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D64 — Color and mix wait on picture lock and the sound gate

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D57 made the edit gate picture lock. D63 put the sound gate in front of color and mix. Phase 7 is that stage.
- Decision: The Colorist and the Re-recording Mixer do not run unless Ron has approved both the edit gate and the sound gate. The Director calls `colorist` with `grade` and `mixer` with `mix`. The call also waits for the treatment and the previs gate. It does not wait for the color-mix gate, because the plans are what Ron reads.
- Consequences: Tests prove the refusal on Harbor Night. The Last Marker is not graded or mixed. Nothing is spent.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D65 — The grade is stated once and applied by scene

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D30 says film facts stay in the production folder. A grade is one of those facts.
- Decision: The Colorist reads `look/look.json` and, when the production has one, `look/grade.json`. The base grade is stated once for the whole cut. A scene adjustment is one object, applied to every shot in that scene. A shot adjustment is written only when the production names that shot. The plan is `color/grade-plan.json`, checked against `grade-plan.schema.json`, plus `color/grade-plan.md`. Numbers the production does not supply stay neutral. The engine does not invent a look. When ffmpeg is installed, each shot is graded with eq and colorbalance. A curves string or a `.cube` LUT in the grade file is applied when the production supplies one. The preview is 160 by 90.
- Consequences: Harbor Night's look file is the proof. A different film uses its own files. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D66 — Adjacent shots in a scene are checked for color

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: A grade that treats one scene as one light should not leave neighboring shots looking like different days.
- Decision: Adjacent shots in the same scene are compared. ffmpeg signalstats reads average brightness and average color. A difference past the tolerance is a flag. The tolerance comes from `look/grade.json` when that file sets `consistency`. Otherwise it is 0.12 on a 0 to 1 scale for brightness and the same for color. Shots in different scenes are not compared. When ffmpeg is missing, or it cannot read the picture, that pair is skipped and the grade plan is still written.
- Consequences: A flag blocks ready-for-approval. The shots stay in the plan. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D67 — The mix ducks under dialogue and fades at scene changes

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D58 times cues to the locked cut. The mix has to turn that sheet into levels.
- Decision: The Mixer reads the cue sheet and the stems. Dialogue is the priority stem, at unity unless the production says otherwise. Music and effects are beds, and they duck under each dialogue cue. A scene change gets a short fade. The studio defaults are dialogue at 0 dB, effects at -8 dB, music at -12 dB, an extra -8 dB of ducking, and a 0.5 second fade. `audio/mix-targets.json` can replace any of those. The plan is `color/mix-plan.json`, checked against `mix-plan.schema.json`, plus `color/mix-plan.md`.
- Consequences: A production with no mix-targets file still gets a plan. The defaults are not a film's facts. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D68 — Loudness uses a cited standard, and a miss is a flag

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: A mix needs a target that is not borrowed from one film. D62 already refuses to invent a price when the rate card has no row.
- Decision: The loudness target is EBU R128 unless the production sets another one in `audio/mix-targets.json`. EBU R128 sets programme loudness at -23.0 LUFS and the maximum true peak at -1.0 dBTP. A mix more than 0.5 LU from the target is flagged. The citation is stored on the plan, including https://tech.ebu.ch/docs/r/r128.pdf. When ffmpeg is installed it renders `color/mix.wav` and measures with ebur128, falling back to loudnorm. Outside the target is a flag and the plan is not marked ready. When ffmpeg is missing, the render and the measurement are skipped and the plan is still written. The estimate stays unknown. It is not stored as zero.
- Consequences: Spent on the proof stays $0.00. A production can name a different target without a code change.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D69 — Color and mix do not add a budget line

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D28 locked the $500 split. A new finishing stage should not invent a new line or a new price.
- Decision: The Colorist is checked against the editor allocation. The Mixer is checked against the sound-designer allocation, which is the Sound line. No new line is added to the split. The grade uses Claude Haiku 5.5. The mix render uses ffmpeg. A notes purpose on the mixer also names Claude Haiku 5.5. The names are in `config/model-routing.json`. This build does not call the model. No key is read. A paid grade or mix rate is unknown because `config/generation-rates.json` has no row for one.
- Consequences: The locked split is unchanged. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D70 — The color-mix gate sits in front of final delivery

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D3 says a person reviews each stage. Phase 8 is final delivery. It should not start on a grade and a mix Ron has not approved.
- Decision: Add a gate named `color-mix` in `config/gates.json`. It starts on. The grade and the mix can be written while the gate is closed. Ron approves it with the existing approve-gate command. Final delivery waits on that approval. This phase does not build final delivery, and it does not approve the gate. When ffmpeg is installed, the graded picture and the mix are married into `color/married-preview.mp4`. `color_mix_approved` stays false on both plans.
- Consequences: Approving the gate does not spend money and does not deliver a finished file. A flagged plan can still be approved by Ron. The plan does not approve itself.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D71 — Final delivery waits on the color-mix gate

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D70 put the color-mix gate in front of final delivery. Phase 8 is that stage.
- Decision: The Post Supervisor does not run unless Ron has approved the color-mix gate. The Director calls `post-supervisor` with `deliver`. The call also waits for the treatment and the previs gate. It does not wait for the delivery gate, because the package is what Ron reads.
- Consequences: Tests prove the refusal on Harbor Night. The Last Marker is not packaged. Nothing is spent.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D72 — The delivery spec is production data

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D30 says film facts stay in the production folder. A master size and a list of variants are those facts.
- Decision: The Post Supervisor reads `delivery/delivery-spec.json` when the production has one. The plan is `delivery/delivery-plan.json`, checked against `delivery-plan.schema.json`, plus `delivery/delivery-plan.md`. A missing field uses a cited platform default: 1920 by 1080 from ITU-R BT.709, high-quality H.264 from ITU-T H.264, ProRes 422 HQ from Apple's ProRes white paper when the encoder exists and the spec leaves the codec open, a 1280 by 720 web file from YouTube's published upload encoding, and safe-area insets from EBU R95. The spec can replace any of them. The engine does not invent a film's frame.
- Consequences: Harbor Night's spec is the proof. A different film uses its own file. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D73 — Captions are timed from the dialogue cues

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D58 times dialogue on the locked cut. A delivered file needs those words on screen or beside the file.
- Decision: Sidecar captions are written as SubRip (SRT) and W3C WebVTT. The start, the end, and the words come from the dialogue cues. A cue past the cut is a QC fail. The spec can ask for burned-in captions as well. The sidecars are still written. When ffmpeg cannot burn them, the plan says so and the sidecars remain.
- Consequences: A production with no dialogue cues gets empty caption files. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D74 — QC is local, and a miss is a fail

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D49 already checks a take with ffprobe and ffmpeg, without a paid model. A delivered file needs the same kind of check against the spec.
- Decision: QC writes `delivery/qc-report.json`, checked against `qc-report.schema.json`, and `delivery/qc-report.md`. Each row is pass, fail, or skipped. The checks are duration, resolution, frame rate, loudness against the production target or EBU R128, black stretches, frozen stretches, and caption timing. The tools are ffprobe, blackdetect, and freezedetect, the same local checks the dailies reviewer uses. The QA program's Claude model is not called. A missing file or a missing tool is skipped. A fail makes the verdict fail. The package is still saved.
- Consequences: A flagged package can still be approved by Ron. The report does not approve itself. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D75 — The manifest lists files, checksums, spend, and gates

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D4 says the output is a finished video. The package has to say what was delivered, what it cost, and who approved each stage.
- Decision: The manifest is `delivery/delivery-manifest.json`, checked against `delivery-manifest.schema.json`, plus a Markdown reading copy. Each file has a SHA-256 checksum, cited to FIPS 180-4, when the file is on disk. A file that was not rendered is listed without a checksum. The spend block shows the film total against the cap and the locked stage split, including what each line has spent. Every recorded gate decision is copied: who, when, and the note. A configured gate with no decision is pending. No delivery rate is on the rate card, so that price is unknown and is not stored as zero.
- Consequences: Spent on the proof stays $0.00. The checksum is of the file on disk. It is not invented.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D76 — The delivery folder is a setting

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D9 says finished files belong on Ron's external drive, and the path is not set. A later film should not require a code change to name the drive.
- Decision: The package is written under `delivery/` inside the production folder unless `MOVIE_SWARM_ASSET_ROOT` or `asset_root` in `config/assets.json` is set. The spec may name a different relative folder. An absolute path in the spec is refused. The resolved path and the setting name are stored on the manifest and in `delivery/location.json`. The code does not contain a drive path.
- Consequences: With no setting, the proof stays in the production folder. Setting the asset root moves only the delivery package. Earlier working files stay put.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D77 — The delivery gate marks the film delivered

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D3 says a person reviews each stage. Phase 9 should not treat a package as delivered because the file exists.
- Decision: Add a gate named `delivery` in `config/gates.json`. It starts on. The package can be written while the gate is closed. Ron approves it with the existing approve-gate command. That approval stamps `delivered` on the manifest, records who approved it and when, and sets the run status to completed. The manifest does not stamp itself.
- Consequences: Approving the gate does not spend money and does not generate a picture. A QC fail can still be approved by Ron. The generation gate is a separate switch and stays closed.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D78 — The studio command stops at each gate

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D41 says the studio is built before the film. The stages now exist, and a person should be able to walk them without approving by accident.
- Decision: `scripts/studio.py`, and the Director command `studio`, run the offline pipeline on a production from the treatment through delivery. The default stops at the first gate that is not approved. Run it again after that approval. The order is treatment, previs, production, dailies, editor, edit, sound-designer, sound, color-mix, and delivery. The generation gate is not approved. When no takes manifest exists, the walk writes synthetic placeholders and labels them. A real takes manifest is left alone. `run_studio(..., auto_approve=True)` is a test harness. It records the approver as `test-auto-approve`. The command line does not set it.
- Consequences: Harbor Night is the proof. The Last Marker is not walked. Nothing is spent.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D79 — Delivery uses the cheap admin model and adds no budget line

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D6 says cheap models for admin work. D28 locked the $500 split. A packaging stage should not invent a model call or a new price.
- Decision: The Post Supervisor is checked against the editor allocation. No new line is added to the split. The role uses Claude Haiku 5.5 for a note. The render uses ffmpeg. QC is local. The names are in `config/model-routing.json`. This build does not call the model. No key is read. A paid delivery rate is unknown because `config/generation-rates.json` has no row for one.
- Consequences: The locked split is unchanged. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D80 — Offline stays the default

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: The provider clients could call out as soon as a key was present. A key on the machine should not spend money by itself.
- Decision: A real provider call is sent only when the command passes `--live`. Without that flag, the Director, the Line Producer, picture, and sound stay offline even if `ANTHROPIC_API_KEY`, `FAL_KEY`, or `ELEVENLABS_API_KEY` is set. The studio command never passes `--live`.
- Consequences: Tests do not need a key. A person can set a key and still get the offline draft. The test shot command with no `--live` records nothing sent.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D81 — Four checks before any live call

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D44 already stops a paid call while the generation gate is closed. A live client needs the rest of the lock as well.
- Decision: A live call also needs the generation gate approved through the Line Producer, a locked stage split, and an estimate that fits the money left on that stage line and under the $500 cap. The lines stay the locked split: Production $270, Sound $55, Fix loop $50, QA $45, Art $25, Director $20, Editor $15, Cinematographer $10, Screenwriter $5, Line Producer $5. The key is read from the environment at call time. Picture uses `FAL_KEY`. Sound uses `ELEVENLABS_API_KEY`. Text uses `ANTHROPIC_API_KEY`.
- Consequences: A missing key, a closed gate, or an estimate over the line refuses the call before any HTTP request. The refusal names the missing piece and does not include the key.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D82 — An unknown price is refused

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D43 and D62 refuse to invent a price. Audio, color, delivery, and the Claude text models are not on the rate card as dollar amounts. No source in this repo names one.
- Decision: If the rate card has no price for the model, the call is not sent. `--price-override` writes an approval request for that one dollar amount. The call waits until Ron approves that request. The approval is recorded. It is not copied onto the rate card as a published price. The card is not given a made-up audio, color, or delivery price.
- Consequences: Harbor Night can prove the refusal and the one-call override with a fake transport. Spent on that proof stays $0.00.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D83 — The ledger reserves the estimate, then records the actual

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: A call can fail after the provider has accepted it. The budget has to show the hold before the bytes come back.
- Decision: The Line Producer writes the estimate on the ledger before the HTTP call. When the provider reports a dollar amount, that same row keeps the estimate and the actual, and the booked amount becomes the actual. When the provider does not report one, the booked amount stays the estimate and the note says so. The request is hashed without the key. A second run of the same hash uses the saved file, writes a dry-run line, and does not charge again.
- Consequences: A crash after the reservation does not send a second paid request. The running total matches the booked amount.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D84 — A failed call stays at the stage gate

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: A timeout or a provider error should not skip the stage or look like a finished film.
- Decision: Connection errors are retried with a short backoff. A timeout, or a 5xx after those retries, keeps the estimate booked when the provider may already have accepted the request, and the same request is not sent again. A connection error that never reached the provider releases the reservation. The run status goes back to waiting. The stage does not move forward.
- Consequences: The generation gate stays as Ron left it. The pipeline does not advance to the next stage because a call failed.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D85 — Keys stay in the environment, and files follow the asset root

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D9 says finished files belong on a drive whose path is a setting. A key must not land in the repo, the ledger, or an error message.
- Decision: Keys are read from the environment only. They are stripped from errors, the ledger, the provider cache, and the test-shot record. `.env.example` lists the three names with empty values. `.env` stays gitignored. Downloaded media goes through `resolve_asset`. That uses `MOVIE_SWARM_ASSET_ROOT` when it is set, otherwise `asset_root` in `config/assets.json`, otherwise the production folder. `asset_root` stays null. No drive path is written in code.
- Consequences: A test can set a fake key and check that it never appears in the production folder. The proof media stays in the temp folder.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D86 — Only a cited endpoint can be called

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: The picture routing names Gemini Omni 1.2 Flash. The older production program names Seedance on fal. Sending Gemini to a guessed fal address would invent an integration.
- Decision: A live picture call uses the fal queue only when that model's row in `config/generation-rates.json` names an endpoint. Seedance 2.0 and Seedance 2.0 fast use the addresses already in `config/model-routing.json`. Gemini Omni and Kling have prices and no endpoint, so a live call for them is refused. ElevenLabs dialogue, effects, and music use the HTTP paths for those three jobs. A dialogue call with no voice id is refused. The engine does not pick a voice.
- Consequences: The default test shot on Harbor Night refuses until a routing override names Seedance, or until an endpoint for Gemini is added from a cited source. Nothing is spent either way.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D87 — Six prep roles, and no new gate

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: The previs package had a Prop Master, a Script Supervisor, a Cinematographer, and a Stunt Coordinator. A shooting schedule, a lighting plan, camera support, wardrobe, makeup, and a VFX breakdown were not roles yet. D3 already puts a gate on every stage that spends or that hands work to the next paid stage.
- Decision: Add the Assistant Director, the Gaffer, the Key Grip, the Costume Designer, Makeup and Hair, and the VFX Supervisor. They write their files while the previs gate is closed, the same way the phase 2 package does. The VFX review is written with the dailies report. No new gate is added. The Director calls them through the Line Producer. The calls do not spend.
- Consequences: `scripts/studio.py` writes the six files before it stops at the previs gate, and it writes the VFX review before it stops at the dailies gate. The generation gate stays closed. Harbor Night is the proof. The Last Marker folder is not changed.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D88 — The new roles bill against the locked split

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D28 locked the $500 split. The new roles were not given their own dollars. A dry run is checked and not charged, the same way D32 checks the phase 2 estimates.
- Decision: The Assistant Director is checked against the line producer allocation ($5). Scheduling is admin. The Gaffer and the Key Grip are checked against the cinematographer allocation ($10). The Costume Designer and Makeup and Hair are checked against the art director allocation ($25). The VFX Supervisor, including the dailies review, is checked against the editor allocation ($15). The breakdown and the turnover are notes for the editor and the colorist, so the review stays on that same line instead of the fix-loop retake reserve. No new line is added. The locked amounts stay Production $270, Sound $55, Fix loop $50, QA $45, Art $25, Director $20, Editor $15, Cinematographer $10, Screenwriter $5, Line Producer $5.
- Consequences: A $0 document pass fits. A larger estimate pauses on that ceiling. The split is unchanged. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D89 — Wardrobe and makeup use the prop lock

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D11 and D33 lock a prop with required phrases and forbidden phrases. A coat or a haircut can drift the same way, and the checker must not know which film it is reading.
- Decision: Costume definitions live in `wardrobe/costume-definitions.json`. Makeup definitions live in `makeup/makeup-definitions.json`. The lock copies garment, color, condition, makeup, hair, effects, and the change by scene. Phrases are checked the way props are: a forbidden phrase is a contradiction, and a shot that shows the person and never states a required phrase is a missing lock. The Script Supervisor reads the locked files. Dailies and the edit use the same check when the shot lists the person. A production with no file gets no invented garment and no invented effect.
- Consequences: Harbor Night locks a coat and short hair from its own files. A shot that says the coat is light, or the hair is long, is drift. The engine does not name a garment of its own.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D90 — Light and grip copy the camera plan

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D34 copies lenses and lighting from the production's look. A gaffer plan that invented a color temperature, or a grip plan that invented a rig, would put one film's light into the next.
- Decision: The Gaffer copies key, fill, practicals, time of day, color temperature, and contrast ratio from the camera package, the look, and the scene heading. A number or a ratio the production did not write is `not named`. The prompt note is those same words. Shots in one scene that disagree about the time of day are flagged. The Key Grip reads the shot's movement for the support. Rigging quotes the gaffer's practicals and fill, and does not add a source. If the camera package names one support and the shot list names another, the shot list wins and the row says they disagree.
- Consequences: Harbor Night's plan says night and the fluorescent practical from its look file. It does not store a Kelvin number. A static shot is sticks even when the package says handheld, and the note says so. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D91 — The call sheet groups the shot list and flags stunts

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: Production needs an order: which shots share a place, a setup, a cast, and a prop, and which of them are safety beats. That order should not be a new approval.
- Decision: The Assistant Director reads the shot list, the scene manifest when the production has one, otherwise the treatment scenes, the lighting plan, and the stunt breakdown. The schedule keeps storyboard order. Days group by location. Setups group by scene, time of day, and the gaffer's source. A shot whose text matches a stunt beat carries that beat's safety line. The file is `schedule/shooting-schedule.json`. It is handed to production. It does not open the production gate by itself.
- Consequences: Harbor Night is one night exterior, one setup, and the step onto the dock is flagged from the stunt breakdown. No beat was added. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D92 — VFX is a breakdown, then a dailies read

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: Some shots need compositing. The editor and the colorist need to know which ones before the cut and the grade. D3 does not require a separate gate for a note Ron already reads at previs and at dailies.
- Decision: `vfx/vfx-needs.json` lists the production's tasks. The breakdown includes a shot when that file names it, or when the shot text itself names an effect. Each row has the task, the method, and the risk. Turnover notes are addressed to the editor and the colorist, and their reading copies quote the notes when the breakdown exists. After dailies, the review checks that a circled VFX shot still shows the note. A miss is drift. The review does not spend and does not add a gate.
- Consequences: Harbor Night's needs file marks the practical lamp as a composite. A circled take that drops that note is drift. A shot that does not ask for an effect is not given one. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D93 — The new roles use the cheap admin model

- Status: pending Ron's approval at merge
- Date: 2026-11-11
- Context: D6 says cheap models for admin. These six roles compute a checklist from files the production already wrote. They are not a writing pass and they are not a picture call.
- Decision: The Assistant Director, the Gaffer, the Key Grip, the Costume Designer, Makeup and Hair, and the VFX Supervisor use Claude Haiku 5.5. The names are in `config/model-routing.json`. A model reply that changes a locked garment, a locked effect, the schedule, the lighting plan, the grip plan, or the breakdown is discarded. The offline path does not call the model and does not read a key. None of these commands pass `--live`. They cannot bypass the generation gate, the budget, or the key.
- Consequences: With no key, the files are labeled `offline-deterministic` and still name the model they would have used. Harbor Night's proof spends $0.00. The provider rules from D80 through D86 are unchanged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D94 — Title and Graphic Design, and a graphics gate

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: No role owns a film's graphic identity. The Art Director owns the in-film look. The Post Supervisor grabs one frame for the poster. The storyboard skips TITLE CARD lines. Titles, credits, subtitle styling, a designed poster, and collateral have nowhere to live.
- Decision: Add Title and Graphic Design. The role writes research, then a brand guide, then the graphic specs. Research and the draft guide are written with the previs package, while a new graphics gate stays closed. Building a graphic waits until that gate approves the guide. The Director calls the role through the Line Producer. The calls do not spend.
- Consequences: `scripts/studio.py` writes the research and the draft guide before it stops at the previs gate, and it writes the graphic specs after the graphics gate. The generation gate stays closed. Harbor Night is the proof. The Last Marker folder is not changed.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D95 — The role bills to the Art line

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: D28 locked the $500 split. Costume and makeup already bill to the art director allocation. A new line would change that lock.
- Decision: Title and Graphic Design is checked against the art director allocation ($25). No new line is added. The locked amounts stay Production $270, Sound $55, Fix loop $50, QA $45, Art $25, Director $20, Editor $15, Cinematographer $10, Screenwriter $5, Line Producer $5.
- Consequences: A $0 document pass fits. A larger estimate pauses on the Art ceiling. The split is unchanged. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D96 — Research, then the guide, then the graphics

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: A title treatment that is not grounded in the film's own documents would put one film's lettering into the next. The guide has to stay tied to the look as the look changes.
- Decision: `graphics/research.json` is written first from the treatment, the screenplay, the brief, the style bible, and the director's notes. Each item is sourced, with the file and the field, or marked inferred. `graphics/brand-guide.json` is built only from that research. Every rule traces to a research item. Fonts, palette values, the wordmark, layout and safe area, image treatment, and the do's and don'ts live there. The guide carries a version and a change log. If the style bible or the look changes, the research is written again and the guide is rebuilt, logged, and returned to draft. A graphic is a hard error when the research is missing, or when the guide is missing or unapproved. Title cards are read from TITLE CARD lines in the screenplay. The storyboard still skips those lines. End credits are copied from the Line Producer credit record. No name is added. Subtitle styling is specified here. Cue times stay with the Post Supervisor.
- Consequences: Harbor Night's guide uses the colors in its style bible and does not name a typeface the documents do not name. A changed look produces a new draft and a log line. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D97 — The designed poster is key-art-poster.png

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: The delivery package already writes `poster.png` as one frame from the locked cut. A designed marketing poster needs its own file, or the two jobs get mixed.
- Decision: The frame grab stays `poster.png`. The designed poster, with the title, an optional tagline, and a billing block, is `graphics/key-art-poster.png`. Thumbnails are `graphics/thumbnail-16x9.png` and `graphics/thumbnail-9x16.png`. The social card is `graphics/social-card.png`. Sizes come from the production's delivery spec or treatment. A size the documents do not name is left unnamed. When ffmpeg is installed and a size is named, a flat placeholder can be rendered. When it is not, the spec is still written. The delivery manifest lists these files when the graphics package is present. QA checks spelling, credits, safe areas, and resolution against the guide. Title and credit overlays are handed to the editor and the colorist before the master.
- Consequences: A delivery with no graphics package still writes `poster.png` the same way. A delivery with a package lists both files and does not treat them as the same poster. Nothing is charged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D98 — Title and Graphic Design uses the cheap admin model

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: D6 says cheap models for admin. This role computes a checklist from files the production already wrote. It is not a writing pass and it is not a picture call. D80 through D86 still govern any live call.
- Decision: Title and Graphic Design uses Claude Haiku 5.5. The name is in `config/model-routing.json`. A model reply that adds a fact is discarded. The offline path does not call the model and does not read a key. None of these commands pass `--live`. They cannot bypass the generation gate, the budget, or the key.
- Consequences: With no key, the files are labeled `offline-deterministic` and still name the model they would have used. Harbor Night's proof spends $0.00. The provider rules from D80 through D86 are unchanged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D99 — One budget and one calculator

- Status: decided
- Date: 2026-11-11
- Context: The film had a hard $500 cap and a locked split, and a trailer would have needed a second set of numbers.
- Decision: There is one budget and one calculator. The trailer is a line on that budget, on the same screen as the rest of the film.
- Consequences: `tools/budget-calculator/index.html` is the only calculator. It reads and writes `budget.json`. The engine reads that same file.
- Who decided: Ron, 2026-11-11 call

## D100 — The budget is not a hard cap

- Status: decided
- Date: 2026-11-11
- Context: A film should be able to come in under the number, or a little over it, the way a production budget works.
- Decision: Going past a line or the film total still pauses the spend and writes an approval request. Ron can approve that overage without editing the budget. The ledger records it. Reports say under or over, and by how much. Nothing is spent past the budget without that record.
- Consequences: A film with no `budget.json` still pauses the same way. With a budget file, the approval does not change the file, and the status shows the gap.
- Who decided: Ron, 2026-11-11 call

## D101 — The budget number is per film

- Status: decided
- Date: 2026-11-11
- Context: One film might be $50. Another might be $2,000. The old cap was one number for every film.
- Decision: Each film sets its own total in `budget.json`. Any amount is allowed.
- Consequences: $50 and $2,000 use the same line shares and scale the dollars. A film with no file keeps the $500 cap and the locked split.
- Who decided: Ron, 2026-11-11 call

## D102 — The trailer is optional and uses approved takes

- Status: decided
- Date: 2026-11-11
- Context: Some films need a teaser and a trailer. Some do not. The trailer should not invent shots, and it should not come out of the Editor's line.
- Decision: The trailer is optional. It runs only when the film turns it on. It uses approved takes only. It has its own Marketing and Distribution line. The Editor is a collaborator and does not bill for it.
- Consequences: A film with the trailer off delivers as before. A beat that cannot be made from an approved take is dropped and logged. The spend is checked against Marketing and Distribution.
- Who decided: Ron, 2026-11-11 call

## D103 — Marketing takes 10 percent, and the other lines scale

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: The trailer needs a line, and the film total should still match the budget.
- Decision: The suggested Marketing and Distribution share is 10 percent of the film budget. When the trailer is on, the other lines are multiplied by the rest, so the lines plus marketing equal the budget. The share can be changed per film.
- Consequences: At $500 with the trailer on and no contingency, marketing is $50 and Production is $243. With the trailer off, the lines stay on the locked split.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D104 — Contingency is 10 percent, held inside the budget

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: Reshoots, extra research, and a model upgrade need a reserve that is still part of the budget.
- Decision: The suggested contingency is 10 percent, held back from every line, including marketing. It can be 0. Retakes and tier upgrades draw on it after the stage line is spent. A new budget written without a contingency flag uses 10. A film with no budget file uses 0, so today's ceilings stay exact.
- Consequences: At $500 with 10 percent contingency and the trailer off, the lines keep 90 percent of today's dollars and the reserve is $50.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D105 — Tiers are good, better, and best

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: A stage should be able to move up a model when the line can hold it.
- Decision: Each stage names good, better, or best. Picture good is Gemini Omni 1.2 Flash. Better is Seedance 2.0 fast at 720p. Best is Seedance 2.0 at 720p. Seedance 2.0 at 1080p is a top option, not a fourth tier. Prices live in `config/rate-card.json`. A price this repo cannot verify is marked unknown. A tier change that fits the line plus contingency is applied. One that does not fit uses the same approval request as an overage.
- Consequences: The calculator and the budget command both read the rate card. A live call still uses `config/generation-rates.json` and still refuses an unknown endpoint.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D106 — The budget files

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: The engine, the calculator, and the Line Producer need one file shape.
- Decision: The film budget is `budget.json` in the production folder, checked against `film-budget.schema.json`. The rate card is `config/rate-card.json`. Trailer research, the spoiler guard, the plan, and the cut live under `marketing/`. When the production does not name trailer lengths, the teaser is 15 seconds and the trailer is 45 seconds, and the plan says so.
- Consequences: The calculator exports that same `budget.json`. A missing length is labeled as a default.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D107 — A trailer gate that does not block delivery

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: Ron should be able to accept the trailer, and a film without one should still ship.
- Decision: `config/gates.json` has a `trailer` switch. It starts on, so the gate starts closed. The studio can write the trailer while the gate is closed. Delivery does not wait for it. Approving the gate stamps the cut. The film can be delivered either way.
- Consequences: Harbor Night with the trailer off does not write `marketing/`. With the trailer on, the files are written and the gate stays closed until Ron approves it.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D108 — The Trailer Editor uses the cheap admin model

- Status: proposal, pending Ron's approval at merge
- Date: 2026-11-12
- Context: D6 says cheap models for admin. This role follows a procedure. The research, the guard, and the plan are production data.
- Decision: The Trailer Editor uses Claude Haiku 5.5. The name is in `config/model-routing.json`. The skill file holds the procedure. The production folder holds the research, the guard, and the plan. The offline path does not call the model and does not read a key. None of these commands pass `--live`.
- Consequences: With no key, the files are labeled `offline-deterministic` and still name the model they would have used. Harbor Night's proof spends $0.00. The provider rules from D80 through D86 are unchanged.
- Who decided: Cursor cloud agent. Pending Ron's approval at merge.

## D109 — Phase 8.9, the key-test fixes

- Status: decided
- Date: 2026-11-12
- Context: The first real key test, on an iMac, found that the machine setup, the `.env` file, and the test-shot model did not match the guide. A live call for the routed picture model was refused because that model has no fal address.
- Decision: Fix those gaps in the engine and the guide. No paid call is made in this phase. The production folder for the first film is not changed.
- Consequences: The proof stays on Harbor Night. Spent on that proof stays $0.00. The choices for how the fixes work are D110 through D115. Those are proposals.
- Who decided: Ron, 2026-11-12

## D110 — An unwired picture model is refused

- Status: proposed
- Date: 2026-11-12
- Context: D86 refuses a live picture call when the rate row has no endpoint. The routed good tier is Gemini Omni 1.2 Flash, which is in that state. One option was to fall back to the cheapest wired model, Seedance 2.0 fast, and say so. That model costs more than the good tier.
- Decision: Do not switch models. If the resolved model has no endpoint, the call is refused. The message names the wired picture models and the `--model` or `--tier` flag that selects each one. Gemini Omni 1.2 Flash stays on the rate card as planned, with a price and no endpoint. Kling stays unwired the same way.
- Consequences: The calculator and a run still name the same model for a tier. A run of the good tier does not silently bill Seedance 2.0 fast. The guide's first real shot names that model on purpose. D86 still holds: only a cited endpoint can be called.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D111 — Test-shot precedence, and tiers that match the budget

- Status: proposed
- Date: 2026-11-12
- Context: D105 puts good, better, and best on the budget rate card. A test shot ignored that file and always used the preview purpose, which is the unwired good-tier model. The calculator and a real shot could name different models.
- Decision: A test shot resolves `--model`, then `--tier`, then the film's `budget.json` tier for that stage, then `config/model-routing.json`. The production tiers in the routing file match the budget rate card. Good is Gemini Omni 1.2 Flash. Better is Seedance 2.0 fast. Best is Seedance 2.0. A model or tier that is not on the rate card is rejected before a call. The generation quote still prices the preview and final purposes, so an existing quote does not change.
- Consequences: `--model seedance-2.0-fast` and `--tier better` are the same picture model. A film whose budget says best uses Seedance 2.0 when the command does not pass a flag. A film with no budget file still uses the preview purpose.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D112 — The commands load `.env` and do not override the shell

- Status: proposed
- Date: 2026-11-12
- Context: D85 keeps keys in the environment. The guide told Ron to copy `.env.example`, and the commands did not read `.env`. He had to load it in the shell.
- Decision: Every command in `scripts/` loads the repo-root `.env` at start. A variable that is already set is left alone, including a variable set to an empty string. A missing file is ignored. Values are not printed, returned, or logged. python-dotenv is not a dependency. The loader is the standard library.
- Consequences: Filling `.env` is enough for a later `--live` command. A key exported in the shell still wins. `.env` stays gitignored. `.env.example` stays empty.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D113 — A test shot prints its quote before anything is sent

- Status: proposed
- Date: 2026-11-12
- Context: A dry run said that offline is the default and did not show the model, the tier, or the price. Ron could not see the estimate before a live call.
- Decision: A dry run prints, for the shot, the model, the tier, the provider, the resolution, the duration, the estimated cost from `config/generation-rates.json`, the production line remaining, and the film remaining. It says nothing was sent. The same summary is printed before a `--live` call, before any request is sent.
- Consequences: The price uses the same per-second math as the generation quote. Seedance 2.0 fast at 720p is $0.2419 per second. Harbor Night's boarded first shot is 2.087 seconds, so that dry run estimates $0.5048. A shot of 4 seconds at the same rate is $0.9676. No key is read for the dry run.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D114 — Doctor checks the machine and does not spend

- Status: proposed
- Date: 2026-11-12
- Context: The system Python on the test machine did not have the requirements, and the guide had no install step. There was no free check for ffmpeg, `.env`, or the keys.
- Decision: `scripts/doctor.py` prints the Python version, whether the requirements import, whether ffmpeg is on the path, whether `.env` is present, whether each of the three keys is set, and whether an asset root is set. Keys are yes or no. Paths and values are not printed for the keys or the asset root. There is no network call unless `--ping` is passed. A ping is Anthropic `GET /v1/models` and ElevenLabs `GET /v1/voices`, and the report is the HTTP status only. fal is not pinged. This repo has no free fal auth check. The line says it is not checked and needs a paid test shot.
- Consequences: A missing import exits with status 1. A missing key, a missing `.env`, or a missing ffmpeg is reported and does not by itself fail the command. The ElevenLabs key needs the Voices: Read permission for the voice list. The guide says so.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D115 — The readable treatment exists before the gate

- Status: proposed
- Date: 2026-11-12
- Context: The guide told Ron to read `treatment/treatment.md` before the treatment gate. Intake writes that file. A copied film that already has `treatment.json` did not get the markdown until the gate was approved.
- Decision: If `treatment/treatment.json` exists and `treatment/treatment.md` does not, starting the run or stopping at the treatment gate writes the markdown from the JSON. That write does not approve the gate and does not change the JSON. The guide tells Ron to read the markdown, then approve.
- Consequences: Harbor Night's fixture still has no markdown in the repo. The first status or studio stop on a copy writes it. An approved gate still rewrites both files, as it did before.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D116 — Phase 8.10, the fal picture-call fix

- Status: decided
- Date: 2026-11-12
- Context: The first live test shot reached fal. The queue accepted the key and returned a request id. The status check used the full endpoint path, and fal returned 405. A result read at the app path came back as a validation error. The body was wrapped under `input`, and the duration was 2.087 seconds. The estimate stayed on the ledger with no actual.
- Decision: Fix that picture call in the engine. No paid call is made in this phase. The production folder for the first film is not changed.
- Consequences: The proof stays on Harbor Night. Spent on that proof stays $0.00. The choices for how the fix works are D117 through D119. Those are proposals.
- Who decided: Ron, 2026-11-12

## D117 — The fal queue body is the input, and polling uses the returned URLs

- Status: proposed
- Date: 2026-11-12
- Context: fal's queue REST API takes the model fields at the top of the JSON body, posted to `https://queue.fal.run/` plus the endpoint. The submit response includes `status_url` and `response_url`. Those URLs use the owner and the app, the first two path segments, and a URL built from the full endpoint returns 405. A completed result whose body is an error, or a `detail` list, is a rejection.
- Decision: Send the payload as the JSON body. Poll `status_url` and `response_url` from the submit response. If either is missing, build the URL from the first two path segments only, on `queue.fal.run`. A result body with `detail` or `error` fails the call. The message names the field and the reason. It does not keep the echoed input. Keys are still stripped.
- Consequences: A contract test checks the method, the URL, and the top-level fields, and it checks that the header names are present. It does not check header values. Polling is checked against the URLs the submit response returned, and against the two-segment fallback.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D118 — Picture duration is rounded up to a length the model accepts

- Status: proposed
- Date: 2026-11-12
- Context: Seedance 2.0 and Seedance 2.0 fast accept duration `auto`, or a whole number from 4 to 15. Fast accepts 480p and 720p. Seedance 2.0 also accepts 1080p and 4k. Those rules were read from the fal API pages on 2026-11-12. Kling 4.0 on fal accepts an integer from 3 to 30, at 720p or 1080p, read the same day from `kling/v4/text-to-video`. The per-shot multi-prompt minimum of 1 second is a different field. Kling still has no endpoint. Gemini Omni's 3 to 15 second quote stays an assumption. Whole seconds were not verified for Gemini, so a length inside that range is not rounded.
- Decision: The rate rows store the minimum, the maximum, whether the length must be a whole number, and the allowed resolutions. A shot is rounded up to the next allowed length. The request sends that length. The estimate bills that length. The dry-run line shows both when they differ: `duration 2.087 seconds (sent as 4 seconds)`. The generation quote and the film budget use the same rule, so a short shot is not priced at its raw length. One call that is longer than the maximum is refused before anything is sent. The quote still shows the pieces.
- Consequences: Harbor Night's first shot at Seedance 2.0 fast, 720p, is sent as 4 seconds and estimated at $0.9676. That is 4 times $0.2419. The $0.5048 figure in D113 was the raw 2.087 seconds. Kling's duration rule is on the row, and a live call for Kling is still refused. The 1080p Seedance price stays unknown.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D119 — A rejected call releases the booked estimate

- Status: proposed
- Date: 2026-11-12
- Context: The live failure left a ledger row booked with actual null. Zeroing that row would erase the booking. A timeout or a server error may still have been accepted, so those stay booked.
- Decision: When a call fails at submit or validation and nothing was produced, the engine appends a release entry for the same amount and takes it off the running total. The original entry stays. An approved request records the release. `scripts/line-producer.py release --entry <id> --by ron --note "..."` does the same thing by hand for an estimate that is still booked and has no reported charge. A second release of the same entry is refused.
- Consequences: A connection error, a client rejection, and a completed result that is an error body all net to $0 and keep the history. A timeout or a server error still leaves the estimate booked. The hand command is how that stuck row is released.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D120 — Phase 8.11, the live-shot cleanup

- Status: decided
- Date: 2026-11-12
- Context: The first successful live picture shot used Seedance 2.0 fast, 4 seconds, 720p, through the fal queue. The submit worked. fal took about 241 seconds. The poll gave up after about 90 seconds and left the estimate booked. Two re-runs collected the clip. The re-run checked the same request and did not send a new one. fal did not report a dollar amount. The older picture program still posted a wrapped body. Doctor said the asset root was not set, because a non-interactive shell does not read `~/.zshrc`.
- Decision: Clean that up in the engine. No paid call is made in this phase. The production folder for the first film is not changed.
- Consequences: The proof stays on Harbor Night. Spent on that proof stays $0.00. The choices for how the cleanup works are D121 through D124. Those are proposals.
- Who decided: Ron, 2026-11-12

## D121 — A fal picture call waits ten minutes, and says so while it waits

- Status: proposed
- Date: 2026-11-12
- Context: The poll stopped after 40 checks, two seconds apart, about 90 seconds in all. A real Seedance job can take a few minutes. The live one took about four.
- Decision: The default wait is 600 seconds, from `config/providers.json`. The first pause is 5 seconds. Each later pause grows by 5 seconds until it reaches 15. A progress line prints about every 30 seconds: the elapsed time, the fal status, and the queue position when fal sends one. `--wait` on a test shot replaces the 600 seconds for that one call. A timeout still leaves the estimate booked, and a re-run checks the same request and does not send a new one. The message is the one already used.
- Consequences: A four-minute Seedance job finishes inside the default wait. A shorter `--wait` can still time out on purpose. Tests pass a pause of zero, so they do not sit on the clock. No live call is made to prove the window.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D122 — The older fal client uses the same queue contract

- Status: proposed
- Date: 2026-11-12
- Context: `agents/05-production/src/fal_client.py` posted `{"input": payload}` and built status URLs from the full endpoint path. The generation pipeline was fixed in Phase 8.10. This older program was not. The picture command that the Director still launches imports this file, so the import has to keep working when that process starts from the agent folder.
- Decision: The queue helpers post the input fields at the top of the body. They poll `status_url` and `response_url` from the submit response, and fall back to the first two path segments. A body with `detail` or `error` fails the call and does not keep the echoed input. Seedance duration is rounded with the same rule as the pipeline. The shared helpers are imported when a queue call runs, not when the file is imported. `generate_shot` still uses the fal SDK. The contract tests use a fake session.
- Consequences: A caller of the older queue helpers no longer sends the wrapped body or the full-path status URL. The production estimate command still starts. No paid call is made.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D123 — Doctor names where the asset root came from

- Status: proposed
- Date: 2026-11-12
- Context: Ron set `MOVIE_SWARM_ASSET_ROOT` in `~/.zshrc`. The film commands load `.env`. A non-interactive shell does not read `~/.zshrc`, so doctor said the asset root was not set. D114 said not to print the path.
- Decision: `.env.example` lists `MOVIE_SWARM_ASSET_ROOT` with an empty value and a comment. Doctor says whether the value came from the shell, from `.env`, or from `config/assets.json`, and whether that folder exists. It does not print the path. The shell still wins over `.env`.
- Consequences: A path that lives only in the shell profile is still invisible until it is also in `.env` or the shell that launches the command. No real path is written in the repo.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D124 — A booked cost with no reported dollars is an estimate

- Status: proposed
- Date: 2026-11-12
- Context: The live fal result had no dollar amount. The ledger kept the estimate in `amount_usd` and left `actual_usd` null. Status printed that number as spent, which reads like a measured charge.
- Decision: A settled call whose provider did not report dollars sets `actual_source` to `estimate`. A call that did report dollars sets `actual_source` to `provider`. The booked amount stays the estimate when the source is `estimate`. Status adds a line when any of that spend is still the estimate, and it says the provider did not report a dollar amount. A release takes that entry off the line.
- Consequences: A report can tell a quote from a measured charge. The running total does not change. The original ledger row stays.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D125 — The first film starts from the top

- Status: decided
- Date: 2026-11-12
- Context: D41 said build the studio first and leave `productions/the-last-marker` alone, apart from moving the pilot sound prompts. The studio through Phase 8.11 is on main. Ron said in chat on 2026-11-12, "lets do The Last Marker from the top."
- Decision: D41 is lifted for `productions/the-last-marker` only. This is the first-film phase. The engine stays generic. Prior run state and approved gate records for this film move to `archive/` inside that folder. A new run starts at the treatment gate. The screenplay, the prop locks, the look, the style bible, and Ron's locked treatment answers stay as inputs. They are not an approved gate.
- Consequences: The live treatment is a draft. Intake can draft again. Run `first-film-1` stops at the treatment gate. Spent on this step stays $0.00. No live call was made. Other productions are unchanged.
- Who decided: Ron, 2026-11-12

## D126 — Trailer, contingency, and the picture tier for The Last Marker

- Status: proposed
- Date: 2026-11-12
- Context: Ron approved the $500 stage split on 2026-11-10: Production $270, Sound $55, Fix loop $50, QA $45, Art $25, Director $20, Editor $15, Cinematographer $10, Screenwriter $5, Line Producer $5. He wants finished films to include marketing materials. The budget file can turn the trailer on, hold contingency, and name a picture tier. Those three were not part of the 2026-11-10 approval.
- Decision: `productions/the-last-marker/budget.json` keeps that split as the line shares. The trailer is on, using the default 10 percent marketing share, and the other lines scale. Contingency is the default 10 percent. The picture tier for preview and production is better, Seedance 2.0 fast, the wired picture model proven live. Best, Seedance 2.0, is the upgrade. Trailer-on, contingency, and the tier are proposed, Ron to confirm.
- Consequences: The Line Producer quotes the film from this file. Approving the treatment later locks the spendable lines, including marketing, and does not edit the file. Nothing in this step spends money.
- Who decided: Cursor cloud agent. Proposed. Ron to confirm.

## D127 — Intake reads creative inputs and does not approve them

- Status: proposed
- Date: 2026-11-12
- Context: A fresh run has to start at intake. An approved treatment makes intake stop, and a question round that already has answers makes intake stop. The locked creative answers still have to be something the Director reads.
- Decision: `treatment/inputs.json` is a partial treatment. Intake merges it into the draft after the screenplay and the brief. `force_draft` still runs, so a status or an approval in that file does not open the gate. An explicit `--partial` still wins over the file. A film with no inputs file is unchanged.
- Consequences: Harbor Night proves the merge and proves an approved status in the inputs file comes out as a draft. The Last Marker keeps Ron's locked answers in that file.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D128 — The treatment split follows budget.json

- Status: proposed
- Date: 2026-11-12
- Context: A film with `budget.json` locks the spendable lines when the treatment is approved. Intake was still proposing the unscaled cap split, so the question and the file could disagree once the trailer and contingency scale the lines.
- Decision: When `budget.json` exists, the draft's budget cap and proposed stage split are the spendable lines from that file. Marketing is included when the trailer is on. Contingency is held back and is not a stage line. A film with no budget file keeps the proposed split of the cap.
- Consequences: Harbor Night proves a $100 budget with the trailer on proposes production at $48.60 and marketing at $10.00, and the treatment stays a draft. The Last Marker question proposes the scaled $500 lines.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D129 — Films live outside the studio repo

- Status: decided
- Date: 2026-11-12
- Context: The studio repo was holding the engine and the working files for a film. Ron decided in chat on 2026-11-12 that the repo holds the engine only. Each film's working data lives in its own folder outside the repo, under the films root. That root is `MOVIE_SWARM_FILMS_ROOT`, or `MOVIE_SWARM_ASSET_ROOT` when the films root is unset. The same value can come from the shell, from `.env`, or from config. A film folder may be its own small private git repo.
- Decision: A production is a path, or a name that means `<films root>/<name>`. The commands accept either. An absolute path may be outside this repo. Nothing in the engine requires the folder to sit under this repo. `scripts/new-film.py` creates a skeleton in the films root. `scripts/export-film.py` copies an in-repo production out, checks a checksum list, and leaves the source in place. `productions/the-last-marker` stays in the repo as an archived copy until Ron exports it and a later phase removes it. Harbor Night stays in `tests/fixtures/` as the example. New folders under `productions/` other than `the-last-marker` are ignored.
- Consequences: The working film is not committed to the studio repo. No real path is written in the repo. Schema checks, run folders, archives, and media paths follow the production folder. Spent on this step: $0.00. No live call was made.
- Who decided: Ron, 2026-11-12

## D130 — Claude writing calls get their own approval

- Status: decided
- Date: 2026-11-12
- Context: A Claude writing call was sent through the same gate as a picture call. That gate opens after previs. The treatment is drafted while the film is still at the treatment gate. The generation gate is the switch for paid pictures and audio.
- Decision: Claude writing calls get their own approval, separate from the generation gate.
- Consequences: A picture or audio call still waits on the generation gate. A text call does not. The choices for how that approval works are D131 through D135. Those are proposals.
- Who decided: Ron, 2026-11-12

## D131 — A writing approval is one ceiling for the run

- Status: proposed
- Date: 2026-11-12
- Context: Intake makes more than one text call: the Director's draft, then the Line Producer's question wording. A per-call price override would stop after the first call and ask Ron to approve a new request for each hash. The ledger already records each call. The approval only needs to say how much writing this run may spend.
- Decision: `approve-writing --run <id> --by Ron --max-usd <amount> --note ...` records one ceiling on the run. It does not book money and it does not open the generation gate. A later command replaces the ceiling. The ledger is left as it is. Each new text call's worst case has to fit the money left under that ceiling. The call is still checked against the film cap and the stage line.
- Consequences: One approval covers the draft and the question wording. Picture and audio keep the one-call price override when the rate card has no price.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D132 — --live without that approval prints a quote and sends nothing

- Status: proposed
- Date: 2026-11-12
- Context: Ron has to see the price before he approves it. Offline is already the default.
- Decision: Without `--live`, a text call is not sent. With `--live` and no writing approval, the command prints the model, the input-token estimate (character count divided by 4, labeled as an estimate), the max output tokens, and the worst-case dollars from the rate card, then stops. Nothing is sent. The treatment file is not replaced. With the approval, and with the worst case inside the ceiling, the line, and the cap, the call is sent.
- Consequences: The first live intake on a run is a quote. The next one, after approve-writing, is the draft.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D133 — A writing call does not need the locked split

- Status: proposed
- Date: 2026-11-12
- Context: The stage split locks when Ron approves the treatment. The writing that drafts the treatment happens before that lock. Requiring the lock would leave the new approval with no line to check at the treatment gate.
- Decision: A writing call checks the film cap and the stage line. When the run's stage split is approved, that line is checked. When it is not, the check uses the lines in `budget.json`. A film with neither a locked split nor a budget file has no line to check, so the call is refused. A locked split is not required for a text call.
- Consequences: A film at the treatment gate can draft from `budget.json`. Picture and audio calls still require the locked split.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D134 — Text prices come from Anthropic's pricing page

- Status: proposed
- Date: 2026-11-12
- Context: The rate card had no dollar amount for a Claude call, so a text call could not be quoted.
- Decision: `config/generation-rates.json` and `config/rate-card.json` record dollars per million input tokens and per million output tokens for `claude-haiku-5-5`, `claude-sonnet-5-5`, and `claude-opus-5-5`. The page is https://platform.claude.com/docs/en/about-claude/pricing, read on 2026-11-12. Haiku 5.5 is $0.10 and $0.50 for a prompt up to 100,000 tokens, and $0.50 and $2.50 over that. Sonnet 5.5 is $2 and $10. Opus 5.5 is $4 and $20. The worst case uses the input-token estimate and the full max output. Cache, batch, and fast mode are not used. The model id `claude-sonnet-4-20250514` is not listed on that page, so its price is null and a live call for it is refused.
- Consequences: A quoted writing call uses these numbers. A model with a null price is not sent.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D135 — A finished text call is booked from the reported tokens

- Status: proposed
- Date: 2026-11-12
- Context: Anthropic does not return a dollar amount. It returns `input_tokens` and `output_tokens`. D124 marks a picture call with no dollars as an estimate.
- Decision: After a live text call, the booked amount is the reported input tokens times the input price plus the reported output tokens times the output price. The ledger row sets `actual_source` to `usage`. The estimate stays on the row. If either token count is missing, the booked amount stays the worst-case estimate and `actual_source` is `estimate`.
- Consequences: The running total moves from the reserved worst case to the usage cost when the response includes both token counts. A picture call is unchanged: `provider` when fal reports dollars, `estimate` when it does not.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D136 — Phase 8.13, the treatment-draft fix

- Status: decided
- Date: 2026-11-12
- Context: On run `first-film-1`, a live Director intake called Claude and was charged $0.0751. The draft call sent the first 12,000 characters of the screenplay and none of the locked files. The reply missed four schema names. The engine kept the offline draft, and the note said no model was called.
- Decision: Fix that path. Send the screenplay. Send the locked files the film already has. Conform the reply onto the treatment schema. Keep the raw reply when it is still not valid, and say so in the note. Do not make a new paid call to retry a response that is already cached. The choices for how that works are D137 through D140. Those are proposals.
- Consequences: The offline draft is unchanged. Intake still refuses an approved treatment and a question round that already has answers. No live call was made in this phase. Spent on this step: $0.00.
- Who decided: Ron, 2026-11-12

## D137 — A live draft sends the screenplay up to 120,000 characters

- Status: proposed
- Date: 2026-11-12
- Context: `Director._draft` sent `script.text[:12000]` and the first 6,000 characters of a partial treatment. The screenplay is about 23,000 characters, so the model never saw the end of it. The writing quote counts the characters it is given. A shortened prompt makes the ceiling check look cheaper than the call Ron expects.
- Decision: `DRAFT_SOURCE_CHAR_LIMIT` is 120,000 characters. The live draft sends the screenplay, and a partial treatment, up to that limit. The same limit applies to each locked file. When a text is longer, the prompt says it was cut and names the original length and the limit. The draft note repeats that sentence. The writing quote uses the system text and the user text that would be sent, character count divided by 4, plus the full max output. It does not quote a shorter copy.
- Consequences: A short screenplay is sent whole. A file past the limit is cut in the open. The worst case rises with the prompt, and the ceiling check uses that number. The proof uses a fake model.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D138 — Locked inputs and prop locks go in the live prompt

- Status: proposed
- Date: 2026-11-12
- Context: `treatment/inputs.json` was merged into the draft after the model replied. The model never saw it. `props/hero-props.json` and `props/prop-definitions.json` were not sent either. D30 says those facts stay in the film folder. The engine must not name one film's props.
- Decision: When the production folder has `treatment/inputs.json`, the live prompt includes it as locked creative inputs. The draft must follow them and must not re-ask them. When the folder has `props/hero-props.json`, `props/prop-definitions.json`, or a text spec under `props/<name>/`, the prompt includes those as locked prop facts. The system prompt says not to raise an open question about a locked item. The offline draft does not read the prop files. Intake still merges `treatment/inputs.json` afterward, and that merge still does not approve the gate.
- Consequences: A film with none of those files is unchanged. A film that has them sends the files it has. The proof uses stand-in names, not one film's locks.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D139 — Conform the reply, then keep it if it is still not valid

- Status: proposed
- Date: 2026-11-12
- Context: The paid reply used `theme` and `emotional_intent` instead of `theme_and_emotional_intent`, `tone` and `genre` instead of `tone_and_genre`, `deliverables.resolution` null, and version `1.0-treatment-draft`. `treatment_errors` returned those four. The engine returned the offline draft. Its note still said no model was called.
- Decision: `conform_treatment` maps those names onto the schema. A version that is already major.minor.patch is kept. `1.2` becomes `1.2.0`, and a single number becomes `1.0.0`. Anything else, including `1.0-treatment-draft`, becomes `0.1.0`. A blank deliverable is filled from the offline draft. The system prompt lists the required top-level keys and their formats from the treatment schema. If errors remain, missing required fields are filled from the offline draft and checked again. The offline draft is kept only when the reply is still not valid. The note then says a model was called, the call cost was booked, and lists the schema errors. It does not say that no model was called. The raw reply is saved at `runs/<run>/rejected-draft-<hash>.txt`. Keys in that file and in the note are redacted.
- Consequences: A reply that only used the wrong names becomes a draft. A reply that is still not valid does not disappear. The command prints that note. The offline path, when no model was called, still says no model was called.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D140 — reconform reads the cache and does not pay again

- Status: proposed
- Date: 2026-11-12
- Context: `runs/<run>/provider-cache.json` stores the response text under the request hash. The same request sent again replays that cache and is not charged again. The screenplay and the locked files change the request, so a new intake will not match the call that was already paid.
- Decision: `director.py reconform --request <hash>` reads that cache, runs the same conform steps, and writes the draft when it is valid. It does not call a model and does not book money. The hash may be the full key or a unique prefix of at least 8 characters. An approved treatment is not overwritten. A question round that already has answers is not wiped. A cache entry that is still not valid is saved as a rejected draft and the treatment file is left as it is.
- Consequences: The paid reply can be conformed again after this fix without a second charge. A new `--live intake` is a new request and is quoted again. The proof writes a fake cache and does not set a provider key.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D141 — Phase 8.14 approved by Ron, 2026-11-12

- Status: decided
- Date: 2026-11-12
- Context: On run `first-film-1`, the live answer command called Opus 5.5 for the final treatment pass with `max_tokens` 8000. The provider reported 4,978 input tokens and 8,000 output tokens. The reply was a treatment cut off inside the last notes field. The JSON parse failed, the earlier draft was kept, and the deterministic answer merge wrote Ron's words into the treatment: a confirmation replaced the drafted tone, and a withheld answer was pasted onto more than one scene. The Sonnet draft quote was $0.1456 and the call booked $0.1686. The Opus quote was $0.1722 and the call booked $0.1799. Tests on a machine where the film-root variables are set also failed.
- Decision: Fix that path. Give the final pass more room, say so when a reply hits the output limit, repair a saved truncated reply without a new charge, keep a confirmation from replacing drafted text, record a withheld fact once, and quote writing calls high enough that the worst case is not below what was booked. The choices for how that works are D142 through D146. Those are proposals. The engine stays generic. Film facts stay in the film folder.
- Consequences: The offline draft is unchanged. An approved treatment is still not overwritten. No live call was made in this phase. Spent on this step: $0.00.
- Who decided: Ron, 2026-11-12

## D142 — The final pass may use 16,000 tokens, and a full output limit is reported

- Status: proposed
- Date: 2026-11-12
- Context: `_final_pass` sent `max_tokens` 8000. The paid Opus reply used all 8,000 output tokens and stopped inside the treatment. The failure note did not say the output limit was the reason. The raw reply was not saved the way a rejected draft is.
- Decision: `FINAL_PASS_MAX_TOKENS` is 16,000. The final pass may return the full treatment or only the fields it changed. Those fields are merged onto the current draft. When the provider `stop_reason` is `max_tokens` or `length`, or the reported output tokens are at least the max, the draft note and the command output say the final pass hit the output limit, and they name the stop reason and the token counts. A final pass that still cannot be read is saved at `runs/<run>/rejected-final-<hash>.txt`. The earlier draft is kept. The call that was already booked stays booked. Nothing new is booked for the failure.
- Consequences: A short final pass is unchanged. A reply that fills the new cap is visible in the note and on the command line. The proof uses a fake model.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D143 — reconform can repair a truncated final-pass reply

- Status: proposed
- Date: 2026-11-12
- Context: `reconform --request <hash>` conformed a cached draft. It did not know how to close a JSON object that was cut off, and it refused to run after answers were stored. The paid Opus reply is already in `runs/<run>/provider-cache.json`. Parsing it failed, so the treatment on disk is the pre-pass draft with the answers pasted in.
- Decision: The same command reads a final-pass reply as well as a draft. If the text is cut off, it closes open strings, arrays, and objects, and it drops the unfinished key or value at the cut. It then conforms and validates. Missing required fields are filled from the current draft. The treatment is written as if the final pass had succeeded. The note says it was repaired from a truncated paid reply, names what was dropped, and says nothing new was booked. The command does not call a model and does not book money. An approved treatment is not overwritten. A question round that already has answers is not wiped. A draft-shaped cache entry is still refused when answers are already stored, so a draft reconform cannot replace an answered treatment.
- Consequences: The saved Opus reply can be rebuilt with one local command. The hash is the cache key for that call. A prefix of at least 8 characters is enough when it matches one call. The proof uses a fake cache and does not set a provider key.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D144 — A confirmation keeps the drafted words, and a withheld fact is stored once

- Status: proposed
- Date: 2026-11-12
- Context: The answer merge treated any non-empty string as replacement text. `Lock.` became the tone. `That's all: withhold only whether the canyon really has water.` was copied onto every scene that shared a long word with the answer, and onto the last scene.
- Decision: An answer that is only a confirmation keeps the drafted field and the note says that field was locked. The confirmations are `Lock`, `Lock.`, `Lock it`, `Yes`, `Approved`, and `Keep`, in any case, with trailing punctuation. A leading `That's all:` is not part of the decision. A withheld answer is written once, on the last scene, and it is not copied into what happens in the scene. The question file still stores the words Ron typed.
- Consequences: A real sentence still replaces the field it answers. A yes no longer erases the draft. The proof uses stand-in sentences, not one film's facts, except where an existing fixture already named them.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D145 — A writing quote rounds the input estimate up

- Status: proposed
- Date: 2026-11-12
- Context: The quote used character count divided by 4 and dropped the remainder. On the Sonnet draft that estimate was $0.1456 and the booking was $0.1686. On the Opus final pass the quote implied 3,050 input tokens and the provider reported 4,978. Both worst cases were below the booking. The ceiling check used the low figure.
- Decision: The input estimate is the character count of the system text plus the user text, divided by 3, plus 25 percent, plus 200 tokens, rounded up. The worst case still prices that estimate plus every output token the call is allowed to write. The ceiling check uses this figure. For the recorded prompts, 131,200 characters for the Sonnet draft and 12,200 characters for the Opus final pass, this quote is at least the booked amount. Those lengths are the ones implied by the old quotes at the published prices and a max output of 8,000.
- Consequences: Quotes are higher than character count divided by 4. A call that would have fitted a ceiling under the old math can now stop at the quote. The line says the number is an estimate. The proof does not call a provider.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D146 — Tests do not inherit the film-root settings

- Status: proposed
- Date: 2026-11-12
- Context: With `MOVIE_SWARM_ASSET_ROOT` set, delivery files were written under that root, so tests looking in the temporary production folder did not find them. One post-supervisor failure was `maximum recursion depth exceeded`. The graphics test replaced `shutil.which` with a wrapper that called `shutil.which` again. That wrapper is the shared function. A master file left under the asset root by an earlier test was probed, the wrapper called itself, and the call failed. A repo `.env` can set the same variables when a command loads it.
- Decision: The test suite clears `MOVIE_SWARM_ASSET_ROOT` and `MOVIE_SWARM_FILMS_ROOT` for each test, and it sets `MOVIE_SWARM_SKIP_ENV_FILE` so `load_env()` with no path does not read the repo `.env`. A test that passes a path to `load_env` still reads that file. A test can still set either root for itself. The ffmpeg wrapper calls the original lookup, so a probe does not recurse. `@pytest.mark.use_envfile` opts a test back into auto-load.
- Consequences: The suite passes when those variables are set in the environment to a real directory or to a path that is not there. A command run outside the suite still loads `.env`.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D147 — Phase 8.15 approved by Ron, 2026-11-12

- Status: decided
- Date: 2026-11-12
- Context: The offline studio wrote a previs package whose continuity check, storyboard tags, prompts, stunt breakdown, lighting plan, shot lists, shot lengths, graphics research, schedule, and treatment note did not match the locks. D142 through D146 were already the Phase 8.14 proposals, so this approval is D147.
- Decision: Fix that path. Keep the engine generic. Film facts stay in the film folder. Product placement stays a continuity fact and is not framed as advertising. The choices for how the fixes work are D148 through D154. Those are proposals. No paid call is part of this phase.
- Consequences: An approved previs gate is not rewritten. An approved treatment is still not overwritten. No live call was made. Spent on this step: $0.00.
- Who decided: Ron, 2026-11-12

## D148 — Character aliases, prop parts, and wardrobe facts

- Status: proposed
- Date: 2026-11-12
- Context: A character lock matched only the full name. A prop lock matched the name and the aliases, not a named part. A wardrobe lock required the whole paragraph, word for word.
- Decision: Derive the surname, the first name, and the screenplay cue from the name, and keep any alias the lock already lists. A hero prop may list `parts`. A shot that says a part shows the prop, and a sidedness phrase is still required. A long wardrobe paragraph is stated when every short garment fact is present, or when the shot says `wardrobe lock: <id>`. A forbidden phrase still fails.
- Consequences: The storyboard tags `characters_in_shot` and `props_in_shot` from the beat and the scene heading. The continuity note lists the locks that tag put in the frame.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D149 — Prompts carry the locked spec and the reference images

- Status: proposed
- Date: 2026-11-12
- Context: A generation prompt for a hero prop said only the side. The reference images on the lock were not on the shot.
- Decision: A shot that shows a hero prop includes that prop's `locked_spec` and does not add a fact the spec did not state. `reference_images` on the shot are the paths from the lock. Generation copies them onto the provider request when the call is allowed. The storyboard section is "Hero prop moments". The engine does not write "featured product", "product shot", "advert", or "sponsor" for that section.
- Consequences: A provider that accepts image references can be given the paths. This phase does not call one.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D150 — A confirmation is not a stunt beat, and a note is not a shot

- Status: proposed
- Date: 2026-11-12
- Context: An answer that only confirmed the beats was stored as another beat. A sentence about the screenplay, and a sentence that classified a fix, became shots.
- Decision: Beats and shots come from the action sentences. A confirmation or a decision is dropped. A note is kept on the beat and is not a shot. The same filter applies when an answer is merged into the treatment.
- Consequences: The safety line is unchanged. A beat with no action sentence is not written.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D151 — Time of day comes from the heading, and the sun is not a practical

- Status: proposed
- Date: 2026-11-12
- Context: The lighting plan said the time of day was not named when the slugline named it. A line about the sun was copied into the practicals.
- Decision: The time of day is the last segment of the heading. `MOMENTS LATER` and `CONTINUOUS` keep the previous concrete time. A scene that already names a concrete time keeps that wording. A line that is only sunlight stays the key. It is not the practicals.
- Consequences: A night heading stays night. A fluorescent practical that also mentions the sun still counts as a practical.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D152 — The older shot list is superseded, and shot lengths stay in range

- Status: proposed
- Date: 2026-11-12
- Context: Generation already preferred the storyboard shot list. The continuity check still read an older `shot-lists/shot-list.json` that had open choices. Storyboard durations ran from under a second to longer than twelve, except where the screenplay named a hold.
- Decision: When the storyboard list is newer, or the storyboard names it as the list generation uses, the older file is marked `superseded` and kept. It is not checked for drift and it is not sent to generation. The continuity report says so. Unlocked shots stay between 1 and 12 seconds. A hold the screenplay names may sit outside that range. Time is moved so the scene still hits its target when the limits allow it. `storyboard/pacing-limits.json` can set the two limits. The boards report the changes.
- Consequences: The older file is not deleted. A scene that cannot hit its target inside the limits says so.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D153 — The graphics year, the hero props on the schedule, and the safety sentence

- Status: proposed
- Date: 2026-11-12
- Context: Graphics research said the documents named no year when the logline or the world named one. The schedule's prop line omitted the hero props. A shot that needed a stunt was marked "Safety."
- Decision: Research reads a four-digit year from the logline and from `world_and_period` and sources each one. The schedule lists a hero prop by name when the shot shows it. The reading copy writes the stunt rule as a full sentence.
- Consequences: A film that names no year still says so. A setup with no hero prop does not invent one.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D154 — reconform drops a stale failure, and redo previs does not touch an approved gate

- Status: proposed
- Date: 2026-11-12
- Context: After `reconform` succeeded, the draft note still said the final model pass had failed and the earlier draft was kept. An operator with the treatment approved and the previs gate still closed needs to regenerate the previs outputs without approving anything.
- Decision: A successful `reconform` removes that failure sentence and writes the repair history. `scripts/studio.py --redo previs`, and the same flag on the Director `studio` command, regenerates the previs package and stops. The command is offline. `--live` is refused. The treatment gate must already be approved. If the previs gate is already approved, the command refuses and does not rewrite the files or the gate.
- Consequences: The command for run `first-film-1` is `python3 scripts/studio.py --production the-last-marker --run first-film-1 --redo previs`, from the repo root, with the films root set. Nothing is spent. D163 covers the case where the treatment is already approved and the stale sentence is still in the note.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D155 — Phase 8.16 approved by Ron, 2026-11-12

- Status: decided
- Date: 2026-11-12
- Context: An offline previs pass after Phase 8.15 still missed pronoun shots, generic nouns, continued actions, placement wording, a false lighting flag, a stunt beat, a short scene, and a stale note on an approved treatment. D148 through D154 were already the Phase 8.15 proposals, so this approval is D155.
- Decision: Fix that path. Keep the engine generic. Film facts stay in the film folder. Product placement stays a continuity fact and is not framed as advertising. The choices for how the fixes work are D156 through D163. Those are proposals. No paid call is part of this phase.
- Consequences: An approved previs gate is not rewritten. `--redo previs` still does not touch an approved treatment. No live call was made. Spent on this step: $0.00.
- Who decided: Ron, 2026-11-12

## D156 — A pronoun can inherit one locked character

- Status: proposed
- Date: 2026-11-12
- Context: Shots that refer to the lead only as "he", "his", or "him" were not tagged, so the wardrobe and makeup lines never reached those prompts.
- Decision: Inside one scene, a shot that uses a personal pronoun and names no locked character inherits the only locked character in that scene. If more than one locked character is named, the pronoun uses the most recent shot that named exactly one, and only when no other character was named in between. If it is ambiguous, the shot is not tagged. The storyboard and the continuity check list it as needing review. A tagged character brings the wardrobe and makeup lines onto the prompt.
- Consequences: The words are generic pronouns. The names still come from the locks.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D157 — Generic nouns, and a kind word when the kind is unique

- Status: proposed
- Date: 2026-11-12
- Context: A shot that said "his bike" was not tagged, because that word was not an alias. The engine must not hard-code one film's nouns.
- Decision: A lock may list `generic_nouns`. Those match that lock when no other lock claims the same noun. `config/kind-nouns.json` lists ordinary nouns for a kind. A film replaces a kind by naming it in `props/kind-nouns.json`. The kind word and that list match only when the locked props contain exactly one prop of that kind.
- Consequences: A second vehicle in the same film stops the kind list from guessing. The film can still name `generic_nouns` on one lock.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D158 — A continued action can carry one prop

- Status: proposed
- Date: 2026-11-12
- Context: A shot such as "He kicks again" continues an action from the previous shot and does not rename the prop.
- Decision: Within one scene, if this shot names no prop, and it says "again", "another", or "still", or it repeats an action verb from the previous shot, and that previous shot has exactly one tagged prop, the prop is carried forward. The storyboard and the continuity check say so. If the previous shot has more than one prop, the shot is listed for review and nothing is carried.
- Consequences: The rule does not invent a prop the previous shot did not already have.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D159 — Placement lines describe the story, and a banned phrase fails

- Status: proposed
- Date: 2026-11-12
- Context: A why-line said "not a product shot". A negation still uses the banned vocabulary. Some prompts also added a sentence that framed the object as something being sold.
- Decision: A moment's why-line is kept only when it contains none of the banned phrases. Otherwise the line says the object stays in the frame for the story the scene is already telling. "The detail stays readable." is added only when the brief asks for a legible detail. It is a focus instruction. Generated previs documents and prompts are scanned. A banned phrase is a continuity finding and the verdict is drift.
- Consequences: The banned list stays in the engine. It is not a list of one film's products. A film's own source file can still contain a banned phrase. The generated package will not copy it, and the check will report it if some other generated file does.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D160 — Time of day is an explicit statement

- Status: proposed
- Date: 2026-11-12
- Context: "Fifteen minutes of day left" was flagged as a change from a pre-dusk heading, because the checker treated the bare word "day" as a time of day.
- Decision: Drift is flagged when the shot states a time of day, such as "at dawn", "night falls", or a heading. A phrase about remaining daylight is not a time-of-day change.
- Consequences: A pre-dusk scene can mention the day that is left. "At dawn" against that heading is still drift.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D161 — Every stunt beat is on the safety list

- Status: proposed
- Date: 2026-11-12
- Context: A kick beat was in the action breakdown and missing from the schedule's safety section, because no storyboard sentence shared a long enough phrase with it.
- Decision: Every beat in the action breakdown appears in the schedule's safety section. The note is the beat's full safety sentence from the stunt rules. If those rules say there are no special safety needs, the line says "No special safety needs, per stunt rules." A shot that overlaps a beat is still flagged.
- Consequences: A beat with no matching shot is still listed. The engine does not invent a safety need the rules did not state.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D162 — Leftover scene time fills shots that have room

- Status: proposed
- Date: 2026-11-12
- Context: Clamping shots to 1–12 seconds left a scene at 44 seconds against a 45 second target, and the film a fraction under its target, while some shots were not yet at the limit.
- Decision: After the limits are applied, leftover time in a scene is spread across shots in that scene that are not pinned to a length the screenplay named and that still have room inside the limits. A named length stays. If every movable shot is already at a limit, the boards say the remainder cannot be placed. A scene that can hit its target does so within a small rounding tolerance.
- Consequences: The word "hold" still sets the transition. It does not freeze the duration unless the screenplay names the seconds.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D163 — reconform clears a stale note without unapproving

- Status: proposed
- Date: 2026-11-12
- Context: An approved treatment still said the final model pass failed and the earlier draft was kept. `reconform` refused to touch an approved file, so the sentence stayed. `--redo previs` correctly leaves the treatment alone.
- Decision: When `reconform` reads a cached reply and that reply conforms, an already approved treatment keeps its scenes, its status, and its approval block. Only a stale "The final model pass failed … The earlier draft was kept" sentence is removed from `draft_note`. The command does not call a model and does not book. The Line Producer's gate decision is not rewritten, so the approval stays valid.
- Consequences: The command is `python3 scripts/director.py --production the-last-marker --run first-film-1 reconform --request <hash>`, from the repo root, with the films root set. Replace `<hash>` with the final-pass request hash. Then run `python3 scripts/studio.py --production the-last-marker --run first-film-1 --redo previs`.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D164 — Phase 8.16.1 hotfix approved by Ron, 2026-11-12

- Status: decided
- Date: 2026-11-12
- Context: `--redo previs` on a real film died in the cinematographer boards with `NameError: name 'mentioned' is not defined`. `_person_in_shot` still asked whether a locked person was named in the shot. Phase 8.16 had switched prop matching to `prop_mentioned` and dropped the people matcher from that file. The tests only resolved a person who was already on the shot, so they never took the branch.
- Decision: Phase 8.16.1 hotfix approved by Ron, 2026-11-12. A person matches with the word-boundary matcher, the same one the catalog uses. A pronoun that already resolved to one locked character still brings that person's wardrobe and makeup. A prop still uses `prop_mentioned`, including a kind noun and a carried action. The engine stays generic. D30 and D38 stay as they are.
- Consequences: The rerun command is unchanged: `python3 scripts/studio.py --production the-last-marker --run first-film-1 --redo previs`, from the repo root, with the films root set. A failed redo does not approve the previs gate and does not write a half-finished storyboard. Run the same command again. Earlier locks from that attempt are overwritten. Nothing needs to be deleted first. No live call. Spent on this step: $0.00.
- Who decided: Ron, 2026-11-12

## D165 — Phase 8.17 approved by Ron, 12 Nov 2026

- Status: decided
- Date: 2026-11-12
- Context: An offline previs pass still treated a departure as the prop in frame, carried that prop into a close-up of another object and into a fade or hold, left a rider untagged when their vehicle passed the camera, and could not place a scene's leftover time once every shot in that scene was at the length cap. The film total came up short of its target.
- Decision: Fix that path. Keep the engine generic. Film facts stay in the film folder. The choices for how the fixes work are D166 through D170. Those are proposals. No paid call is part of this phase.
- Consequences: An approved previs gate is not rewritten. No live call was made. Spent on this step: $0.00.
- Who decided: Ron, 12 Nov 2026

## D166 — An absence phrase does not put a prop in frame

- Status: proposed
- Date: 2026-11-13
- Context: A line such as "he has left the bike" named the vehicle, so the shot was tagged and the locked spec and reference images were added. The vehicle was not in the frame.
- Decision: `config/absence-phrases.json` lists phrases that mention a prop without showing it. `{prop}` stands for the lock's name, an alias, a part, or a kind noun. A film replaces either list by writing that key in `props/absence-phrases.json`. An empty list clears it. When every mention of the prop sits inside an absence phrase, the prop is not tagged. When a configured phrase could still show the prop, or the shot both leaves the prop and shows it, the shot is not tagged and the storyboard and the continuity check list it for review.
- Consequences: The default list is generic English. It includes leaving, abandoning, walking away, being without the prop, and looking back at it, including from a distance. "Left the prop in" or "left the prop running" is ambiguous, because the prop may still be sitting there.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D167 — A continued prop stops at a different subject

- Status: proposed
- Date: 2026-11-13
- Context: A close-up of a different object inherited the vehicle from the previous shot, including the locked spec and the reference images. The previous shot had tagged the vehicle only because an absence phrase was treated as presence, so there was nothing that should have carried.
- Decision: Within one scene, a continued action still carries one prop when the previous shot had exactly one prop in frame and this shot does not name a prop. It does not carry into a close-up, an insert, or an extreme close-up of some other object. It does not carry when the shot's subject is a different thing. If the previous shot did not put the prop in frame, including because of an absence phrase, the next shot has nothing to carry. A tight shot that continues the action but names neither the prop nor another object is listed for review and is not guessed.
- Consequences: "He kicks again" can still carry the one prop from the previous shot. A close view of a different object does not.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D168 — A line with no picture does not carry a prop

- Status: proposed
- Date: 2026-11-13
- Context: A fade, then silence, then a hold, inherited the vehicle from the previous wide. The line does not describe a picture of that vehicle.
- Decision: If every sentence in the shot is sound, a fade, a hold, black, or a title, and the shot would otherwise have carried a prop, the prop is not carried. The storyboard and the continuity check list the shot for review. A sentence that also has a visible action, such as riding while a fade starts, can still carry.
- Consequences: A named hold still sets the shot length. The word "hold" by itself still sets the transition. The carry rule is separate from the length rule.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D169 — One rider is tagged when their vehicle passes

- Status: proposed
- Date: 2026-11-13
- Context: A shot whose subject is a vehicle in motion, with no name and no pronoun, was not tagged with a character. The rider was in frame, so the wardrobe line never reached the prompt.
- Decision: When the shot's subject is one locked vehicle in motion, the shot names no person, and exactly one character in the scene rides or drives that vehicle, that character is tagged. The wardrobe and makeup lines then follow, the same way they do for a pronoun. If no rider is clear, or more than one person rides it, or the vehicle itself is not one lock, the shot is not tagged and the storyboard and the continuity check list it for review.
- Consequences: The ride and motion words are generic English. The names still come from the locks. A vehicle that is only waiting is not treated as a rider passing the camera.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D170 — A scene remainder can land in another scene

- Status: proposed
- Date: 2026-11-13
- Context: Clamping every shot in a scene to the maximum length left a remainder the scene could not place. The boards then totaled 179 seconds against a 180 second target, while other scenes still had shots under the cap.
- Decision: After each scene places what it can inside the limits, any remainder is spread across shots in other scenes that are not pinned to a length the screenplay named and that still have room under the maximum. The time is added so each scene stays as close to its own target as the limits allow. The pacing note names the scene that absorbed it, and which scene it came from. The board total then hits the sum of the scene targets. Only when no shot anywhere has room does the note keep the line that the limits left no room to place the remainder.
- Consequences: A named length still stays. A scene that can hit its own target still does. A scene that absorbs leftover time runs long by that amount, and the note says so.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D171 — Phase 8.17.1 hotfix approved by Ron, 12 Nov 2026

- Status: decided
- Date: 2026-11-12
- Context: After Phase 8.17, a real previs pass still logged a major continuity finding for a line that had left the vehicle, flagged that line for review, and left a later passing-vehicle shot with no rider and no review flag.
- Decision: Fix that path. Keep the engine generic. Film facts stay in the film folder. The choices for how the fixes work are D172, D173, and D174. Those are proposals. No paid call is part of this hotfix.
- Consequences: An approved previs gate is not rewritten. No live call was made. Spent on this step: $0.00.
- Who decided: Ron, 12 Nov 2026

## D172 — Continuity uses the storyboard tags or the absence phrases

- Status: proposed
- Date: 2026-11-13
- Context: The storyboard left `vehicles_in_shot` empty and did not attach the locked spec. The continuity check still read the vehicle name in the sentence and logged a major unstated finding, which turned the verdict to drift.
- Decision: A prop is shown when `props_in_shot` or `vehicles_in_shot` names it, including a prop carried from the previous shot. Otherwise the check uses `prop_frame_state` on the shot description, the same absence phrases as the storyboard, including a film's `props/absence-phrases.json`. Absent, ambiguous, and unnamed are not shown. A raw name mention is not a second detector. The generated continuity note is not scanned for that decision, so the word "prop" in "No locked prop is in this frame" is not a mention.
- Consequences: A shot that shows the prop and omits a required phrase still drifts. A shot that only names the prop inside an absence phrase does not. A person is still matched from the name and the character tag.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D173 — A perfect-tense absence is absence

- Status: proposed
- Date: 2026-11-13
- Context: "He has left the bike." was listed for review. The alias "bike" and a longer label "the bike" overlapped on the same word. The absence template already contains "the", so the longer label did not match it and looked like a second, in-frame mention. The sentence end is only punctuation. The auxiliary "has" is the perfect of "left".
- Decision: has, have, and had plus the participle of leave, abandon, walk, or look count as the absence phrase they come from. The same expansion applies to the ambiguous list. Overlapping labels are one mention. If any of them is an explicit ambiguous phrase, the mention is a review. Otherwise an absence phrase keeps the prop out of frame. Only the ambiguous list, such as "left the X in", "on", "running", or "there", is a review.
- Consequences: "She has left the bike.", "had left", and "has abandoned" do not tag the prop and do not ask for review. "Has left the bike in the lane" still does. A film that replaces the phrase list gets the same perfect-tense forms for those verbs.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D174 — Ride language anywhere in the scene can name the rider

- Status: proposed
- Date: 2026-11-13
- Context: An earlier shot said the person was on the vehicle, then "rides", then "has been riding". A later shot, "LOW ANGLE. The vehicle passes camera," named nobody. The first sentence was the shot size, so the vehicle was not read as the subject. The shot got neither a character tag nor a review flag, and the wardrobe line never reached the prompt.
- Decision: D169 still stands. The ride can be anywhere in the scene: an earlier shot, the scene description, "on a vehicle" with a short modifier such as a year, "rides", or "riding". A leading shot-size sentence is not the subject. Exactly one rider is tagged, and the wardrobe line follows. No rider, or more than one, is a review. A passing vehicle is not left untagged and unflagged.
- Consequences: The ride and motion words stay generic English. The names still come from the locks. A vehicle that is only waiting is not a rider passing the camera.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D175 — A perfect-tense absence with nothing after the object is clear

- Status: decided
- Date: 2026-11-13
- Context: After Phase 8.17.1, a line such as "he has left the bike" left the prop untagged and the continuity check clear. The storyboard review could still treat that line as an ambiguous absence when nothing followed the object. The continuation words "in", "on", "running", and "there" belong to a later clause in the same shot, or they are not there at all.
- Decision: Ron, 2026-11-13: approved the 8.17.2 hotfix so a perfect-tense absence with nothing after the object is clear, not ambiguous.
- Consequences: "He has left the bike." and "She had left the truck" are clear. They are not tagged and they are not listed for review. "Has left the bike running", "left the bike in the barn", "left the bike on its stand", and "left the X there" stay reviews. The engine stays generic. How the shared phrase file draws that line is D176.
- Who decided: Ron, 2026-11-13

## D176 — A closed perfect-tense tail is read from the shared phrase file

- Status: proposed
- Date: 2026-11-13
- Context: The review list and the frame classifier have to use one phrase file, or a perfect-tense line can be clear in one place and a review in the other. A conjunction can start the next clause without naming the prop again.
- Decision: `config/absence-phrases.json` holds the absence phrases, the ambiguous continuations, and `closed_clause.conjunctions`. A film replaces any of those keys in `props/absence-phrases.json`. An empty list clears that key. has, have, or had plus an absence phrase, with nothing after the object, is absence. Punctuation is nothing. One conjunction from that list is nothing, because it starts the next clause. An ambiguous continuation in the same clause still wins, including "in", "on", "running", and "there". The storyboard review is the ambiguous result of that same decision. The schema is `schemas/absence-phrases.schema.json`.
- Consequences: "He has left the bike, and he walks on." is clear. "He has left the bike in the barn." is a review. A film that lists "and" as an ambiguous continuation still gets a clear line when "and" is one of its closed-clause conjunctions. Clearing those conjunctions lets that continuation stay a review.
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

## D177 — The pronoun "it" is not an absence object on its own

- Status: proposed
- Date: 2026-11-13
- Context: "Left it in the barn" is the same shape as "left the X in", with a pronoun where the object name would be. The phrase file stands in `{prop}` for a name, an alias, a part, or a kind noun.
- Decision: "It" names the prop only when a lock lists that word as a label. The review for a place after the object stays "left the X in", "on", "running", or "there", with the lock's own word in place of X.
- Consequences: "He left the bike in the barn" is a review. "He left it in the barn" is not a prop mention, and it is not a review, unless the lock's label is "it".
- Who decided: Cursor cloud agent. Proposed. Ron has not accepted or rejected this.

