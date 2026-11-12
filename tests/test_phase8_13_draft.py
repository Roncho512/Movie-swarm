"""Phase 8.13: a live treatment draft keeps the whole screenplay and a paid reply.

The model is a fake. No test sets a real provider key, and none of these
checks open a socket. Harbor Night is not required. The archived film is
not modified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from movie_swarm.cli_director import main as director_main
from movie_swarm.director import DRAFT_SOURCE_CHAR_LIMIT, Director, DirectorError
from movie_swarm.handoff import write_handoff
from movie_swarm.line_producer import LineProducer
from movie_swarm.llm import LLMClient, WritingQuote
from movie_swarm.providers import GuardedLLM, quote_text_call
from movie_swarm.treatment_doc import (
    conform_treatment,
    force_draft,
    load_treatment,
    treatment_errors,
    treatment_json_path,
)
from movie_swarm.validate import load_schema, validate_data


SECRET = "anthropic-test-key-do-not-leak"
QUESTIONS = json.dumps({"questions": [{"id": "q-intent", "question": "Lock the intent?"}]})


class Recording:
    """A fake transport. It records the prompt and returns scripted replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, *, model, system, user, max_tokens):
        self.calls.append(
            {"model": model, "system": system, "user": user, "max_tokens": max_tokens}
        )
        if not self.replies:
            raise AssertionError("The draft asked for another model call.")
        return self.replies.pop(0)


def _production(tmp_path: Path) -> Path:
    folder = tmp_path / "demo"
    folder.mkdir()
    return folder


def _screenplay(production: Path, text: str) -> Path:
    path = production / "screenplay.md"
    path.write_text(text, encoding="utf-8")
    return path


def _valid_draft(logline: str = "A rider chooses.") -> dict:
    return {
        "version": "0.1.0",
        "status": "draft",
        "approval": {"state": "pending", "by": None, "at": None, "note": ""},
        "production_id": "demo",
        "title": "Demo",
        "logline": logline,
        "theme_and_emotional_intent": {"theme": "MODEL-THEME", "emotional_intent": "Relief."},
        "tone_and_genre": {"tone": "Sparse", "genre": "western"},
        "characters": [{"name": "Ada", "role": "protagonist", "look": "Lean."}],
        "scenes": [{"what_happens": "She rides.", "emotional_purpose": "The road is larger."}],
        "deliverables": {"aspect_ratio": "2.39:1", "resolution": "1920x1080", "length": "3 minutes"},
        "open_questions": [],
        "constraints_and_budget": {"budget_cap_usd": 500},
    }


def _variant_draft() -> dict:
    """The four mistakes from the paid draft: renamed keys, a null resolution, a bad version."""
    document = _valid_draft("A rider chooses water.")
    document.pop("theme_and_emotional_intent")
    document.pop("tone_and_genre")
    document["version"] = "1.0-treatment-draft"
    document["theme"] = "MODEL-THEME"
    document["emotional_intent"] = "Relief when the rider chooses to live."
    document["tone"] = "Sparse and sun-bleached."
    document["genre"] = "western"
    document["deliverables"] = {"aspect_ratio": "2.39:1", "resolution": None, "length": "3 minutes"}
    return document


def _long_screenplay() -> str:
    marker = "END-OF-SCREENPLAY-MARKER"
    text = "EXT. ROAD - DAY\n\n" + ("He rides. " * 2500) + "\n\n" + marker + "\n"
    assert len(text) > 12000
    assert marker not in text[:12000]
    assert len(text) < DRAFT_SOURCE_CHAR_LIMIT
    return text


def test_the_four_model_mistakes_conform_into_a_valid_draft():
    raw = _variant_draft()
    schema = load_schema("treatment")
    before = validate_data(raw, schema)
    assert any("theme_and_emotional_intent" in item and "required" in item for item in before)
    assert any("tone_and_genre" in item and "required" in item for item in before)
    assert any(item.startswith("deliverables/resolution") and "string" in item for item in before)
    assert any("1.0-treatment-draft" in item for item in before)
    offline = {
        "deliverables": {
            "aspect_ratio": "16:9",
            "resolution": "1920x1080, framed in the delivery aspect ratio",
            "length": "Length is still open.",
        }
    }
    fixed = force_draft(conform_treatment(raw, fallback=offline))
    assert treatment_errors(fixed) == []
    assert fixed["theme_and_emotional_intent"]["theme"] == "MODEL-THEME"
    assert fixed["theme_and_emotional_intent"]["emotional_intent"] == "Relief when the rider chooses to live."
    assert fixed["tone_and_genre"]["tone"] == "Sparse and sun-bleached."
    assert fixed["tone_and_genre"]["genre"] == "western"
    assert fixed["deliverables"]["resolution"] == "1920x1080, framed in the delivery aspect ratio"
    assert fixed["deliverables"]["aspect_ratio"] == "2.39:1"
    assert fixed["deliverables"]["length"] == "3 minutes"
    assert fixed["version"] == "0.1.0"
    assert fixed["status"] == "draft"
    assert fixed["approval"]["state"] == "pending"


