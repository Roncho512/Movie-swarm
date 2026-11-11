"""Model routing records the generators the programs already call."""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys

import pytest

from movie_swarm.models import ModelRoutingError, resolve_model
from movie_swarm.paths import repo_root


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_seeded_models_match_the_agent_code():
    root = repo_root()
    production = _load(root / "agents/05-production/src/config.py", "phase0_prod_config")
    routing = resolve_model("production")
    endpoints = routing["endpoints"]
    assert routing["model"] == "seedance-2.0"
    assert routing["provider"] == "fal.ai"
    assert endpoints["text-to-video"] == production.Endpoint.TEXT_TO_VIDEO.value
    assert endpoints["image-to-video"] == production.Endpoint.IMAGE_TO_VIDEO.value
    assert endpoints["reference-to-video"] == production.Endpoint.REFERENCE_TO_VIDEO.value
    assert endpoints["fast-text-to-video"] == production.Endpoint.FAST_TEXT_TO_VIDEO.value
    assert endpoints["fast-image-to-video"] == production.Endpoint.FAST_IMAGE_TO_VIDEO.value
    assert endpoints["fast-reference-to-video"] == production.Endpoint.FAST_REFERENCE_TO_VIDEO.value

    sound = _load(
        root / "agents/06-sound-designer/src/elevenlabs_client.py",
        "phase0_elevenlabs_client",
    )
    dialogue = inspect.signature(sound.generate_dialogue).parameters["model"].default
    sfx = inspect.signature(sound.generate_sfx).parameters["model"].default
    assert resolve_model("sound-designer", purpose="dialogue")["model"] == dialogue
    assert resolve_model("sound-designer", purpose="sfx")["model"] == sfx
    assert dialogue == "eleven_v3"
    assert sfx == "eleven_text_to_sound_v2"
    music_source = (root / "agents/06-sound-designer/src/elevenlabs_client.py").read_text()
    assert "client.music.compose" in music_source
    assert resolve_model("sound-designer", purpose="score")["model"] == "elevenlabs-music-compose"

    qa = _load(root / "agents/08-qa/src/pipeline.py", "phase0_qa_pipeline")
    qa_model = inspect.signature(qa.analyze_frames_with_claude).parameters["model"].default
    assert resolve_model("qa")["model"] == qa_model
    assert qa_model == "claude-sonnet-4-20250514"
    assert resolve_model("editor")["model"] == "ffmpeg"


def test_unknown_role_and_purpose():
    with pytest.raises(ModelRoutingError) as caught:
        resolve_model("best-boy")
    assert "best-boy" in str(caught.value)
    with pytest.raises(ModelRoutingError):
        resolve_model("qa", purpose="dialogue")


def test_shot_override_replaces_the_role_default(tmp_path):
    config = json.loads((repo_root() / "config" / "model-routing.json").read_text())
    config["overrides"] = [
        {
            "role": "production",
            "shot": "s01-sh01",
            "model": "veo-3.1",
            "provider": "google",
        }
    ]
    path = tmp_path / "model-routing.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    default = resolve_model("production", shot="s01-sh02", config_path=path)
    override = resolve_model("production", shot="s01-sh01", config_path=path)
    assert default["model"] == "seedance-2.0"
    assert override["model"] == "veo-3.1"
    assert override["provider"] == "google"
    assert "override" in override
