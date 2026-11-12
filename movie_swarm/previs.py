"""Run one phase 2 command and write its files.

The Director calls this after the Line Producer has allowed the call.
"""

from __future__ import annotations

from movie_swarm.assistant_director import build_schedule
from movie_swarm.camera import build_package
from movie_swarm.costume import lock_costumes
from movie_swarm.gaffer import build_lighting_plan
from movie_swarm.grip import build_grip_plan
from movie_swarm.makeup import lock_makeup
from movie_swarm.prop_master import lock_props
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.stunts import build_breakdown
from movie_swarm.graphics import build_graphics, write_guide, write_research
from movie_swarm.vfx import build_breakdown as build_vfx
from movie_swarm.vfx import review_vfx


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
    if call.agent == "costume-designer" and call.command == "lock":
        document = lock_costumes(production, llm=llm)
        return f"Locked wardrobe for {len(document['characters'])} character(s). File: wardrobe/costume-lock.json"
    if call.agent == "makeup-hair" and call.command == "lock":
        document = lock_makeup(production, llm=llm)
        return f"Locked makeup for {len(document['characters'])} character(s). File: makeup/makeup-lock.json"
    if call.agent == "gaffer" and call.command == "plan":
        document = build_lighting_plan(production, llm=llm)
        return f"Lighting plan: {len(document['scenes'])} scene(s). File: lighting/lighting-plan.json"
    if call.agent == "key-grip" and call.command == "plan":
        document = build_grip_plan(production, llm=llm)
        return f"Grip plan: {len(document['shots'])} shot(s). File: grip/grip-plan.json"
    if call.agent == "assistant-director" and call.command == "schedule":
        document = build_schedule(production, llm=llm)
        return f"Shooting schedule: {document['shot_count']} shot(s). File: schedule/shooting-schedule.json"
    if call.agent == "vfx-supervisor" and call.command == "breakdown":
        document = build_vfx(production, llm=llm)
        return f"VFX breakdown: {len(document['shots'])} shot(s). File: vfx/vfx-breakdown.json"
    if call.agent == "vfx-supervisor" and call.command == "review":
        document = review_vfx(production, llm=llm)
        return f"VFX review: {document['verdict']}. File: vfx/vfx-review.json"
    if call.agent == "title-graphic-design" and call.command == "research":
        document = write_research(production, llm=llm)
        return f"Graphics research: {len(document['items'])} item(s). File: graphics/research.json"
    if call.agent == "title-graphic-design" and call.command == "guide":
        document = write_guide(production, llm=llm)
        return f"Brand guide: {document['status']}. File: graphics/brand-guide.json"
    if call.agent == "title-graphic-design" and call.command == "build":
        document = build_graphics(production, llm=llm)
        return f"Graphics: {len(document['title_cards'])} title card(s). File: graphics/graphics.json"
    raise ValueError(f"{call.agent} has no phase 2 command named {call.command}.")
