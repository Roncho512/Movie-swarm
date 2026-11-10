"""The Last Marker audit: three handoffs pass, four older files are known mismatches."""

from __future__ import annotations

import subprocess
import sys

from movie_swarm.paths import repo_root
from movie_swarm.validate import audit_exit_code, audit_production, format_audit


def test_pilot_audit_matches_the_recorded_gaps():
    items = audit_production(repo_root() / "productions" / "the-last-marker")
    by_path = {item.path: item for item in items}

    passed = {
        "productions/the-last-marker/scene-manifest/scene-manifest.json",
        "productions/the-last-marker/shot-lists/shot-list.json",
        "productions/the-last-marker/visual-style-bible.json",
    }
    known = {
        "productions/the-last-marker/audio/audio-manifest.json": [
            "(root): 'created_at' is a required property",
            "(root): 'layers' is a required property",
            "(root): 'version' is a required property",
        ],
        "productions/the-last-marker/seedance-output/clip-metadata.json": [
            "(root): 'created_at' is a required property",
            "(root): 'version' is a required property",
            "clips/0: 'clip_id' is a required property",
            "clips/0: 'file_path' is a required property",
            "clips/0/status: 'preview' is not one of ['generated', 'validated', 'selected', 'rejected', 'needs-regen']",
        ],
        "productions/the-last-marker/qa-reports/qa-report-v1.json": [
            "(root): 'issues' is a required property",
            "(root): 'review_pass' is a required property",
            "(root): 'reviewed_at' is a required property",
            "(root): 'verdict' is a required property",
            "(root): 'version' is a required property",
        ],
        "productions/the-last-marker/qa-reports/qa-report-v2.json": [
            "(root): 'issues' is a required property",
            "(root): 'review_pass' is a required property",
            "(root): 'reviewed_at' is a required property",
            "(root): 'verdict' is a required property",
            "(root): 'version' is a required property",
        ],
    }
    skipped = {
        "productions/the-last-marker/edit/edit-decision-list.json",
        "productions/the-last-marker/seedance-output/cost-report.json",
    }

    assert set(by_path) == passed | set(known) | skipped
    for path in passed:
        assert by_path[path].status == "pass", path
    for path, errors in known.items():
        assert by_path[path].status == "known"
        assert by_path[path].errors == errors
    for path in skipped:
        assert by_path[path].status == "skip"
    assert audit_exit_code(items) == 0
    report = format_audit(items)
    assert "3 passed" in report
    assert "4 known mismatches" in report
    assert "0 failed" in report


def test_cli_audit_exits_zero_and_a_bad_file_exits_one(tmp_path):
    root = repo_root()
    audit = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "validate-schema.py"),
            "--production",
            str(root / "productions" / "the-last-marker"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert audit.returncode == 0, audit.stderr
    assert "PASS" in audit.stdout
    assert "KNOWN" in audit.stdout

    bad = tmp_path / "shot-list.json"
    bad.write_text("{}\n", encoding="utf-8")
    failed = subprocess.run(
        [sys.executable, str(root / "scripts" / "validate-schema.py"), str(bad)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode == 1
    assert "FAIL" in failed.stdout
    assert "total_shots" in failed.stdout
