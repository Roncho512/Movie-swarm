"""The operating guide names commands that run, offline, on Harbor Night."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from movie_swarm.paths import repo_root


def _run(args: list[str], folder: Path, *, ok: set[int] = frozenset({0})) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        ["python3", *args],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode in ok, completed.stdout + completed.stderr
    return completed


def test_start_here_is_linked_and_its_commands_run(tmp_path: Path):
    root = repo_root()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert readme.splitlines()[4] == "New to a film, or coming back after a long gap? Read [START-HERE.md](START-HERE.md)."
    guide = (root / "START-HERE.md").read_text(encoding="utf-8")
    assert "tools/budget-calculator/index.html" in guide
    assert (root / "tools" / "budget-calculator" / "index.html").is_file()
    for line in guide.splitlines():
        if "python3 scripts/" not in line:
            continue
        script = line.split("python3 ")[1].split()[0]
        assert (root / script).is_file(), script

    harbor = tmp_path / "harbor-night"
    shutil.copytree(root / "tests" / "fixtures" / "harbor-night", harbor)
    new_film = tmp_path / "new-film"
    (new_film / "screenplay").mkdir(parents=True)
    shutil.copy(harbor / "screenplay" / "harbor-night.md", new_film / "screenplay" / "harbor-night.md")

    intake = _run(
        [
            "scripts/director.py",
            "--production",
            str(new_film),
            "--run",
            "guide-1",
            "--offline",
            "intake",
            "--screenplay",
            str(new_film / "screenplay" / "harbor-night.md"),
        ],
        new_film,
    )
    assert "Draft treatment" in intake.stdout
    assert (new_film / "treatment" / "treatment.json").is_file()

    budget = _run(
        [
            "scripts/line-producer.py",
            "--production",
            str(harbor),
            "budget",
            "--write",
            "--total",
            "500",
            "--trailer",
            "off",
            "--contingency",
            "0",
        ],
        harbor,
    )
    assert "Wrote" in budget.stdout
    assert (harbor / "budget.json").is_file()

    _run(["scripts/line-producer.py", "--production", str(harbor), "--run", "guide-1", "start"], harbor)
    stopped = _run(
        ["scripts/studio.py", "--production", str(harbor), "--run", "guide-1"],
        harbor,
        ok={2},
    )
    assert "treatment" in stopped.stdout
    _run(
        [
            "scripts/line-producer.py",
            "--production",
            str(harbor),
            "--run",
            "guide-1",
            "approve-gate",
            "--stage",
            "treatment",
            "--decision",
            "approved",
            "--by",
            "ron",
            "--note",
            "The treatment can proceed.",
        ],
        harbor,
    )
    previs = _run(
        ["scripts/studio.py", "--production", str(harbor), "--run", "guide-1"],
        harbor,
        ok={2},
    )
    assert "previs" in previs.stdout
    shot = _run(
        [
            "scripts/line-producer.py",
            "--production",
            str(harbor),
            "--run",
            "guide-1",
            "test-shot",
            "--shot",
            "s01-sh01",
        ],
        harbor,
    )
    assert "Offline is the default" in shot.stdout
    _run(
        [
            "scripts/line-producer.py",
            "--production",
            str(harbor),
            "--run",
            "guide-1",
            "spend",
            "--stage",
            "director",
            "--amount",
            "20",
            "--description",
            "draft",
            "--kind",
            "generation",
        ],
        harbor,
    )
    paused = _run(
        [
            "scripts/line-producer.py",
            "--production",
            str(harbor),
            "--run",
            "guide-1",
            "spend",
            "--stage",
            "director",
            "--amount",
            "1",
            "--description",
            "one more pass",
            "--kind",
            "generation",
        ],
        harbor,
        ok={2},
    )
    assert "req-001" in paused.stdout
    decided = _run(
        [
            "scripts/line-producer.py",
            "--production",
            str(harbor),
            "--run",
            "guide-1",
            "decide",
            "--request",
            "req-001",
            "--decision",
            "approved",
            "--by",
            "ron",
            "--note",
            "Allow it.",
        ],
        harbor,
    )
    assert "budget was not changed" in decided.stdout.casefold() or "Approved overage" in decided.stdout
    skipped = _run(
        [
            "scripts/director.py",
            "--production",
            str(harbor),
            "--run",
            "guide-1",
            "--offline",
            "dispatch",
            "--agent",
            "trailer-editor",
            "--crew-command",
            "research",
            "--estimate",
            "0",
        ],
        harbor,
    )
    assert "off" in skipped.stdout.casefold()
    assert not (harbor / "marketing").exists()
