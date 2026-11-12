"""Director: turn a screenplay into a treatment, ask Ron, and call crew.

The Director drafts and revises. The Director does not approve. Ron's yes
or no is a Line Producer command. Crew calls go through the Line Producer
before any agent runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from movie_swarm.dispatch import CrewCall, DispatchResult, dispatch_call
from movie_swarm.gates import budget_cap_usd
from movie_swarm.handoff import HandoffError
from movie_swarm.line_producer import LineProducer, LineProducerError
from movie_swarm.llm import LLMError, WritingQuote
from movie_swarm.redact import redact
from movie_swarm.script_intake import ParsedSource, load_source
from movie_swarm.treatment_doc import (
    apply_answers,
    build_questions,
    conform_treatment,
    draft_offline,
    extract_json_object,
    force_draft,
    load_questions,
    load_treatment,
    merge_missing_required,
    merge_sources,
    questions_path,
    skill_excerpt,
    skill_note,
    treatment_errors,
    treatment_schema_instructions,
    treatment_json_path,
    unanswered_required,
    write_questions,
    write_treatment_files,
)


class DirectorError(Exception):
    """The Director stopped. The message says what Ron, or the files, need to do."""


# Characters of screenplay, partial JSON, or one locked file sent on a live draft.
# A short screenplay fits. A longer file is cut, and the prompt says so.
DRAFT_SOURCE_CHAR_LIMIT = 120_000


class Director:
    def __init__(self, production_dir: str | Path, llm=None):
        self.production_dir = Path(production_dir)
        self.llm = llm

    def intake(
        self,
        screenplay: str | Path | None = None,
        partial: str | Path | None = None,
        run_id: str = "phase-1",
    ) -> dict:
        """Draft a treatment and the first question round. Does not approve it."""
        if not self.production_dir.is_dir():
            raise DirectorError(f"Production folder not found: {self.production_dir}")
        self._refuse_if_approved()
        self._refuse_if_answered()
        brief = _load_brief(self.production_dir)
        screenplay_path = screenplay or _screenplay_from_brief(self.production_dir, brief)
        script = load_source(screenplay_path) if screenplay_path else None
        partial_source = load_source(partial) if partial else None
        if script is None and partial_source is None:
            raise DirectorError("Give a screenplay, a partial treatment, or both.")
        if script is not None and script.partial and partial_source is None:
            partial_source = script
            script = None
        cap = _cap(brief)
        locked = _load_inputs(self.production_dir)
        treatment, method, called = self._draft(script, partial_source, brief, cap, run_id)
        treatment = _apply_inputs(treatment, locked, partial_source, script is not None)
        treatment = force_draft(conform_treatment(treatment))
        errors = treatment_errors(treatment)
        if errors:
            fallback = draft_offline(
                production_id=self.production_dir.name,
                script=script or partial_source,
                brief=brief,
                cap_usd=cap,
            )
            fallback = _apply_inputs(fallback, locked, partial_source, True)
            fallback = force_draft(conform_treatment(fallback))
            if called:
                fallback["draft_note"] = _fallback_note(errors, None, [])
            else:
                fallback["draft_note"] = (
                    (fallback.get("draft_note") or "")
                    + " The draft did not match the treatment checklist. "
                    + " ".join(redact(item) for item in errors)
                ).strip()
            treatment = fallback
            method = "offline-deterministic"
            errors = treatment_errors(treatment)
        if errors:
            raise DirectorError("The draft is not a valid treatment.\n" + "\n".join(errors))
        return self._finish(treatment, script, partial_source, run_id, method, phrase=True)

    def reconform(
        self,
        request_hash: str,
        run_id: str = "phase-1",
        screenplay: str | Path | None = None,
    ) -> dict:
        """Conform a cached model reply again. Does not call a model and does not book money.

        An identical live request replays the provider cache and is not charged again.
        The draft prompt changed in this phase, so that replay will not match the call
        that was already paid. This command reads the saved response instead.
        """
        if not self.production_dir.is_dir():
            raise DirectorError(f"Production folder not found: {self.production_dir}")
        self._refuse_if_approved()
        self._refuse_if_answered()
        raw, matched = _cached_draft_text(self.production_dir, run_id, request_hash)
        brief = _load_brief(self.production_dir)
        screenplay_path = screenplay or _screenplay_from_brief(self.production_dir, brief)
        script = load_source(screenplay_path) if screenplay_path else None
        if script is not None and script.partial:
            script = None
        cap = _cap(brief)
        offline = draft_offline(
            production_id=self.production_dir.name,
            script=script,
            brief=brief,
            cap_usd=cap,
        )
        try:
            drafted, errors = _draft_from_raw(raw, offline, self.production_dir.name)
        except ValueError as exc:
            saved = _save_rejected_draft(self.production_dir, run_id, raw)
            raise DirectorError(
                "The cached reply is not a treatment. "
                + redact(str(exc))
                + f" The raw reply was saved to {saved}. No new model call was made."
            ) from exc
        if drafted is None:
            saved = _save_rejected_draft(self.production_dir, run_id, raw)
            listed = "\n".join(redact(item) for item in errors)
            raise DirectorError(
                "The cached draft still does not match the treatment checklist. "
                "No new model call was made. The call cost from the original request stays booked.\n"
                + listed
                + f"\nThe raw reply was saved to {saved}."
            )
        locked = _load_inputs(self.production_dir)
        drafted = _apply_inputs(drafted, locked, None, False)
        drafted = force_draft(conform_treatment(drafted, fallback=offline))
        errors = treatment_errors(drafted)
        if errors:
            raise DirectorError(
                "The cached draft still does not match the treatment checklist. "
                "No new model call was made.\n" + "\n".join(redact(item) for item in errors)
            )
        drafted["draft_note"] = (
            (drafted.get("draft_note") or "")
            + f" Reconformed from cached request {matched[:12]}. "
            "No new model call was made. Nothing new was booked."
        ).strip()
        result = self._finish(drafted, script, None, run_id, "model", phrase=False)
        result["request_hash"] = matched
        return result

    def answer(self, answers: str | Path, run_id: str = "phase-1") -> dict:
        """Read Ron's answers, revise the draft, and keep it unapproved."""
        self._refuse_if_approved()
        try:
            treatment = load_treatment(self.production_dir)
            questions = load_questions(self.production_dir)
        except HandoffError as exc:
            raise DirectorError(str(exc)) from exc
        incoming = _read_answers(answers)
        treatment, questions = apply_answers(treatment, questions, incoming)
        treatment["draft_method"] = treatment.get("draft_method") or "offline-deterministic"
        pending = unanswered_required(questions)
        if not pending and self.llm is not None:
            treatment = self._final_pass(treatment)
        treatment = force_draft(conform_treatment(treatment))
        errors = treatment_errors(treatment)
        if errors:
            raise DirectorError(
                "The revised treatment does not match the checklist.\n" + "\n".join(errors)
            )
        write_treatment_files(self.production_dir, treatment)
        write_questions(self.production_dir, questions)
        try:
            producer = LineProducer.open(self.production_dir, run_id)
            producer.run.data["notes"] = (
                "Questions are still open."
                if pending
                else "Questions for this round are answered. The treatment is still a draft until Ron approves the gate."
            )
            producer.run.data["status"] = "waiting-for-review"
            producer.run.save()
        except LineProducerError:
            pass
        return {
            "status": "draft",
            "questions_status": questions["status"],
            "open_required": len(pending),
            "treatment": str(treatment_json_path(self.production_dir)),
            "questions": str(questions_path(self.production_dir)),
        }

    def dispatch(self, call: CrewCall, run_id: str, handler=None) -> DispatchResult:
        """Call one coded crew agent. The Line Producer checks the gate and the cap first."""
        try:
            producer = LineProducer.open(self.production_dir, run_id)
        except LineProducerError as exc:
            return DispatchResult(status="refused", message=str(exc))
        call.production_dir = call.production_dir or str(self.production_dir)
        if call.llm is None:
            call.llm = self.llm
        return dispatch_call(producer, call, handler=handler)

    def _finish(self, treatment, script, partial_source, run_id: str, method: str, *, phrase: bool) -> dict:
        treatment = _apply_film_budget(self.production_dir, treatment)
        script_text = "\n".join(
            part.text for part in (script, partial_source) if part is not None and part.text
        )
        questions = build_questions(treatment, script_text)
        if phrase:
            questions = self._phrase_questions(questions)
        treatment["open_questions"] = [item["question"] for item in questions["questions"]]
        errors = treatment_errors(treatment)
        if errors:
            raise DirectorError("The draft is not a valid treatment.\n" + "\n".join(errors))
        json_path, md_path = write_treatment_files(self.production_dir, treatment)
        q_path = write_questions(self.production_dir, questions)
        producer = self._run(run_id)
        producer.set_stage("treatment", "waiting-for-review")
        producer.ensure_artifact("treatment", "treatment/treatment.json", "treatment.schema.json")
        producer.ensure_artifact("treatment-markdown", "treatment/treatment.md")
        producer.ensure_artifact("questions", "treatment/questions.json", "director-questions.schema.json")
        producer.run.data["notes"] = "Draft treatment is waiting on Ron. The Director did not approve it."
        producer.run.save()
        return {
            "treatment": str(json_path),
            "treatment_markdown": str(md_path),
            "questions": str(q_path),
            "run_id": producer.run.data["run_id"],
            "drafted_by": method,
            "question_count": len(questions["questions"]),
            "status": "draft",
            "draft_note": treatment.get("draft_note") or "",
        }

    def _draft(self, script: ParsedSource | None, partial: ParsedSource | None, brief, cap: float, run_id: str):
        offline = draft_offline(
            production_id=self.production_dir.name,
            script=script or partial,
            brief=brief,
            cap_usd=cap,
        )
        if self.llm is None:
            return offline, "offline-deterministic", False
        user, clips = _draft_user(self.production_dir, script, partial, brief)
        try:
            raw = self.llm.complete(
                role="director",
                purpose="draft",
                system=_draft_system(),
                user=user,
                max_tokens=8000,
            )
        except WritingQuote:
            raise
        except (LLMError, ValueError) as exc:
            noted, called = _note_after_exception(offline, exc)
            return noted, "offline-deterministic", called
        try:
            drafted, errors = _draft_from_raw(raw, offline, self.production_dir.name)
        except ValueError as exc:
            saved = _save_rejected_draft(self.production_dir, run_id, raw)
            offline["draft_note"] = _fallback_note([str(exc)], saved, clips)
            offline["draft_method"] = "offline-deterministic"
            return offline, "offline-deterministic", True
        if drafted is None:
            saved = _save_rejected_draft(self.production_dir, run_id, raw)
            offline["draft_note"] = _fallback_note(errors, saved, clips)
            offline["draft_method"] = "offline-deterministic"
            return offline, "offline-deterministic", True
        if clips:
            drafted["draft_note"] = ((drafted.get("draft_note") or "") + " " + " ".join(clips)).strip()
        return drafted, "model", True

    def _phrase_questions(self, questions: dict) -> dict:
        if self.llm is None:
            return questions
        try:
            raw = self.llm.complete(
                role="line-producer",
                purpose="questions",
                system=(
                    "You keep the question list tidy. Return JSON: "
                    "{\"questions\": [{\"id\": \"...\", \"question\": \"...\"}]}. "
                    "Keep every id. Do not add or drop questions. Shorten the wording only."
                ),
                user=json.dumps(
                    [{"id": item["id"], "question": item["question"]} for item in questions["questions"]]
                ),
                max_tokens=2000,
            )
            data = extract_json_object(raw)
        except WritingQuote:
            raise
        except (LLMError, ValueError):
            return questions
        by_id = {
            item.get("id"): item.get("question")
            for item in data.get("questions") or []
            if isinstance(item, dict)
        }
        for item in questions["questions"]:
            text = by_id.get(item["id"])
            if isinstance(text, str) and text.strip():
                item["question"] = text.strip()
        questions["drafted_by"] = "model"
        questions["model"] = "claude-haiku-5-5"
        return questions

    def _final_pass(self, treatment: dict) -> dict:
        try:
            raw = self.llm.complete(
                role="director",
                purpose="final",
                system=(
                    "You are the Director writing the final treatment pass. "
                    "Return the full treatment as one JSON object. "
                    "Keep every fact Ron answered. status must stay draft. "
                    "You cannot approve the film."
                ),
                user=json.dumps(treatment),
                max_tokens=8000,
            )
            revised = force_draft(conform_treatment(extract_json_object(raw)))
            revised["production_id"] = self.production_dir.name
            revised["draft_method"] = "model"
            revised["draft_note"] = "Final pass from the model. Still a draft until Ron approves the gate."
            if treatment_errors(revised):
                treatment["draft_note"] = (
                    (treatment.get("draft_note") or "")
                    + " The final model pass did not match the checklist, so the earlier draft was kept."
                ).strip()
                return treatment
            return revised
        except WritingQuote:
            raise
        except (LLMError, ValueError) as exc:
            treatment["draft_note"] = (
                (treatment.get("draft_note") or "")
                + f" The final model pass failed ({exc}). The earlier draft was kept."
            ).strip()
            return treatment

    def _run(self, run_id: str) -> LineProducer:
        try:
            return LineProducer.open(self.production_dir, run_id)
        except LineProducerError:
            return LineProducer.start(self.production_dir, run_id=run_id, stage="treatment")

    def _refuse_if_approved(self) -> None:
        path = treatment_json_path(self.production_dir)
        if not path.is_file():
            return
        try:
            current = load_treatment(self.production_dir)
        except HandoffError:
            return
        if current.get("status") == "approved":
            raise DirectorError(
                "The treatment is already approved. The Director will not write over Ron's approval."
            )

    def _refuse_if_answered(self) -> None:
        path = questions_path(self.production_dir)
        if not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if any(str(item.get("answer") or "").strip() for item in payload.get("questions", [])):
            raise DirectorError(
                "This round already has answers. The Director will not wipe them. "
                "Use the answer command to continue."
            )


