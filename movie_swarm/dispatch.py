"""The Director calls a coded crew agent only through the Line Producer.

The call is checked against the treatment gate, the stage gate, and the
budget before anything runs. This phase runs cost estimates and dry runs.
It does not spend generation money.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from movie_swarm.color_mix import run_color_mix
from movie_swarm.dailies import run_dailies
from movie_swarm.edit import run_edit
from movie_swarm.generation import run_picture
from movie_swarm.line_producer import Authorization, LineProducer
from movie_swarm.paths import repo_root
from movie_swarm.previs import run_previs
from movie_swarm.roles import (
    CALLABLE,
    COLOR_MIX_BILLING,
    DAILIES_BILLING,
    PHASE2_BILLING,
    PHASE2_CREW,
    SOUND_BILLING,
)
from movie_swarm.sound import run_sound


class DispatchError(Exception):
    """The call is not a known crew command."""


@dataclass
class CrewCall:
    """A typed request from the Director to one existing crew agent."""

    agent: str
    command: str
    estimated_cost_usd: float
    note: str = ""
    shot_list: str | None = None
    output_dir: str | None = None
    production_dir: str | None = None
    llm: object | None = None
    image_client: object | None = None
    client: object | None = None
    takes: str | None = None


@dataclass
class DispatchResult:
    status: str  # ran, paused, refused, failed
    message: str
    output: str = ""
    request_id: str | None = None


# Commands that exist on the agents today. ``executes`` means this phase
# actually runs the command. The others are routed and named, and not run,
# because they would read or write the cut.
_COMMANDS = {
    "production": {
        "commands": {"estimate": True, "dry-run": True, "plan": True, "generate": True},
    },
    "sound-designer": {
        "commands": {"dry-run": True, "spot": True, "generate": True},
    },
    "composer": {
        "commands": {"spot": True, "generate": True},
    },
    "editor": {
        "commands": {"dry-run": False, "assemble": True},
    },
    "qa": {
        "commands": {"dry-run": False},
    },
    "fix-loop": {
        "commands": {"dry-run": False},
    },
    "prop-master": {
        "commands": {"lock": True},
    },
    "script-supervisor": {
        "commands": {"check": True},
    },
    "cinematographer": {
        "commands": {"package": True, "boards": True},
    },
    "stunt-coordinator": {
        "commands": {"breakdown": True},
    },
    "dailies": {
        "commands": {"review": True},
    },
    "colorist": {
        "commands": {"grade": True},
    },
    "mixer": {
        "commands": {"mix": True},
    },
}

_PHASE2_OUTPUTS = {
    "prop-master": (
        ("hero-props", "props/hero-props.json", "hero-props.schema.json"),
        ("hero-props-notes", "props/hero-props.md", None),
    ),
    "script-supervisor": (
        ("continuity-check", "continuity/continuity-check.json", "continuity-check.schema.json"),
        ("continuity-notes", "continuity/continuity-check.md", None),
    ),
    "cinematographer": (
        ("camera-package", "camera/camera-package.json", "camera-package.schema.json"),
        ("camera-notes", "camera/camera-package.md", None),
        ("storyboard", "storyboard/storyboard.json", "storyboard.schema.json"),
        ("storyboard-notes", "storyboard/storyboard.md", None),
        ("storyboard-shot-list", "storyboard/shot-list.json", "shot-list.schema.json"),
    ),
    "stunt-coordinator": (
        ("action-breakdown", "stunts/action-breakdown.json", "action-breakdown.schema.json"),
        ("action-notes", "stunts/action-breakdown.md", None),
    ),
}


def dispatch_call(
    producer: LineProducer,
    call: CrewCall,
    handler=None,
) -> DispatchResult:
    """Check the gate and the budget, then run ``handler`` or the default crew command."""
    if call.agent not in _COMMANDS:
        known = ", ".join(CALLABLE)
        return DispatchResult(
            status="refused",
            message=f"The Director cannot call '{call.agent}'. Crew calls go to: {known}.",
        )
    spec = _COMMANDS[call.agent]
    if call.command not in spec["commands"]:
        known = ", ".join(sorted(spec["commands"]))
        return DispatchResult(
            status="refused",
            message=f"{call.agent} has no '{call.command}' command here. Commands: {known}.",
        )
    description = call.note or f"{call.agent} {call.command}"
    billing = (
        PHASE2_BILLING.get(call.agent)
        or DAILIES_BILLING.get(call.agent)
        or SOUND_BILLING.get(call.agent)
        or COLOR_MIX_BILLING.get(call.agent)
        or call.agent
    )
    try:
        auth: Authorization = producer.authorize_crew(
            call.agent,
            call.estimated_cost_usd,
            description,
        )
    except Exception as exc:
        return DispatchResult(status="refused", message=str(exc))
    if not auth.allowed:
        return DispatchResult(status="paused", message=auth.message, request_id=auth.request_id)
    if call.command == "generate" and call.agent in {"production", "sound-designer", "composer"}:
        block = producer.paid_generation_block()
        if block is not None:
            return DispatchResult(status="paused", message=block.message, request_id=block.request_id)

    if handler is None and call.agent == "dailies" and call.command == "review":
        runner = lambda current: run_dailies(producer, current)
    elif handler is None and call.agent == "editor" and call.command == "assemble":
        runner = lambda current: run_edit(producer, current)
    elif handler is None and call.agent == "production" and call.command in {"plan", "generate"}:
        runner = lambda current: run_picture(producer, current)
    elif handler is None and call.agent in {"sound-designer", "composer"} and call.command in {"spot", "generate"}:
        runner = lambda current: run_sound(producer, current)
    elif handler is None and call.agent == "colorist" and call.command == "grade":
        runner = lambda current: run_color_mix(producer, current)
    elif handler is None and call.agent == "mixer" and call.command == "mix":
        runner = lambda current: run_color_mix(producer, current)
    else:
        runner = handler or default_handler
    try:
        output = runner(call)
    except Exception as exc:
        return DispatchResult(
            status="failed",
            message=f"The gate allowed the call, but {call.agent} failed. {exc}",
        )
    producer.note_dry_run(
        billing,
        call.estimated_cost_usd,
        description,
        allowance_request_id=auth.allowance_request_id,
    )
    if call.agent in PHASE2_CREW:
        _register_phase2(producer, call.agent)
    return DispatchResult(
        status="ran",
        message=auth.message,
        output=output,
    )


def default_handler(call: CrewCall) -> str:
    """Run a free local command, or name the command and stop before the cut is touched."""
    if call.agent in PHASE2_CREW:
        return run_previs(call)
    spec = _COMMANDS[call.agent]
    executes = spec["commands"][call.command]
    argv, cwd = _argv(call)
    if not executes:
        shown = " ".join(argv)
        return (
            f"Routed to {call.agent}. This phase does not run that command, "
            f"because it would read or write the picture. Command: {shown}"
        )
    completed = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise DispatchError(output.strip() or f"{call.agent} exited {completed.returncode}.")
    return output.strip()


def _register_phase2(producer: LineProducer, agent: str) -> None:
    """Remember the files this call wrote, and leave them waiting on Ron."""
    production = producer.production_dir
    for name, relative, schema in _PHASE2_OUTPUTS.get(agent, ()):
        if (production / relative).is_file():
            producer.ensure_artifact(name, relative, schema)
    if producer.gate_decision("previs") == "approved":
        producer.run.data["notes"] = (
            "Phase 2 files were written again after Ron approved the previs gate. "
            "The approval still stands until Ron rejects it."
        )
        producer.run.save()
        return
    producer.set_stage("previs", "waiting-for-review")
    producer.run.data["notes"] = (
        "The phase 2 package is waiting on Ron. "
        "Previs means the prop lock, the continuity check, the camera package, "
        "the storyboard, and the action breakdown. The Director did not approve them."
    )
    producer.run.save()
    _ensure_credits(producer)


def _ensure_credits(producer: LineProducer) -> None:
    have = {item["role"] for item in producer.record["credits"]}
    added = False
    for role, name in (
        ("Script Supervisor", "Script Supervisor"),
        ("Prop Master", "Prop Master"),
        ("Cinematographer", "Cinematographer"),
        ("Stunt and Action Coordinator", "Stunt and Action Coordinator"),
    ):
        if role not in have:
            producer.record["credits"].append({"role": role, "name": name})
            added = True
    if added:
        producer._save_record()


def _argv(call: CrewCall) -> tuple[list[str], Path]:
    root = repo_root()
    if call.agent == "production" and call.command == "estimate":
        if not call.shot_list:
            raise DispatchError("A production estimate needs a shot list.")
        return (
            [sys.executable, "-m", "src.cli", "estimate", str(Path(call.shot_list).resolve())],
            root / "agents" / "05-production",
        )
    if call.agent == "production" and call.command == "dry-run":
        if not call.shot_list or not call.output_dir:
            raise DispatchError("A production dry run needs a shot list and an output folder.")
        return (
            [
                sys.executable,
                "-m",
                "src.cli",
                "run",
                str(Path(call.shot_list).resolve()),
                str(Path(call.output_dir).resolve()),
                "--dry-run",
                "--pass",
                "preview",
            ],
            root / "agents" / "05-production",
        )
    if call.agent == "sound-designer":
        if not call.shot_list or not call.output_dir:
            raise DispatchError("A sound dry run needs a shot list and an output folder.")
        return (
            [
                sys.executable,
                "-m",
                "src.cli",
                "sfx",
                str(Path(call.shot_list).resolve()),
                str(Path(call.output_dir).resolve()),
                "--dry-run",
            ],
            root / "agents" / "06-sound-designer",
        )
    production = call.production_dir or ""
    folder = {
        "editor": "07-editor",
        "qa": "08-qa",
        "fix-loop": "09-fix-loop",
    }[call.agent]
    command = {"editor": "probe", "qa": "frames", "fix-loop": "show"}[call.agent]
    return (
        [sys.executable, "-m", "src.cli", command, production],
        root / "agents" / folder,
    )
