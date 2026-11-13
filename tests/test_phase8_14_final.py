"""Phase 8.14: a cut-off final pass can be repaired, and a yes does not replace the draft.

No test sets a real provider key. The model is a fake. Nothing here books money.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from movie_swarm.cli_director import main as director_main
from movie_swarm.director import FINAL_PASS_MAX_TOKENS, Director
from movie_swarm.line_producer import LineProducer
from movie_swarm.llm import ModelReply
from movie_swarm.money import as_money
from movie_swarm.providers import estimate_input_tokens, quote_text_call
from movie_swarm.rates import token_dollars
from movie_swarm.treatment_doc import (
    apply_answers,
    build_questions,
    load_treatment,
    repair_truncated_json,
    treatment_errors,
)
from movie_swarm.delivery import _probe_media


def _production(tmp_path: Path) -> Path:
    folder = tmp_path / "demo"
    folder.mkdir()
    script = folder / "screenplay.md"
    script.write_text("EXT. CANYON - DAY\n\nShe rides toward the canyon.\n", encoding="utf-8")
    Director(folder).intake(screenplay=script, run_id="run-1")
    return folder


def _answers(production: Path, value: str = "Lock.") -> Path:
    questions = json.loads((production / "treatment" / "questions.json").read_text(encoding="utf-8"))
    path = production / "answers.json"
    path.write_text(
        json.dumps(
            {"answers": [{"id": item["id"], "answer": value} for item in questions["questions"]]}
        ),
        encoding="utf-8",
    )
    return path


class Recording:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, *, role, purpose, system, user, max_tokens):
        self.calls.append(
            {"role": role, "purpose": purpose, "system": system, "user": user, "max_tokens": max_tokens}
        )
        if not self.replies:
            raise AssertionError("The final pass asked for another model call.")
        return self.replies.pop(0)


def _cut_inside_notes(document: dict) -> str:
    body = json.dumps(document)
    needle = document["constraints_and_budget"].get("notes") or ""
    if needle and needle in body:
        return body[: body.rfind(needle) + max(8, len(needle) // 2)]
    return body[: max(1, len(body) - 12)]


def test_a_cut_off_object_drops_the_unfinished_field_and_closes():
    raw = '{"title": "Demo", "constraints_and_budget": {"budget_cap_usd": 500, "notes": "Keep this'
    parsed, dropped = repair_truncated_json(raw)
    assert parsed["title"] == "Demo"
    assert parsed["constraints_and_budget"]["budget_cap_usd"] == 500
    assert "notes" not in parsed["constraints_and_budget"]
    assert dropped == ["constraints_and_budget.notes"]
    whole, nothing = repair_truncated_json('{"title": "Demo"}')
    assert whole == {"title": "Demo"}
    assert nothing == []


def test_the_final_pass_allows_16000_tokens_and_names_the_output_limit(tmp_path):
    production = _production(tmp_path)
    before = load_treatment(production)
    before["logline"] = "The repaired logline stays."
    before["constraints_and_budget"]["notes"] = "The budget note runs long and is cut off at the end of the reply."
    cut = _cut_inside_notes(before)
    assert not cut.rstrip().endswith("}")
    reply = ModelReply(
        cut,
        stop_reason="max_tokens",
        output_tokens=FINAL_PASS_MAX_TOKENS,
        max_tokens=FINAL_PASS_MAX_TOKENS,
    )
    recorder = Recording([reply])
    result = Director(production, llm=recorder).answer(_answers(production), run_id="run-1")
    assert recorder.calls[0]["purpose"] == "final"
    assert recorder.calls[0]["max_tokens"] == FINAL_PASS_MAX_TOKENS
    assert recorder.calls[0]["max_tokens"] == 16000
    treatment = load_treatment(production)
    assert treatment_errors(treatment) == []
    assert treatment["logline"] == "The repaired logline stays."
    assert treatment["status"] == "draft"
    assert "output limit" in treatment["draft_note"].casefold()
    assert "stop_reason was max_tokens" in treatment["draft_note"]
    assert f"reached the max of {FINAL_PASS_MAX_TOKENS}" in treatment["draft_note"]
    assert "Dropped: constraints_and_budget.notes" in treatment["draft_note"]
    assert "repaired" in treatment["draft_note"].casefold()
    assert result["draft_note"] == treatment["draft_note"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_a_final_pass_that_is_not_json_is_saved_and_the_draft_stays(tmp_path):
    production = _production(tmp_path)
    original = load_treatment(production)["logline"]
    reply = ModelReply(
        "not json at all",
        stop_reason="max_tokens",
        output_tokens=8000,
        max_tokens=8000,
    )
    Director(production, llm=Recording([reply])).answer(_answers(production, "Keep."), run_id="run-1")
    treatment = load_treatment(production)
    assert treatment["logline"] == original
    assert treatment["tone_and_genre"]["tone"] != "Keep."
    assert "Locked the drafted tone." in treatment["draft_note"]
    assert "output limit" in treatment["draft_note"].casefold()
    assert "earlier draft was kept" in treatment["draft_note"]
    saved = list((production / "runs" / "run-1").glob("rejected-final-*.txt"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == "not json at all"
    assert "rejected-final-" in treatment["draft_note"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_a_final_pass_may_return_only_the_changed_field(tmp_path):
    production = _production(tmp_path)
    tone = load_treatment(production)["tone_and_genre"]["tone"]
    Director(production, llm=Recording(['{"logline": "Only the logline changed."}'])).answer(
        _answers(production), run_id="run-1"
    )
    treatment = load_treatment(production)
    assert treatment_errors(treatment) == []
    assert treatment["logline"] == "Only the logline changed."
    assert treatment["tone_and_genre"]["tone"] == tone
    assert treatment["status"] == "draft"


def test_the_cli_prints_the_output_limit(tmp_path, monkeypatch, capsys):
    production = _production(tmp_path)
    answers = _answers(production)
    reply = ModelReply(
        "not json at all",
        stop_reason="max_tokens",
        output_tokens=FINAL_PASS_MAX_TOKENS,
        max_tokens=FINAL_PASS_MAX_TOKENS,
    )
    monkeypatch.setattr(
        "movie_swarm.cli_director.llm_for_command",
        lambda *args, **kwargs: Recording([reply]),
    )
    code = director_main(
        ["--production", str(production), "--run", "run-1", "--live", "answer", "--answers", str(answers)]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "The final pass hit the output limit." in printed
    assert "stop_reason was max_tokens" in printed
    assert "rejected-final-" in printed
    assert "Ron has not approved it." in printed


def test_reconform_repairs_a_truncated_final_pass_and_books_nothing(tmp_path, capsys):
    production = _production(tmp_path)
    Director(production).answer(_answers(production, "Lock."), run_id="run-1")
    current = load_treatment(production)
    tone = current["tone_and_genre"]["tone"]
    assert tone != "Lock."
    revised = json.loads(json.dumps(current))
    revised["logline"] = "Rebuilt from the saved reply."
    revised["constraints_and_budget"]["notes"] = "The note was still being written when the reply stopped"
    raw = _cut_inside_notes(revised)
    request_hash = "b" * 64
    cache = production / "runs" / "run-1" / "provider-cache.json"
    cache.write_text(
        json.dumps(
            {
                "calls": {
                    request_hash: {
                        "status": "settled",
                        "purpose": "final",
                        "text": raw,
                        "stop_reason": "max_tokens",
                        "output_tokens": 8000,
                        "max_tokens": 8000,
                        "truncated": True,
                        "actual_usd": 0.1799,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    questions_before = (production / "treatment" / "questions.json").read_text(encoding="utf-8")
    code = director_main(
        [
            "--production",
            str(production),
            "--run",
            "run-1",
            "reconform",
            "--request",
            request_hash[:12],
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "Nothing new was booked" in printed
    assert "truncated paid reply" in printed
    assert "Dropped:" in printed
    treatment = load_treatment(production)
    assert treatment_errors(treatment) == []
    assert treatment["logline"] == "Rebuilt from the saved reply."
    assert treatment["tone_and_genre"]["tone"] == tone
    assert treatment["status"] == "draft"
    assert "Nothing new was booked." in treatment["draft_note"]
    assert (production / "treatment" / "questions.json").read_text(encoding="utf-8") == questions_before
    assert "Lock." in questions_before
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0
    assert list((production / "runs" / "run-1").glob("rejected-final-*.txt")) == []

    document = load_treatment(production)
    document["status"] = "approved"
    document["approval"] = {
        "state": "approved",
        "by": "ron",
        "at": "2026-11-12T00:00:00Z",
        "note": "Approved.",
    }
    from movie_swarm.handoff import write_handoff
    from movie_swarm.treatment_doc import treatment_json_path

    write_handoff(treatment_json_path(production), document, schema="treatment")
    approved = load_treatment(production)
    result = Director(production).reconform(request_hash, run_id="run-1")
    saved = load_treatment(production)
    assert result["status"] == "approved"
    assert saved["status"] == "approved"
    assert saved["logline"] == approved["logline"]
    assert saved["scenes"] == approved["scenes"]
    assert saved["approval"] == approved["approval"]
    assert saved["tone_and_genre"] == approved["tone_and_genre"]


def test_reconform_repairs_a_truncated_draft_when_no_answers_are_stored(tmp_path):
    production = _production(tmp_path)
    raw = json.dumps(
        {
            "logline": "From the cached draft.",
            "theme_and_emotional_intent": {"theme": "MODEL-THEME", "emotional_intent": "Relief."},
        }
    )
    raw = raw[:-1]  # drop the closing brace
    request_hash = "c" * 64
    cache = production / "runs" / "run-1" / "provider-cache.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({"calls": {request_hash: {"status": "settled", "purpose": "draft", "text": raw}}}),
        encoding="utf-8",
    )
    result = Director(production).reconform(request_hash, run_id="run-1")
    treatment = load_treatment(production)
    assert treatment_errors(treatment) == []
    assert treatment["logline"] == "From the cached draft."
    assert treatment["theme_and_emotional_intent"]["theme"] == "MODEL-THEME"
    assert treatment["title"]
    assert treatment["scenes"]
    assert "Repaired a truncated reply" in result["draft_note"]
    assert "Nothing new was booked" in result["draft_note"]
    assert LineProducer.open(production, "run-1").run.data["cost_usd"] == 0


def test_a_confirmation_keeps_the_drafted_text_and_withheld_is_recorded_once():
    treatment = {
        "version": "0.1.0",
        "status": "draft",
        "approval": {"state": "pending", "by": None, "at": None, "note": ""},
        "production_id": "demo",
        "title": "Demo",
        "logline": "A rider chooses.",
        "theme_and_emotional_intent": {"theme": "Water", "emotional_intent": "Relief."},
        "tone_and_genre": {"tone": "Sparse and sun-bleached.", "genre": "western"},
        "characters": [{"name": "Ada", "role": "protagonist", "look": "Lean.", "arc": "She wants to finish."}],
        "scenes": [
            {
                "heading": "The canyon",
                "what_happens": "She sees the canyon and wonders about water.",
                "emotional_purpose": "Doubt.",
            },
            {
                "heading": "The canyon again",
                "what_happens": "She leaves the canyon without knowing.",
                "emotional_purpose": "The choice.",
            },
        ],
        "deliverables": {"aspect_ratio": "2.39:1", "resolution": "1920x1080", "length": "3 minutes"},
        "open_questions": [],
        "constraints_and_budget": {"budget_cap_usd": 500, "stage_split": {"production": 270}},
        "draft_note": "Offline draft.",
    }
    questions = build_questions(treatment)
    for word in ("Lock", "Lock.", "Lock it", "Yes", "Approved", "Keep"):
        sample = json.loads(json.dumps(treatment))
        sample_questions = json.loads(json.dumps(questions))
        apply_answers(sample, sample_questions, {"q-tone": word})
        assert sample["tone_and_genre"]["tone"] == "Sparse and sun-bleached.", word
        assert "Locked the drafted tone." in sample["draft_note"]
        assert word not in sample["tone_and_genre"]["tone"]
    apply_answers(
        treatment,
        questions,
        {
            "q-tone": "That's all: Lock.",
            "q-withheld": "That's all: withhold only whether the canyon really has water.",
            "q-arcs": "That's all: she chooses water over the finish.",
        },
    )
    assert treatment["tone_and_genre"]["tone"] == "Sparse and sun-bleached."
    assert treatment["characters"][0]["arc"] == "she chooses water over the finish."
    assert "That's all" not in treatment["characters"][0]["arc"]
    withheld = [scene.get("withheld") for scene in treatment["scenes"]]
    assert withheld[0] in (None, "")
    assert withheld[1] == "withhold only whether the canyon really has water."
    assert "That's all" not in withheld[1]
    rendered = json.dumps(treatment["scenes"])
    assert rendered.count("withhold only whether the canyon really has water.") == 1


def test_the_conservative_estimate_covers_the_recorded_calls():
    """The paid calls booked more than character count / 4 had quoted.

    The character counts are the ones implied by those quotes, using the
    prices on the rate card and a max output of 8,000. The old estimate was
    character count // 4. The remainder was dropped, so each count here is
    the smallest multiple of 4 that produces the quote.

    - Sonnet draft, max output 8,000, quote $0.1456. At $2 and $10 per
      million tokens that is 32,800 input tokens, so the prompt was 131,200
      characters. The call booked $0.1686.
    - Opus final pass, max output 8,000, quote $0.1722. At $4 and $20 per
      million tokens that is 3,050 input tokens, so the prompt was 12,200
      characters. The provider reported 4,978 input tokens and 8,000 output
      tokens. That books $0.1799.

    The fixtures are treatment-shaped text of those lengths. The new quote
    uses character count / 3, plus 25 percent, plus 200 tokens, rounded up,
    and prices every allowed output token. That worst case is what the
    ceiling check uses.
    """
    sonnet_chars = 131_200
    opus_chars = 12_200
    assert token_dollars(sonnet_chars // 4, 8000, as_money("2"), as_money("10")) == as_money("0.1456")
    assert token_dollars(opus_chars // 4, 8000, as_money("4"), as_money("20")) == as_money("0.1722")
    opus_actual = token_dollars(4978, 8000, as_money("4"), as_money("20"))
    assert opus_actual == as_money("0.1799")

    def shaped(count: int) -> str:
        unit = '{"scene": "A rider crosses the canyon and does not say if the canyon has water."} '
        text = (unit * ((count // len(unit)) + 1))[:count]
        assert len(text) == count
        return text

    sonnet = quote_text_call("claude-sonnet-5-5", "", shaped(sonnet_chars), 8000)
    opus = quote_text_call("claude-opus-5-5", "", shaped(opus_chars), 8000)
    assert sonnet["input_tokens_estimate"] == estimate_input_tokens(sonnet_chars)
    assert sonnet["input_tokens_estimate"] > sonnet_chars // 4
    assert opus["input_tokens_estimate"] >= 4978
    assert as_money(sonnet["worst_case_usd"]) >= as_money("0.1686")
    assert as_money(opus["worst_case_usd"]) >= opus_actual
    assert "character count / 3, plus 25 percent, plus 200 tokens" in sonnet["text"]


def test_ffprobe_lookup_does_not_recurse_when_ffmpeg_is_hidden(tmp_path, monkeypatch):
    """The graphics test hides ffmpeg by wrapping shutil.which.

    That wrapper replaces the shared shutil.which. It has to call the original
    lookup. A probe of a file left under the asset root used to call the
    wrapper again until Python stopped it.
    """
    video = tmp_path / "master.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    original = shutil.which
    monkeypatch.setattr(
        "movie_swarm.graphics.shutil.which",
        lambda name, _which=original: None if name == "ffmpeg" else _which(name),
    )
    probe = _probe_media(video)
    assert isinstance(probe, dict)
    assert "recursion" not in json.dumps(probe).casefold()
