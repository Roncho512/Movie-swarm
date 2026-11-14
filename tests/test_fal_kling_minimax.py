"""Kling 4.0 and MiniMax H3 Max picture calls.

The transport is fake. Nothing here uploads to fal or spends money.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.duration import clip_lengths, request_value
from movie_swarm.money import as_money
from movie_swarm.http_retry import HttpResult
from movie_swarm.paths import repo_root
from movie_swarm.providers import _video_request_refusal
from movie_swarm.rates import generator_rate, load_rate_card, usd_per_second
from movie_swarm.references import fit_aspect, prepare_references
from tests.test_phase8_10_fal import _row
from tests.test_phase8_5 import SECRET, Scripted, _harbor, _open, _settings
from tests.test_reference_to_video import _board, _film, _png, _write


FAL_QUEUE = "https://queue.fal.run"
KLING_TEXT = "kling/v4/text-to-video"
KLING_IMAGE = "kling/v4/image-to-video"
KLING_REFERENCE = "kling/v4/reference-to-video"
MINIMAX_TEXT = "minimax/h3-max/text-to-video"
MINIMAX_IMAGE = "minimax/h3-max/image-to-video"
MINIMAX_REFERENCE = "minimax/h3-max/reference-to-video"


def _done(endpoint: str) -> list[HttpResult]:
    status = f"{FAL_QUEUE}/{endpoint}/requests/job-1/status"
    result = f"{FAL_QUEUE}/{endpoint}/requests/job-1"
    return [
        HttpResult(200, json.dumps({
            "request_id": "job-1",
            "status_url": status,
            "response_url": result,
        }).encode()),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps({"video": {"url": "https://cdn.example/clip.mp4"}}).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ]


def _uploader(folder: Path, calls: list):
    root = folder.resolve()

    def upload(path: Path) -> str:
        calls.append(path)
        relative = path.resolve().relative_to(root).as_posix()
        return f"https://fal.example/{relative}"

    return upload


def _shot(folder: Path) -> dict:
    from movie_swarm.generation import load_shots

    return load_shots(folder)[0][0]


def _aspect(folder: Path, ratio: str) -> None:
    path = folder / "treatment" / "treatment.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["deliverables"]["aspect_ratio"] = ratio
    path.write_text(json.dumps(document), encoding="utf-8")


def test_published_prices_and_endpoints_match_the_pages():
    card = load_rate_card()
    routing = json.loads((repo_root() / "config" / "model-routing.json").read_text(encoding="utf-8"))
    endpoints = routing["roles"]["production"]["endpoints"]
    kling = generator_rate(card, "kling-4.0")
    mini = generator_rate(card, "minimax-h3-max")
    seedance = generator_rate(card, "seedance-2.0")
    fast = generator_rate(card, "seedance-2.0-fast")

    assert routing["roles"]["production"]["model"] == "seedance-2.0"
    assert routing["roles"]["production"]["tiers"]["better"] == "seedance-2.0-fast"
    assert routing["roles"]["production"]["tiers"]["best"] == "seedance-2.0"
    assert seedance["endpoint"] == "bytedance/seedance-2.0/text-to-video"
    assert seedance["usd_per_second"] == "0.3034"
    assert seedance["reference_to_video"]["usd_per_second"] == "0.3024"
    assert fast["usd_per_second"] == "0.2419"
    assert fast["reference_to_video"]["endpoint"] == endpoints["fast-reference-to-video"]

    assert kling["endpoint"] == endpoints["kling-text-to-video"] == KLING_TEXT
    assert kling["image_to_video"]["endpoint"] == endpoints["kling-image-to-video"] == KLING_IMAGE
    assert kling["reference_to_video"]["endpoint"] == endpoints["kling-reference-to-video"] == KLING_REFERENCE
    assert kling["usd_per_second"] == "0.157"
    assert kling["resolution"] == "720p"
    assert kling["resolution_prices"] == {"720p": "0.157", "1080p": "0.235"}
    assert usd_per_second(kling) == usd_per_second({"resolution": "720p", "resolution_prices": kling["resolution_prices"], "usd_per_second": "0"})
    dear = dict(kling)
    dear["resolution"] = "1080p"
    assert usd_per_second(dear) == usd_per_second({"usd_per_second": "0.235"})
    assert kling["reference_to_video"]["resolution_prices"]["1080p"] == "0.235"
    assert kling["reference_to_video"]["video_reference_usd_per_second"] == {"720p": "0.094", "1080p": "0.141"}
    assert kling["reference_to_video"]["max_images"] == 10
    assert kling["reference_to_video"]["max_elements"] == 7
    assert kling["reference_to_video"]["max_angles"] == 3
    assert kling["reference_to_video"]["max_bytes"] == 31457280
    assert "21:9" in kling["aspect_ratios"]
    assert "auto" not in kling["aspect_ratios"]
    assert "auto" in kling["reference_to_video"]["aspect_ratios"]
    assert kling["image_to_video"]["aspect_ratios"] == []
    assert kling["min_seconds"] == "3"
    assert kling["max_seconds"] == "30"
    assert kling["duration_format"] == "integer"

    assert mini["endpoint"] == endpoints["minimax-h3-max-text-to-video"] == MINIMAX_TEXT
    assert mini["image_to_video"]["endpoint"] == endpoints["minimax-h3-max-image-to-video"] == MINIMAX_IMAGE
    assert mini["reference_to_video"]["endpoint"] == endpoints["minimax-h3-max-reference-to-video"] == MINIMAX_REFERENCE
    assert mini["resolution_prices"] == {"480P": "0.05", "768P": "0.08", "1080P": "0.16"}
    assert mini["resolution"] == "768P"
    assert usd_per_second(mini) == usd_per_second({"usd_per_second": "0.08"})
    refined = dict(mini)
    refined["resolution"] = "1080P"
    assert usd_per_second(refined) == usd_per_second({"usd_per_second": "0.16"})
    assert mini["reference_to_video"]["max_images"] == 12
    assert mini["reference_to_video"]["included_reference_tokens"] == 4096
    assert mini["reference_to_video"]["included_square_images"] == 4
    assert mini["reference_to_video"]["extra_square_image_usd"] == "0.02048"
    assert mini["reference_to_video"]["image_field"] == "reference_image_urls"
    assert mini["reference_to_video"]["prompt_token"] == "Image"
    assert "21:9" in mini["aspect_ratios"]
    assert "adaptive" in mini["reference_to_video"]["aspect_ratios"]
    assert mini["image_to_video"]["aspect_ratios"] == []
    assert mini["min_seconds"] == "0.92"
    assert mini["max_seconds"] == "15"
    assert mini["duration_format"] == "number"
    assert mini["request_fields"]["prompt_expansion_mode"] == "disabled"
    assert "0.035" in mini["quote_note"]
    assert "0.16" in mini["quote"]


def test_kling_reference_payload_maps_characters_to_elements(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _film(tmp_path)
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_done(KLING_REFERENCE))
    uploads = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport, uploader=_uploader(folder, uploads)),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    post = transport.calls[0]
    assert post["url"] == f"{FAL_QUEUE}/{KLING_REFERENCE}"
    body = post["body"]
    assert body["duration"] == 4
    assert body["resolution"] == "720p"
    assert body["aspect_ratio"] == "21:9"
    assert "generate_audio" not in body
    assert "keep_audio" not in body
    assert "voice_ids" not in body
    assert "prompt_expansion_mode" not in body
    assert "start_image_url" not in body
    assert body["elements"] == [
        {
            "frontal_image_url": "https://fal.example/characters/ada/front.png",
            "reference_image_urls": ["https://fal.example/characters/ada/side.png"],
        },
        {"frontal_image_url": "https://fal.example/characters/beau/front.png"},
    ]
    assert body["image_urls"] == [
        "https://fal.example/locations/dock/wide.png",
        "https://fal.example/props/scarf/face.png",
        "https://fal.example/shots/extra.png",
        "https://fal.example/locations/dock/detail.png",
        "https://fal.example/props/scarf/back.png",
        "https://fal.example/shots/second.png",
    ]
    assert "characters/" not in " ".join(body["image_urls"])
    assert "Use @Element1 as the character face (Ada)." in body["prompt"]
    assert "Use @Element2 as the character face (Beau)." in body["prompt"]
    assert "Use @Image1 as the location (The dock)." in body["prompt"]
    assert "Use @Image2 as the prop (Red scarf)." in body["prompt"]
    assert [path.relative_to(folder.resolve()).as_posix() for path in uploads] == [
        "characters/ada/front.png",
        "characters/ada/side.png",
        "characters/beau/front.png",
        "locations/dock/wide.png",
        "props/scarf/face.png",
        "shots/extra.png",
        "locations/dock/detail.png",
        "props/scarf/back.png",
        "shots/second.png",
    ]
    for element in body["elements"]:
        assert "voice_id" not in element
        assert "video_url" not in element
    assert SECRET not in json.dumps(body)


def test_kling_without_references_stays_on_text_to_video(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _harbor(tmp_path)
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_done(KLING_TEXT))
    uploads = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport, uploader=_uploader(folder, uploads)),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    body = transport.calls[0]["body"]
    assert transport.calls[0]["url"] == f"{FAL_QUEUE}/{KLING_TEXT}"
    assert set(body) == {"prompt", "duration", "resolution", "aspect_ratio"}
    assert body["duration"] == 4
    assert body["resolution"] == "720p"
    assert body["aspect_ratio"] == "16:9"
    assert uploads == []


def test_a_start_image_alone_uses_image_to_video(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _film(tmp_path)
    _board(
        folder,
        characters_in_shot=[],
        location_id="",
        reference_images=[],
        reference_from={"characters": [], "location": "", "props": []},
        start_image="shots/extra.png",
    )
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_done(KLING_IMAGE))
    uploads = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport, uploader=_uploader(folder, uploads)),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    body = transport.calls[0]["body"]
    assert transport.calls[0]["url"] == f"{FAL_QUEUE}/{KLING_IMAGE}"
    assert body["start_image_url"] == "https://fal.example/shots/extra.png"
    assert "aspect_ratio" not in body
    assert "image_urls" not in body
    assert "elements" not in body
    assert "generate_audio" not in body
    assert uploads == [(folder / "shots" / "extra.png").resolve()]

    mini = Scripted(_done(MINIMAX_IMAGE))
    mini_uploads = []
    mini_result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(mini, uploader=_uploader(folder, mini_uploads)),
        model="minimax-h3-max",
        announce=lambda _text: None,
    )
    assert mini_result["status"] == "generated", mini_result["message"]
    mini_body = mini.calls[0]["body"]
    assert mini.calls[0]["url"] == f"{FAL_QUEUE}/{MINIMAX_IMAGE}"
    assert mini_body["image_url"] == "https://fal.example/shots/extra.png"
    assert mini_body["resolution"] == "768P"
    assert mini_body["prompt_expansion_mode"] == "disabled"
    assert "aspect_ratio" not in mini_body
    assert "reference_image_urls" not in mini_body


def test_minimax_reference_payload_uses_image_tags(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _film(tmp_path)
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_done(MINIMAX_REFERENCE))
    uploads = []
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport, uploader=_uploader(folder, uploads)),
        model="minimax-h3-max",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    body = transport.calls[0]["body"]
    assert transport.calls[0]["url"] == f"{FAL_QUEUE}/{MINIMAX_REFERENCE}"
    assert body["duration"] == 4
    assert isinstance(body["duration"], int)
    assert body["resolution"] == "768P"
    assert body["aspect_ratio"] == "21:9"
    assert body["prompt_expansion_mode"] == "disabled"
    assert "generate_audio" not in body
    assert "image_urls" not in body
    assert "elements" not in body
    assert "target_audio_url" not in body
    assert body["reference_image_urls"] == [
        "https://fal.example/characters/ada/front.png",
        "https://fal.example/characters/beau/front.png",
        "https://fal.example/locations/dock/wide.png",
        "https://fal.example/props/scarf/face.png",
        "https://fal.example/shots/extra.png",
        "https://fal.example/characters/ada/side.png",
        "https://fal.example/locations/dock/detail.png",
        "https://fal.example/props/scarf/back.png",
        "https://fal.example/shots/second.png",
    ]
    assert "Image 1 is the character face (Ada)." in body["prompt"]
    assert "Image 2 is the character face (Beau)." in body["prompt"]
    assert "Image 3 is the location (The dock)." in body["prompt"]
    assert "@Image1" not in body["prompt"]
    assert len(uploads) == 9


def test_minimax_without_references_stays_on_text_to_video(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _harbor(tmp_path)
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_done(MINIMAX_TEXT))
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport, uploader=_uploader(folder, [])),
        model="minimax-h3-max",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    body = transport.calls[0]["body"]
    assert transport.calls[0]["url"] == f"{FAL_QUEUE}/{MINIMAX_TEXT}"
    assert body["duration"] == 4
    assert body["resolution"] == "768P"
    assert body["aspect_ratio"] == "16:9"
    assert body["prompt_expansion_mode"] == "disabled"
    assert "reference_image_urls" not in body
    assert "image_url" not in body


def test_caps_drop_extra_elements_angles_and_images(tmp_path):
    folder = _film(tmp_path)
    kling = _row("kling-4.0")
    for index in range(5):
        _png(folder, f"characters/ada/angle-{index}.png")
    images = [f"characters/ada/angle-{index}.png" for index in range(5)]
    _write(folder, "characters/character-lock.json", {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "status": "locked",
        "characters": [{
            "character_id": "ada",
            "name": "Ada",
            "locked_spec": "The face in the photographs.",
            "reference_images": images,
        }],
    })
    _board(
        folder,
        characters_in_shot=["ada"],
        location_id="",
        reference_images=[],
        reference_from={"characters": ["ada"], "location": "", "props": []},
    )
    angled = prepare_references(folder, _shot(folder), "Ada stands.", kling)
    assert len(angled.elements) == 1
    assert angled.elements[0].frontal.relative == "characters/ada/angle-0.png"
    assert [item.relative for item in angled.elements[0].angles] == [
        "characters/ada/angle-1.png",
        "characters/ada/angle-2.png",
        "characters/ada/angle-3.png",
    ]
    assert any("extra-angle cap" in note and "angle-4.png" in note for note in angled.skipped)

    characters = []
    for index in range(8):
        _png(folder, f"characters/c{index}/front.png")
        characters.append({
            "character_id": f"c{index}",
            "name": f"Person {index}",
            "locked_spec": "The face in the photograph.",
            "reference_images": [f"characters/c{index}/front.png"],
        })
    _write(folder, "characters/character-lock.json", {
        "version": "1.0.0",
        "production_id": "harbor-night",
        "status": "locked",
        "characters": characters,
    })
    _board(
        folder,
        characters_in_shot=[f"c{index}" for index in range(8)],
        reference_from={"characters": [f"c{index}" for index in range(8)], "location": "", "props": []},
        reference_images=[],
    )
    crowded = prepare_references(folder, _shot(folder), "A crowd.", kling)
    assert [item.token for item in crowded.elements] == [f"@Element{index}" for index in range(1, 8)]
    assert any("element cap" in note and "c7/front.png" in note for note in crowded.skipped)

    shot_images = []
    for index in range(11):
        _png(folder, f"shots/ref-{index}.png")
        shot_images.append(f"shots/ref-{index}.png")
    _board(
        folder,
        characters_in_shot=[],
        reference_images=shot_images,
        reference_from={"characters": [], "location": "", "props": []},
    )
    packed = prepare_references(folder, _shot(folder), "The dock.", kling)
    assert [item.relative for item in packed.chosen] == [f"shots/ref-{index}.png" for index in range(10)]
    assert any("image cap" in note and "ref-10.png" in note for note in packed.skipped)

    mini = prepare_references(folder, _shot(folder), "The dock.", _row("minimax-h3-max"))
    assert len(mini.chosen) == 11
    assert mini.elements == []
    assert not any("image cap" in note for note in mini.skipped)

    _png(folder, "shots/first.png")
    _board(
        folder,
        characters_in_shot=[],
        reference_images=shot_images,
        reference_from={"characters": [], "location": "", "props": []},
        start_image="shots/first.png",
    )
    framed = prepare_references(folder, _shot(folder), "The dock.", kling)
    assert framed.start.relative == "shots/first.png"
    assert len(framed.chosen) == 9
    assert any("image cap" in note for note in framed.skipped)


def test_duration_resolution_and_aspect_caps(tmp_path, monkeypatch):
    kling = _row("kling-4.0")
    mini = _row("minimax-h3-max")
    short, short_notes = clip_lengths("2", kling)
    assert short == [as_money(3)]
    assert request_value(short[0], kling) == 3
    assert "whole number from 3 to 30" in " ".join(short_notes)
    tiny, tiny_notes = clip_lengths("0.5", mini)
    assert request_value(tiny[0], mini) == 0.92
    assert "length from 0.92 to 15" in " ".join(tiny_notes)
    assert "whole number" not in " ".join(tiny_notes)
    assert request_value(4, mini) == 4
    assert isinstance(request_value(4, mini), int)
    long_kling, _notes = clip_lengths(31, kling)
    assert len(long_kling) == 2
    refusal = _video_request_refusal("kling-4.0", kling, 31)
    assert refusal is not None
    assert "Nothing was sent." in refusal
    odd = dict(kling)
    odd["resolution"] = "480p"
    assert "does not accept 480p" in _video_request_refusal("kling-4.0", odd, 4)

    asked = fit_aspect("2.39:1", kling["aspect_ratios"], kling["aspect_aliases"])
    assert asked.ratio == "21:9"
    assert asked.refuse is False
    assert "not cropped to 16:9" in asked.note
    blocked = fit_aspect("4:3", kling["aspect_ratios"], kling["aspect_aliases"])
    assert blocked.refuse is True
    assert blocked.ratio is None
    kept = fit_aspect("4:3", mini["aspect_ratios"], mini["aspect_aliases"])
    assert kept.ratio == "4:3"
    assert kept.refuse is False

    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _harbor(tmp_path)
    _aspect(folder, "4:3")
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    transport = Scripted(_done(KLING_TEXT))
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert result["status"] == "refused"
    assert "4:3" in result["message"]
    assert "not cropped" in result["message"]
    assert transport.calls == []


def test_quotes_price_the_models_and_make_no_network_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)

    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("movie_swarm.providers._default_upload", boom)
    monkeypatch.setattr("urllib.request.urlopen", boom)
    folder = _film(tmp_path)
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    kling = run_test_shot(
        producer,
        "s01-sh01",
        live=False,
        settings=_settings(Scripted([]), uploader=_uploader(folder, [])),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert kling["status"] == "offline"
    assert kling["sent"] is False
    assert "Nothing was sent." in kling["message"]
    assert "estimated cost $0.6280" in kling["quote"]
    assert KLING_REFERENCE in kling["quote"]
    assert "$0.1570 per second" in kling["quote"]
    assert "@Element1 character face characters/ada/front.png (angles characters/ada/side.png)" in kling["quote"]
    assert "@Element2 character face characters/beau/front.png" in kling["quote"]
    assert "@Image1 location locations/dock/wide.png" in kling["quote"]
    assert "characters/ada/front.png" in kling["quote"].split("References that would be sent", 1)[0]
    assert "Aspect ratio 21:9." in kling["quote"]
    assert "keep_audio" in kling["quote"]
    assert "$0.094" not in kling["quote"]
    assert "does not upload" in kling["quote"]

    mini = run_test_shot(
        producer,
        "s01-sh01",
        live=False,
        settings=_settings(Scripted([]), uploader=_uploader(folder, [])),
        model="minimax-h3-max",
        announce=lambda _text: None,
    )
    assert "estimated cost $0.3200" in mini["quote"]
    assert MINIMAX_REFERENCE in mini["quote"]
    assert "$0.0800 per second" in mini["quote"]
    assert "Image 1 character face characters/ada/front.png" in mini["quote"]
    assert "Image 3 location locations/dock/wide.png" in mini["quote"]
    assert "does not add a token charge" in mini["quote"]
    assert "$0.02048" in mini["quote"]
    assert "estimated cost $0.4224" not in mini["quote"]
    assert "0.035" in mini["quote"]
    assert "Aspect ratio 21:9." in mini["quote"]
    assert "prompt_expansion_mode is disabled" in mini["quote"]

    bare = _harbor(tmp_path / "bare")
    bare_producer = _open(bare)
    text = run_test_shot(
        bare_producer,
        "s01-sh01",
        live=False,
        settings=_settings(Scripted([])),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert "estimated cost $0.6280" in text["quote"]
    assert f"Endpoint {KLING_TEXT}" in text["quote"]
    assert "Reference endpoint" not in text["quote"]
    assert "Aspect ratio 16:9." in text["quote"]

    short = _harbor(tmp_path / "short")
    _board_duration(short, "2")
    short_quote = run_test_shot(
        _open(short),
        "s01-sh01",
        live=False,
        settings=_settings(Scripted([])),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert "sent as 3 seconds" in short_quote["quote"]
    assert "estimated cost $0.4710" in short_quote["quote"]

    half = _harbor(tmp_path / "half")
    _board_duration(half, "0.5")
    half_quote = run_test_shot(
        _open(half),
        "s01-sh01",
        live=False,
        settings=_settings(Scripted([])),
        model="minimax-h3-max",
        announce=lambda _text: None,
    )
    assert "sent as 0.92 seconds" in half_quote["quote"]
    assert "estimated cost $0.0736" in half_quote["quote"]


def test_a_scope_ratio_is_sent_as_21_9_and_the_queue_fallback_uses_the_full_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", SECRET)
    folder = _harbor(tmp_path)
    _aspect(folder, "2.39:1")
    from movie_swarm.providers import run_test_shot

    producer = _open(folder)
    producer.approve_gate("generation", "approved", "ron")
    script = [
        HttpResult(200, json.dumps({"request_id": "job-9"}).encode()),
        HttpResult(200, json.dumps({"status": "COMPLETED"}).encode()),
        HttpResult(200, json.dumps({"video": {"url": "https://cdn.example/clip.mp4"}}).encode()),
        HttpResult(200, b"fake-video-bytes"),
    ]
    transport = Scripted(script)
    result = run_test_shot(
        producer,
        "s01-sh01",
        live=True,
        settings=_settings(transport),
        model="kling-4.0",
        announce=lambda _text: None,
    )
    assert result["status"] == "generated", result["message"]
    assert transport.calls[0]["body"]["aspect_ratio"] == "21:9"
    assert transport.calls[1]["url"] == f"{FAL_QUEUE}/{KLING_TEXT}/requests/job-9/status"
    assert transport.calls[2]["url"] == f"{FAL_QUEUE}/{KLING_TEXT}/requests/job-9"
    assert "2.39:1" in result["quote"]
    assert "21:9" in result["quote"]


def _board_duration(folder: Path, seconds: str) -> None:
    path = folder / "storyboard" / "storyboard.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["frames"][0]["duration_seconds"] = float(seconds) if "." in seconds else int(seconds)
    path.write_text(json.dumps(document), encoding="utf-8")
