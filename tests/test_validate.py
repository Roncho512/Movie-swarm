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
        "grade.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "scenes": [
                {"scene_id": "s01", "time_of_day": "night", "contrast": 1.1, "note": "One scene grade."}
            ],
            "consistency": {"brightness": 0.12, "color": 0.12},
        },
        "grade-plan.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "grade-plan",
            "created_at": "2026-01-01T00:00:00Z",
            "cut_runtime_seconds": 4,
            "ready_for_color_mix_approval": True,
            "color_mix_approved": False,
            "spent_usd": 0,
            "cut_source": "edit/picture-lock.json",
            "sources": {"edit": "edit/picture-lock.json", "look": "look/look.json", "grade": None},
            "look_reference": {
                "look_name": "Unnamed look",
                "summary": "The production names the look.",
                "palette": [],
                "lighting": [],
            },
            "base": {
                "time_of_day": "unspecified",
                "contrast": 1,
                "saturation": 1,
                "warmth": 0,
                "brightness": 0,
                "gamma": 1,
                "source": "look/look.json",
            },
            "adjustments": [
                {
                    "adjustment_id": "scene-s01",
                    "scope": "scene",
                    "scene_id": "s01",
                    "shot_id": None,
                    "shot_ids": ["s01-sh01"],
                    "time_of_day": "night",
                    "contrast": 1.1,
                    "saturation": 1,
                    "warmth": 0,
                    "brightness": 0,
                    "gamma": 1,
                    "note": "Scene grade, stated once.",
                }
            ],
            "applied": [
                {
                    "shot_id": "s01-sh01",
                    "scene_id": "s01",
                    "adjustment_id": "scene-s01",
                    "time_of_day": "night",
                    "contrast": 1.1,
                    "saturation": 1,
                    "warmth": 0,
                    "brightness": 0,
                    "gamma": 1,
                }
            ],
            "consistency": {
                "brightness_tolerance": 0.12,
                "color_tolerance": 0.12,
                "tolerance_source": "studio default",
                "checks": [],
            },
            "lut": None,
            "render": {"status": "skipped", "preview": None, "married": None, "note": "ffmpeg is not installed."},
            "budget": {
                "stage": "editor",
                "estimated_usd": None,
                "rate_status": "unknown",
                "note": "No rate is published.",
            },
            "models": {"colorist": "claude-haiku-5-5", "render": "ffmpeg"},
            "draft_method": "offline-deterministic",
        },
        "mix-plan.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "mix-plan",
            "created_at": "2026-01-01T00:00:00Z",
            "cut_runtime_seconds": 4,
            "ready_for_color_mix_approval": True,
            "color_mix_approved": False,
            "spent_usd": 0,
            "cut_source": "edit/picture-lock.json",
            "cue_source": "sound/cue-sheet.json",
            "sources": {
                "edit": "edit/picture-lock.json",
                "cue_sheet": "sound/cue-sheet.json",
                "mix_targets": None,
                "stems": [],
            },
            "levels": [
                {"stem": "dialogue", "gain_db": 0, "priority": "dialogue"},
                {"stem": "music", "gain_db": -12, "priority": "bed"},
            ],
            "ducking": [
                {
                    "stem": "music",
                    "under": "dialogue",
                    "cue_id": "line-s01-sh01",
                    "duck_db": -8,
                    "start_seconds": 0,
                    "end_seconds": 4,
                }
            ],
            "fades": [],
            "loudness": {
                "integrated_lufs": -23,
                "true_peak_dbtp": -1,
                "tolerance_lufs": 0.5,
                "standard": "EBU R128",
                "citation": "EBU R128.",
                "source": "EBU R128",
            },
            "measurement": {
                "status": "skipped",
                "meter": None,
                "integrated_lufs": None,
                "true_peak_dbtp": None,
                "within_target": None,
                "flags": [],
                "note": "ffmpeg is not installed.",
            },
            "render": {"status": "skipped", "mix": None, "married": None, "note": "ffmpeg is not installed."},
            "budget": {
                "stage": "sound-designer",
                "estimated_usd": None,
                "rate_status": "unknown",
                "note": "No rate is published.",
            },
            "models": {"mixer": "ffmpeg", "notes": "claude-haiku-5-5"},
            "draft_method": "offline-deterministic",
        },
        "mix-targets.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "integrated_lufs": -23,
            "true_peak_dbtp": -1,
            "standard": "EBU R128",
        },
        "delivery-spec.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "master": {"codec": "h264", "width": 320, "height": 180, "frame_rate": 24},
            "captions": {"mode": "sidecar", "formats": ["srt", "vtt"]},
        },
        "delivery-plan.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "delivery-plan",
            "created_at": "2026-01-01T00:00:00Z",
            "cut_runtime_seconds": 2,
            "spent_usd": 0,
            "spec_source": "delivery/delivery-spec.json",
            "spec_note": "The spec names the sizes.",
            "defaults_used": [],
            "ready_for_delivery_approval": True,
            "delivery_approved": False,
            "sources": {
                "edit": "edit/picture-lock.json",
                "cue_sheet": "sound/cue-sheet.json",
                "mix": None,
                "grade": None,
                "spec": "delivery/delivery-spec.json",
            },
            "master": {
                "codec": "h264",
                "encoder": "libx264",
                "container": "mp4",
                "width": 320,
                "height": 180,
                "frame_rate": 24,
                "crf": 18,
                "profile": "high",
                "filename": "master.mp4",
                "citation": "ITU-T H.264.",
                "note": "High-quality H.264.",
            },
            "variants": [],
            "poster": {
                "shot_id": "s01-sh01",
                "filename": "poster.png",
                "time_seconds": 0,
                "width": 320,
                "height": 180,
                "note": "First shot.",
                "source_file": "frames/s01-sh01.mp4",
            },
            "captions": {
                "mode": "sidecar",
                "formats": ["srt", "vtt"],
                "cues": [
                    {"cue_id": "line-s01-sh01", "start_seconds": 0, "end_seconds": 1, "text": "Hold."}
                ],
                "citation": "W3C WebVTT.",
                "files": ["delivery/captions.srt"],
                "burned_file": None,
            },
            "loudness": {
                "integrated_lufs": -23,
                "true_peak_dbtp": -1,
                "tolerance_lufs": 0.5,
                "standard": "EBU R128",
                "citation": "EBU R128.",
                "source": "EBU R128",
            },
            "qc_tolerances": {
                "duration_tolerance_seconds": 0.5,
                "frame_rate_tolerance": 0.05,
                "black_max_seconds": 0.5,
                "freeze_max_seconds": 0.5,
                "loudness_tolerance_lufs": 0.5,
            },
            "location": {"relative": "delivery", "setting": None, "resolved": "/tmp/demo/delivery"},
            "standards": [{"id": "EBU R128", "citation": "EBU R128."}],
            "render": {
                "status": "skipped",
                "note": "ffmpeg is not installed.",
                "master": None,
                "variants": [],
                "poster": None,
                "burned": None,
            },
            "budget": {
                "stage": "editor",
                "estimated_usd": None,
                "rate_status": "unknown",
                "note": "No rate is published.",
            },
            "models": {
                "post-supervisor": "claude-haiku-5-5",
                "notes": "claude-haiku-5-5",
                "render": "ffmpeg",
                "qc": "local",
            },
            "draft_method": "offline-deterministic",
        },
        "qc-report.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "qc-report",
            "created_at": "2026-01-01T00:00:00Z",
            "verdict": "pass",
            "spent_usd": 0,
            "cut_runtime_seconds": 2,
            "checks": [
                {
                    "check_id": "captions-timing",
                    "target": "delivery/captions.srt",
                    "kind": "captions",
                    "status": "pass",
                    "detail": "The cues sit inside the cut.",
                }
            ],
            "draft_method": "offline-deterministic",
        },
        "delivery-manifest.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "delivery-manifest",
            "created_at": "2026-01-01T00:00:00Z",
            "ready_for_delivery_approval": True,
            "delivery_approved": False,
            "delivered": False,
            "approved_by": None,
            "approved_at": None,
            "approval_note": "",
            "spent_usd": 0,
            "qc_verdict": "pass",
            "qc_report": "delivery/qc-report.json",
            "plan": "delivery/delivery-plan.json",
            "location": {"relative": "delivery", "setting": None, "resolved": "/tmp/demo/delivery"},
            "spend": {
                "spent_usd": 0,
                "budget_cap_usd": 500,
                "within_cap": True,
                "currency": "USD",
                "stage_split": {"editor": 15},
                "stage_spent": {"editor": 0},
                "rate_status": "unknown",
                "note": "No delivery rate is published.",
            },
            "gates": [
                {
                    "stage": "color-mix",
                    "decision": "approved",
                    "by": "ron",
                    "decided_at": "2026-01-01T00:00:00Z",
                    "note": "Final delivery can start.",
                }
            ],
            "files": [
                {
                    "path": "delivery/captions.srt",
                    "role": "captions",
                    "sha256": None,
                    "bytes": None,
                    "status": "not-rendered",
                    "label": "Captions",
                }
            ],
            "budget": {
                "stage": "editor",
                "estimated_usd": None,
                "rate_status": "unknown",
                "note": "No rate is published.",
            },
            "models": {
                "post-supervisor": "claude-haiku-5-5",
                "notes": "claude-haiku-5-5",
                "render": "ffmpeg",
                "qc": "local",
            },
            "standards": [{"id": "FIPS 180-4", "citation": "SHA-256."}],
            "checksum": "SHA-256.",
            "draft_method": "offline-deterministic",
        },
        "costume-lock.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "status": "locked",
            "characters": [],
        },
        "makeup-lock.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "status": "locked",
            "characters": [],
        },
        "lighting-plan.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "continuity": "clear",
            "source": {"camera": None, "look": None, "shots": "storyboard/shot-list.json", "scenes": "treatment/treatment.json"},
            "scenes": [
                {
                    "scene_id": "s01",
                    "time_of_day": "not named",
                    "key": "not named",
                    "fill": "not named",
                    "practicals": "not named",
                    "color_temperature": "not named",
                    "contrast_ratio": "not named",
                    "prompt_note": "Time of day: not named.",
                    "shot_ids": [],
                    "continuity": {"verdict": "clear", "findings": []},
                }
            ],
        },
        "grip-plan.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "source": {"shots": "storyboard/shot-list.json", "camera": None, "lighting": None},
            "shots": [],
        },
        "shooting-schedule.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "kind": "shooting-schedule",
            "source": {"shots": "storyboard/shot-list.json", "scenes": "treatment/treatment.json", "stunts": None, "lighting": None},
            "days": [],
            "safety": [],
        },
        "vfx-needs.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "items": [],
        },
        "vfx-breakdown.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "source": {"shots": "storyboard/shot-list.json", "needs": None},
            "shots": [],
            "turnover": [],
        },
        "vfx-review.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "verdict": "clear",
            "shots": [],
            "checked_at": "2026-01-01T00:00:00Z",
        },
        "graphics-research.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "items": [
                {
                    "item_id": "film-title",
                    "topic": "director",
                    "text": "Title: Demo.",
                    "basis": "inferred",
                    "source_file": None,
                    "source_field": None,
                }
            ],
            "fingerprints": {"style_bible": None, "look": None},
            "draft_method": "offline-deterministic",
            "model": "claude-haiku-5-5",
            "note": "Sample.",
            "written_at": "2026-01-01T00:00:00Z",
        },
        "graphics-brand-guide.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "status": "draft",
            "research": "graphics/research.json",
            "fonts": {
                "title": {"family": "not named", "licensing": "No license is named.", "trace": "period-type"},
                "credits": {"family": "not named", "licensing": "No license is named.", "trace": "period-type"},
                "subtitles": {"family": "not named", "licensing": "No license is named.", "trace": "period-type"},
                "marketing": {"family": "not named", "licensing": "No license is named.", "trace": "period-type"},
            },
            "palette": [{"name": "not named", "value": "not named", "trace": "palette-unnamed"}],
            "wordmark": {
                "title": "Demo",
                "rules": [{"rule_id": "wordmark-spelling", "text": "Set the title as written.", "trace": "film-title"}],
            },
            "layout": {
                "safe_area": "not named",
                "rules": [{"rule_id": "layout-safe", "text": "No inset is named.", "trace": "safe-area"}],
            },
            "image_treatment": {
                "rules": [{"rule_id": "treatment-look", "text": "Follow the research.", "trace": "look-summary"}]
            },
            "dos": [{"rule_id": "do-palette", "text": "Use the palette.", "trace": "palette-unnamed"}],
            "donts": [{"rule_id": "dont-invent", "text": "Do not invent a face.", "trace": "period-type"}],
            "fingerprints": {"style_bible": None, "look": None},
            "change_log": [{"version": "1.0.0", "at": "2026-01-01T00:00:00Z", "change": "Created from research."}],
            "rules_fingerprint": "abc",
            "draft_method": "offline-deterministic",
            "model": "claude-haiku-5-5",
            "note": "Sample.",
            "written_at": "2026-01-01T00:00:00Z",
        },
        "graphics-package.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "guide": "graphics/brand-guide.json",
            "guide_version": "1.0.0",
            "main_title": {"text": "Demo", "font": "not named", "safe_area": "not named", "trace": "film-title"},
            "title_cards": [],
            "end_credits": {"source": None, "lines": []},
            "subtitles": {
                "timing_owner": "post-supervisor",
                "note": "Timing stays with the Post Supervisor.",
                "family": "not named",
                "color": "not named",
                "safe_area": "not named",
            },
            "key_art": {
                "filename": "graphics/key-art-poster.png",
                "kind": "designed",
                "distinct_from": "poster.png",
                "title": "Demo",
                "tagline": None,
                "billing_block": [],
                "width": None,
                "height": None,
                "size_source": None,
                "safe_area": "not named",
                "render_status": "not-rendered",
            },
            "collateral": [
                {
                    "id": "thumbnail-16x9",
                    "aspect_ratio": "16:9",
                    "filename": "graphics/thumbnail-16x9.png",
                    "width": None,
                    "height": None,
                    "size_source": None,
                    "safe_area": "not named",
                    "render_status": "not-rendered",
                }
            ],
            "handoff": {
                "for": ["editor", "colorist"],
                "overlays_before_master": True,
                "note": "Hand the overlays over before the master.",
            },
            "package_fingerprint": "abc",
            "draft_method": "offline-deterministic",
            "model": "claude-haiku-5-5",
            "note": "Sample.",
            "written_at": "2026-01-01T00:00:00Z",
        },
        "film-budget.schema.json": {
            "version": "1.0.0",
            "total_usd": 500,
            "currency": "USD",
            "line_shares": {
                "production": 54,
                "sound-designer": 11,
                "fix-loop": 10,
                "qa": 9,
                "art-director": 5,
                "director": 4,
                "editor": 3,
                "cinematographer": 2,
                "screenwriter": 1,
                "line-producer": 1,
            },
            "contingency_share": 0,
            "trailer_on": False,
            "marketing_share": 10,
            "tiers": {"production": "better"},
            "production_resolution": "720p",
            "note": "Sample budget.",
        },
        "trailer-research.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "items": [
                {
                    "item_id": "tone",
                    "topic": "treatment",
                    "text": "Tone: quiet.",
                    "basis": "sourced",
                    "source_file": "treatment/treatment.json",
                    "source_field": "tone_and_genre.tone",
                }
            ],
            "draft_method": "offline-deterministic",
            "model": "claude-haiku-5-5",
            "note": "Sample.",
            "written_at": "2026-01-01T00:00:00Z",
        },
        "spoiler-guard.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "may_show": [{"id": "premise", "text": "A person waits.", "source_field": "logline"}],
            "hold_back": [
                {
                    "id": "ending",
                    "text": "The last step.",
                    "source_field": "scenes",
                    "reason": "The trailer stops before the ending.",
                }
            ],
            "teaser_rule": "Tone and mood only.",
            "trailer_rule": "Stop before the ending.",
            "tone": "Quiet.",
            "director_signed": False,
            "signed_by": None,
            "signed_at": None,
            "sign_note": "",
            "draft_method": "offline-deterministic",
            "model": "claude-haiku-5-5",
            "note": "Sample.",
            "written_at": "2026-01-01T00:00:00Z",
        },
        "trailer-plan.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "lengths": {"teaser_seconds": 15, "trailer_seconds": 45},
            "length_source": "default",
            "length_note": "Lengths were not named. The defaults are 15 and 45 seconds.",
            "picture_lock_sha256": "abc",
            "beats": [
                {
                    "deliverable": "teaser",
                    "shot_id": "s01-sh01",
                    "source_file": "frames/s01-sh01.mp4",
                    "record_in": 0,
                    "record_out": 1,
                    "duration_seconds": 1,
                    "card_text": "Quiet.",
                    "music": "No cue.",
                }
            ],
            "gaps": [],
            "cards": [{"id": "teaser-card", "text": "Quiet.", "for": "title-graphic-design"}],
            "music": {"cue_id": None},
            "loudness": {"integrated_lufs": -23.0, "standard": "EBU R128"},
            "safe_area": {"action_inset_percent": 3.5, "graphics_inset_percent": 5},
            "versions": ["16:9", "9:16"],
            "handoff": {"cards_to": "title-graphic-design"},
            "draft_method": "offline-deterministic",
            "model": "claude-haiku-5-5",
            "note": "Sample.",
            "written_at": "2026-01-01T00:00:00Z",
        },
        "trailer-cut.schema.json": {
            "version": "1.0.0",
            "production_id": "demo",
            "picture_lock_sha256": "abc",
            "lock_status": "current",
            "picture": "edit/picture-lock.json",
            "picture_note": "Selects come from the locked cut.",
            "kept": [],
            "gaps": [{"shot_id": "missing-shot", "reason": "Dropped."}],
            "cards": [],
            "files": [
                {
                    "deliverable": "teaser",
                    "aspect_ratio": "16:9",
                    "filename": "marketing/teaser-16x9.mp4",
                    "width": 320,
                    "height": 180,
                    "target_seconds": 15,
                    "render_status": "not-rendered",
                    "safe_area": {"graphics_inset_percent": 5},
                }
            ],
            "loudness": {"standard": "EBU R128"},
            "gate": "pending",
            "gate_by": None,
            "gate_at": None,
            "gate_note": "",
            "draft_method": "offline-deterministic",
            "model": "claude-haiku-5-5",
            "note": "Sample.",
            "written_at": "2026-01-01T00:00:00Z",
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
