"""The readable treatment is written before the gate, and the guide says so."""

from __future__ import annotations

import shutil

from movie_swarm.line_producer import LineProducer
from movie_swarm.paths import repo_root
from movie_swarm.studio import run_studio


def test_status_writes_the_markdown_before_the_gate(tmp_path):
    production = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", production)
    assert not (production / "treatment" / "treatment.md").is_file()
    producer = LineProducer.start(production, run_id="guide-1")
    assert producer.gate_decision("treatment") != "approved"
    producer.status_text()
    markdown = (production / "treatment" / "treatment.md").read_text(encoding="utf-8")
    assert "Harbor Night" in markdown
    assert producer.gate_decision("treatment") != "approved"
    before = (production / "treatment" / "treatment.json").read_text(encoding="utf-8")
    producer.status_text()
    assert (production / "treatment" / "treatment.json").read_text(encoding="utf-8") == before


def test_the_studio_names_the_markdown_before_approval(tmp_path):
    production = tmp_path / "harbor-night"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", production)
    result = run_studio(production, run_id="guide-1", auto_approve=False)
    assert result["status"] == "stopped"
    assert result["stopped_at"] == "treatment"
    assert "treatment/treatment.md" in result["message"]
    assert (production / "treatment" / "treatment.md").is_file()
    assert LineProducer.open(production, "guide-1").gate_decision("treatment") != "approved"


def test_the_guide_has_setup_the_wired_shot_and_the_voice_permission():
    guide = (repo_root() / "START-HERE.md").read_text(encoding="utf-8")
    assert "python3 -m venv .venv" in guide
    assert "python3 -m pip install -r requirements.txt" in guide
    assert "cp .env.example .env" in guide
    assert "chmod 600 .env" in guide
    assert "python3 scripts/doctor.py" in guide
    assert "Voices: Read" in guide
    assert "--model seedance-2.0-fast" in guide
    assert "--live" in guide
    assert "writes `treatment/treatment.md` from that JSON" in guide
    assert "Approving that gate does not create the markdown." in guide
