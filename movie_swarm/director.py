"""Director: turn a screenplay into a treatment, ask Ron, and call crew.

The Director drafts and revises. The Director does not approve. Ron's yes
or no is a Line Producer command. Crew calls go through the Line Producer
before any agent runs.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.dispatch import CrewCall, DispatchResult, dispatch_call
from movie_swarm.gates import budget_cap_usd
from movie_swarm.handoff import HandoffError
from movie_swarm.line_producer import LineProducer, LineProducerError
from movie_swarm.llm import LLMError
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
    merge_sources,
    questions_path,
    skill_excerpt,
    skill_note,
    treatment_errors,
    treatment_json_path,
    unanswered_required,
    write_questions,
    write_treatment_files,
)


class DirectorError(Exception):
    """The Director stopped. The message says what Ron, or the files, need to do."""


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
        treatment, method = self._draft(script, partial_source, brief, cap)
        if partial_source and partial_source.partial and script is not None:
            treatment = merge_sources(treatment, partial_source.partial)
        treatment = force_draft(conform_treatment(treatment))
        errors = treatment_errors(treatment)
        if errors:
            fallback = draft_offline(
                production_id=self.production_dir.name,
                script=script,
                brief=brief,
                cap_usd=cap,
            )
            if partial_source and partial_source.partial:
                fallback = merge_sources(fallback, partial_source.partial)
            fallback = force_draft(conform_treatment(fallback))
            fallback["draft_note"] = (
                (fallback.get("draft_note") or "")
                + " A model draft was discarded because it did not match the treatment checklist."
            ).strip()
            treatment = fallback
            method = "offline-deterministic"
            errors = treatment_errors(treatment)
        if errors:
            raise DirectorError("The draft is not a valid treatment.\n" + "\n".join(errors))

        script_text = "\n".join(
            part.text for part in (script, partial_source) if part is not None and part.text
        )
        questions = build_questions(treatment, script_text)
        questions = self._phrase_questions(questions)
        treatment["open_questions"] = [item["question"] for item in questions["questions"]]
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
        }

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
        return dispatch_call(producer, call, handler=handler)

    def _draft(self, script: ParsedSource | None, partial: ParsedSource | None, brief, cap: float):
        offline = draft_offline(
            production_id=self.production_dir.name,
            script=script or partial,
            brief=brief,
            cap_usd=cap,
        )
        if self.llm is None:
            return offline, "offline-deterministic"
        source_text = ""
        if script is not None:
            source_text += script.text[:12000]
        if partial is not None and partial.partial:
            source_text += "\n\nPartial treatment JSON:\n" + json.dumps(partial.partial)[:6000]
        try:
            raw = self.llm.complete(
                role="director",
                purpose="draft",
                system=(
                    "You are the Director of a short film. Return one JSON object that matches "
                    "the treatment schema. status must be draft. approval.state must be pending. "
                    "Do not approve your own work. Use the screenplay and the brief. "
                    "Required: logline, theme, emotional intent, tone, genre, characters "
                    "(name, role, look), scenes (what happens, emotional purpose), "
                    "deliverables (aspect ratio, resolution, length), open_questions.\n\n"
                    + skill_excerpt()
                ),
                user=source_text or json.dumps(brief or {}),
                max_tokens=8000,
            )
            drafted = force_draft(conform_treatment(extract_json_object(raw)))
            drafted["production_id"] = self.production_dir.name
            drafted["draft_method"] = "model"
            drafted["draft_note"] = "Model draft. " + skill_note()
            if treatment_errors(drafted):
                return offline, "offline-deterministic"
            return drafted, "model"
        except (LLMError, ValueError):
            note = offline.get("draft_note") or ""
            offline["draft_note"] = (note + " The model draft failed, so this is the offline draft.").strip()
            return offline, "offline-deterministic"

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