def _apply_film_budget(production_dir: Path, treatment: dict) -> dict:
    """Use budget.json for the proposed split when the film has one.

    The question Ron reads and the split the Line Producer locks are the
    spendable lines. Contingency stays in the reserve. A film with no budget
    file keeps the proposed split of the cap.
    """
    from movie_swarm.budget import compute, load_film_budget
    from movie_swarm.money import money_number

    film = load_film_budget(production_dir)
    if film is None:
        return treatment
    math = compute(film)
    split = {name: money_number(amount) for name, amount in math.spendable().items()}
    budget = treatment.setdefault("constraints_and_budget", {})
    budget["budget_cap_usd"] = money_number(film["total_usd"])
    budget["stage_split"] = split
    if math.trailer_on:
        trailer = "The trailer is on, so Marketing and Distribution is in the split and the other lines are scaled."
    else:
        trailer = "The trailer is off, so Marketing and Distribution is not in the split."
    note = (
        "The proposed split is the spendable lines from budget.json. "
        "Contingency is held back and is not a stage line. "
        + trailer
    )
    budget["notes"] = ((budget.get("notes") or "") + " " + note).strip()
    return treatment


def _load_inputs(production_dir: Path) -> dict | None:
    """Creative facts the Director reads. They are not a gate approval.

    ``treatment/inputs.json`` is a partial treatment. A status or an approval
    in that file is ignored. ``force_draft`` still runs after the merge.
    """
    path = production_dir / "treatment" / "inputs.json"
    if not path.is_file():
        return None
    try:
        loaded = load_source(path)
    except ValueError as exc:
        raise DirectorError(str(exc)) from exc
    return loaded.partial


