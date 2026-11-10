"""The QA summary counts findings whose severity is note."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import QAPipeline


def test_one_note_prints_as_one(tmp_path):
    production = tmp_path / "the-last-marker"
    production.mkdir()
    qa = QAPipeline(production)
    qa.analysis = {
        "overall_verdict": "revise",
        "overall_notes": "One note.",
        "findings": [
            {
                "finding_id": "F004",
                "severity": "note",
                "category": "technical_quality",
                "shots_affected": ["s01-sh04"],
                "timestamp": "32.6s",
                "description": "Motion blur in the mid frame.",
                "recommendation": "Replace the frame.",
                "assigned_to": "production",
            }
        ],
        "shot_grades": [],
    }
    qa.report = qa._build_report("rough-cut-v1.mp4")
    assert qa.report.statistics["note"] == 1
    assert qa.report.statistics["total_findings"] == 1
    qa._write_summary()
    summary = (production / "qa-reports" / "qa-summary-v1.txt").read_text(encoding="utf-8")
    assert "Notes: 1" in summary
    assert "Notes: 0" not in summary
