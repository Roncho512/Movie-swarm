"""The CLI loads .env without overriding the shell and without printing values."""

from __future__ import annotations

import os

from movie_swarm.envfile import load_env
from movie_swarm.paths import repo_root


def test_load_env_sets_missing_names_and_does_not_override_or_print(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAL_KEY", "fal-already-set-do-not-leak")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "\n".join([
            "# comment",
            "FAL_KEY=fal-from-file-do-not-leak",
            "ANTHROPIC_API_KEY=\"anthropic-from-file-do-not-leak\"",
            "export ELEVENLABS_API_KEY='eleven-from-file-do-not-leak'",
            "not a pair",
            "",
        ]),
        encoding="utf-8",
    )
    set_names = load_env(path)
    captured = capsys.readouterr()
    assert set_names == ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"]
    assert os.environ["FAL_KEY"] == "fal-already-set-do-not-leak"
    assert os.environ["ANTHROPIC_API_KEY"] == "anthropic-from-file-do-not-leak"
    assert os.environ["ELEVENLABS_API_KEY"] == "eleven-from-file-do-not-leak"
    blob = captured.out + captured.err
    assert "do-not-leak" not in blob
    assert blob == ""


def test_a_missing_env_file_is_fine(tmp_path):
    assert load_env(tmp_path / "missing.env") == []


def test_autoload_stays_off_when_the_suite_skips_the_env_file(tmp_path, monkeypatch):
    """The suite sets MOVIE_SWARM_SKIP_ENV_FILE. A repo .env must not leak in."""
    env = tmp_path / ".env"
    env.write_text("MOVIE_SWARM_ASSET_ROOT=/tmp/should-not-load\n", encoding="utf-8")
    monkeypatch.setattr("movie_swarm.envfile.repo_root", lambda: tmp_path)
    monkeypatch.delenv("MOVIE_SWARM_ASSET_ROOT", raising=False)
    assert load_env() == []
    assert os.environ.get("MOVIE_SWARM_ASSET_ROOT", "") == ""
    assert load_env(env) == ["MOVIE_SWARM_ASSET_ROOT"]
    assert os.environ["MOVIE_SWARM_ASSET_ROOT"] == "/tmp/should-not-load"


def test_every_script_loads_the_env_file():
    scripts = repo_root() / "scripts"
    found = [path.name for path in scripts.glob("*.py")]
    assert found
    for name in found:
        text = (scripts / name).read_text(encoding="utf-8")
        assert "load_env()" in text, name
