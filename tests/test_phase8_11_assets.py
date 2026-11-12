"""Phase 8.11: doctor names where the asset root came from, and not the path."""

from __future__ import annotations

import os

import pytest

from movie_swarm.doctor import main, report
from movie_swarm.paths import repo_root


TOKEN = "asset-root-token-9f3a"


@pytest.fixture(autouse=True)
def _restore_asset_root(monkeypatch):
    """A ``.env`` load writes the process environment. Put it back afterwards.

    ``monkeypatch.delenv`` does not record an undo when the name is already
    absent, so a later ``load_env`` would leak into the next test.
    """
    name = "MOVIE_SWARM_ASSET_ROOT"
    if name not in os.environ:
        monkeypatch.setitem(os.environ, name, "placeholder")
        monkeypatch.delitem(os.environ, name)
    yield


def test_dotenv_is_named_when_the_shell_did_not_set_the_root(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MOVIE_SWARM_ASSET_ROOT", raising=False)
    drive = tmp_path / TOKEN
    drive.mkdir()
    env = tmp_path / ".env"
    env.write_text(f"MOVIE_SWARM_ASSET_ROOT={drive}\n", encoding="utf-8")
    code = main([], env_path=env)
    text = capsys.readouterr().out
    assert code == 0
    assert "asset root: set from .env (MOVIE_SWARM_ASSET_ROOT), folder exists" in text
    assert TOKEN not in text
    assert str(drive) not in text


def test_the_shell_wins_and_a_missing_folder_is_reported(tmp_path, monkeypatch, capsys):
    shell_dir = tmp_path / "from-shell-token"
    shell_dir.mkdir()
    file_dir = tmp_path / "from-file-token"
    env = tmp_path / ".env"
    env.write_text(f"MOVIE_SWARM_ASSET_ROOT={file_dir}\n", encoding="utf-8")
    monkeypatch.setenv("MOVIE_SWARM_ASSET_ROOT", str(shell_dir))
    code = main([], env_path=env)
    text = capsys.readouterr().out
    assert code == 0
    assert "asset root: set from shell (MOVIE_SWARM_ASSET_ROOT), folder exists" in text
    assert "from-shell-token" not in text
    assert "from-file-token" not in text

    monkeypatch.setenv("MOVIE_SWARM_ASSET_ROOT", str(tmp_path / "missing-folder-token"))
    lines, _failed = report(env_file=tmp_path / "missing.env", loaded_names=[])
    report_text = "\n".join(lines)
    assert "asset root: set from shell (MOVIE_SWARM_ASSET_ROOT), folder missing" in report_text
    assert "missing-folder-token" not in report_text


def test_config_is_the_source_when_the_environment_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("MOVIE_SWARM_ASSET_ROOT", raising=False)
    drive = tmp_path / TOKEN
    drive.mkdir()
    monkeypatch.setattr(
        "movie_swarm.doctor.load_asset_config",
        lambda config_path=None: {"asset_root": str(drive)},
    )
    lines, failed = report(env_file=tmp_path / "missing.env", loaded_names=[])
    text = "\n".join(lines)
    assert failed is False
    assert "asset root: set from config/assets.json, folder exists" in text
    assert TOKEN not in text


def test_the_example_env_names_the_asset_root_and_leaves_it_empty():
    text = (repo_root() / ".env.example").read_text(encoding="utf-8")
    assert ".zshrc" in text
    assignments = [
        line for line in text.splitlines() if line.startswith("MOVIE_SWARM_ASSET_ROOT=")
    ]
    assert assignments == ["MOVIE_SWARM_ASSET_ROOT="]
    guide = (repo_root() / "START-HERE.md").read_text(encoding="utf-8")
    assert "MOVIE_SWARM_ASSET_ROOT" in guide
    assert ".zshrc" in guide
    assert "does not print the path" in guide