def test_a_live_draft_sends_the_full_screenplay_and_the_locked_files(tmp_path):
    production = _production(tmp_path)
    script_text = _long_screenplay()
    script = _screenplay(production, script_text)
    (production / "treatment").mkdir()
    (production / "treatment" / "inputs.json").write_text(
        json.dumps(
            {
                "logline": "LOCKED-INPUT-LOGLINE",
                "theme_and_emotional_intent": {
                    "theme": "LOCKED-THEME",
                    "emotional_intent": "A quiet choice.",
                },
            }
        ),
        encoding="utf-8",
    )
    (production / "props").mkdir()
    (production / "props" / "hero-props.json").write_text(
        json.dumps({"props": [{"name": "signal mirror", "locked_spec": "LOCKED-PROP-FACT"}]}),
        encoding="utf-8",
    )
    (production / "props" / "prop-definitions.json").write_text(
        json.dumps({"props": [{"name": "signal mirror", "locked_spec": "LOCKED-PROP-DEFINITION"}]}),
        encoding="utf-8",
    )
    spec = production / "props" / "signal" / "spec.json"
    spec.parent.mkdir()
    spec.write_text(json.dumps({"name": "signal mirror", "fact": "LOCKED-SPEC-FILE"}), encoding="utf-8")
    recorder = Recording([json.dumps(_valid_draft()), QUESTIONS])
    result = Director(production, llm=LLMClient(recorder)).intake(screenplay=script, run_id="run-1")
    assert result["drafted_by"] == "model"
    assert result["status"] == "draft"
    call = recorder.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["max_tokens"] == 8000
    assert script_text in call["user"]
    assert "END-OF-SCREENPLAY-MARKER" in call["user"]
    assert "was cut" not in call["user"]
    assert "LOCKED-INPUT-LOGLINE" in call["user"]
    assert "treatment/inputs.json" in call["user"]
    assert "must not re-ask" in call["user"]
    assert "LOCKED-PROP-FACT" in call["user"]
    assert "LOCKED-PROP-DEFINITION" in call["user"]
    assert "LOCKED-SPEC-FILE" in call["user"]
    assert "props/signal/spec.json" in call["user"]
    schema = load_schema("treatment")
    for key in schema["required"]:
        assert key in call["system"]
    assert schema["properties"]["version"]["pattern"] in call["system"]
    assert "Do not raise open questions" in call["system"]
    quote = quote_text_call("claude-sonnet-5-5", call["system"], call["user"], call["max_tokens"])
    assert quote["input_tokens_estimate"] == (len(call["system"]) + len(call["user"])) // 4
    sliced = call["user"].replace(script_text, script_text[:12000])
    short = quote_text_call("claude-sonnet-5-5", call["system"], sliced, call["max_tokens"])
    assert "END-OF-SCREENPLAY-MARKER" not in sliced
    assert quote["input_tokens_estimate"] > short["input_tokens_estimate"]
    assert quote["worst_case_usd"] > short["worst_case_usd"]
    treatment = json.loads(Path(result["treatment"]).read_text(encoding="utf-8"))
    assert treatment["status"] == "draft"
    assert treatment["logline"] == "LOCKED-INPUT-LOGLINE"
    assert "No model was called" not in treatment["draft_note"]
    assert "treatment/inputs.json" in treatment["draft_note"]


def test_a_partial_treatment_longer_than_the_old_cut_is_sent_whole(tmp_path):
    production = _production(tmp_path)
    script = _screenplay(production, "EXT. ROAD - DAY\n\nShe waits.\n")
    partial = production / "partial.json"
    partial.write_text(json.dumps({"logline": "P" * 7000, "title": "Demo"}), encoding="utf-8")
    recorder = Recording([json.dumps(_valid_draft()), QUESTIONS])
    Director(production, llm=LLMClient(recorder)).intake(
        screenplay=script, partial=partial, run_id="run-1"
    )
    user = recorder.calls[0]["user"]
    assert user.count("P") >= 7000
    assert "was cut" not in user


