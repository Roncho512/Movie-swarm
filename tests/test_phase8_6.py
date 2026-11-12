"""Phase 8.6 crew: schedule, light, grip, wardrobe, makeup, and VFX.

The proof is Harbor Night. The Last Marker folder is not written.
Nothing here calls a provider. Spent stays $0.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.assistant_director import build_schedule
from movie_swarm.camera import build_package
from movie_swarm.costume import lock_costumes
from movie_swarm.dailies import review_production, write_report
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.edit import assemble_production, write_edit
from movie_swarm.gaffer import build_lighting_plan
from movie_swarm.grip import build_grip_plan
from movie_swarm.line_producer import LineProducer
from movie_swarm.makeup import lock_makeup
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.prop_master import lock_props
from movie_swarm.roles import CREW_MAP, PHASE2_BILLING, PHASE2_CREW
from movie_swarm.script_supervisor import check_continuity
from movie_swarm.storyboard import build_boards
from movie_swarm.studio import run_studio
from movie_swarm.stunts import build_breakdown
from movie_swarm.treatment_doc import proposed_split
from movie_swarm.validate import validate_file
from movie_swarm.vfx import build_breakdown as build_vfx
from tests.test_line_producer import _treatment


def _harbor(tmp_path: Path) -> Path:
    source = repo_root() / "tests" / "fixtures" / "harbor-night"
    dest = tmp_path / "harbor-night"
    shutil.copytree(source, dest)
    return dest


def _package(production: Path) -> None:
    lock_props(production)
    lock_costumes(production)
    lock_makeup(production)
    build_package(production)
    build_boards(production)
    build_lighting_plan(production)
    build_grip_plan(production)
    build_breakdown(production)
    build_schedule(production)
    build_vfx(production)


def test_each_role_writes_a_valid_handoff(tmp_path):
    production = _harbor(tmp_path)
    _package(production)
    check = check_continuity(production)

    files = {
        "wardrobe/costume-lock.json": "costume-lock.schema.json",
        "makeup/makeup-lock.json": "makeup-lock.schema.json",
        "lighting/lighting-plan.json": "lighting-plan.schema.json",
        "grip/grip-plan.json": "grip-plan.schema.json",
        "schedule/shooting-schedule.json": "shooting-schedule.schema.json",
        "vfx/vfx-breakdown.json": "vfx-breakdown.schema.json",
        "continuity/continuity-check.json": "continuity-check.schema.json",
    }
    for relative, schema in files.items():
        result = validate_file(production / relative)
        assert result.ok, result.errors
        assert result.schema_name == schema

    costume = json.loads((production / "wardrobe" / "costume-lock.json").read_text(encoding="utf-8"))
    ada = costume["characters"][0]
    assert ada["garment"] == "coat"
    assert ada["color"] == "dark"
    assert ada["condition"] == "worn"
    assert ada["changes"][0]["scene_id"] == "s01"
    assert costume["draft_method"] == "offline-deterministic"

    makeup = json.loads((production / "makeup" / "makeup-lock.json").read_text(encoding="utf-8"))
    assert makeup["characters"][0]["hair"] == "short"
    assert makeup["characters"][0]["changes"][0]["scene_id"] == "s01"

    light = json.loads((production / "lighting" / "lighting-plan.json").read_text(encoding="utf-8"))
    scene = light["scenes"][0]
    assert scene["time_of_day"] == "NIGHT"
    assert scene["color_temperature"] == "not named"
    assert scene["contrast_ratio"] == "not named"
    assert "fluorescent" in scene["prompt_note"].casefold()
    assert "3200" not in scene["prompt_note"]
    assert scene["fill"] == "not named"
    assert light["continuity"] == "clear"

    grip = json.loads((production / "grip" / "grip-plan.json").read_text(encoding="utf-8"))
    by_id = {shot["shot_id"]: shot for shot in grip["shots"]}
    assert by_id["s01-sh01"]["support"] == "dolly"
    assert by_id["s01-sh02"]["support"] == "sticks"
    assert by_id["s01-sh02"]["consistent_with_camera"] is False
    assert "handheld" in by_id["s01-sh02"]["note"].casefold()
    assert by_id["s01-sh02"]["consistent_with_gaffer"] is True
    assert "practical" in by_id["s01-sh02"]["rigging"].casefold()

    schedule = json.loads((production / "schedule" / "shooting-schedule.json").read_text(encoding="utf-8"))
    day = schedule["days"][0]
    assert day["location"] == "HARBOR DOCK"
    assert day["time_of_day"] == "NIGHT"
    assert day["int_ext"] == "EXT"
    ordered = [shot["shot_id"] for setup in day["setups"] for shot in setup["shots"]]
    assert ordered == ["s01-sh01", "s01-sh02", "s01-sh03"]
    assert schedule["safety"][0]["shot_id"] == "s01-sh03"
    assert "real fall" in schedule["safety"][0]["note"]

    breakdown = json.loads((production / "vfx" / "vfx-breakdown.json").read_text(encoding="utf-8"))
    assert [shot["shot_id"] for shot in breakdown["shots"]] == ["s01-sh01"]
    assert breakdown["shots"][0]["method"] == "composite"
    assert breakdown["turnover"][0]["for"] == ["editor", "colorist"]
    assert "s01-sh01" in breakdown["turnover"][0]["editor"]
    assert "s01-sh01" in breakdown["turnover"][0]["colorist"]

    assert check["verdict"] == "clear"
    board = json.loads((production / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))
    ada_board = next(frame for frame in board["frames"] if frame["shot_id"] == "s01-sh01")
    assert "dark coat" in ada_board["board_prompt"].casefold()
    assert "short hair" in ada_board["board_prompt"].casefold()


def test_wardrobe_and_makeup_drift_are_caught(tmp_path):
    production = _harbor(tmp_path)
    _package(production)
    shot_list_path = production / "storyboard" / "shot-list.json"
    shot_list = json.loads(shot_list_path.read_text(encoding="utf-8"))
    shot = shot_list["shots"][0]
    shot["description"] = "Ada wears a light coat and long hair."
    shot["generation_prompt"] = shot["description"]
    shot["continuity_notes"] = ""
    shot_list_path.write_text(json.dumps(shot_list), encoding="utf-8")
    drifted = check_continuity(production)
    assert drifted["verdict"] == "drift"
    observed = " ".join(item.get("observed", "") for item in drifted["findings"]).casefold()
    assert "light coat" in observed
    assert "long hair" in observed
    ids = {item.get("costume_id") for item in drifted["findings"]}
    assert "ada" in ids
    makeup_ids = {item.get("makeup_id") for item in drifted["findings"]}
    assert "ada" in makeup_ids


def test_dailies_catch_a_wardrobe_miss(tmp_path):
    production = _harbor(tmp_path)
    lock_costumes(production)
    lock_makeup(production)
    shot = {
        "shot_id": "s01-sh01",
        "scene_number": 1,
        "shot_number": 1,
        "shot_type": "wide",
        "description": "Ada stands on the dock.",
        "camera_movement": "static",
        "generation_prompt": "Ada stands on the dock.",
        "characters_in_shot": ["Ada"],
        "target_duration_seconds": 4,
    }
    board = production / "storyboard"
    board.mkdir(exist_ok=True)
    (board / "shot-list.json").write_text(json.dumps({"shots": [shot]}), encoding="utf-8")
    frame = production / "frames" / "s01-sh01.png"
    frame.parent.mkdir(parents=True, exist_ok=True)
    frame.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x04\x00\x01\x01\x00\x05\x18\xd4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    takes = production / "takes"
    takes.mkdir(exist_ok=True)
    (takes / "takes-manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": "harbor-night",
                "takes": [{"take_id": "s01-sh01-t01", "shot_id": "s01-sh01", "file": "frames/s01-sh01.png", "kind": "frame"}],
            }
        ),
        encoding="utf-8",
    )

    class Vision:
        def describe(self, *, path, shot_id):
            return (
                "A wide view. Ada stands on the dock. "
                "Available fluorescent light. Cool gray. Short hair."
            )

    report = review_production(production, vision=Vision(), allocations=proposed_split(500))
    write_report(report, production)
    assert report["shots"][0]["verdict"] == "retake"
    text = " ".join(report["shots"][0]["reasons"]).casefold()
    assert "dark coat" in text
    assert report["spent_usd"] == 0


def _dailies_report(shots: list[dict]) -> dict:
    rows = []
    for shot in shots:
        rows.append(
            {
                "shot_id": shot["shot_id"],
                "verdict": "circle",
                "best_take": shot["shot_id"] + "-t01",
                "reasons": [shot["description"]],
                "takes": [
                    {
                        "take_id": shot["shot_id"] + "-t01",
                        "file": "frames/" + shot["shot_id"] + ".png",
                        "verdict": "circle",
                        "reasons": [shot["description"]],
                        "description_source": "client",
                        "checks": {
                            "technical": {"status": "pass", "detail": "The file is on disk."},
                            "continuity": {"status": "pass", "detail": shot["description"]},
                            "shot_match": {"status": "pass", "detail": "The take matches the shot list."},
                            "look_match": {"status": "pass", "detail": "The description matches the look."},
                        },
                    }
                ],
            }
        )
    return {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "reviewed_at": "2026-11-11T00:00:00Z",
        "source": "takes/takes-manifest.json",
        "spent_usd": 0,
        "fix_loop_reserve_usd": 50,
        "retake_estimate_usd": 0,
        "within_fix_loop": True,
        "shots": rows,
        "retakes": [],
        "model": "gemini-omni-1.2-flash",
        "draft_method": "offline-deterministic",
    }


def test_the_edit_catches_makeup_drift_across_a_cut(tmp_path):
    production = _harbor(tmp_path)
    lock_costumes(production)
    lock_makeup(production)
    shots = []
    frames = []
    for index, description in enumerate(
        (
            "Ada stands on the dock in a dark coat. Short hair.",
            "Ada stands on the dock in a dark coat. Long hair.",
        ),
        start=1,
    ):
        shot_id = f"s01-sh0{index}"
        shots.append(
            {
                "shot_id": shot_id,
                "scene_number": 1,
                "shot_number": index,
                "shot_type": "wide",
                "description": description,
                "generation_prompt": description,
                "characters_in_shot": ["Ada"],
                "target_duration_seconds": 4,
            }
        )
        frames.append(
            {
                "order": index,
                "shot_id": shot_id,
                "scene_id": "s01",
                "what_we_see": description,
                "board_prompt": description,
                "duration_seconds": 4,
                "image_status": "not-generated",
                "image_ref": None,
            }
        )
    (production / "storyboard").mkdir(exist_ok=True)
    (production / "storyboard" / "shot-list.json").write_text(
        json.dumps({"production_id": "harbor-night", "version": "1.0.0", "total_shots": 2, "shots": shots}),
        encoding="utf-8",
    )
    (production / "storyboard" / "storyboard.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "production_id": "harbor-night",
                "frames": frames,
                "animatic": {"total_duration_seconds": 8, "order": ["s01-sh01", "s01-sh02"]},
                "image_generation": "not-run",
            }
        ),
        encoding="utf-8",
    )
    report = _dailies_report(shots)
    dailies = production / "dailies"
    dailies.mkdir()
    from movie_swarm.handoff import write_handoff

    write_handoff(dailies / "dailies-report.json", report, schema="dailies-report")
    edl = assemble_production(production, dailies_approved=True)
    write_edit(edl, production)
    assert edl["continuity"][0]["status"] == "fail"
    assert "long hair" in edl["continuity"][0]["detail"].casefold()
    assert edl["ready_for_picture_lock"] is False
    assert not (production / "edit" / "picture-lock.json").exists()


def test_vfx_review_flags_a_missing_note(tmp_path):
    production = _harbor(tmp_path)
    _package(production)
    report = _dailies_report(
        [{"shot_id": "s01-sh01", "description": "A dark room with no lamp."}]
    )
    from movie_swarm.handoff import write_handoff
    from movie_swarm.vfx import review_vfx

    write_handoff(production / "dailies" / "dailies-report.json", report, schema="dailies-report")
    reviewed = review_vfx(production)
    result = validate_file(production / "vfx" / "vfx-review.json")
    assert result.ok, result.errors
    assert reviewed["verdict"] == "drift"
    assert reviewed["shots"][0]["status"] == "fail"
    assert "fluorescent lamp" in reviewed["shots"][0]["detail"]


def test_crew_map_billing_and_dispatch(tmp_path):
    assert set(CREW_MAP) == {
        "assistant-director",
        "gaffer",
        "key-grip",
        "costume-designer",
        "makeup-hair",
        "vfx-supervisor",
        "title-graphic-design",
    }
    assert all(role in PHASE2_CREW for role in CREW_MAP)
    assert PHASE2_BILLING["assistant-director"] == "line-producer"
    assert PHASE2_BILLING["gaffer"] == "cinematographer"
    assert PHASE2_BILLING["key-grip"] == "cinematographer"
    assert PHASE2_BILLING["costume-designer"] == "art-director"
    assert PHASE2_BILLING["makeup-hair"] == "art-director"
    assert PHASE2_BILLING["vfx-supervisor"] == "editor"
    assert PHASE2_BILLING["title-graphic-design"] == "art-director"
    assert CREW_MAP["assistant-director"]["hands_to"] == ["production"]
    assert "stunt-coordinator" in CREW_MAP["assistant-director"]["receives_from"]
    assert CREW_MAP["vfx-supervisor"]["hands_to"] == ["editor", "colorist", "production"]
    assert CREW_MAP["costume-designer"]["hands_to"] == ["script-supervisor", "assistant-director"]

    production = tmp_path / "demo"
    _treatment(production)
    LineProducer.start(production, run_id="run-1")
    director = Director(production)
    paused = director.dispatch(CrewCall(agent="gaffer", command="plan", estimated_cost_usd=0), "run-1")
    assert paused.status == "paused"
    assert "treatment" in paused.message

    LineProducer.open(production, "run-1").approve_gate("treatment", "approved", "ron")
    over_light = director.dispatch(
        CrewCall(agent="gaffer", command="plan", estimated_cost_usd=11, note="too much camera"),
        "run-1",
    )
    assert over_light.status == "paused"
    assert "cinematographer" in over_light.message
    over_call = director.dispatch(
        CrewCall(agent="assistant-director", command="schedule", estimated_cost_usd=6, note="too much admin"),
        "run-1",
    )
    assert over_call.status == "paused"
    assert "line-producer" in over_call.message
    over_art = director.dispatch(
        CrewCall(agent="costume-designer", command="lock", estimated_cost_usd=26, note="too much art"),
        "run-1",
    )
    assert over_art.status == "paused"
    assert "art-director" in over_art.message
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0

    harbor = _harbor(tmp_path)
    producer = LineProducer.start(harbor, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", stage_split=proposed_split(500))
    ran = Director(harbor).dispatch(
        CrewCall(agent="costume-designer", command="lock", estimated_cost_usd=0),
        "run-1",
    )
    assert ran.status == "ran", ran.message
    assert (harbor / "wardrobe" / "costume-lock.json").is_file()
    assert LineProducer.open(harbor, "run-1").run.data["cost_usd"] == 0


def test_new_roles_use_the_cheap_model_and_do_not_call_out():
    for role, purpose in (
        ("assistant-director", "schedule"),
        ("gaffer", "plan"),
        ("key-grip", "plan"),
        ("costume-designer", "lock"),
        ("makeup-hair", "lock"),
        ("vfx-supervisor", "breakdown"),
        ("vfx-supervisor", "review"),
    ):
        assert resolve_model(role, purpose=purpose)["model"] == "claude-haiku-5-5"
    banned = ("urllib", "requests", "http.client", "httpx", "ANTHROPIC_API_KEY", "FAL_KEY")
    roots = [
        repo_root() / "movie_swarm" / "assistant_director.py",
        repo_root() / "movie_swarm" / "gaffer.py",
        repo_root() / "movie_swarm" / "grip.py",
        repo_root() / "movie_swarm" / "costume.py",
        repo_root() / "movie_swarm" / "makeup.py",
        repo_root() / "movie_swarm" / "vfx.py",
        repo_root() / "movie_swarm" / "prep_inputs.py",
    ]
    for path in roots:
        text = path.read_text(encoding="utf-8")
        for word in banned:
            assert word not in text, f"{path.name} mentions {word}"
    film = ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967")
    offenders = []
    scan = [
        repo_root() / "movie_swarm" / "assistant_director.py",
        repo_root() / "movie_swarm" / "gaffer.py",
        repo_root() / "movie_swarm" / "grip.py",
        repo_root() / "movie_swarm" / "costume.py",
        repo_root() / "movie_swarm" / "makeup.py",
        repo_root() / "movie_swarm" / "vfx.py",
        repo_root() / "movie_swarm" / "prep_inputs.py",
        repo_root() / "agents" / "13-assistant-director",
        repo_root() / "agents" / "14-gaffer",
        repo_root() / "agents" / "15-key-grip",
        repo_root() / "agents" / "16-costume-designer",
        repo_root() / "agents" / "17-makeup-hair",
        repo_root() / "agents" / "18-vfx-supervisor",
    ]
    for root in scan:
        files = [root] if root.is_file() else list(root.rglob("*"))
        for path in files:
            if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            for word in film:
                if word in text:
                    offenders.append(f"{path.relative_to(repo_root())}: {word}")
    assert offenders == []


def test_studio_still_stops_at_each_gate(tmp_path):
    production = _harbor(tmp_path)
    first = run_studio(production, run_id="studio-1")
    assert first["status"] == "stopped"
    assert first["stopped_at"] == "treatment"
    assert first["generation_gate"] == "closed"
    assert first["spent_usd"] == 0
    assert not (production / "schedule" / "shooting-schedule.json").exists()

    LineProducer.open(production, "studio-1").approve_gate(
        "treatment", "approved", "ron", note="The treatment can go forward."
    )
    second = run_studio(production, run_id="studio-1")
    assert second["status"] == "stopped", second["message"]
    assert second["stopped_at"] == "previs"
    for relative in (
        "wardrobe/costume-lock.json",
        "makeup/makeup-lock.json",
        "lighting/lighting-plan.json",
        "grip/grip-plan.json",
        "schedule/shooting-schedule.json",
        "vfx/vfx-breakdown.json",
        "continuity/continuity-check.json",
    ):
        assert (production / relative).is_file(), relative
    assert not (production / "dailies" / "dailies-report.json").exists()
    assert not (production / "vfx" / "vfx-review.json").exists()

    producer = LineProducer.open(production, "studio-1")
    producer.approve_gate("previs", "approved", "ron", note="The package can go forward.")
    producer.approve_gate("graphics", "approved", "ron", note="The brand guide can be used.")
    producer.approve_gate("production", "approved", "ron", note="A quote can be written.")
    third = run_studio(production, run_id="studio-1")
    assert third["status"] == "stopped", third["message"]
    assert third["stopped_at"] == "dailies"
    assert (production / "vfx" / "vfx-review.json").is_file()
    review = json.loads((production / "vfx" / "vfx-review.json").read_text(encoding="utf-8"))
    assert review["verdict"] == "clear"
    assert not (production / "edit" / "rough-cut.json").exists()
    assert LineProducer.open(production, "studio-1").run.data["cost_usd"] == 0
    assert LineProducer.open(production, "studio-1").gate_decision("generation") != "approved"
