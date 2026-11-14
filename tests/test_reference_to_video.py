"""Reference images on a Seedance picture call.

The transport is fake. Nothing here uploads to fal or spends money.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from movie_swarm.http_retry import HttpResult
from movie_swarm.paths import repo_root
from movie_swarm.providers import _default_upload
from movie_swarm.rates import generator_rate, load_rate_card
from movie_swarm.references import prepare_references
from movie_swarm.validate import load_schema, validate_data
from tests.test_phase8_10_fal import FAST_URL, _submit_body
from tests.test_phase8_5 import SECRET, Scripted, _harbor, _open, _settings


FAST_REFERENCE = "bytedance/seedance-2.0/fast/reference-to-video"
STANDARD_REFERENCE = "bytedance/seedance-2.0/reference-to-video"


def _png(folder: Path, relative: str, payload: bytes = b"png") -> None:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write(folder: Path, relative: str, document: dict) -> None:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _row(max_images: int = 9) -> dict:
    row = dict(generator_rate(load_rate_card(), "seedance-2.0-fast"))
    block = dict(row["reference_to_video"])
    block["max_images"] = max_images
    row["reference_to_video"] = block
    return row


def _locks(folder: Path) -> None:
    _png(folder, "characters/ada/front.png")
    _png(folder, "characters/ada/side.png")
    _png(folder, "characters/beau/front.png")
    _png(folder, "locations/dock/wide.png")
    _png(folder, "locations/dock/detail.png")
    _png(folder, "props/scarf/face.png")
    _png(folder, "props/scarf/back.png")
    _png(folder, "shots/extra.png")
    _png(folder, "shots/second.png")
    _write(folder, "characters/character-lock.json", {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "status": "locked",
        "characters": [
            {
                "character_id": "ada",
                "name": "Ada",
                "locked_spec": "The face in the photographs.",
                "reference_images": ["characters/ada/front.png", "characters/ada/side.png"],
            },
            {
                "character_id": "beau",
                "name": "Beau",
                "locked_spec": "The face in the photograph.",
                "reference_images": ["characters/beau/front.png"],
            },
        ],
    })
    _write(folder, "locations/location-lock.json", {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "status": "locked",
        "locations": [
            {
                "location_id": "dock",
                "name": "The dock",
                "aliases": ["harbor"],
                "scene_ids": ["s01"],
                "locked_spec": "The place in the photographs.",
                "reference_images": ["locations/dock/wide.png", "locations/dock/detail.png"],
            }
        ],
    })
    _write(folder, "props/hero-props.json", {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "status": "locked",
        "props": [
            {
                "prop_id": "red-scarf",
                "name": "Red scarf",
                "locked_spec": "Wool, red.",
                "reference_images": ["props/scarf/face.png", "props/scarf/back.png"],
                "attributes": [],
            }
        ],
    })


def _board(folder: Path, **shot) -> None:
    frame = {
        "shot_id": "s01-sh01",
        "scene_id": "s01",
        "duration_seconds": 4,
        "board_prompt": "Ada stands on the dock.",
        "props_in_frame": ["red-scarf"],
        "characters_in_shot": ["ada", "beau"],
        "location_id": "dock",
        "reference_images": ["shots/extra.png", "shots/second.png"],
    }
    frame.update(shot)
    _write(folder, "storyboard/storyboard.json", {"frames": [frame]})
    treatment = json.loads((folder / "treatment" / "treatment.json").read_text(encoding="utf-8"))
    treatment["deliverables"]["aspect_ratio"] = "21:9"
    _write(folder, "treatment/treatment.json", treatment)


def _film(tmp_path: Path) -> Path:
    folder = _harbor(tmp_path)
    _locks(folder)
    _board(folder)
    return folder


def _uploader(calls: list):
    def upload(path: Path) -> str:
        calls.append(path)
        return f"https://fal.example/{path.name}"

    return upload


def test_published_reference_prices_match_the_pages():
    card = load_rate_card()
    fast = generator_rate(card, "seedance-2.0-fast")
    full = generator_rate(card, "seedance-2.0")
    routing = json.loads((repo_root() / "config" / "model-routing.json").read_text(encoding="utf-8"))
    endpoints = routing["roles"]["production"]["endpoints"]
    assert fast["usd_per_second"] == "0.2419"
    assert fast["reference_to_video"]["usd_per_second"] == "0.2419"
    assert fast["reference_to_video"]["max_images"] == 9
    assert fast["reference_to_video"]["max_bytes"] == 31457280
    assert fast["reference_to_video"]["endpoint"] == endpoints["fast-reference-to-video"]
    assert fast["reference_to_video"]["image_field"] == "image_urls"
    assert full["usd_per_second"] == "0.3034"
    assert full["reference_to_video"]["usd_per_second"] == "0.3024"
    assert full["reference_to_video"]["endpoint"] == endpoints["reference-to-video"]
    assert "jpeg" in fast["reference_to_video"]["formats"]
    assert "png" in fast["reference_to_video"]["formats"]
    assert "webp" in fast["reference_to_video"]["formats"]


def test_priority_takes_one_image_per_subject_before_a_second(tmp_path):
    folder = _film(tmp_path)
    from movie_swarm.generation import load_shots

    shot = load_shots(folder)[0][0]
    prepared = prepare_references(folder, shot, shot["prompt"], _row(4))
    assert [item.relative for item in prepared.chosen] == [
        "characters/ada/front.png",
        "characters/beau/front.png",
        "locations/dock/wide.png",
        "props/scarf/face.png",
    ]
    assert [item.role for item in prepared.chosen] == [
        "character face",
        "character face",
        "location",
        "prop",
    ]
    assert [item.token for item in prepared.chosen] == ["@Image1", "@Image2", "@Image3", "@Image4"]
    assert any("shots/extra.png" in note for note in prepared.skipped)
    full = prepare_references(folder, shot, shot["prompt"], _row(9))
    assert [item.relative for item in full.chosen] == [
        "characters/ada/front.png",
        "characters/beau/front.png",
        "locations/dock/wide.png",
        "props/scarf/face.png",
        "shots/extra.png",
        "characters/ada/side.png",
        "locations/dock/detail.png",
        "props/scarf/back.png",
        "shots/second.png",
    ]


def test_a_scene_match_pulls_the_location_when_the_shot_does_not_name_one(tmp_path):
    folder = _film(tmp_path)
    _board(
        folder,
        characters_in_shot=["ada"],
        location_id="",
        reference_images=[],
        reference_from={"characters": ["ada"], "props": []},
    )
    from movie_swarm.generation import load_shots

    shot = load_shots(folder)[0][0]
    prepared = prepare_references(folder, shot, "A wide view.", _row())
    assert [item.relative for item in prepared.chosen] == [
        "characters/ada/front.png",
        "locations/dock/wide.png",
        "characters/ada/side.png",
        "locations/dock/detail.png",
    ]


def test_paths_resolve_from_the_film_folder_not_the_working_directory(tmp_path, monkeypatch):
    folder = _film(tmp_path / "reel")
    monkeypatch.chdir(tmp_path)
    from movie_swarm.generation import load_shots

    shot = load_shots(folder)[0][0]
    prepared = prepare_references(folder, shot, shot["prompt"], _row(1))
    assert prepared.chosen[0].path == (folder / "characters" / "ada" / "front.png").resolve()
    assert prepared.chosen[0].relative == "characters/ada/front.png"


def test_a_missing_file_is_skipped_and_an_outside_path_is_not_sent(tmp_path, caplog):
    folder = _film(tmp_path)
    missing = tmp_path / "secret.png"
    missing.write_bytes(b"nope")
    _board(
        folder,
        characters_in_shot=["ada"],
        location_id="",
        reference_images=["characters/ada/missing.png", "../secret.png", "notes/plain.txt"],
        reference_from={"characters": ["ada"], "location": "", "props": []},
    )
    _png(folder, "notes/plain.txt", b"text")
    from movie_swarm.generation import load_shots

    shot = load_shots(folder)[0][0]
    with caplog.at_level(logging.WARNING, logger="movie_swarm.references"):
        prepared = prepare_references(folder, shot, "Ada stands on the dock.", _row())
    relatives = [item.relative for item in prepared.chosen]
    assert relatives[0] == "characters/ada/front.png"
    assert "characters/ada/missing.png" not in relatives
    assert all(item.path is None or folder.resolve() in item.path.parents for item in prepared.chosen)
    assert any("missing.png" in note for note in prepared.skipped)
    assert any("outside the film folder" in note for note in prepared.skipped)
    assert any("suffix" in note for note in prepared.skipped)
    assert "Skipped missing reference" in caplog.text
    assert not any(item.path == missing.resolve() for item in prepared.chosen if item.path)


def test_a_draft_lock_and_an_oversized_file_are_not_sent(tmp_path):
    folder = _film(tmp_path)
    lock = json.loads((folder / "locations" / "location-lock.json").read_text(encoding="utf-8"))
    lock["status"] = "draft"
    _write(folder, "locations/location-lock.json", lock)
    _png(folder, "characters/ada/front.png", b"12345")
    from movie_swarm.generation import load_shots

    shot = load_shots(folder)[0][0]
    row = _row(9)
    row["reference_to_video"] = dict(row["reference_to_video"])
    row["reference_to_video"]["max_bytes"] = 4
    prepared = prepare_references(folder, shot, shot["prompt"], row)
    assert "locations/dock/wide.png" not in [item.relative for item in prepared.chosen]
    assert any("front.png" in note and "byte limit" in note for note in prepared.skipped)


def test_a_prompt_that_already_names_the_images_is_left_alone(tmp_path):
    folder = _film(tmp_path)
    _board(
        folder,
        characters_in_shot=["ada"],
        location_id="",
        reference_images=[],
        reference_from={"characters": ["ada"], "location": "", "props": []},
        board_prompt="@Image1 is the face.",
    )
    from movie_swarm.generation import load_shots

    shot = load_shots(folder)[0][0]
    prepared = prepare_references(folder, shot, shot["prompt"], _row(1))
    assert prepared.prompt == "@Image1 is the face."
    assert prepared.chosen[0].token == "@Image1"


def test_a_shot_list_fills_character_ids_the_frame_left_off(tmp_path):
    folder = _harbor(tmp_path)
    _write(folder, "storyboard/shot-list.json", {
        "production_id": "harbor-night",
        "version": "1.0.0",
        "total_shots": 1,
        "created_at": "2026-11-14T00:00:00Z",
        "shots": [
            {
                "shot_id": "s01-sh01",
                "scene_number": 1,
                "shot_number": 1,
                "shot_type": "wide",
                "description": "Ada on the dock.",
                "generation_prompt": "Ada on the dock.",
                "tool_routing": {"primary_tool": "seedance-2.0", "rationale": "Test."},
                "target_duration_seconds": 4,
                "characters_in_shot": ["ada"],
                "location_id": "dock",
            }
        ],
    })
    from movie_swarm.generation import load_shots

    shot = load_shots(folder)[0][0]
    assert shot["characters_in_shot"] == ["ada"]
    assert shot["location_id"] == "dock"


def test_the_quote_prices_reference_to_video_and_does_not_call_out(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _film(tmp_path)
    from movie_swarm.providers import run_test_shot

    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("movie_swarm.providers._default_upload", boom)
    monkeypatch.setattr("urllib.request.urlopen", boom)
    producer = _open(folder)
    transport = Scripted([])
    uploads = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=False,
        settings=_settings(transport, uploader=_uploader(uploads)),
        model="seedance-2.0-fast",
        announce=lambda _text: None,
    )
    assert transport.calls == []
    assert uploads == []
    assert result["sent"] is False
    assert "Nothing was sent." in result["message"]
    assert result["status"] == "offline"
    assert "estimated cost $0.9676" in result["quote"]
    assert FAST_REFERENCE in result["quote"]
    assert "$0.2419 per second" in result["quote"]
    assert "characters/ada/front.png" in result["quote"]
    assert "locations/dock/wide.png" in result["quote"]
    assert "does not upload" in result["quote"]
    assert SECRET not in result["quote"]

    standard = run_test_shot(
        producer,
        "s01-sh01",
        live=False,
        settings=_settings(Scripted([]), uploader=_uploader([])),
        model="seedance-2.0",
        announce=lambda _text: None,
    )
    assert "estimated cost $1.2096" in standard["quote"]
    assert STANDARD_REFERENCE in standard["quote"]
    assert "$0.3024 per second" in standard["quote"]
    assert "estimated cost $1.2136" not in standard["quote"]


def test_a_shot_without_references_stays_on_text_to_video(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _harbor(tmp_path)
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted([
        _submit_body(),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps({"video": {"url": "https://cdn.example/clip.mp4"}}).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ])
    uploads = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport, uploader=_uploader(uploads)),
        model="seedance-2.0-fast",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    body = transport.calls[0]["body"]
    assert transport.calls[0]["url"] == FAST_URL
    assert "image_urls" not in body
    assert set(body) >= {"prompt", "duration", "resolution", "aspect_ratio", "generate_audio"}
    assert body["duration"] == "4"
    assert body["resolution"] == "720p"
    assert body["aspect_ratio"] == "16:9"
    assert body["generate_audio"] is True
    assert uploads == []
    assert "Reference endpoint" not in result["quote"]


def test_a_live_call_uploads_local_files_and_posts_reference_to_video(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _film(tmp_path / "films" / "reel")
    monkeypatch.chdir(tmp_path)
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    reference_url = f"https://queue.fal.run/{FAST_REFERENCE}"
    transport = Scripted([
        _submit_body(),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps({"video": {"url": "https://cdn.example/clip.mp4"}}).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ])
    uploads = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport, uploader=_uploader(uploads)),
        model="seedance-2.0-fast",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    post = transport.calls[0]
    assert post["url"] == reference_url
    body = post["body"]
    assert "input" not in body
    assert body["aspect_ratio"] == "21:9"
    assert body["generate_audio"] is True
    assert body["duration"] == "4"
    assert body["resolution"] == "720p"
    assert body["image_urls"] == [f"https://fal.example/{path.name}" for path in uploads]
    assert body["image_urls"][0] == "https://fal.example/front.png"
    assert "@Image1" in body["prompt"]
    assert "character face (Ada)" in body["prompt"]
    assert all(path.is_relative_to(folder.resolve()) for path in uploads)
    assert len(uploads) == 9
    assert SECRET not in json.dumps(body)


def test_a_missing_reference_does_not_stop_the_call(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _film(tmp_path)
    _board(
        folder,
        characters_in_shot=["ada"],
        location_id="",
        reference_images=["characters/ada/missing.png"],
        reference_from={"characters": ["ada"], "location": "", "props": []},
    )
    (folder / "characters" / "ada" / "side.png").unlink()
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted([
        _submit_body(),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps({"video": {"url": "https://cdn.example/clip.mp4"}}).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ])
    uploads = []
    with caplog.at_level(logging.WARNING, logger="movie_swarm.references"):
        result = run_test_shot(
            producer,
            "s01-sh01",
            live=True,
            settings=_settings(transport, uploader=_uploader(uploads)),
            model="seedance-2.0-fast",
            announce=lambda _text: None,
        )
    assert result["status"] == "generated", result["message"]
    assert uploads == [(folder / "characters" / "ada" / "front.png").resolve()]
    assert transport.calls[0]["body"]["image_urls"] == ["https://fal.example/front.png"]
    assert "missing.png" in caplog.text


def test_the_default_uploader_calls_fal_client_upload_file(tmp_path, monkeypatch):
    path = tmp_path / "front.png"
    path.write_bytes(b"png")
    seen = []

    class Fake:
        @staticmethod
        def upload_file(file_path):
            seen.append(file_path)
            return "https://fal.example/front.png"

    monkeypatch.setitem(__import__("sys").modules, "fal_client", Fake)
    assert _default_upload(path) == "https://fal.example/front.png"
    assert seen == [path]


def test_location_and_character_locks_match_their_schemas():
    location = {
        "version": "1.0.0",
        "production_id": "reel",
        "status": "locked",
        "locations": [
            {
                "location_id": "dock",
                "name": "The dock",
                "scene_ids": ["s01"],
                "locked_spec": "The place in the photographs.",
                "reference_images": ["locations/dock/wide.png"],
            }
        ],
    }
    character = {
        "version": "1.0.0",
        "production_id": "reel",
        "status": "locked",
        "characters": [
            {
                "character_id": "ada",
                "name": "Ada",
                "locked_spec": "The face in the photograph.",
                "reference_images": ["characters/ada/front.png"],
            }
        ],
    }
    assert validate_data(location, load_schema("location-lock")) == []
    assert validate_data(character, load_schema("character-lock")) == []
