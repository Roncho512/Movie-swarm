"""Films live outside the studio repo. Harbor Night can run from a temp folder."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from pathlib import Path

from movie_swarm.assets import ASSET_ROOT_ENV, resolve_asset
from movie_swarm.films import (
    CHECKSUM_NAME,
    FILMS_ROOT_ENV,
    FilmsError,
    create_film,
    export_film,
    file_checksums,
    resolve_production,
)
from movie_swarm.paths import repo_root
from movie_swarm.validate import audit_production


def _outside(path) -> None:
    resolved = path.resolve()
    root = repo_root().resolve()
    assert root != resolved
    assert root not in resolved.parents


def test_a_name_uses_the_films_root_and_not_the_repo(tmp_path, monkeypatch):
    films = tmp_path / "films"
    films.mkdir()
    monkeypatch.setenv(FILMS_ROOT_ENV, str(films))
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    resolved = resolve_production("harbor-night")
    assert resolved == films / "harbor-night"
    _outside(films)
    archive = repo_root() / "productions" / "the-last-marker"
    named = resolve_production("the-last-marker")
    assert named == films / "the-last-marker"
    assert named != archive


def test_an_absolute_path_outside_the_repo_is_kept(tmp_path, monkeypatch):
    monkeypatch.setenv(FILMS_ROOT_ENV, str(tmp_path / "unused"))
    production = tmp_path / "elsewhere" / "harbor-night"
    production.mkdir(parents=True)
    resolved = resolve_production(str(production))
    assert resolved == production
    _outside(resolved)


def test_a_relative_path_is_not_rewritten_into_the_films_root(tmp_path, monkeypatch):
    monkeypatch.setenv(FILMS_ROOT_ENV, str(tmp_path / "films"))
    resolved = resolve_production("productions/the-last-marker")
    assert resolved == Path("productions/the-last-marker")


def test_the_asset_root_is_the_films_root_when_the_films_root_is_unset(tmp_path, monkeypatch):
    monkeypatch.delenv(FILMS_ROOT_ENV, raising=False)
    drive = tmp_path / "drive"
    drive.mkdir()
    monkeypatch.setenv(ASSET_ROOT_ENV, str(drive))
    assert resolve_production("harbor-night") == drive / "harbor-night"


def test_a_name_without_a_films_root_is_refused(monkeypatch):
    monkeypatch.delenv(FILMS_ROOT_ENV, raising=False)
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    monkeypatch.setattr("movie_swarm.films.load_asset_config", lambda config_path=None: {"asset_root": None, "films_root": None})
    try:
        resolve_production("harbor-night")
    except FilmsError as exc:
        assert "MOVIE_SWARM_FILMS_ROOT" in str(exc)
        assert "/" not in str(exc)
    else:
        raise AssertionError("a bare name should need a films root")


def test_config_films_root_is_used_when_the_environment_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv(FILMS_ROOT_ENV, raising=False)
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    films = tmp_path / "from-config"
    films.mkdir()
    monkeypatch.setattr(
        "movie_swarm.films.load_asset_config",
        lambda config_path=None: {"films_root": str(films), "asset_root": str(tmp_path / "asset")},
    )
    assert resolve_production("harbor-night") == films / "harbor-night"


def test_media_for_an_outside_production_stays_out_of_the_repo(tmp_path, monkeypatch):
    films = tmp_path / "films"
    production = films / "harbor-night"
    production.mkdir(parents=True)
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    inside = resolve_asset(production, "clips/selected/s01-sh01.mp4")
    assert inside == (production / "clips/selected/s01-sh01.mp4").resolve()
    _outside(inside)

    drive = tmp_path / "drive"
    monkeypatch.setenv(ASSET_ROOT_ENV, str(drive))
    parked = resolve_asset(production, "edit/export/final.mp4")
    assert parked == (drive / "harbor-night" / "edit/export/final.mp4").resolve()
    _outside(parked)

    monkeypatch.setenv(ASSET_ROOT_ENV, str(films))
    same_folder = resolve_asset(production, "delivery/master.mp4")
    assert same_folder == (production / "delivery/master.mp4").resolve()


def test_an_outside_copy_keeps_the_known_schema_mismatches(tmp_path):
    source = repo_root() / "productions" / "the-last-marker" / "audio" / "audio-manifest.json"
    production = tmp_path / "the-last-marker"
    target = production / "audio"
    target.mkdir(parents=True)
    shutil.copy(source, target / "audio-manifest.json")
    _outside(production)
    items = audit_production(production)
    assert len(items) == 1
    item = items[0]
    assert item.status == "known"
    assert item.path == "the-last-marker/audio/audio-manifest.json"
    assert str(tmp_path) not in item.path
    assert item.schema_name == "audio-manifest.schema.json"


def test_harbor_night_runs_from_a_folder_outside_the_repo(tmp_path):
    films = tmp_path / "films"
    shutil.copytree(repo_root() / "tests" / "fixtures" / "harbor-night", films / "harbor-night")
    production = films / "harbor-night"
    _outside(production)
    env = os.environ.copy()
    env[FILMS_ROOT_ENV] = str(films)
    env.pop(ASSET_ROOT_ENV, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    root = repo_root()
    by_name = subprocess.run(
        [sys.executable, str(root / "scripts" / "studio.py"), "--production", "harbor-night", "--run", "outside-1"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert by_name.returncode == 2, by_name.stdout + by_name.stderr
    assert "treatment" in by_name.stdout
    assert "$0.00" in by_name.stdout
    run_state = production / "runs" / "outside-1" / "run-state.json"
    assert run_state.is_file()
    assert not (root / "productions" / "harbor-night").exists()
    _outside(run_state)

    by_path = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "line-producer.py"),
            "--production",
            str(production),
            "--run",
            "outside-1",
            "status",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert by_path.returncode == 0, by_path.stdout + by_path.stderr
    assert "treatment" in by_path.stdout.casefold()
    items = audit_production(production)
    assert items
    assert all(str(tmp_path) not in item.path for item in items)
    assert any(item.schema_name and item.status == "pass" for item in items)
    assert all(item.status != "fail" or "No schema named" not in " ".join(item.errors) for item in items)


def test_a_relative_screenplay_is_read_from_the_outside_production(tmp_path, monkeypatch):
    films = tmp_path / "films"
    films.mkdir()
    monkeypatch.setenv(FILMS_ROOT_ENV, str(films))
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    create_film("night-shift")
    production = films / "night-shift"
    screenplay = production / "screenplay"
    screenplay.mkdir()
    shutil.copy(
        repo_root() / "tests" / "fixtures" / "harbor-night" / "screenplay" / "harbor-night.md",
        screenplay / "harbor-night.md",
    )
    from movie_swarm.cli_director import main

    code = main([
        "--production",
        "night-shift",
        "--run",
        "outside-1",
        "--offline",
        "intake",
        "--screenplay",
        "screenplay/harbor-night.md",
    ])
    assert code == 0
    draft = json.loads((production / "treatment" / "treatment.json").read_text(encoding="utf-8"))
    assert draft["status"] == "draft"
    assert (production / "runs" / "outside-1" / "run-state.json").is_file()
    _outside(production)


def test_new_film_flags_a_missing_total_and_can_init_git(tmp_path, monkeypatch):
    films = tmp_path / "films"
    films.mkdir()
    monkeypatch.setenv(FILMS_ROOT_ENV, str(films))
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    folder = create_film("my-film", git=True)
    budget = json.loads((folder / "budget.json").read_text(encoding="utf-8"))
    assert budget["total_usd"] == 500
    assert budget["trailer_on"] is False
    assert budget["contingency_share"] == 10
    assert "Total was not asked" in budget["note"]
    inputs = json.loads((folder / "treatment" / "inputs.json").read_text(encoding="utf-8"))
    assert "logline" in inputs
    assert "approve" in inputs["note"]
    assert "*.mp4" in (folder / ".gitignore").read_text(encoding="utf-8")
    assert (folder / ".git").is_dir()
    remotes = subprocess.run(["git", "-C", str(folder), "remote"], capture_output=True, text=True, check=False)
    assert remotes.stdout.strip() == ""
    _outside(folder)

    asked = create_film("asked-film", total_usd=240)
    asked_budget = json.loads((asked / "budget.json").read_text(encoding="utf-8"))
    assert asked_budget["total_usd"] == 240
    assert "Total asked" in asked_budget["note"]


def test_new_film_refuses_a_root_inside_the_repo(monkeypatch):
    monkeypatch.setenv(FILMS_ROOT_ENV, str(repo_root()))
    try:
        create_film("my-film")
    except FilmsError as exc:
        assert "inside the studio repo" in str(exc)
    else:
        raise AssertionError("a film should not be created inside the studio repo")
    assert not (repo_root() / "my-film").exists()


def test_export_copies_checks_checksums_and_leaves_the_source(tmp_path, monkeypatch):
    films = tmp_path / "films"
    films.mkdir()
    monkeypatch.setenv(FILMS_ROOT_ENV, str(films))
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    source = tmp_path / "in-repo-shape"
    source.mkdir()
    (source / "note.txt").write_text("keep\n", encoding="utf-8")
    nested = source / "treatment"
    nested.mkdir()
    (nested / "inputs.json").write_text("{}\n", encoding="utf-8")
    result = export_film(str(source), "exported-film")
    dest = films / "exported-film"
    assert result["source_remains"] is True
    assert source.is_dir()
    assert (source / "note.txt").read_text(encoding="utf-8") == "keep\n"
    assert (dest / "note.txt").read_text(encoding="utf-8") == "keep\n"
    assert (dest / CHECKSUM_NAME).is_file()
    assert not (source / CHECKSUM_NAME).exists()
    hashes = file_checksums(dest)
    assert all(not key.startswith("productions/") for key in hashes)
    assert "treatment/inputs.json" in hashes
    script = subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "export-film.py"),
            "--from",
            str(source),
            "--to",
            str(films / "second-copy"),
        ],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, FILMS_ROOT_ENV: str(films), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert script.returncode == 0, script.stdout + script.stderr
    assert "source was left in place" in script.stdout
    assert source.is_dir()


def test_new_productions_under_the_repo_are_ignored_except_the_archive():
    root = repo_root()
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "productions/my-film/README.md"],
        cwd=root,
        check=False,
    )
    assert ignored.returncode == 0
    kept = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "productions/the-last-marker/README.md"],
        cwd=root,
        check=False,
    )
    assert kept.returncode == 1
    comment = (root / ".gitignore").read_text(encoding="utf-8")
    assert "MOVIE_SWARM_FILMS_ROOT" in comment


def test_doctor_checks_a_named_production_without_printing_the_path(tmp_path, monkeypatch, capsys):
    films = tmp_path / "films-token-4c1e"
    production = films / "harbor-night"
    production.mkdir(parents=True)
    monkeypatch.setenv(FILMS_ROOT_ENV, str(films))
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    from movie_swarm.doctor import main

    code = main(["--production", "harbor-night"], env_path=tmp_path / "missing.env")
    text = capsys.readouterr().out
    assert code == 0
    assert "production: folder exists" in text
    assert "films root: set from shell (MOVIE_SWARM_FILMS_ROOT), folder exists" in text
    assert "films-token-4c1e" not in text
    assert str(films) not in text


def test_the_archived_readme_points_at_the_films_folder():
    first = (repo_root() / "productions" / "the-last-marker" / "README.md").read_text(encoding="utf-8").splitlines()[0]
    assert first == "Archived copy. The working film lives in the films folder; see START-HERE."
    guide = (repo_root() / "START-HERE.md").read_text(encoding="utf-8")
    assert "## Where films live" in guide
    assert "--production the-last-marker" in guide
    assert "MOVIE_SWARM_FILMS_ROOT" in guide


def test_the_example_env_leaves_the_films_root_empty():
    text = (repo_root() / ".env.example").read_text(encoding="utf-8")
    assignments = [line for line in text.splitlines() if line.startswith("MOVIE_SWARM_FILMS_ROOT=")]
    assert assignments == ["MOVIE_SWARM_FILMS_ROOT="]
