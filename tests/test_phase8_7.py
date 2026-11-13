"""Phase 8.7: Title and Graphic Design.

The proof is Harbor Night. Research comes before the brand guide, and the
guide comes before any graphic. Nothing here calls a provider. Spent stays $0.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from movie_swarm.camera import build_package
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.graphics import GraphicsError, build_graphics, write_guide, write_research
from movie_swarm.line_producer import LineProducer
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.storyboard import build_boards
from movie_swarm.treatment_doc import proposed_split
from movie_swarm.validate import validate_file
from tests.test_phase5 import _harbor
from tests.test_phase7 import _open, _prepare, _shot
from tests.test_phase8 import _deliver


def _traces(node):
    found = []
    if isinstance(node, dict):
        if "trace" in node:
            found.append(node["trace"])
        for value in node.values():
            found.extend(_traces(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_traces(item))
    return found


def _ready(tmp_path: Path) -> tuple[Path, LineProducer]:
    production = _harbor(tmp_path)
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", stage_split=proposed_split(500))
    return production, producer


def test_research_comes_before_the_guide_and_the_guide_before_graphics(tmp_path):
    production, producer = _ready(tmp_path)
    with pytest.raises(GraphicsError):
        write_guide(production)

    research = write_research(production)
    assert research["draft_method"] == "offline-deterministic"
    topics = {item["topic"] for item in research["items"]}
    assert topics == {"director", "setting", "genre", "period", "references"}
    for item in research["items"]:
        if item["basis"] == "sourced":
            assert item["source_file"]
            assert item["source_field"]
        elif item["basis"] == "designer-proposal":
            assert item["reference"]
        else:
            assert item["basis"] == "inferred"
            assert item["source_file"] is None

    guide = write_guide(production)
    result = validate_file(production / "graphics" / "brand-guide.json")
    assert result.ok, result.errors
    assert guide["status"] == "draft"
    ids = {item["item_id"] for item in research["items"]}
    traces = _traces(guide)
    assert traces
    assert set(traces) <= ids
    with pytest.raises(GraphicsError) as caught:
        build_graphics(production)
    assert "draft" in str(caught.value).casefold()

    producer.approve_gate("graphics", "approved", "ron", note="The brand guide can be used.")
    approved = json.loads((production / "graphics" / "brand-guide.json").read_text(encoding="utf-8"))
    assert approved["status"] == "approved"
    assert any("Approved" in entry["change"] for entry in approved["change_log"])

    research_path = production / "graphics" / "research.json"
    research_path.unlink()
    with pytest.raises(GraphicsError) as missing:
        write_guide(production)
    assert "research" in str(missing.value).casefold()


def test_a_changed_look_is_logged_and_the_guide_returns_to_draft(tmp_path):
    production, producer = _ready(tmp_path)
    write_research(production)
    write_guide(production)
    producer.approve_gate("graphics", "approved", "ron", note="Use it.")
    look_path = production / "look" / "look.json"
    look = json.loads(look_path.read_text(encoding="utf-8"))
    look["summary"] = look["summary"] + " Quieter titles."
    look_path.write_text(json.dumps(look), encoding="utf-8")
    with pytest.raises(GraphicsError) as stale:
        write_guide(production)
    assert "research" in str(stale.value).casefold()
    write_research(production)
    rebuilt = write_guide(production)
    assert rebuilt["status"] == "draft"
    assert rebuilt["version"] == "1.0.1"
    assert any("look" in entry["change"].casefold() for entry in rebuilt["change_log"])
    with pytest.raises(GraphicsError):
        build_graphics(production)
    producer.approve_gate("graphics", "approved", "ron", note="Use the new guide.")
    built = build_graphics(production)
    assert built["guide_version"] == "1.0.1"


def test_title_cards_credits_and_the_frame_grab_poster(tmp_path, monkeypatch):
    # Patching graphics.shutil.which replaces shutil.which for every module.
    # Call the original lookup, or a later ffprobe check calls this wrapper again.
    original_which = shutil.which
    monkeypatch.setattr(
        "movie_swarm.graphics.shutil.which",
        lambda name, _which=original_which: None if name == "ffmpeg" else _which(name),
    )
    shots = [_shot("s01-sh01", duration=1)]
    production = _prepare(tmp_path, shots)
    producer = _open(production)
    write_research(production)
    write_guide(production)
    producer.approve_gate("graphics", "approved", "ron", note="The brand guide can be used.")
    producer.add_credit("Boat Hand", "Nia")
    ran = Director(production).dispatch(
        CrewCall(
            agent="title-graphic-design",
            command="build",
            estimated_cost_usd=0,
            note="checked for Someone Extra",
        ),
        "run-1",
    )
    assert ran.status == "ran", ran.message
    package = json.loads((production / "graphics" / "graphics.json").read_text(encoding="utf-8"))
    result = validate_file(production / "graphics" / "graphics.json")
    assert result.ok, result.errors
    assert package["main_title"]["text"] == "Harbor Night"
    assert package["title_cards"][0]["text"] == "HARBOR NIGHT"
    assert package["title_cards"][0]["source_file"] == "screenplay/harbor-night.md"
    assert "start_seconds" not in package["subtitles"]
    assert package["subtitles"]["timing_owner"] == "post-supervisor"
    names = [line["name"] for line in package["end_credits"]["lines"]]
    assert "Nia" in names
    assert "Someone Extra" not in names
    assert package["key_art"]["filename"] == "graphics/key-art-poster.png"
    assert package["key_art"]["distinct_from"] == "poster.png"
    assert package["key_art"]["width"] == 320
    assert package["key_art"]["height"] == 180
    assert {item["id"] for item in package["collateral"]} == {"thumbnail-16x9", "thumbnail-9x16", "social-card"}
    assert package["key_art"]["render_status"] == "not-rendered"
    assert package["draft_method"] == "offline-deterministic"

    build_package(production)
    board = build_boards(production)
    assert "TITLE CARD" not in json.dumps(board)
    assert len(board["frames"]) >= 1

    delivered = _deliver(production)
    assert delivered.status == "ran", delivered.message
    plan = json.loads((production / "delivery" / "delivery-plan.json").read_text(encoding="utf-8"))
    assert plan["poster"]["filename"] == "poster.png"
    manifest = json.loads((production / "delivery" / "delivery-manifest.json").read_text(encoding="utf-8"))
    roles = {item["path"]: item["role"] for item in manifest["files"]}
    assert roles["delivery/poster.png"] == "poster"
    assert roles["graphics/key-art-poster.png"] == "graphics"
    poster = next(item for item in manifest["files"] if item["path"].endswith("poster.png") and item["role"] == "poster")
    assert poster["path"].endswith("poster.png")
    assert "key-art" not in poster["path"]
    report = json.loads((production / "delivery" / "qc-report.json").read_text(encoding="utf-8"))
    graphics_checks = [item for item in report["checks"] if item["kind"] == "graphics"]
    assert {item["check_id"] for item in graphics_checks} >= {
        "graphics-spelling",
        "graphics-credits",
        "graphics-safe-area",
        "graphics-resolution",
    }
    assert all(item["status"] != "fail" for item in graphics_checks)
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_billing_model_and_no_film_facts_in_the_engine():
    assert resolve_model("title-graphic-design", purpose="research")["model"] == "claude-haiku-5-5"
    assert resolve_model("title-graphic-design", purpose="guide")["model"] == "claude-haiku-5-5"
    assert resolve_model("title-graphic-design", purpose="build")["model"] == "claude-haiku-5-5"
    banned = (
        "last marker",
        "leone",
        "spaghetti",
        "1967",
        "baja",
        "breitling",
        "triumph",
        "morricone",
        "1965",
    )
    roots = [
        repo_root() / "movie_swarm" / "graphics.py",
        repo_root() / "agents" / "19-title-graphic-design",
        repo_root() / "schemas" / "graphics-research.schema.json",
        repo_root() / "schemas" / "graphics-brand-guide.schema.json",
        repo_root() / "schemas" / "graphics-package.schema.json",
    ]
    offenders = []
    for root in roots:
        files = [root] if root.is_file() else list(root.rglob("*"))
        for path in files:
            if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            for word in banned:
                if word in text:
                    offenders.append(f"{path.relative_to(repo_root())}: {word}")
    assert offenders == []
    assert "urllib" not in (repo_root() / "movie_swarm" / "graphics.py").read_text(encoding="utf-8")


def test_an_over_art_estimate_is_not_charged(tmp_path):
    production, _producer = _ready(tmp_path)
    paused = Director(production).dispatch(
        CrewCall(agent="title-graphic-design", command="research", estimated_cost_usd=26, note="too much art"),
        "run-1",
    )
    assert paused.status == "paused"
    assert "art-director" in paused.message
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert not (production / "graphics" / "research.json").exists()


def test_sizes_are_not_invented_when_the_documents_omit_them(tmp_path):
    production, producer = _ready(tmp_path)
    spec_path = production / "delivery" / "delivery-spec.json"
    spec_path.unlink()
    treatment_path = production / "treatment" / "treatment.json"
    treatment = json.loads(treatment_path.read_text(encoding="utf-8"))
    treatment["deliverables"] = {"aspect_ratio": "scope", "resolution": "open", "length": "short"}
    treatment_path.write_text(json.dumps(treatment), encoding="utf-8")
    write_research(production)
    write_guide(production)
    producer.approve_gate("graphics", "approved", "ron", note="Use it.")
    built = build_graphics(production)
    assert built["key_art"]["width"] is None
    assert built["key_art"]["height"] is None
    assert built["key_art"]["render_status"] == "not-rendered"
    assert all(item["width"] is None for item in built["collateral"])

