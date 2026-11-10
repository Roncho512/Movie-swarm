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

from movie_swarm.line_producer import Authorization, LineProducer
from movie_swarm.paths import repo_root
from movie_swarm.roles import GATED_CREW


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
        "stage": "production",
        "commands": {
            "estimate": True,
            "dry-run": True,
        },
    },
    "sound-designer": {
        "stage": "sound-designer",
        "commands": {"dry-run": True},
    },
    "editor": {
        "stage": "editor",
        "commands": {"dry-run": False},
    },
    "qa": {
        "stage": "qa",
        "commands": {"dry-run": False},
    },
    "fix-loop": {
        "stage": "fix-loop",
        "commands": {"dry-run": False},
    },
}


def dispatch_call(
    producer: LineProducer,
    call: CrewCall,
    handler=None,
) -> DispatchResult:
    """Check the gate and the budget, then run ``handler`` or the default crew command."""
    if call.agent not in _COMMANDS:
        known = ", ".join(GATED_CREW)
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
    try:
        auth: Authorization = producer.authorize_crew(
            spec["stage"],
            call.estimated_cost_usd,
            description,
        )
    except Exception as exc:
        return DispatchResult(status="refused", message=str(exc))
    if not auth.allowed:
        return DispatchResult(status="paused", message=auth.message, request_id=auth.request_id)

    runner = handler or default_handler
    try:
        output = runner(call)
    except Exception as exc:
        return DispatchResult(
            status="failed",
            message=f"The gate allowed the call, but {call.agent} failed. {exc}",
        )
    producer.note_dry_run(
        spec["stage"],
        call.estimated_cost_usd,
        description,
        allowance_request_id=auth.allowance_request_id,
    )
    return DispatchResult(
        status="ran",
        message=auth.message,
        output=output,
    )


def default_handler(call: CrewCall) -> str:
    """Run a free local command, or name the command and stop before the cut is touched."""
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