def _apply_inputs(treatment: dict, locked: dict | None, partial: ParsedSource | None, merge_partial: bool) -> dict:
    if locked:
        treatment = merge_sources(treatment, locked)
        treatment["draft_note"] = (
            (treatment.get("draft_note") or "")
            + " Locked creative inputs were read from treatment/inputs.json. They do not approve the gate."
        ).strip()
    if merge_partial and partial is not None and partial.partial:
        treatment = merge_sources(treatment, partial.partial)
    return treatment


def _load_brief(production_dir: Path) -> dict | None:
    path = production_dir / "production-brief.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DirectorError(f"The production brief is not valid JSON. {exc}") from exc
    if not isinstance(data, dict):
        raise DirectorError("The production brief must be a JSON object.")
    return data


def _screenplay_from_brief(production_dir: Path, brief: dict | None) -> Path | None:
    if not brief or not brief.get("screenplay_path"):
        return None
    path = production_dir / brief["screenplay_path"]
    if not path.is_file():
        raise DirectorError(f"The brief names a screenplay that is not there: {path}")
    return path


def _cap(brief: dict | None) -> float:
    if brief and brief.get("budget_cap_usd"):
        return float(brief["budget_cap_usd"])
    return budget_cap_usd()


def _read_answers(path: str | Path) -> dict[str, str]:
    document = Path(path)
    if not document.is_file():
        raise DirectorError(f"Answers file not found: {document}")
    try:
        data = json.loads(document.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DirectorError(f"The answers file is not valid JSON. {exc}") from exc
    if isinstance(data, dict) and "questions" in data and "answers" not in data:
        pairs = data["questions"]
        return {
            item["id"]: item.get("answer") or ""
            for item in pairs
            if isinstance(item, dict) and item.get("id")
        }
    if isinstance(data, dict) and "answers" in data:
        return {
            item["id"]: item.get("answer") or ""
            for item in data["answers"]
            if isinstance(item, dict) and item.get("id")
        }
    raise DirectorError(
        "The answers file needs an answers list, or it can be the questions file with answer fields filled in."
    )


def _draft_system() -> str:
    return (
        "You are the Director of a short film. Return one JSON object that matches "
        "the treatment schema. status must be draft. approval.state must be pending. "
        "Do not approve your own work. Use the screenplay and the brief. "
        "Follow locked creative inputs and locked prop facts. "
        "Do not raise open questions about items already locked.\n\n"
        + treatment_schema_instructions()
        + "\n\n"
        + skill_excerpt()
    )


def _draft_user(production_dir: Path, script, partial, brief) -> tuple[str, list[str]]:
    """The user message for one live draft, and any notes about text that was cut."""
    notes: list[str] = []
    parts: list[str] = []
    if script is not None and script.text:
        text, note = _bounded(script.text, "The screenplay")
        parts.append("Screenplay:\n" + text)
        if note:
            notes.append(note)
    if partial is not None and partial.partial:
        text, note = _bounded(json.dumps(partial.partial), "The partial treatment JSON")
        parts.append("Partial treatment JSON:\n" + text)
        if note:
            notes.append(note)
    locked, locked_notes = _locked_prompt(production_dir)
    if locked:
        parts.append(locked)
    notes.extend(locked_notes)
    if not parts:
        parts.append(json.dumps(brief or {}))
    return "\n\n".join(parts), notes


def _locked_prompt(production_dir: Path) -> tuple[str, list[str]]:
    """Creative inputs and prop locks, when the production folder has them."""
    notes: list[str] = []
    blocks: list[str] = []
    inputs = production_dir / "treatment" / "inputs.json"
    if inputs.is_file():
        body, note = _read_bounded(inputs, "treatment/inputs.json")
        blocks.append(
            "Locked creative inputs. The draft must follow these and must not re-ask them.\n"
            "Source: treatment/inputs.json\n"
            + body
        )
        if note:
            notes.append(note)
    chunks: list[str] = []
    for relative in ("props/hero-props.json", "props/prop-definitions.json"):
        path = production_dir / relative
        if not path.is_file():
            continue
        body, note = _read_bounded(path, relative)
        chunks.append(f"Source: {relative}\n{body}")
        if note:
            notes.append(note)
    props = production_dir / "props"
    if props.is_dir():
        for path in sorted(props.glob("*/*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in {".json", ".md", ".txt"}:
                continue
            relative = path.relative_to(production_dir).as_posix()
            body, note = _read_bounded(path, relative)
            chunks.append(f"Source: {relative}\n{body}")
            if note:
                notes.append(note)
    if chunks:
        blocks.append(
            "Locked prop facts. The draft must follow these and must not re-ask them.\n"
            + "\n\n".join(chunks)
        )
    return "\n\n".join(blocks), notes


def _read_bounded(path: Path, label: str) -> tuple[str, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return f"[{label} could not be read: {exc}]", f"{label} could not be read."
    return _bounded(text, label)


def _bounded(text: str, label: str) -> tuple[str, str | None]:
    if len(text) <= DRAFT_SOURCE_CHAR_LIMIT:
        return text, None
    note = (
        f"{label} was cut from {len(text)} characters to the first {DRAFT_SOURCE_CHAR_LIMIT}. "
        "The rest was not sent."
    )
    return text[:DRAFT_SOURCE_CHAR_LIMIT] + "\n\n[" + note + "]", note


def _draft_from_raw(raw: str, offline: dict, production_id: str) -> tuple[dict | None, list[str]]:
    parsed = extract_json_object(raw)
    drafted = _stamp_model(
        force_draft(conform_treatment(parsed, fallback=offline)),
        production_id,
        filled=False,
    )
    errors = treatment_errors(drafted)
    if not errors:
        return drafted, []
    merged = merge_missing_required(drafted, offline)
    merged = _stamp_model(
        force_draft(conform_treatment(merged, fallback=offline)),
        production_id,
        filled=True,
    )
    errors = treatment_errors(merged)
    if not errors:
        return merged, []
    return None, errors


def _stamp_model(treatment: dict, production_id: str, *, filled: bool) -> dict:
    treatment["production_id"] = production_id
    treatment["draft_method"] = "model"
    if filled:
        treatment["draft_note"] = (
            "Model draft. Missing required fields were filled from the offline draft. " + skill_note()
        )
    else:
        treatment["draft_note"] = "Model draft. " + skill_note()
    return treatment


def _fallback_note(errors: list[str], saved: str | None, clips: list[str]) -> str:
    parts = [
        "A model was called. The call cost was booked.",
        "The model draft did not match the treatment checklist, so the offline draft was kept.",
    ]
    if errors:
        parts.append("Schema errors: " + "; ".join(redact(item) for item in errors) + ".")
    if saved:
        parts.append(f"The raw reply was saved to {saved}.")
    parts.extend(clips)
    parts.append(skill_note())
    return " ".join(part.strip() for part in parts if part and str(part).strip())


def _note_after_exception(offline: dict, exc: Exception) -> tuple[dict, bool]:
    reason = redact(str(exc))
    booked = _call_was_booked(reason)
    if booked:
        offline["draft_note"] = (
            "A model was called. The call cost was booked. "
            "The model draft failed, so this is the offline draft. "
            + reason
        )
        return offline, True
    note = offline.get("draft_note") or ""
    offline["draft_note"] = (note + " The model draft was not used. " + reason).strip()
    return offline, False


def _call_was_booked(reason: str) -> bool:
    lowered = reason.casefold()
    if "nothing was sent" in lowered or "nothing was booked" in lowered:
        return False
    return "stays booked" in lowered or "was booked" in lowered


def _save_rejected_draft(production_dir: Path, run_id: str, raw: str) -> str:
    from movie_swarm.run_state import default_run_state_path

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    relative = f"runs/{run_id}/rejected-draft-{digest}.txt"
    path = default_run_state_path(production_dir, run_id).parent / f"rejected-draft-{digest}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(raw), encoding="utf-8")
    return relative


def _cached_draft_text(production_dir: Path, run_id: str, request_hash: str) -> tuple[str, str]:
    from movie_swarm.assets import resolve_asset
    from movie_swarm.line_producer import record_path

    path = record_path(production_dir, run_id).with_name("provider-cache.json")
    if not path.is_file():
        raise DirectorError(
            f"No provider cache for run {run_id}. A cached draft is saved after a text call. Nothing was called."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DirectorError(f"The provider cache is not valid JSON. {exc}") from exc
    calls = data.get("calls") if isinstance(data, dict) else None
    if not isinstance(calls, dict) or not calls:
        raise DirectorError("The provider cache has no calls. Nothing was called.")
    needle = request_hash.strip().lower()
    if len(needle) < 8:
        raise DirectorError("Pass at least 8 characters of the request hash. Nothing was called.")
    matches = [key for key in calls if str(key).lower().startswith(needle)]
    if not matches:
        raise DirectorError("No cached call matches that request hash. Nothing was called.")
    if len(matches) > 1:
        raise DirectorError(
            "That prefix matches more than one cached call. Pass a longer hash. Nothing was called."
        )
    key = matches[0]
    entry = calls[key] if isinstance(calls[key], dict) else {}
    text = entry.get("text") if isinstance(entry, dict) else None
    if isinstance(text, str) and text.strip():
        return text, key
    output = entry.get("output") if isinstance(entry, dict) else None
    if isinstance(output, str) and output.strip():
        for candidate in (production_dir / output, resolve_asset(production_dir, output)):
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8"), key
    raise DirectorError("That cached call has no response text. Nothing was called.")
