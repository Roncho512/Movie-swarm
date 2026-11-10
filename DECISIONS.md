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
- Consequences: The treatment has a slot for the locked spec and for those images. The two checker roles are Phase 2 and Phase 3. They are not in the code yet. Sidedness for this film is still open.
- Who decided: Ron

## D12 — A stunt and action role

- Date: 2026-11-10
- Context: Action beats were being invented inside other jobs. Kicks, plugs, and falls need an owner.
- Decision: Add a Stunt and Action Coordinator role.
- Consequences: The treatment has a place for action beats. The role itself arrives in Phase 2. The Director's first questions ask Ron to confirm the beats.
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