def test_a_screenplay_past_the_limit_is_cut_out_loud(tmp_path):
    production = _production(tmp_path)
    text = "EXT. ROAD - DAY\n\n" + ("A" * DRAFT_SOURCE_CHAR_LIMIT) + "NOT-SENT-TAIL\n"
    script = _screenplay(production, text)
    recorder = Recording([json.dumps(_valid_draft()), QUESTIONS])
    result = Director(production, llm=LLMClient(recorder)).intake(screenplay=script, run_id="run-1")
    user = recorder.calls[0]["user"]
    assert "NOT-SENT-TAIL" not in user
    assert "was cut from" in user
    assert "The rest was not sent." in user
    assert result["drafted_by"] == "model"
    assert "was cut from" in result["draft_note"]
    assert "The rest was not sent." in result["draft_note"]
    assert "No model was called" not in result["draft_note"]


def test_a_live_draft_conforms_the_four_mistakes_and_keeps_the_model_text(tmp_path):
    production = _production(tmp_path)
    script = _screenplay(production, "EXT. ROAD - DAY\n\nShe rides.\n")
    recorder = Recording([json.dumps(_variant_draft()), QUESTIONS])
    result = Director(production, llm=LLMClient(recorder)).intake(screenplay=script, run_id="run-1")
    assert result["drafted_by"] == "model"
    treatment = json.loads(Path(result["treatment"]).read_text(encoding="utf-8"))
    assert treatment_errors(treatment) == []
    assert treatment["theme_and_emotional_intent"]["theme"] == "MODEL-THEME"
    assert treatment["tone_and_genre"]["genre"] == "western"
    assert treatment["deliverables"]["resolution"] == "1920x1080, framed in the delivery aspect ratio"
    assert treatment["deliverables"]["length"] == "3 minutes"
    assert treatment["version"] == "0.1.0"
    assert treatment["status"] == "draft"
    assert "filled from the offline draft" not in treatment["draft_note"]
    assert "No model was called" not in treatment["draft_note"]
    assert list((production / "runs" / "run-1").glob("rejected-draft-*.txt")) == []


def test_a_missing_required_field_is_filled_from_the_offline_draft(tmp_path):
    production = _production(tmp_path)
    script = _screenplay(production, "EXT. ROAD - DAY\n\nShe rides.\n")
    document = _valid_draft("MODEL-LOGLINE")
    document.pop("characters")
    recorder = Recording([json.dumps(document), QUESTIONS])
    result = Director(production, llm=LLMClient(recorder)).intake(screenplay=script, run_id="run-1")
    assert result["drafted_by"] == "model"
    treatment = json.loads(Path(result["treatment"]).read_text(encoding="utf-8"))
    assert treatment_errors(treatment) == []
    assert treatment["logline"] == "MODEL-LOGLINE"
    assert treatment["characters"][0]["name"]
    assert "filled from the offline draft" in treatment["draft_note"]
    assert "No model was called" not in treatment["draft_note"]


