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

