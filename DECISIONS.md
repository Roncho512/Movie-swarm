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
- Consequences: New checks and new roles are tried on this production first. Its files stay in `productions/the-last-marker/`.
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
- Consequences: The treatment has a slot for the locked spec and for those images. The Script Supervisor is the before-generation check. The Dailies Reviewer is still Phase 3. D27 locked this film's sidedness. D30 says the checker reads the production's prop file and does not hard-code it.
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
- Consequences: Phase 2 reads `props/prop-definitions.json` and `look/look.json` from the production. Tests include Harbor Night, a second tiny production with a scarf and a documentary look. The shared treatment draft no longer invents this film's props, theme, or tone. The pilot sound library is still inside the sound program. Moving it is open.
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

