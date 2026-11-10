"""Treatment checklist, intake formats, and the question round trip."""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.paths import repo_root

import pytest

from movie_swarm.director import Director
from movie_swarm.llm import LLMClient
from movie_swarm.script_intake import load_source
from movie_swarm.treatment_doc import treatment_errors
from movie_swarm.validate import load_schema, validate_data


class Scripted:
    def __init__(self, replies):
        self.replies = list(replies)
        self.models = []

    def complete(self, *, model, system, user, max_tokens):
        self.models.append(model)
        return self.replies.pop(0)


def _pdf(path: Path, text: str) -> None:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 72 720 Td ({safe}) Tj ET\n".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(bytes(out))


def _minimal_model_treatment(production_id: str, logline: str, status: str = "draft") -> str:
    document = {
        "version": "0.1.0",
        "status": status,
        "approval": {
            "state": "approved" if status == "approved" else "pending",
            "by": "Director" if status == "approved" else None,
            "at": "2026-11-10T00:00:00Z" if status == "approved" else None,
            "note": "",
        },
        "production_id": production_id,
        "title": "Demo",
        "logline": logline,
        "theme_and_emotional_intent": {"theme": "Survival", "emotional_intent": "Relief."},
        "tone_and_genre": {"tone": "Sparse", "genre": "western"},
        "characters": [{"name": "Miguel", "role": "protagonist", "look": "Lean."}],
        "scenes": [{"what_happens": "He rides.", "emotional_purpose": "The desert is larger."}],
        "deliverables": {"aspect_ratio": "2.39:1", "resolution": "1920x1080", "length": "3 minutes"},
        "open_questions": [],
        "constraints_and_budget": {"budget_cap_usd": 500, "stage_split": {"production": 500}},
    }
    return json.dumps(document)


def test_committed_last_marker_treatment_is_an_unapproved_draft():
    path = repo_root() / "productions" / "the-last-marker" / "treatment" / "treatment.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["status"] == "draft"
    assert document["draft_method"] == "offline-deterministic"
    assert document["approval"]["state"] == "pending"
    assert document["world_and_period"].startswith("Baja California, 1967")
    assert treatment_errors(document) == []


def test_missing_logline_is_named():
    document = {
        "version": "0.1.0",
        "status": "draft",
        "approval": {"state": "pending"},
        "production_id": "demo",
        "title": "Demo",
        "theme_and_emotional_intent": {"theme": "Survival", "emotional_intent": "Relief."},
        "tone_and_genre": {"tone": "Sparse", "genre": "western"},
        "characters": [{"name": "Miguel", "role": "protagonist", "look": "Lean."}],
        "scenes": [{"what_happens": "He rides.", "emotional_purpose": "Big."}],
        "deliverables": {"aspect_ratio": "2.39:1", "resolution": "1920x1080", "length": "3 minutes"},
        "open_questions": [],
    }
    errors = validate_data(document, load_schema("treatment"))
    assert any("logline" in error for error in errors)


def test_approved_without_a_person_fails():
    document = json.loads(_minimal_model_treatment("demo", "A rider chooses.", status="approved"))
    document["approval"]["by"] = None
    errors = validate_data(document, load_schema("treatment"))
    assert errors


@pytest.mark.parametrize(
    "suffix, kind",
    [(".md", "markdown"), (".fountain", "fountain")],
)
def test_text_screenplay_scenes(tmp_path, suffix, kind):
    path = tmp_path / f"script{suffix}"
    path.write_text(
        "Title: Desert Ride\n\nEXT. DESERT - DAY\n\nMiguel rides west.\n",
        encoding="utf-8",
    )
    source = load_source(path)
    assert source.kind == kind
    assert source.scenes
    assert "DESERT" in source.scenes[0]["heading"].upper()
    assert "Miguel" in source.scenes[0]["body"]


def test_pdf_and_docx(tmp_path):
    pdf = tmp_path / "script.pdf"
    _pdf(pdf, "EXT. DESERT - DAY Miguel rides west.")
    parsed = load_source(pdf)
    assert parsed.kind == "pdf"
    assert "EXT. DESERT" in parsed.text
    assert parsed.scenes

    from docx import Document

    docx_path = tmp_path / "script.docx"
    document = Document()
    document.add_paragraph("EXT. GARAGE - NIGHT")
    document.add_paragraph("The engine will not start.")
    document.save(docx_path)
    parsed_docx = load_source(docx_path)
    assert parsed_docx.kind == "docx"
    assert parsed_docx.scenes
    assert "GARAGE" in parsed_docx.scenes[0]["heading"].upper()


