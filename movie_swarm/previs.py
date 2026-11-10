"""Run one phase 2 command and write its files.

The Director calls this after the Line Producer has allowed the call.
"""

from __future__ import annotations

from movie_swarm.camera import build_package
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.stunts import build_breakdown


def run_previs(call) -> str:
    """Write the files for one phase 2 command. Return a short status line."""
    production = call.production_dir
    if not production:
        raise ValueError("A phase 2 call needs a production folder.")
    llm = getattr(call, "llm", None)
    if call.agent == "prop-master" and call.command == "lock":
        document = lock_props(production, llm=llm)
        count = len(document.get("props") or [])
        return f"Locked {count} hero prop(s). File: props/hero-props.json"
    if call.agent == "script-supervisor" and call.command == "check":
        document = check_continuity(production, llm=llm)
        return (
            f"Continuity verdict: {document['verdict']}. "
            f"{len(document['findings'])} finding(s). File: continuity/continuity-check.json"
        )
    if call.agent == "cinematographer" and call.command == "package":
        document = build_package(production, llm=llm)
        return f"Camera package: {document['look_name']}. File: camera/camera-package.json"
    if call.agent == "cinematographer" and call.command == "boards":
        document = build_boards(production, llm=llm, image_client=getattr(call, "image_client", None))
        return (
            f"Storyboard: {len(document['frames'])} board(s). "
            f"Images: {document['image_generation']}. File: storyboard/storyboard.json"
        )
    if call.agent == "stunt-coordinator" and call.command == "breakdown":
        document = build_breakdown(production, llm=llm)
        return f"Action breakdown: {len(document['beats'])} beat(s). File: stunts/action-breakdown.json"
    raise ValueError(f"{call.agent} has no phase 2 command named {call.command}.")
