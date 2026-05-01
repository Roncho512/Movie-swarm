"""
pipeline.py — The Fix Loop agent's coordination pipeline.

Reads QA reports, generates fix plans routed to the correct agent,
modifies generation prompts based on QA findings, tracks fix progress,
and coordinates the reassembly → re-review cycle.

Usage:
    from src.pipeline import FixLoopPipeline
    fixer = FixLoopPipeline("productions/the-last-marker")
    plan = fixer.generate_fix_plan()
    # ... execute fixes (manual or automated) ...
    fixer.mark_fix_complete("FIX-001", new_clip_path="clips/selected/s01-sh02.mp4")
    fixer.finalize_iteration()
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("fix-loop.pipeline")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class FixTask:
    """A single fix task routed to an agent."""
    task_id: str
    finding_id: str
    severity: str
    assigned_to: str            # "production", "editor", "sound_designer", etc.
    shots_affected: list[str]
    action: str                 # "regenerate", "re-cut", "replace_audio", "update_ref"
    description: str            # From the QA finding
    recommendation: str         # From the QA finding
    original_prompt: str = ""
    modified_prompt: str = ""
    prompt_modifications: list[str] = field(default_factory=list)
    reference_assets: list[str] = field(default_factory=list)
    status: str = "pending"     # "pending", "in_progress", "complete", "failed", "skipped"
    attempts: int = 0
    max_attempts: int = 3
    result_notes: str = ""
    new_clip_path: str = ""


@dataclass
class FixPlan:
    """Complete fix plan for one QA iteration."""
    production_id: str
    qa_report_version: int
    iteration: int
    created_at: str
    fix_tasks: list[FixTask]
    summary: dict[str, Any] = field(default_factory=dict)
    overall_status: str = "pending"  # "pending", "in_progress", "complete"


@dataclass
class FixLog:
    """Execution log for one fix iteration."""
    production_id: str
    iteration: int
    started_at: str
    completed_at: str = ""
    tasks_attempted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    clips_regenerated: list[str] = field(default_factory=list)
    audio_replaced: list[str] = field(default_factory=list)
    reassembly_triggered: bool = False
    qa_rerun_triggered: bool = False
    cumulative_cost: float = 0.0


# ---------------------------------------------------------------------------
# Prompt modification
# ---------------------------------------------------------------------------


def modify_prompt_for_finding(
    original_prompt: str,
    finding: dict,
    shot_info: dict,
) -> tuple[str, list[str]]:
    """
    Modify a generation prompt based on a QA finding.

    Returns (modified_prompt, list_of_modifications).

    Strategy:
      - Lighting issues: inject explicit lighting direction
      - Continuity issues: inject matching constraints from adjacent shots
      - Environment issues: inject explicit environment anchors
      - Technical issues: flag for parameter change (not prompt change)
    """
    modifications = []
    prompt = original_prompt

    category = finding.get("category", "")
    description = finding.get("description", "").lower()
    recommendation = finding.get("recommendation", "")

    # -------------------------------------------------------------------
    # Lighting / temporal continuity
    # -------------------------------------------------------------------
    if category in ("temporal_continuity", "style_adherence") or \
       any(kw in description for kw in ["lighting", "light", "golden hour",
                                         "sunset", "shadow", "sun angle",
                                         "color temperature"]):
        # Extract lighting cues from the recommendation
        lighting_fix = _extract_lighting_direction(recommendation, description)
        if lighting_fix:
            prompt = _inject_into_prompt(prompt, lighting_fix, section="lighting")
            modifications.append(f"Added lighting direction: {lighting_fix}")

    # -------------------------------------------------------------------
    # Visual continuity (character, vehicle, props)
    # -------------------------------------------------------------------
    if category == "visual_continuity" or \
       any(kw in description for kw in ["goggles", "costume", "wardrobe",
                                         "clothing", "appearance", "face",
                                         "hair", "helmet", "jacket"]):
        continuity_fix = _extract_continuity_constraint(recommendation, description)
        if continuity_fix:
            prompt = _inject_into_prompt(prompt, continuity_fix, section="subject")
            modifications.append(f"Added continuity constraint: {continuity_fix}")

    # -------------------------------------------------------------------
    # Environment / spatial continuity
    # -------------------------------------------------------------------
    if category == "spatial_continuity" or \
       any(kw in description for kw in ["desert", "landscape", "environment",
                                         "mountain", "terrain", "vegetation",
                                         "cactus", "rock"]):
        env_fix = _extract_environment_anchor(recommendation, description)
        if env_fix:
            prompt = _inject_into_prompt(prompt, env_fix, section="environment")
            modifications.append(f"Added environment anchor: {env_fix}")

    # -------------------------------------------------------------------
    # Technical quality
    # -------------------------------------------------------------------
    if category == "technical_quality":
        modifications.append(f"Technical fix needed: {recommendation}")
        # Technical fixes are parameter changes, not prompt changes.
        # Flag but don't modify the prompt text.

    # If no specific modifications were made, append the raw recommendation
    if not modifications and recommendation:
        prompt = prompt.rstrip(". ") + ". " + recommendation
        modifications.append(f"Appended raw recommendation: {recommendation}")

    return prompt, modifications


def _extract_lighting_direction(recommendation: str, description: str) -> str:
    """Extract or generate a lighting direction string from QA feedback."""
    combined = f"{recommendation} {description}".lower()

    parts = []
    if any(kw in combined for kw in ["golden", "sunset", "golden hour", "warm"]):
        parts.append("warm golden sunset light")
    if any(kw in combined for kw in ["low sun", "low angle"]):
        parts.append("low sun angle")
    if any(kw in combined for kw in ["amber", "long shadow"]):
        parts.append("long amber shadows on the ground")
    if any(kw in combined for kw in ["camera-left", "left"]):
        parts.append("sun from camera-left")
    elif any(kw in combined for kw in ["camera-right", "right"]):
        parts.append("sun from camera-right")

    if not parts:
        # Fallback: use the recommendation as-is if it mentions lighting
        if any(kw in combined for kw in ["light", "lighting"]):
            return recommendation
        return ""

    return ", ".join(parts)


def _extract_continuity_constraint(recommendation: str, description: str) -> str:
    """Extract a continuity matching constraint from QA feedback."""
    # Look for specific prop/costume mentions in the finding
    combined = f"{recommendation} {description}"

    # Common continuity items
    for item in ["goggles over eyes", "goggles pushed up", "goggles on forehead",
                 "jacket open", "jacket closed", "sleeves rolled",
                 "helmet on", "helmet off"]:
        if item in combined.lower():
            return f"matching previous shot: {item}"

    # Fallback: use the recommendation
    if recommendation:
        return f"continuity match: {recommendation}"
    return ""


def _extract_environment_anchor(recommendation: str, description: str) -> str:
    """Extract an environment anchor from QA feedback."""
    combined = f"{recommendation} {description}".lower()

    if "baja" in combined or "sonoran" in combined:
        return "Baja California desert, Sonoran landscape with saguaro cactus and red rock formations"
    if "mojave" in combined:
        return "Mojave desert with Joshua trees and scrubland"

    if recommendation:
        return recommendation
    return ""


def _inject_into_prompt(prompt: str, injection: str, section: str = "") -> str:
    """
    Inject text into a generation prompt.

    Tries to place it in a logical location based on the section hint.
    Falls back to appending at the end.
    """
    # Simple strategy: append with a period separator
    # A more sophisticated version could parse the prompt structure
    # (style anchor, shot type, subject, environment, lighting, action)
    # and insert into the right section. For now, append.
    clean_prompt = prompt.rstrip(". ")
    return f"{clean_prompt}. {injection}"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class FixLoopPipeline:
    """
    Coordinates the QA → fix → reassemble → re-review loop.

    Usage:
        fixer = FixLoopPipeline("productions/the-last-marker")

        # Step 1: Generate fix plan from latest QA report
        plan = fixer.generate_fix_plan()

        # Step 2: Execute fixes (manual in MVP)
        # ... regenerate clips in Flow/Seedance ...
        # ... place new clips in clips/selected/ ...

        # Step 3: Mark fixes as complete
        fixer.mark_fix_complete("FIX-001", new_clip_path="clips/selected/s01-sh02.mp4")
        fixer.mark_fix_complete("FIX-002", new_clip_path="clips/selected/s01-sh05.mp4")

        # Step 4: Finalize iteration (write logs, trigger reassembly hint)
        fixer.finalize_iteration()

        # Step 5: Re-run editor, then QA, then check again
    """

    MAX_ITERATIONS = 3
    SEVERITY_FILTER = ("critical", "major")   # What gets fixed automatically

    def __init__(self, production_dir: str | Path):
        self.prod_dir = Path(production_dir)
        self.fix_dir = self.prod_dir / "fix-loop"
        self.fix_dir.mkdir(parents=True, exist_ok=True)

        self.plan: Optional[FixPlan] = None
        self.log: Optional[FixLog] = None

    def _current_iteration(self) -> int:
        """Determine the current iteration number from existing fix plans."""
        existing = sorted(self.fix_dir.glob("fix-plan-v*.json"))
        if not existing:
            return 1
        # Extract version numbers
        versions = []
        for p in existing:
            m = re.search(r"v(\d+)", p.name)
            if m:
                versions.append(int(m.group(1)))
        return max(versions) + 1 if versions else 1

    def _latest_qa_report(self) -> tuple[dict, int]:
        """Load the latest QA report and its version number."""
        qa_dir = self.prod_dir / "qa-reports"
        reports = sorted(qa_dir.glob("qa-report-v*.json"))
        if not reports:
            raise FileNotFoundError(f"No QA reports found in {qa_dir}")

        latest = reports[-1]
        m = re.search(r"v(\d+)", latest.name)
        version = int(m.group(1)) if m else 1

        data = json.loads(latest.read_text())
        return data, version

    def _load_shot_list(self) -> dict:
        """Load the shot list for original prompts and references."""
        shot_list_path = self.prod_dir / "shot-lists" / "shot-list.json"
        if not shot_list_path.exists():
            logger.warning("No shot list found at %s", shot_list_path)
            return {"shots": []}
        return json.loads(shot_list_path.read_text())

    def _shot_by_id(self, shot_list: dict, shot_id: str) -> dict:
        """Look up a shot in the shot list by ID."""
        for s in shot_list.get("shots", []):
            if s.get("shot_id") == shot_id:
                return s
        return {}

    def generate_fix_plan(
        self,
        include_minor: bool = False,
    ) -> FixPlan:
        """
        Read the latest QA report and generate a fix plan.

        Args:
            include_minor: If True, include minor severity findings.
                           Default is critical + major only.
        """
        qa_report, qa_version = self._latest_qa_report()
        shot_list = self._load_shot_list()
        iteration = self._current_iteration()

        # Check iteration limit
        if iteration > self.MAX_ITERATIONS:
            logger.warning(
                "Max iterations (%d) reached. Escalating to human review.",
                self.MAX_ITERATIONS,
            )
            # Still generate the plan for reference, but flag it
            pass

        # Check if already approved
        verdict = qa_report.get("overall_verdict", "")
        if verdict == "approved":
            logger.info("QA verdict is APPROVED. No fixes needed.")
            self.plan = FixPlan(
                production_id=self.prod_dir.name,
                qa_report_version=qa_version,
                iteration=iteration,
                created_at=datetime.now(timezone.utc).isoformat(),
                fix_tasks=[],
                summary={"total_tasks": 0, "verdict": "approved"},
                overall_status="complete",
            )
            self._write_fix_plan()
            return self.plan

        # Filter findings by severity
        severity_filter = set(self.SEVERITY_FILTER)
        if include_minor:
            severity_filter.add("minor")

        findings = [
            f for f in qa_report.get("findings", [])
            if f.get("severity", "").lower() in severity_filter
        ]

        if not findings:
            logger.info("No actionable findings (severity filter: %s)", severity_filter)
            self.plan = FixPlan(
                production_id=self.prod_dir.name,
                qa_report_version=qa_version,
                iteration=iteration,
                created_at=datetime.now(timezone.utc).isoformat(),
                fix_tasks=[],
                summary={"total_tasks": 0, "verdict": "no_actionable_findings"},
                overall_status="complete",
            )
            self._write_fix_plan()
            return self.plan

        # Generate fix tasks
        fix_tasks = []
        for i, finding in enumerate(findings, 1):
            task_id = f"FIX-{iteration:02d}-{i:03d}"
            assigned_to = finding.get("assigned_to", "production")
            shots = finding.get("shots_affected", [])

            # Determine action type based on agent assignment
            action_map = {
                "production": "regenerate",
                "editor": "re-cut",
                "sound_designer": "replace_audio",
                "art_director": "update_ref",
                "cinematographer": "revise_shot_plan",
            }
            action = action_map.get(assigned_to, "regenerate")

            # For production fixes, modify the prompt
            original_prompt = ""
            modified_prompt = ""
            prompt_mods = []
            ref_assets = []

            if assigned_to == "production" and shots:
                # Get the original prompt for the primary affected shot
                primary_shot = shots[0]
                shot_info = self._shot_by_id(shot_list, primary_shot)
                original_prompt = shot_info.get("generation_prompt", "")
                ref_assets = shot_info.get("reference_assets", [])

                if original_prompt:
                    modified_prompt, prompt_mods = modify_prompt_for_finding(
                        original_prompt=original_prompt,
                        finding=finding,
                        shot_info=shot_info,
                    )

            fix_tasks.append(FixTask(
                task_id=task_id,
                finding_id=finding.get("finding_id", f"F{i:03d}"),
                severity=finding.get("severity", "major"),
                assigned_to=assigned_to,
                shots_affected=shots,
                action=action,
                description=finding.get("description", ""),
                recommendation=finding.get("recommendation", ""),
                original_prompt=original_prompt,
                modified_prompt=modified_prompt,
                prompt_modifications=prompt_mods,
                reference_assets=ref_assets,
            ))

        # Build summary
        by_agent: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for t in fix_tasks:
            by_agent[t.assigned_to] = by_agent.get(t.assigned_to, 0) + 1
            by_severity[t.severity] = by_severity.get(t.severity, 0) + 1

        self.plan = FixPlan(
            production_id=self.prod_dir.name,
            qa_report_version=qa_version,
            iteration=iteration,
            created_at=datetime.now(timezone.utc).isoformat(),
            fix_tasks=fix_tasks,
            summary={
                "total_tasks": len(fix_tasks),
                "by_agent": by_agent,
                "by_severity": by_severity,
                "max_iterations_reached": iteration > self.MAX_ITERATIONS,
            },
        )

        self._write_fix_plan()

        # Initialize the fix log
        self.log = FixLog(
            production_id=self.prod_dir.name,
            iteration=iteration,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        return self.plan

    def mark_fix_complete(
        self,
        task_id: str,
        new_clip_path: str = "",
        notes: str = "",
    ):
        """
        Mark a fix task as complete after the human (or automated agent)
        has executed the fix.

        Args:
            task_id: The FIX-XX-XXX identifier
            new_clip_path: Path to the new clip (for production fixes)
            notes: Any notes about the fix execution
        """
        if not self.plan:
            raise RuntimeError("No fix plan loaded. Call generate_fix_plan() first.")

        for task in self.plan.fix_tasks:
            if task.task_id == task_id:
                task.status = "complete"
                task.attempts += 1
                task.new_clip_path = new_clip_path
                task.result_notes = notes
                logger.info("Marked %s as complete: %s", task_id, notes or new_clip_path)

                # Update the log
                if self.log:
                    self.log.tasks_completed += 1
                    if task.assigned_to == "production" and new_clip_path:
                        self.log.clips_regenerated.append(new_clip_path)
                    elif task.assigned_to == "sound_designer":
                        self.log.audio_replaced.append(task_id)
                return

        logger.warning("Task %s not found in fix plan", task_id)

    def mark_fix_failed(self, task_id: str, notes: str = ""):
        """Mark a fix task as failed after max attempts or other failure."""
        if not self.plan:
            raise RuntimeError("No fix plan loaded.")

        for task in self.plan.fix_tasks:
            if task.task_id == task_id:
                task.status = "failed"
                task.attempts += 1
                task.result_notes = notes
                logger.warning("Marked %s as failed: %s", task_id, notes)
                if self.log:
                    self.log.tasks_failed += 1
                return

        logger.warning("Task %s not found in fix plan", task_id)

    def mark_fix_skipped(self, task_id: str, notes: str = ""):
        """Skip a fix task (e.g., minor finding deferred)."""
        if not self.plan:
            raise RuntimeError("No fix plan loaded.")

        for task in self.plan.fix_tasks:
            if task.task_id == task_id:
                task.status = "skipped"
                task.result_notes = notes
                logger.info("Skipped %s: %s", task_id, notes)
                if self.log:
                    self.log.tasks_skipped += 1
                return

    def get_pending_tasks(self) -> list[FixTask]:
        """Return all tasks still pending execution."""
        if not self.plan:
            return []
        return [t for t in self.plan.fix_tasks if t.status == "pending"]

    def get_production_tasks(self) -> list[FixTask]:
        """Return only production (regeneration) tasks — the ones you need to
        execute manually in Flow/Seedance."""
        if not self.plan:
            return []
        return [t for t in self.plan.fix_tasks
                if t.assigned_to == "production" and t.status == "pending"]

    def print_fix_instructions(self):
        """Print human-readable fix instructions for manual execution."""
        if not self.plan:
            print("No fix plan loaded.")
            return

        prod_tasks = self.get_production_tasks()
        if not prod_tasks:
            print("No production tasks pending.")
            return

        print(f"\n{'='*60}")
        print(f"FIX PLAN — Iteration {self.plan.iteration}")
        print(f"{'='*60}")

        for task in prod_tasks:
            print(f"\n--- {task.task_id} [{task.severity.upper()}] ---")
            print(f"Shot(s): {', '.join(task.shots_affected)}")
            print(f"Issue: {task.description}")
            print(f"Fix: {task.recommendation}")
            if task.modified_prompt:
                print(f"\nModified prompt:")
                print(f"  {task.modified_prompt}")
            if task.prompt_modifications:
                print(f"\nChanges from original:")
                for mod in task.prompt_modifications:
                    print(f"  - {mod}")
            if task.reference_assets:
                print(f"\nReference assets to include:")
                for ref in task.reference_assets:
                    print(f"  - {ref}")
            print(f"\nAfter regenerating, run:")
            print(f"  python3 -m src.cli complete {task.task_id} --clip <path_to_new_clip>")

    def finalize_iteration(self):
        """
        Finalize the current fix iteration.
        Writes the fix log and updated fix plan.
        """
        if not self.plan:
            raise RuntimeError("No fix plan loaded.")

        # Update plan status
        pending = [t for t in self.plan.fix_tasks if t.status == "pending"]
        failed = [t for t in self.plan.fix_tasks if t.status == "failed"]

        if not pending and not failed:
            self.plan.overall_status = "complete"
        elif pending:
            self.plan.overall_status = "in_progress"
        else:
            self.plan.overall_status = "complete"  # All attempted, some failed

        # Write updated plan
        self._write_fix_plan()

        # Finalize log
        if self.log:
            self.log.completed_at = datetime.now(timezone.utc).isoformat()
            self.log.tasks_attempted = (
                self.log.tasks_completed +
                self.log.tasks_failed +
                self.log.tasks_skipped
            )
            self._write_fix_log()

        # Print next steps
        completed = [t for t in self.plan.fix_tasks if t.status == "complete"]
        if completed:
            print(f"\n{'='*60}")
            print(f"ITERATION {self.plan.iteration} COMPLETE")
            print(f"{'='*60}")
            print(f"  Tasks completed: {len(completed)}")
            print(f"  Tasks failed: {len(failed)}")
            print(f"  Tasks skipped: {len([t for t in self.plan.fix_tasks if t.status == 'skipped'])}")

            if any(t.assigned_to == "production" for t in completed):
                print(f"\nNext steps:")
                print(f"  1. Re-run the Editor to reassemble:")
                print(f"     cd ../07-editor")
                print(f"     python3 -m src.cli assemble ../../productions/{self.plan.production_id}")
                print(f"  2. Re-run QA on the new cut:")
                print(f"     cd ../08-qa")
                print(f"     python3 -m src.cli review ../../productions/{self.plan.production_id}")
                print(f"  3. Check the new QA verdict. If REVISE, run fix-loop again.")

    def _write_fix_plan(self):
        """Write the fix plan to disk."""
        if not self.plan:
            return
        out = self.fix_dir / f"fix-plan-v{self.plan.iteration}.json"
        out.write_text(json.dumps(asdict(self.plan), indent=2))
        logger.info("Wrote fix plan → %s", out)

    def _write_fix_log(self):
        """Write the fix log to disk."""
        if not self.log:
            return
        out = self.fix_dir / f"fix-log-v{self.log.iteration}.json"
        out.write_text(json.dumps(asdict(self.log), indent=2))
        logger.info("Wrote fix log → %s", out)
