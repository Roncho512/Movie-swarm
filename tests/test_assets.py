"""Asset root defaults to the production folder and can be pointed elsewhere."""

from __future__ import annotations

import json

from movie_swarm.assets import ASSET_ROOT_ENV, configured_asset_root, resolve_asset
from movie_swarm.paths import repo_root


def test_default_stays_inside_the_production_folder(tmp_path, monkeypatch):
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    production = tmp_path / "the-last-marker"
    production.mkdir()
    resolved = resolve_asset(production, "clips/selected/s01-sh01.mp4")
    assert resolved == (production / "clips/selected/s01-sh01.mp4").resolve()
    assert configured_asset_root() is None


def test_environment_variable_wins_over_the_config_file(tmp_path, monkeypatch):
    drive = tmp_path / "external"
    config = {"asset_root": str(tmp_path / "from-config"), "env_var": ASSET_ROOT_ENV}
    config_path = tmp_path / "assets.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv(ASSET_ROOT_ENV, str(drive))

    production = tmp_path / "the-last-marker"
    resolved = resolve_asset(production, "edit/export/final.mp4", config_path=config_path)
    assert resolved == (drive / "the-last-marker" / "edit/export/final.mp4").resolve()


def test_config_file_is_used_when_the_environment_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    drive = tmp_path / "drive"
    config_path = tmp_path / "assets.json"
    config_path.write_text(
        json.dumps({"asset_root": str(drive), "env_var": ASSET_ROOT_ENV}),
        encoding="utf-8",
    )
    production = repo_root() / "productions" / "the-last-marker"
    resolved = resolve_asset(production, "audio/sfx/engine-healthy.mp3", config_path=config_path)
    assert resolved == (drive / "the-last-marker" / "audio/sfx/engine-healthy.mp3").resolve()


def test_path_cannot_escape_the_root(tmp_path, monkeypatch):
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    production = tmp_path / "the-last-marker"
    try:
        resolve_asset(production, "../secrets.txt")
    except ValueError as exc:
        assert "inside the production folder" in str(exc)
    else:
        raise AssertionError("expected an escape path to be refused")


def test_shipped_config_keeps_files_in_the_repo(monkeypatch):
    monkeypatch.delenv(ASSET_ROOT_ENV, raising=False)
    assert configured_asset_root() is None
    production = repo_root() / "productions" / "the-last-marker"
    resolved = resolve_asset(production, "shot-lists/shot-list.json")
    assert resolved == (production / "shot-lists/shot-list.json").resolve()
    assert resolved.is_file()
