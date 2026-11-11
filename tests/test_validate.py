"""Schema documents and the validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from movie_swarm.paths import repo_root, schemas_dir
from movie_swarm.validate import (
    SchemaLookupError,
    check_schema_document,
    load_schema,
    validate_data,
    validate_file,
)


ROOT = repo_root()


def test_every_schema_document_is_a_valid_schema():
    paths = sorted(schemas_dir().glob("*.schema.json"))
    assert len(paths) >= 11
    for path in paths:
        check_schema_document(load_schema(path))


def test_each_schema_accepts_a_minimal_document():
    samples = {
        "production-brief.schema.json": {
            "production_id": "demo",
            "title": "Demo",
            "concept": "A short film.",
            "target_runtime_seconds": 180,
            "visual_style": {"description": "16mm."},
            "created_at": "2026-01-01T00:00:00Z",
        },
        "scene-manifest.schema.json": {
            "production_id": "demo",
            "version": "1.0.0",
            "total_scenes": 1,
            "target_runtime_seconds": 60,
            "characters": [{"character_id": "miguel-vega", "name": "Miguel Vega"}],
            "scenes": [
                {
                    "scene_number": 1,
                    "scene_id": "s01-open",
                    "heading": "EXT. DESERT - DAY",
                    "location": "Desert",
                    "time_of_day": "day",
                    "target_duration_seconds": 60,
                    "color_notes": "Amber.",
                    "sound_notes": "Engine.",
                    "action_blocks": [
                        {"block_id": "s01-b01", "type": "action", "content": "He rides."}
                    ],
                }
            ],
            "created_at": "2026-01-01T00:00:00Z",
        },
        "visual-style-bible.schema.json": {
            "production_id": "demo",
            "version": "1.0.0",
            "style_summary": {
                "description": "Grain.",
                "film_stock": "16mm",
                "aspect_ratio": "16:9",
            },
            "character_references": [],
            "color_system": {"palette": [], "scene_progression": []},
            "created_at": "2026-01-01T00:00:00Z",
        },
        "shot-list.schema.json": {
            "production_id": "demo",
            "version": "1.0.0",
            "total_shots": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "shots": [
                {
                    "shot_id": "s01-sh01",
                    "scene_number": 1,
                    "shot_number": 1,
                    "shot_type": "wide",
                    "description": "Desert.",
                    "generation_prompt": "Wide desert.",
                    "target_duration_seconds": 4,
                    "tool_routing": {
                        "primary_tool": "seedance-2.0",
                        "rationale": "Test.",
                    },
                }
            ],
        },
        "clip-metadata.schema.json": {
            "production_id": "demo",
            "version": "1.0.0",
            "clips": [
                {
                    "clip_id": "s01-sh01-v1",
                    "shot_id": "s01-sh01",
                    "status": "selected",
                    "file_path": "clips/selected/s01-sh01.mp4",
                }
            ],
            "created_at": "2026-01-01T00:00:00Z",
        },
        "audio-manifest.schema.json": {
            "production_id": "demo",
            "version": "1.0.0",
            "layers": {},
            "created_at": "2026-01-01T00:00:00Z",
        },
        "continuity-report.schema.json": {
            "production_id": "demo",
            "version": "1.0.0",
            "review_pass": 1,
            "verdict": "approved",
            "issues": [],
            "reviewed_at": "2026-01-01T00:00:00Z",
        },
        "run-state.schema.json": {
            "production_id": "demo",
            "run_id": "run-1",
            "stage": "qa",
            "status": "waiting-for-review",
            "artifacts": [],
            "cost_usd": 0,
            "budget_cap_usd": 500,
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "gate-config.schema.json": json.loads((ROOT / "config" / "gates.json").read_text()),
        "model-routing.schema.json": json.loads(
            (ROOT / "config" / "model-routing.json").read_text()
        ),
        "asset-config.schema.json": json.loads((ROOT / "config" / "assets.json").read_text()),
        "treatment.schema.json": {
            "version": "0.1.0",
            "status": "draft",
            "approval": {"state": "pending", "by": None, "at": None, "note": ""},
            "production_id": "demo",
            "title": "Demo",
            "logline": "A rider chooses.",
            "theme_and_emotional_intent": {
                "theme": "Survival",
                "emotional_intent": "Relief.",
            },
            "tone_and_genre": {"tone": "Sparse", "genre": "western"},
            "characters": [
                {"name": "Miguel", "role": "protagonist", "look": "Lean, sun-darkened."}
            ],
            "scenes": [
                {
                    "what_happens": "He rides.",
                    "emotional_purpose": "The desert is larger than he is.",
                }
            ],
            "deliverables": {
                "aspect_ratio": "2.39:1",
                "resolution": "1920x1080",
                "length": "3 minutes",
            },
            "open_questions": [],
        },
        "director-questions.schema.json": {
            "production_id": "demo",
            "round": 1,
            "status": "open",
            "questions": [
                {"id": "q-intent", "topic": "intent", "question": "Lock the intent?"}
            ],
        },
        "line-producer-record.schema.json": {
            "production_id": "demo",
            "run_id": "run-1",
            "credits": [{"role": "Executive Producer", "name": "Ron"}],
            "stage_allocations": {
                "status": "unlocked",
                "split": {},
                "approved_at": None,
                "approved_by": None,
            },
            "ledger": [],
            "gate_decisions": [],
            "requests": [],
            "schedule": {"treatment": "waiting-for-review"},
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "hero-props.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "status": "locked",
            "props": [],
        },
        "continuity-check.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "verdict": "clear",
            "findings": [],
            "checked_at": "2026-01-01T00:00:00Z",
        },
        "look.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "look_name": "Unnamed look",
            "summary": "The production names the look.",
        },
        "camera-package.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "look_name": "Unnamed look",
            "summary": "The production names the look.",
            "lenses": [],
            "framing": [{"id": "stated-look", "description": "The production names the frame."}],
            "lighting": [{"id": "stated-look", "description": "The production names the light."}],
            "source": "treatment",
        },
        "storyboard.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "frames": [
                {
                    "order": 1,
                    "shot_id": "s01-sh01",
                    "scene_id": "s01",
                    "board_prompt": "Wide. The production names the action.",
                    "image_status": "not-generated",
                    "image_ref": None,
                }
            ],
            "animatic": {"total_duration_seconds": 4, "order": ["s01-sh01"]},
            "image_generation": "not-run",
        },
        "action-breakdown.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "safety_policy": "One movement per shot.",
            "beats": [],
        },
        "sound-prompts.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "sfx": [],
            "dialogue": [],
            "music": [],
        },
        "takes-manifest.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "takes": [
                {"take_id": "s01-sh01-t01", "shot_id": "s01-sh01", "file": "frames/s01-sh01.png", "kind": "frame"}
            ],
        },
        "edit-decision-list.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "rough-cut",
            "created_at": "2026-01-01T00:00:00Z",
            "target_runtime_seconds": 4,
            "tolerance_seconds": 1,
            "runtime_seconds": 4,
            "runtime_delta_seconds": 0,
            "within_tolerance": True,
            "runtime_note": "The cut matches the target.",
            "ready_for_picture_lock": True,
            "picture_lock": False,
            "spent_usd": 0,
            "order_source": "storyboard/storyboard.json",
            "sources": {
                "order": "storyboard/storyboard.json",
                "dailies": "dailies/dailies-report.json",
                "editing_style": None,
                "runtime": "production-brief.json",
            },
            "events": [
                {
                    "event": 1,
                    "shot_id": "s01-sh01",
                    "scene_id": "s01",
                    "take_id": "s01-sh01-t01",
                    "source_file": "frames/s01-sh01.png",
                    "source_in": 0,
                    "source_out": 4,
                    "record_in": 0,
                    "record_out": 4,
                    "duration_seconds": 4,
                    "transition": "cut",
                    "transition_duration_seconds": 0,
                }
            ],
            "scene_markers": [{"scene_id": "s01", "label": "Scene", "record_in": 0}],
            "blockers": [],
            "continuity": [],
            "render": {"status": "skipped", "path": None, "note": "ffmpeg is not installed."},
            "model": "ffmpeg",
            "draft_method": "offline-deterministic",
        },
        "dailies-report.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "reviewed_at": "2026-01-01T00:00:00Z",
            "spent_usd": 0,
            "fix_loop_reserve_usd": 50,
            "retake_estimate_usd": 0,
            "within_fix_loop": True,
            "shots": [
                {
                    "shot_id": "s01-sh01",
                    "verdict": "circle",
                    "best_take": "s01-sh01-t01",
                    "reasons": ["Circled."],
                    "takes": [
                        {
                            "take_id": "s01-sh01-t01",
                            "file": "frames/s01-sh01.png",
                            "verdict": "circle",
                            "reasons": ["Circled."],
                            "description_source": "client",
                            "checks": {
                                "technical": {"status": "pass", "detail": "The file is on disk."},
                                "continuity": {"status": "pass"},
                                "shot_match": {"status": "pass"},
                                "look_match": {"status": "skipped"},
                            },
                        }
                    ],
                }
            ],
            "retakes": [],
        },
        "cue-sheet.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "cue-sheet",
            "created_at": "2026-01-01T00:00:00Z",
            "cut_runtime_seconds": 4,
            "sync_tolerance_seconds": 0.5,
            "ready_for_sound_approval": True,
            "sound_approved": False,
            "spent_usd": 0,
            "cut_source": "edit/picture-lock.json",
            "sources": {
                "edit": "edit/picture-lock.json",
                "sound_prompts": None,
                "score_brief": None,
                "props": None,
            },
            "cues": [
                {
                    "cue_id": "line-s01-sh01",
                    "type": "dialogue",
                    "start_seconds": 0,
                    "end_seconds": 4,
                    "shot_ids": ["s01-sh01"],
                    "prompt": "A short line.",
                    "description": "A short line.",
                    "source": "generated",
                    "prop_id": None,
                    "role": "sound-designer",
                    "model": "eleven_v3",
                }
            ],
            "sync": [
                {
                    "cue_id": "line-s01-sh01",
                    "status": "pass",
                    "kind": "clear",
                    "detail": "The cue stays inside the cut.",
                }
            ],
            "continuity": [
                {
                    "cue_id": "line-s01-sh01",
                    "status": "pass",
                    "kind": "clear",
                    "detail": "No locked prop sound is on this cue.",
                }
            ],
            "unplaced": [],
            "budget": {
                "stage": "sound-designer",
                "locked_usd": None,
                "spent_on_stage_usd": 0,
                "estimated_usd": None,
                "rate_status": "unknown",
                "within_allocation": None,
                "models_without_a_rate": ["eleven_v3"],
                "note": "The estimate is unknown.",
            },
            "render": {
                "status": "skipped",
                "dialogue": None,
                "effects": None,
                "music": None,
                "mix": None,
                "note": "ffmpeg is not installed.",
            },
            "models": {"sound-designer": "claude-haiku-5-5", "composer": "claude-haiku-5-5"},
            "draft_method": "offline-deterministic",
        },
        "score-brief.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "tempo_bpm": 72,
            "instrumentation": ["piano"],
            "motifs": [
                {"motif_id": "hold", "description": "A held note.", "shot_ids": ["s01-sh01"]}
            ],
            "silence": [{"shot_id": "s01-sh02", "reason": "Leave this shot quiet."}],
        },
    }
    on_disk = {path.name for path in schemas_dir().glob("*.schema.json")}
    assert on_disk == set(samples)
    for name, document in samples.items():
        errors = validate_data(document, load_schema(name))
        assert errors == [], name


def test_missing_field_is_named():
    errors = validate_data({}, load_schema("shot-list"))
    joined = "\n".join(errors)
    assert "total_shots" in joined
    assert "(root):" in joined


def test_bad_date_fails():
    document = {
        "production_id": "demo",
        "version": "1.0.0",
        "layers": {},
        "created_at": "yesterday",
    }
    errors = validate_data(document, load_schema("audio-manifest"))
    assert any("date-time" in error for error in errors)


def test_real_shot_list_passes():
    result = validate_file(ROOT / "productions/the-last-marker/shot-lists/shot-list.json")
    assert result.ok, result.errors
    assert result.schema_name == "shot-list.schema.json"


def test_unknown_schema_name():
    with pytest.raises(SchemaLookupError):
        load_schema("not-a-real-schema")
