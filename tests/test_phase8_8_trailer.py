"""Phase 8.8 trailer: one role, two deliverables, approved takes only.

The proof is Harbor Night. A film with the trailer off is unchanged.
Nothing here calls a provider.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from movie_swarm.budget import proposed_document, write_film_budget
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.gates import is_stage_gated
from movie_swarm.handoff import write_handoff
from movie_swarm.line_producer import LineProducer
from movie_swarm.models import resolve_model
from movie_swarm.paths import repo_root
from movie_swarm.studio import run_studio
from movie_swarm.trailer import (
    TrailerError,
    cut_trailer,
    recheck_trailer,
    request_shot,
    sign_guard,
    write_guard,
    write_plan,
    write_research,
)
from movie_swarm.validate import validate_file
from tests.test_phase5 import _harbor, _shot
from tests.test_phase7 import _open, _prepare
from tests.test_phase8 import _deliver


def _with_trailer(tmp_path: Path) -> Path:
    production = _harbor(tmp_path)
    write_film_budget(production, proposed_document(500, trailer_on=True, contingency_percent=0))
    return production


def _lock_and_dailies(production: Path) -> None:
    (production / "edit").mkdir(parents=True, exist_ok=True)
    (production / "dailies").mkdir(parents=True, exist_ok=True)
    lock = {
        "events": [
            {
                "shot_id": "s01-sh01",
                "source_file": "frames/s01-sh01.mp4",
                "record_in": 0,
                "record_out": 2,
                "duration_seconds": 2,
                "description": "Ada stands under a fluorescent lamp.",
            },
            {
                "shot_id": "s01-sh99",
                "source_file": "frames/s01-sh99.mp4",
                "record_in": 2,
                "record_out": 3,
                "duration_seconds": 1,
                "description": "A shot that was not circled.",
            },
        ]
    }
    (production / "edit" / "picture-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    report = {
        "shots": [
            {"shot_id": "s01-sh01", "verdict": "circle"},
            {"shot_id": "s01-sh99", "verdict": "retake"},
        ]
    }
    (production / "dailies" / "dailies-report.json").write_text(json.dumps(report), encoding="utf-8")


def test_refuses_without_research_and_without_a_plan(tmp_path):
    production = _with_trailer(tmp_path)
    with pytest.raises(TrailerError) as missing_research:
        write_plan(production)
    assert "research" in str(missing_research.value).casefold()
    write_research(production)
    with pytest.raises(TrailerError) as unsigned:
        write_plan(production)
    assert "guard" in str(unsigned.value).casefold()
    write_guard(production)
    with pytest.raises(TrailerError) as needs_signature:
        write_plan(production)
    assert "signed" in str(needs_signature.value).casefold()
    with pytest.raises(TrailerError) as missing_plan:
        cut_trailer(production)
    assert "plan" in str(missing_plan.value).casefold()


def test_approved_takes_only_and_gaps_are_logged(tmp_path):
    production = _with_trailer(tmp_path)
    _lock_and_dailies(production)
    research = write_research(production)
    assert research["draft_method"] == "offline-deterministic"
    assert {item["basis"] for item in research["items"]} <= {"sourced", "inferred"}
    assert any(item["basis"] == "sourced" and item["source_file"] for item in research["items"])
    guard = write_guard(production)
    sign_guard(production)
    plan = write_plan(production)
    assert validate_file(production / "marketing" / "trailer-plan.json").ok
    assert plan["length_source"] == "default"
    assert "15" in plan["length_note"]
    assert "45" in plan["length_note"]
    assert any(beat["shot_id"] == "s01-sh01" for beat in plan["beats"])
    assert all(beat["shot_id"] != "s01-sh99" for beat in plan["beats"])
    assert any(gap["shot_id"] == "s01-sh99" for gap in plan["gaps"])
    plan["beats"].append(
        {
            "deliverable": "trailer",
            "shot_id": "missing-shot",
            "source_file": "",
            "record_in": 0,
            "record_out": 1,
            "duration_seconds": 1,
            "card_text": "Do not shoot this.",
            "music": "None.",
        }
    )
    write_handoff(production / "marketing" / "trailer-plan.json", plan, schema="trailer-plan")
    cut = cut_trailer(production)
    assert validate_file(production / "marketing" / "trailer-cut.json").ok
    assert any(gap["shot_id"] == "missing-shot" for gap in cut["gaps"])
    assert all(item.get("shot_id") != "missing-shot" for item in cut["kept"])
    assert "no new shot" in " ".join(gap["reason"].casefold() for gap in cut["gaps"])
    with pytest.raises(TrailerError) as refused:
        request_shot("missing-shot")
    assert "cannot request" in str(refused.value).casefold()
    assert not (production / "generation").exists()
    versions = {item["aspect_ratio"] for item in cut["files"]}
    assert versions == {"16:9", "9:16"}
    assert {item["deliverable"] for item in cut["files"]} == {"teaser", "trailer"}


def test_a_changed_cut_is_stale(tmp_path):
    production = _with_trailer(tmp_path)
    _lock_and_dailies(production)
    write_research(production)
    write_guard(production)
    sign_guard(production)
    write_plan(production)
    cut_trailer(production)
    lock = production / "edit" / "picture-lock.json"
    lock.write_text(lock.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    checked = recheck_trailer(production)
    assert checked["lock_status"] == "stale"
    with pytest.raises(TrailerError) as caught:
        cut_trailer(production)
    assert "changed" in str(caught.value).casefold()


def test_billing_goes_to_marketing_and_not_the_editor(tmp_path):
    production = _with_trailer(tmp_path)
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron")
    producer.approve_gate("edit", "approved", "ron", note="Picture lock.")
    paused = producer.authorize_crew("trailer-editor", 5000, "too much trailer")
    assert paused.allowed is False
    assert "marketing-distribution" in paused.message
    assert "editor allocation" not in paused.message
    assert producer.run.data["cost_usd"] == 0
    ran = Director(production).dispatch(
        CrewCall(agent="trailer-editor", command="research", estimated_cost_usd=0, note="research"),
        "run-1",
    )
    assert ran.status == "ran", ran.message
    kinds = [
        (entry["stage"], entry["kind"])
        for entry in LineProducer.open(production, "run-1").record["ledger"]
    ]
    assert ("marketing-distribution", "dry-run") in kinds
    assert all(stage != "editor" for stage, _kind in kinds)


def test_trailer_off_skips_and_the_film_can_deliver(tmp_path):
    production = _harbor(tmp_path)
    producer = LineProducer.start(production, run_id="run-1")
    ran = Director(production).dispatch(
        CrewCall(agent="trailer-editor", command="research", estimated_cost_usd=0, note="skip"),
        "run-1",
    )
    assert ran.status == "ran"
    assert "off" in ran.message.casefold()
    assert not (production / "marketing").exists()
    assert producer.run.data["cost_usd"] == 0
    assert is_stage_gated("trailer") is True
    stopped = run_studio(production, run_id="studio-1")
    assert stopped["stopped_at"] == "treatment"
    assert not (production / "marketing").exists()


def test_manifest_includes_marketing_files_when_present(tmp_path):
    shots = [_shot("s01-sh01", duration=1, description="Ada stands under a fluorescent lamp.")]
    production = _prepare(tmp_path, shots)
    write_film_budget(production, proposed_document(500, trailer_on=True, contingency_percent=0))
    write_research(production)
    write_guard(production)
    sign_guard(production)
    write_plan(production)
    cut_trailer(production)
    _open(production)
    delivered = _deliver(production)
    assert delivered.status == "ran", delivered.message
    manifest = json.loads((production / "delivery" / "delivery-manifest.json").read_text(encoding="utf-8"))
    marketing = [item for item in manifest["files"] if item["role"] == "marketing"]
    assert marketing
    assert any("usage-sheet" in item["path"] for item in marketing)
    assert any(item["sha256"] for item in marketing)
    report = json.loads((production / "delivery" / "qc-report.json").read_text(encoding="utf-8"))
    trailer_checks = [item for item in report["checks"] if item["kind"] == "trailer"]
    assert {item["check_id"] for item in trailer_checks} >= {
        "trailer-spoiler-guard",
        "trailer-card-text",
        "trailer-approved-takes",
    }
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_model_and_no_film_facts():
    assert resolve_model("trailer-editor", purpose="research")["model"] == "claude-haiku-5-5"
    assert resolve_model("trailer-editor", purpose="cut")["model"] == "claude-haiku-5-5"
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
        repo_root() / "movie_swarm" / "trailer.py",
        repo_root() / "agents" / "20-trailer-editor",
        repo_root() / "schemas" / "trailer-research.schema.json",
        repo_root() / "schemas" / "spoiler-guard.schema.json",
        repo_root() / "schemas" / "trailer-plan.schema.json",
        repo_root() / "schemas" / "trailer-cut.schema.json",
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
    assert "urllib" not in (repo_root() / "movie_swarm" / "trailer.py").read_text(encoding="utf-8")
