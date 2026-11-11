"""Line Producer: budget, schedule, credits, and gates for one run.

Uses the Phase 0 run state for the stage, the status, and the running total.
The ledger, the stage split, the credits, and Ron's decisions live beside it
in ``line-producer.json``. Nothing here asks a question in the terminal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from movie_swarm.gates import budget_cap_usd, is_stage_gated, load_gate_config, would_exceed_budget
from movie_swarm.handoff import read_handoff, write_handoff
from movie_swarm.money import as_money, money_number
from movie_swarm.roles import (
    CALLABLE,
    DAILIES_BILLING,
    DAILIES_CREW,
    DAILIES_STAGE,
    EDIT_STAGE,
    GATED_CREW,
    GENERATION_STAGE,
    PHASE2_BILLING,
    PHASE2_CREW,
    PICTURE_CREW,
    PREVIS_STAGE,
    SOUND_BILLING,
    SOUND_STAGE,
)
from movie_swarm.run_state import RunState, default_run_state_path
from movie_swarm.treatment_doc import load_treatment, treatment_json_path, write_treatment_files


class LineProducerError(Exception):
    """The Line Producer will not do this. The message says why, in plain language."""


@dataclass
class SpendResult:
    recorded: bool
    total_usd: float
    message: str
    request_id: str | None = None


@dataclass
class Authorization:
    """Whether a crew call may proceed. A pause writes an approval request."""

    allowed: bool
    message: str
    request_id: str | None = None
    allowance_request_id: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_path(production_dir: str | Path, run_id: str) -> Path:
    return default_run_state_path(production_dir, run_id).with_name("line-producer.json")


def request_file(production_dir: str | Path, run_id: str, request_id: str) -> Path:
    return default_run_state_path(production_dir, run_id).parent / "requests" / f"{request_id}.json"


class LineProducer:
    """One production run's money, gates, credits, and schedule."""

    def __init__(self, run: RunState, record: dict, production_dir: Path, config_path: Path | None = None):
        self.run = run
        self.record = record
        self.production_dir = Path(production_dir)
        self.config_path = config_path

    @classmethod
    def start(
        cls,
        production_dir: str | Path,
        *,
        run_id: str | None = None,
        stage: str = "treatment",
        config_path: str | Path | None = None,
    ) -> "LineProducer":
        """Open a run. The cap is copied from the gate config, same as Phase 0."""
        production = Path(production_dir)
        if not production.is_dir():
            raise LineProducerError(f"Production folder not found: {production}")
        run = RunState.create(
            production,
            run_id=run_id,
            stage=stage,
            status="waiting-for-review",
            notes="Waiting on Ron.",
            config_path=config_path,
        )
        stages = list(load_gate_config(config_path)["gates"])
        schedule = {name: "pending" for name in stages}
        if stage in schedule:
            schedule[stage] = "waiting-for-review"
        record = {
            "production_id": run.data["production_id"],
            "run_id": run.data["run_id"],
            "credits": [
                {"role": "Executive Producer", "name": "Ron"},
                {"role": "Line Producer", "name": "Line Producer"},
                {"role": "Director", "name": "Director"},
            ],
            "stage_allocations": {
                "status": "unlocked",
                "split": {},
                "approved_at": None,
                "approved_by": None,
                "note": "The split locks when Ron approves the treatment.",
            },
            "ledger": [],
            "gate_decisions": [],
            "requests": [],
            "schedule": schedule,
            "updated_at": _now(),
        }
        producer = cls(run, record, production, Path(config_path) if config_path else None)
        producer._save_record()
        return producer

    @classmethod
    def open(
        cls,
        production_dir: str | Path,
        run_id: str,
        config_path: str | Path | None = None,
    ) -> "LineProducer":
        production = Path(production_dir)
        state_path = default_run_state_path(production, run_id)
        if not state_path.is_file():
            raise LineProducerError(
                f"No run named {run_id} in {production}. Start one with the Line Producer first."
            )
        run = RunState.load(state_path)
        path = record_path(production, run_id)
        record = read_handoff(path, schema="line-producer-record")
        return cls(run, record, production, Path(config_path) if config_path else None)

    def save(self) -> None:
        self.run.save()
        self._save_record()

    def _save_record(self) -> None:
        self.record["updated_at"] = _now()
        write_handoff(
            record_path(self.production_dir, self.run.data["run_id"]),
            self.record,
            schema="line-producer-record",
        )

    def add_credit(self, role: str, name: str, note: str = "") -> None:
        item = {"role": role.strip(), "name": name.strip()}
        if note.strip():
            item["note"] = note.strip()
        if not item["role"] or not item["name"]:
            raise LineProducerError("A credit needs a role and a name.")
        self.record["credits"].append(item)
        self._save_record()

    def ensure_artifact(self, name: str, path: str, schema: str | None = None) -> None:
        self.run.data["artifacts"] = [
            item for item in self.run.data["artifacts"] if item.get("path") != path
        ]
        self.run.add_artifact(name, path, schema)

    def set_stage(self, stage: str, status: str) -> None:
        self.run.set_stage(stage, status=status)
        self.record["schedule"][stage] = _schedule_word(status)
        self._save_record()

    def gate_decision(self, stage: str) -> str | None:
        found = None
        for item in self.record["gate_decisions"]:
            if item["stage"] == stage:
                found = item["decision"]
        return found

    def gate_is_open(self, stage: str) -> bool:
        """True when this stage does not require Ron, or Ron has approved it."""
        if not is_stage_gated(stage, self.config_path):
            return True
        return self.gate_decision(stage) == "approved"

    def stage_spent(self, stage: str) -> float:
        total = as_money(0)
        for entry in self.record["ledger"]:
            if entry["stage"] == stage and entry["kind"] != "dry-run":
                total += as_money(entry["amount_usd"])
        return money_number(total)

    def record_spend(
        self,
        stage: str,
        amount_usd: float,
        description: str,
        kind: str = "generation",
    ) -> SpendResult:
        """Record a real spend, or pause and write an approval request."""
        if kind not in {"generation", "retake"}:
            raise LineProducerError("A recorded spend is a generation or a retake. A dry run is not a spend.")
        self._require_known_stage(stage)
        amount = self._check_amount(amount_usd)
        block = self._block_reason(stage, amount, books_money=True, description=description, crew_gates=True)
        if block is not None:
            return SpendResult(
                recorded=False,
                total_usd=float(self.run.data["cost_usd"]),
                message=block.message,
                request_id=block.request_id,
            )
        self._book(stage, amount, kind, description, request_id=None)
        total = float(self.run.data["cost_usd"])
        label = "retake" if kind == "retake" else "spend"
        return SpendResult(
            recorded=True,
            total_usd=total,
            message=(
                f"Recorded ${money_number(amount):.2f} for {stage} ({label}). "
                f"The film has spent ${total:.2f} of ${float(self.run.data['budget_cap_usd']):.2f}."
            ),
        )

    def paid_generation_block(self) -> Authorization | None:
        """Stop a paid call while the generation gate is still closed.

        A dry run does not ask. Opening the gate is Ron's recorded yes.
        This method does not book money.
        """
        if not is_stage_gated(GENERATION_STAGE, self.config_path):
            return None
        if self.gate_is_open(GENERATION_STAGE):
            return None
        return self._pause_gate(
            GENERATION_STAGE,
            "The generation gate is still closed. Ron has not approved a paid generation, so no provider was called.",
        )

    def authorize_crew(self, stage: str, amount_usd: float, description: str) -> Authorization:
        """Gate and budget check before the Director calls a crew agent. Does not book money."""
        if stage not in CALLABLE:
            raise LineProducerError(
                f"{stage} is not a crew agent the Director can call. "
                f"Calls go to: {', '.join(CALLABLE)}."
            )
        billing = (
            PHASE2_BILLING.get(stage)
            or DAILIES_BILLING.get(stage)
            or SOUND_BILLING.get(stage)
            or stage
        )
        self._require_known_stage(billing)
        amount = self._check_amount(amount_usd)
        allowance = self._allowance(billing, amount)
        if allowance is not None:
            return Authorization(
                allowed=True,
                message=(
                    f"Ron already approved this ${money_number(amount):.2f} {billing} estimate "
                    f"({allowance['request_id']}). The call can proceed. It will not be charged."
                ),
                allowance_request_id=allowance["request_id"],
            )
        gate_block = self._crew_gate_block(stage)
        if gate_block is not None:
            return gate_block
        block = self._block_reason(
            billing,
            amount,
            books_money=False,
            description=description,
            crew_gates=False,
        )
        if block is not None:
            return block
        where = billing if billing != stage else stage
        return Authorization(
            allowed=True,
            message=(
                f"{stage} is allowed. The estimate ${money_number(amount):.2f} fits the cap "
                f"and the {where} allocation. No money is charged for a dry run or an estimate."
            ),
        )

    def note_dry_run(
        self,
        stage: str,
        estimate_usd: float,
        description: str,
        allowance_request_id: str | None = None,
    ) -> None:
        """Remember that a crew call ran without charging the cap."""
        entry = {
            "entry_id": self._next_id("spend", [item["entry_id"] for item in self.record["ledger"]]),
            "stage": stage,
            "amount_usd": 0.0,
            "kind": "dry-run",
            "description": (
                f"{description} Estimate ${money_number(estimate_usd):.2f} was checked and not charged."
            ),
            "recorded_at": _now(),
            "request_id": allowance_request_id,
        }
        self.record["ledger"].append(entry)
        if allowance_request_id:
            for request in self.record["requests"]:
                if request["request_id"] == allowance_request_id:
                    request["consumed"] = True
        self._save_record()

    def approve_gate(
        self,
        stage: str,
        decision: str,
        by: str,
        note: str = "",
        stage_split: dict | None = None,
    ) -> str:
        """Record Ron's yes or no. Approving the treatment locks the stage split."""
        decision = _decision(decision)
        by = by.strip()
        if not by:
            raise LineProducerError("Say who decided. For this film, that is Ron.")
        if stage == "treatment" and decision == "approved":
            self._lock_treatment(by, note, stage_split)
        item = {
            "stage": stage,
            "decision": decision,
            "by": by,
            "note": note.strip(),
            "decided_at": _now(),
        }
        self.record["gate_decisions"].append(item)
        self.record["schedule"][stage] = "approved" if decision == "approved" else "rejected"
        self._close_gate_requests(stage, decision, by, note)
        if decision == "approved":
            self.run.data["status"] = "running" if not self._still_waiting() else "waiting-for-review"
            message = f"Ron approved the {stage} gate."
        else:
            self.run.data["status"] = "waiting-for-review"
            message = f"Ron rejected the {stage} gate. The work stays unapproved."
        self.run.data["notes"] = message
        self.run.save()
        self._save_record()
        return message

    def decide_request(self, request_id: str, decision: str, by: str, note: str = "") -> str:
        """Approve or reject one spend request. Approving a real spend books it, even past the cap."""
        decision = _decision(decision)
        by = by.strip()
        if not by:
            raise LineProducerError("Say who decided. For this film, that is Ron.")
        request = self._find_request(request_id)
        if request["status"] != "pending":
            raise LineProducerError(
                f"{request_id} is already {request['status']}. It will not be decided again."
            )
        request["status"] = decision
        request["decided_at"] = _now()
        request["decided_by"] = by
        request["note"] = note.strip()
        self._write_request_file(request)
        if decision == "approved" and request["books_money"]:
            amount = as_money(request["amount_usd"])
            kind = "retake" if "retake" in (request.get("description") or "").lower() else "generation"
            self._book(request["stage"], amount, kind, request.get("description") or request["reason"], request_id)
            self._raise_allocation(request["stage"])
            message = (
                f"Ron approved {request_id}. "
                f"${money_number(amount):.2f} is now spent on {request['stage']}. "
                f"Film total: ${float(self.run.data['cost_usd']):.2f} "
                f"of ${float(self.run.data['budget_cap_usd']):.2f}."
            )
        elif decision == "approved":
            message = (
                f"Ron approved {request_id}. No money was booked. "
                "The next matching dry run or estimate may proceed."
            )
        else:
            message = f"Ron rejected {request_id}. Nothing was charged."
        if not self._still_waiting() and self.run.data["status"] == "waiting-for-review":
            self.run.data["status"] = "running"
        self.run.data["notes"] = message
        self.run.save()
        self._save_record()
        return message

    def status_text(self, narration: str = "") -> str:
        """Plain-language status. Numbers come from the ledger, not from a model."""
        data = self.run.data
        spent = float(data["cost_usd"])
        cap = float(data["budget_cap_usd"])
        title = self._title()
        lines = [
            f"{title} — run {data['run_id']}",
            f"Stage: {data['stage']}",
            f"Status: {_plain_status(data['status'])}",
            f"Spent: ${spent:.2f} of ${cap:.2f}",
        ]
        over = as_money(spent) - as_money(cap)
        if over > 0:
            lines.append(
                f"${money_number(over):.2f} of that spend was approved past the ${cap:.2f} cap."
            )
        allocations = self.record["stage_allocations"]
        if allocations["status"] == "approved":
            lines.append("Stage allocations are locked:")
            for stage, amount in allocations["split"].items():
                lines.append(
                    f"  {stage}: ${self.stage_spent(stage):.2f} of ${float(amount):.2f}"
                )
            split_sum = sum(as_money(value) for value in allocations["split"].values())
            if split_sum > as_money(cap):
                lines.append(
                    "The locked stage ceilings add up to more than the film cap. "
                    "The film cap is still checked on every new spend."
                )
        else:
            lines.append(
                "Stage allocations are not locked. They lock when Ron approves the treatment."
            )
        waiting = self.waiting_lines()
        if waiting:
            lines.append("Waiting on Ron:")
            lines.extend(f"  - {item}" for item in waiting)
        else:
            lines.append("Waiting on Ron: nothing.")
        if narration.strip():
            lines.extend(["", narration.strip()])
        return "\n".join(lines)

    def waiting_lines(self) -> list[str]:
        lines = []
        questions = self.production_dir / "treatment" / "questions.json"
        open_questions = 0
        if questions.is_file():
            try:
                payload = json.loads(questions.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if payload.get("status") == "open":
                open_questions = sum(
                    1 for item in payload.get("questions", [])
                    if not str(item.get("answer") or "").strip()
                )
                lines.append(
                    f"Answer {open_questions} question(s) from the Director. "
                    "File: treatment/questions.json"
                )
        treatment = treatment_json_path(self.production_dir)
        if treatment.is_file() and self.gate_decision("treatment") != "approved":
            if open_questions:
                lines.append(
                    "After the questions are answered, approve or reject the treatment gate. "
                    "Read treatment/treatment.md first."
                )
            else:
                lines.append(
                    "Approve or reject the treatment gate. Read treatment/treatment.md first."
                )
        for request in self.record["requests"]:
            if request["status"] == "pending":
                lines.append(f"{request['request_id']}: {request['reason']}")
        package = self.production_dir / "props" / "hero-props.json"
        if package.is_file() and self.gate_decision("previs") != "approved":
            lines.append(
                "Approve or reject the previs gate. "
                "Read the prop lock, the continuity check, the camera package, the storyboard, and the action breakdown."
            )
        if (
            self.gate_decision("previs") == "approved"
            and is_stage_gated(GENERATION_STAGE, self.config_path)
            and not self.gate_is_open(GENERATION_STAGE)
        ):
            lines.append(
                "Approve or reject the generation gate before any paid image, video, or audio call. "
                "A dry-run cost estimate does not need that approval."
            )
        report = self.production_dir / "dailies" / "dailies-report.md"
        if (
            report.is_file()
            and is_stage_gated(DAILIES_STAGE, self.config_path)
            and not self.gate_is_open(DAILIES_STAGE)
        ):
            lines.append(
                "Approve or reject the dailies gate before the editor runs. "
                "Read dailies/dailies-report.md. Circled takes stay out of the edit until you approve."
            )
        rough_cut = self.production_dir / "edit" / "rough-cut.md"
        if (
            rough_cut.is_file()
            and is_stage_gated(EDIT_STAGE, self.config_path)
            and not self.gate_is_open(EDIT_STAGE)
        ):
            lines.append(
                "Approve or reject the edit gate before sound runs. "
                "Read edit/rough-cut.md. That approval is picture lock."
            )
        cue_sheet = self.production_dir / "sound" / "cue-sheet.md"
        if (
            cue_sheet.is_file()
            and is_stage_gated(SOUND_STAGE, self.config_path)
            and not self.gate_is_open(SOUND_STAGE)
        ):
            lines.append(
                "Approve or reject the sound gate before color and mix. Read sound/cue-sheet.md."
            )
        return lines

    def _still_waiting(self) -> bool:
        return bool(self.waiting_lines())

    def _title(self) -> str:
        brief = self.production_dir / "production-brief.json"
        if brief.is_file():
            try:
                data = json.loads(brief.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            if data.get("title"):
                return str(data["title"])
        return self.production_dir.name

    def _require_known_stage(self, stage: str) -> None:
        try:
            is_stage_gated(stage, self.config_path)
        except ValueError as exc:
            raise LineProducerError(str(exc)) from exc

    def _check_amount(self, amount_usd: float):
        try:
            amount = as_money(amount_usd)
        except ValueError as exc:
            raise LineProducerError(str(exc)) from exc
        if amount < 0:
            raise LineProducerError("A spend cannot be negative.")
        return amount

    def _block_reason(
        self,
        stage: str,
        amount,
        *,
        books_money: bool,
        description: str,
        crew_gates: bool,
    ) -> Authorization | None:
        if crew_gates and stage in GATED_CREW:
            gate_block = self._crew_gate_block(stage)
            if gate_block is not None:
                return gate_block
        spent = as_money(self.run.data["cost_usd"])
        cap = as_money(self.run.data["budget_cap_usd"])
        if would_exceed_budget(amount, spent_usd=spent, cap_usd=cap):
            projected = money_number(spent + amount)
            return self._pause_spend(
                stage,
                amount,
                books_money,
                description,
                (
                    f"This ${money_number(amount):.2f} {stage} spend would put the film at "
                    f"${projected:.2f}, over the ${money_number(cap):.2f} cap. Nothing was charged."
                ),
            )
        allocations = self.record["stage_allocations"]
        if allocations["status"] == "approved":
            ceiling = as_money(allocations["split"].get(stage, 0))
            stage_spent = as_money(self.stage_spent(stage))
            if stage_spent + amount > ceiling:
                return self._pause_spend(
                    stage,
                    amount,
                    books_money,
                    description,
                    (
                        f"This ${money_number(amount):.2f} {stage} spend would put that stage at "
                        f"${money_number(stage_spent + amount):.2f}, over its ${money_number(ceiling):.2f} allocation. "
                        "The film cap was not the blocker. Nothing was charged."
                    ),
                )
        return None

    def _crew_gate_block(self, stage: str) -> Authorization | None:
        """The gates a call must already have open. Phase 2 drafts are the review, so their own gate stays shut."""
        if is_stage_gated("treatment", self.config_path) and not self.gate_is_open("treatment"):
            return self._pause_gate(
                "treatment",
                f"The treatment gate is still closed. The Director cannot call {stage} until Ron approves the treatment.",
            )
        if stage == "composer":
            if is_stage_gated("sound-designer", self.config_path) and not self.gate_is_open("sound-designer"):
                return self._pause_gate(
                    "sound-designer",
                    "The sound-designer gate is still closed. Ron has not approved that stage, so the composer was not called.",
                )
            if is_stage_gated(PREVIS_STAGE, self.config_path) and not self.gate_is_open(PREVIS_STAGE):
                return self._pause_gate(
                    PREVIS_STAGE,
                    (
                        "The previs gate is still closed. Previs is the phase 2 package: props, continuity, "
                        "camera, storyboards, and stunts. Ron has not reviewed it, so the composer was not called."
                    ),
                )
            if is_stage_gated(EDIT_STAGE, self.config_path) and not self.gate_is_open(EDIT_STAGE):
                return self._pause_gate(
                    EDIT_STAGE,
                    "The edit gate is still closed. Ron has not approved picture lock, so sound was not called.",
                )
            return None
        if stage in PHASE2_CREW or stage in DAILIES_CREW:
            if stage in DAILIES_CREW and is_stage_gated(PREVIS_STAGE, self.config_path) and not self.gate_is_open(PREVIS_STAGE):
                return self._pause_gate(
                    PREVIS_STAGE,
                    (
                        "The previs gate is still closed. Previs is the phase 2 package: props, continuity, "
                        "camera, storyboards, and stunts. Ron has not reviewed it, so dailies was not called."
                    ),
                )
            return None
        if stage in PICTURE_CREW and is_stage_gated(stage, self.config_path) and not self.gate_is_open(stage):
            return self._pause_gate(
                stage,
                f"The {stage} gate is still closed. Ron has not approved that stage, so this call was not made.",
            )
        if stage in PICTURE_CREW and is_stage_gated(PREVIS_STAGE, self.config_path) and not self.gate_is_open(PREVIS_STAGE):
            return self._pause_gate(
                PREVIS_STAGE,
                (
                    f"The previs gate is still closed. Previs is the phase 2 package: props, continuity, "
                    f"camera, storyboards, and stunts. Ron has not reviewed it, so {stage} was not called."
                ),
            )
        if stage == "editor" and is_stage_gated(DAILIES_STAGE, self.config_path) and not self.gate_is_open(DAILIES_STAGE):
            return self._pause_gate(
                DAILIES_STAGE,
                "The dailies gate is still closed. Ron has not approved the circled takes, so the editor was not called.",
            )
        if stage == "sound-designer" and is_stage_gated(EDIT_STAGE, self.config_path) and not self.gate_is_open(EDIT_STAGE):
            return self._pause_gate(
                EDIT_STAGE,
                "The edit gate is still closed. Ron has not approved picture lock, so sound was not called.",
            )
        return None

    def _pause_gate(self, stage: str, reason: str) -> Authorization:
        existing = self._pending_match("gate", stage, as_money(0))
        if existing:
            return Authorization(False, existing["reason"], existing["request_id"])
        request = self._new_request("gate", stage, as_money(0), reason, books_money=False, description=reason)
        self.run.set_stage(self.run.data["stage"], status="waiting-for-review")
        return Authorization(False, request["reason"] + f" Approval request {request['request_id']} is waiting for Ron.", request["request_id"])

    def _pause_spend(self, stage, amount, books_money: bool, description: str, reason: str) -> Authorization:
        existing = self._pending_match("extra-spend", stage, amount)
        if existing and existing["books_money"] == books_money:
            return Authorization(
                False,
                existing["reason"] + f" Approval request {existing['request_id']} is waiting for Ron.",
                existing["request_id"],
            )
        request = self._new_request(
            "extra-spend",
            stage,
            amount,
            reason,
            books_money=books_money,
            description=description,
        )
        self.run.data["status"] = "waiting-for-review"
        self.run.data["notes"] = reason
        self.run.save()
        return Authorization(
            False,
            reason + f" Approval request {request['request_id']} is waiting for Ron.",
            request["request_id"],
        )

    def _new_request(self, kind, stage, amount, reason, *, books_money: bool, description: str) -> dict:
        request = {
            "request_id": self._next_id("req", [item["request_id"] for item in self.record["requests"]]),
            "kind": kind,
            "stage": stage,
            "amount_usd": money_number(amount),
            "reason": reason,
            "description": description,
            "status": "pending",
            "books_money": books_money,
            "consumed": False,
            "created_at": _now(),
            "decided_at": None,
            "decided_by": None,
            "note": "",
        }
        self.record["requests"].append(request)
        self._save_record()
        self._write_request_file(request)
        return request

    def _write_request_file(self, request: dict) -> None:
        path = request_file(self.production_dir, self.run.data["run_id"], request["request_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")

    def _pending_match(self, kind: str, stage: str, amount) -> dict | None:
        for request in self.record["requests"]:
            if request["status"] != "pending" or request["kind"] != kind or request["stage"] != stage:
                continue
            if as_money(request["amount_usd"]) == as_money(amount):
                return request
        return None

    def _allowance(self, stage: str, amount) -> dict | None:
        for request in self.record["requests"]:
            if (
                request["status"] == "approved"
                and request["kind"] == "extra-spend"
                and not request["books_money"]
                and not request.get("consumed")
                and request["stage"] == stage
                and as_money(amount) <= as_money(request["amount_usd"])
            ):
                return request
        return None

    def _book(self, stage: str, amount, kind: str, description: str, request_id: str | None) -> None:
        entry = {
            "entry_id": self._next_id("spend", [item["entry_id"] for item in self.record["ledger"]]),
            "stage": stage,
            "amount_usd": money_number(amount),
            "kind": kind,
            "description": description,
            "recorded_at": _now(),
            "request_id": request_id,
        }
        self.record["ledger"].append(entry)
        self._save_record()
        try:
            self.run.add_cost(amount)
        except Exception:
            self.record["ledger"].pop()
            self._save_record()
            raise

    def _raise_allocation(self, stage: str) -> None:
        allocations = self.record["stage_allocations"]
        if allocations["status"] != "approved":
            return
        spent = as_money(self.stage_spent(stage))
        current = as_money(allocations["split"].get(stage, 0))
        if spent > current:
            allocations["split"][stage] = money_number(spent)

    def _lock_treatment(self, by: str, note: str, stage_split: dict | None) -> None:
        path = treatment_json_path(self.production_dir)
        if not path.is_file():
            raise LineProducerError("There is no treatment to approve yet. The Director has not written one.")
        treatment = load_treatment(self.production_dir)
        budget = treatment.get("constraints_and_budget") or {}
        split = stage_split if stage_split is not None else budget.get("stage_split") or {}
        if not isinstance(split, dict) or not split:
            raise LineProducerError(
                "The treatment has no stage split. Ron can send one with the approval, as stage names and dollar amounts."
            )
        known = set(load_gate_config(self.config_path)["gates"])
        unknown = sorted(set(split) - known)
        if unknown:
            raise LineProducerError(
                "The split names a stage that has no gate: "
                + ", ".join(unknown)
                + ". Known stages: "
                + ", ".join(sorted(known))
                + "."
            )
        try:
            amounts = {str(key): as_money(value) for key, value in split.items()}
        except ValueError as exc:
            raise LineProducerError(f"The stage split has a bad amount. {exc}") from exc
        if any(value < 0 for value in amounts.values()):
            raise LineProducerError("A stage allocation cannot be negative.")
        total = sum(amounts.values(), as_money(0))
        cap = as_money(self.run.data["budget_cap_usd"])
        if total > cap:
            raise LineProducerError(
                f"The stage split adds up to ${money_number(total):.2f}, "
                f"over the ${money_number(cap):.2f} film cap. Nothing was locked."
            )
        stored = {key: money_number(value) for key, value in amounts.items()}
        self.record["stage_allocations"] = {
            "status": "approved",
            "split": stored,
            "approved_at": _now(),
            "approved_by": by,
            "note": note.strip() or "Locked when Ron approved the treatment.",
        }
        treatment["status"] = "approved"
        treatment["version"] = "1.0.0"
        treatment["approval"] = {
            "state": "approved",
            "by": by,
            "at": _now(),
            "note": note.strip(),
        }
        if "constraints_and_budget" not in treatment:
            treatment["constraints_and_budget"] = {"budget_cap_usd": money_number(cap)}
        treatment["constraints_and_budget"]["stage_split"] = stored
        write_treatment_files(self.production_dir, treatment)

    def _close_gate_requests(self, stage: str, decision: str, by: str, note: str) -> None:
        for request in self.record["requests"]:
            if request["kind"] == "gate" and request["stage"] == stage and request["status"] == "pending":
                request["status"] = decision
                request["decided_at"] = _now()
                request["decided_by"] = by
                request["note"] = note.strip()
                self._write_request_file(request)

    def _find_request(self, request_id: str) -> dict:
        for request in self.record["requests"]:
            if request["request_id"] == request_id:
                return request
        known = ", ".join(item["request_id"] for item in self.record["requests"]) or "none"
        raise LineProducerError(f"No approval request named {request_id}. Requests on this run: {known}.")

    @staticmethod
    def _next_id(prefix: str, existing: list[str]) -> str:
        numbers = []
        for item in existing:
            match = re_suffix(item, prefix)
            if match is not None:
                numbers.append(match)
        nxt = (max(numbers) if numbers else 0) + 1
        return f"{prefix}-{nxt:03d}"


def _decision(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned in {"approved", "approve", "yes"}:
        return "approved"
    if cleaned in {"rejected", "reject", "no"}:
        return "rejected"
    raise LineProducerError("Decision must be approved or rejected.")


def _plain_status(status: str) -> str:
    return {
        "pending": "not started",
        "running": "in progress",
        "waiting-for-review": "waiting on Ron",
        "completed": "finished",
        "failed": "failed",
        "blocked": "paused",
    }.get(status, status)


def _schedule_word(status: str) -> str:
    if status == "waiting-for-review":
        return "waiting-for-review"
    if status == "running":
        return "in-progress"
    if status == "completed":
        return "complete"
    if status == "pending":
        return "pending"
    return "in-progress"


def re_suffix(item: str, prefix: str) -> int | None:
    head, sep, tail = item.partition("-")
    if head == prefix and sep and tail.isdigit():
        return int(tail)
    return None


def cap_from_config(config_path: str | Path | None = None) -> float:
    return budget_cap_usd(config_path)