def test_a_paid_rejection_keeps_the_reply_and_tells_the_truth(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    production = _production(tmp_path)
    script = _screenplay(production, "EXT. ROAD - DAY\n\nShe rides.\n")
    document = _variant_draft()
    document["logline"] = "A rider. " + SECRET
    document["scenes"] = [{"what_happens": "She rides.", "emotional_purpose": ""}]
    raw = json.dumps(document)
    recorder = Recording([raw, QUESTIONS])
    monkeypatch.setattr(
        "movie_swarm.cli_director.llm_for_command",
        lambda *args, **kwargs: LLMClient(recorder),
    )
    code = director_main(
        ["--production", str(production), "--run", "run-1", "--live", "intake", "--screenplay", str(script)]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "call cost was booked" in printed
    assert "No model was called" not in printed
    assert "emotional_purpose" in printed
    assert SECRET not in printed
    assert "The live draft was not used." not in printed
    treatment = json.loads((production / "treatment" / "treatment.json").read_text(encoding="utf-8"))
    assert treatment["draft_method"] == "offline-deterministic"
    assert "No model was called" not in treatment["draft_note"]
    assert "call cost was booked" in treatment["draft_note"]
    assert "emotional_purpose" in treatment["draft_note"]
    assert SECRET not in treatment["draft_note"]
    saved = list((production / "runs" / "run-1").glob("rejected-draft-*.txt"))
    assert len(saved) == 1
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    assert saved[0].name == f"rejected-draft-{digest}.txt"
    body = saved[0].read_text(encoding="utf-8")
    assert SECRET not in body
    assert "[redacted]" in body
    assert "MODEL-THEME" in body
    assert saved[0].name in treatment["draft_note"]


def test_the_offline_path_still_says_no_model_was_called(tmp_path):
    production = _production(tmp_path)
    script = _screenplay(production, "EXT. ROAD - DAY\n\nShe rides.\n")
    (production / "treatment").mkdir()
    (production / "treatment" / "inputs.json").write_text(
        json.dumps({"logline": "LOCKED-INPUT-LOGLINE"}),
        encoding="utf-8",
    )
    (production / "props").mkdir()
    (production / "props" / "hero-props.json").write_text(
        json.dumps({"locked_spec": "LOCKED-PROP-FACT"}),
        encoding="utf-8",
    )
    result = Director(production).intake(screenplay=script, run_id="run-1")
    assert result["drafted_by"] == "offline-deterministic"
    treatment = json.loads(Path(result["treatment"]).read_text(encoding="utf-8"))
    assert treatment["draft_note"].startswith(
        "Offline draft. No model was called, because this path does not use an API key."
    )
    assert "call cost was booked" not in treatment["draft_note"]
    assert "treatment/inputs.json" in treatment["draft_note"]
    assert "LOCKED-PROP-FACT" not in json.dumps(treatment)
    assert "LOCKED-INPUT-LOGLINE" in treatment["logline"]


def test_reconform_uses_the_cached_reply_and_does_not_call_a_model(tmp_path, capsys):
    production = _production(tmp_path)
    script = _screenplay(production, "EXT. ROAD - DAY\n\nShe rides.\n")
    raw = json.dumps(_variant_draft())
    request_hash = "a" * 64
    cache = production / "runs" / "run-1" / "provider-cache.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(
        json.dumps({"calls": {request_hash: {"status": "settled", "text": raw, "actual_usd": 0.0751}}}),
        encoding="utf-8",
    )
    code = director_main(
        [
            "--production",
            str(production),
            "--run",
            "run-1",
            "--live",
            "reconform",
            "--request",
            request_hash[:12],
            "--screenplay",
            str(script),
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "No new model call" in printed
    treatment = json.loads((production / "treatment" / "treatment.json").read_text(encoding="utf-8"))
    assert treatment_errors(treatment) == []
    assert treatment["draft_method"] == "model"
    assert treatment["theme_and_emotional_intent"]["theme"] == "MODEL-THEME"
    assert treatment["version"] == "0.1.0"
    assert treatment["status"] == "draft"
    assert "Nothing new was booked." in treatment["draft_note"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert list((production / "runs" / "run-1").glob("rejected-draft-*.txt")) == []


def test_intake_and_reconform_still_refuse_an_approved_treatment_and_answered_questions(tmp_path):
    production = _production(tmp_path)
    script = _screenplay(production, "EXT. ROAD - DAY\n\nShe rides.\n")
    director = Director(production)
    director.intake(screenplay=script, run_id="run-1")
    document = load_treatment(production)
    document["status"] = "approved"
    document["approval"] = {
        "state": "approved",
        "by": "ron",
        "at": "2026-11-12T00:00:00Z",
        "note": "Lock it.",
    }
    write_handoff(treatment_json_path(production), document, schema="treatment")
    with pytest.raises(DirectorError, match="approved"):
        director.intake(screenplay=script, run_id="run-1")
    with pytest.raises(DirectorError, match="approved"):
        director.reconform("abcdef0123456789", run_id="run-1")

    other = tmp_path / "other-demo"
    other.mkdir()
    other_script = _screenplay(other, "EXT. ROAD - DAY\n\nShe rides.\n")
    other_director = Director(other)
    other_director.intake(screenplay=other_script, run_id="run-1")
    questions_path = other / "treatment" / "questions.json"
    payload = json.loads(questions_path.read_text(encoding="utf-8"))
    payload["questions"][0]["answer"] = "Lock it."
    questions_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DirectorError, match="answers"):
        other_director.intake(screenplay=other_script, run_id="run-1")
    with pytest.raises(DirectorError, match="answers"):
        other_director.reconform("abcdef0123456789", run_id="run-1")


def test_the_writing_quote_grows_with_the_user_text(tmp_path):
    production = _production(tmp_path)
    LineProducer.start(production, run_id="run-1")
    client = GuardedLLM(production, "run-1")

    def quoted(user: str) -> str:
        try:
            client.complete(
                role="director",
                purpose="draft",
                system="Be brief.",
                user=user,
                max_tokens=8000,
            )
        except WritingQuote as exc:
            return str(exc)
        raise AssertionError("The call should have stopped at the quote.")

    short = quoted("Write a line.")
    long = quoted("He rides. " * 3000)
    assert "Worst case:" in short
    assert "Worst case:" in long
    assert "Nothing was sent." in long
    assert "estimate, character count / 4" in long
    short_tokens = int(short.split("Input tokens: ", 1)[1].split(" ", 1)[0])
    long_tokens = int(long.split("Input tokens: ", 1)[1].split(" ", 1)[0])
    short_worst = float(short.split("Worst case: $", 1)[1].split(" ", 1)[0])
    long_worst = float(long.split("Worst case: $", 1)[1].split(" ", 1)[0])
    assert long_tokens > short_tokens
    assert long_worst > short_worst
    assert long_tokens == (len("Be brief.") + len("He rides. " * 3000)) // 4
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