def test_partial_treatment_and_screenplay_together(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    script = production / "script.md"
    script.write_text("### EXT. DESERT - DAY\n\nHe rides until the engine dies.\n", encoding="utf-8")
    partial = production / "partial.json"
    partial.write_text(
        json.dumps({"title": "Demo", "logline": "Ron already wrote this logline."}),
        encoding="utf-8",
    )
    result = Director(production).intake(screenplay=script, partial=partial, run_id="run-1")
    treatment = json.loads(Path(result["treatment"]).read_text(encoding="utf-8"))
    assert treatment["logline"] == "Ron already wrote this logline."
    assert treatment["scenes"][0]["what_happens"]
    assert treatment["status"] == "draft"
    assert treatment_errors(treatment) == []


def test_question_round_trip_stays_a_draft(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    script = production / "script.md"
    script.write_text(
        "# Demo\n\n### EXT. DESERT - DAY\n\nMiguel rides west. The bike coughs.\n",
        encoding="utf-8",
    )
    director = Director(production)
    director.intake(screenplay=script, run_id="run-1")
    questions = json.loads((production / "treatment" / "questions.json").read_text())
    assert questions["status"] == "open"
    assert {item["topic"] for item in questions["questions"]} >= {
        "intent",
        "tone",
        "references",
        "character-arcs",
        "withheld",
        "action-beats",
        "hero-props",
        "budget-split",
    }
    # Leave the arc unanswered so the round stays open.
    answers = {
        "round": 1,
        "answers": [
            {"id": item["id"], "answer": "Locked."}
            for item in questions["questions"]
            if item["id"] != "q-arcs"
        ],
    }
    path = production / "answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    partial = director.answer(path, run_id="run-1")
    assert partial["questions_status"] == "open"
    assert partial["open_required"] == 1
    assert partial["status"] == "draft"

    questions = json.loads((production / "treatment" / "questions.json").read_text())
    for item in questions["questions"]:
        if not item.get("answer"):
            item["answer"] = "He chooses to live. He does not become someone else."
    path.write_text(json.dumps(questions), encoding="utf-8")
    done = director.answer(path, run_id="run-1")
    assert done["questions_status"] == "closed"
    assert done["status"] == "draft"
    treatment = json.loads((production / "treatment" / "treatment.json").read_text())
    assert treatment["status"] == "draft"
    assert treatment["approval"]["state"] == "pending"
    assert "live" in treatment["characters"][0]["arc"]


def test_models_are_routed_and_cannot_self_approve(tmp_path):
    production = tmp_path / "demo"
    production.mkdir()
    script = production / "script.md"
    script.write_text("### EXT. DESERT - DAY\n\nHe rides.\n", encoding="utf-8")
    scripted = Scripted([
        _minimal_model_treatment("demo", "Model logline.", status="approved"),
        json.dumps({"questions": [{"id": "q-intent", "question": "Lock the intent, Ron?"}]}),
        _minimal_model_treatment("demo", "FINAL PASS", status="approved"),
    ])
    director = Director(production, llm=LLMClient(scripted))
    result = director.intake(screenplay=script, run_id="run-1")
    assert result["drafted_by"] == "model"
    treatment = json.loads(Path(result["treatment"]).read_text())
    assert treatment["status"] == "draft"
    assert treatment["logline"] == "Model logline."
    questions = json.loads(Path(result["questions"]).read_text())
    intent = next(item for item in questions["questions"] if item["id"] == "q-intent")
    assert intent["question"] == "Lock the intent, Ron?"
    answers = {
        "answers": [{"id": item["id"], "answer": "Yes. production=100, qa=50"} for item in questions["questions"]]
    }
    # The budget answer is the same for every question. The budget topic still parses the pairs.
    path = production / "answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    director.answer(path, run_id="run-1")
    revised = json.loads((production / "treatment" / "treatment.json").read_text())
    assert revised["logline"] == "FINAL PASS"
    assert revised["status"] == "draft"
    assert revised["approval"]["state"] == "pending"
    assert scripted.models == [
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
        "claude-opus-5-5",
    ]


def test_lock_it_keeps_the_draft_and_prop_sides_are_recorded():
    from movie_swarm.treatment_doc import apply_answers, build_questions

    treatment = json.loads(_minimal_model_treatment("demo", "A rider chooses."))
    treatment["theme_and_emotional_intent"]["theme"] = "Arrive first. Winning can wait."
    treatment["hero_props"] = [
        {
            "name": "1965 Triumph TR6SC",
            "locked_spec": "1965 Triumph. Exhaust side is not locked.",
            "sidedness": "not locked",
            "reference_images": [],
        },
        {
            "name": "Breitling Top Time",
            "locked_spec": "Black dial. Which wrist it sits on is not locked.",
            "sidedness": "not locked",
            "reference_images": [],
        },
    ]
    treatment["scenes"][0]["what_happens"] = "He sees a canyon and the word agua."
    treatment["action_and_stunt_beats"] = ["Three kicks."]
    treatment["constraints_and_budget"]["stage_split"] = {"production": 270, "fix-loop": 50}
    questions = build_questions(treatment)
    answers = {
        "q-intent": "Lock it.",
        "q-tone": "Lock it.",
        "q-references": "Lock it.",
        "q-arcs": "He wants to finish the race, but in the end water (life) is more important. (He chooses life over winning.)",
        "q-withheld": "Withhold whether the canyon really has water.",
        "q-action": "Yes, those beats.",
        "q-props": "Yes, lock exhaust on the RIGHT side and the watch on the LEFT wrist.",
        "q-budget": "Looks good, approve the proposed split as written.",
    }
    apply_answers(treatment, questions, answers)
    assert treatment["theme_and_emotional_intent"]["emotional_intent"] == "Relief."
    assert treatment["tone_and_genre"]["tone"] == "Sparse"
    assert "From Ron" not in [item["reference"] for item in treatment.get("reference_lookbook") or []]
    assert "life over winning" in treatment["characters"][0]["arc"]
    assert treatment["scenes"][0]["withheld"] == "Withhold whether the canyon really has water."
    assert treatment["action_and_stunt_beats"] == ["Three kicks."]
    triumph = treatment["hero_props"][0]
    watch = treatment["hero_props"][1]
    assert triumph["sidedness"] == "exhaust on the right"
    assert "right" in triumph["locked_spec"].lower()
    assert watch["sidedness"] == "left wrist"
    assert "left wrist" in watch["locked_spec"].lower()
    assert treatment["constraints_and_budget"]["stage_split"]["production"] == 270
    assert questions["status"] == "closed"
