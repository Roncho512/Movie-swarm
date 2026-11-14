"""Phase 8.18: the graphic designer researches, and the title card keeps its words.

Harbor Night stays a documentary. A synthetic yard film carries a title-card
direction, a featured object, and a look whose name matches a design pack.
Nothing here calls a provider. Spent stays $0.
"""

from __future__ import annotations

import json
from pathlib import Path

from movie_swarm.graphics import _matched_packs, build_graphics, write_guide, write_research
from movie_swarm.line_producer import LineProducer
from movie_swarm.mentions import advertising_phrases
from movie_swarm.paths import repo_root
from movie_swarm.treatment_doc import proposed_split
from movie_swarm.validate import load_schema, validate_data, validate_file
from tests.test_phase5 import _harbor


def _ready(tmp_path: Path) -> tuple[Path, LineProducer]:
    production = _harbor(tmp_path)
    producer = LineProducer.start(production, run_id="run-1")
    producer.approve_gate("treatment", "approved", "ron", stage_split=proposed_split(500))
    return production, producer


def _screen(production: Path, text: str) -> None:
    (production / "screenplay" / "harbor-night.md").write_text(text, encoding="utf-8")


def test_a_title_card_keeps_the_title_and_the_direction_apart(tmp_path):
    production, producer = _ready(tmp_path)
    _screen(
        production,
        "\n".join(
            [
                "TITLE CARD over the blue dusk landscape. Same vintage pulp typography.",
                "",
                '# **"YARD LIGHT"**',
                "",
                "Hold for three seconds.",
                "",
                "EXT. YARD - DUSK",
                "",
                "Ada ties the scarf.",
                "",
            ]
        ),
    )
    research = write_research(production)
    cues = [item for item in research["items"] if item["item_id"].startswith("typography-")]
    assert cues
    assert cues[0]["text"] == "Typography style: vintage pulp typography."
    assert cues[0]["basis"] == "sourced"
    assert cues[0]["source_file"] == "screenplay/harbor-night.md"
    guide = write_guide(production)
    wordmark = " ".join(rule["text"] for rule in guide["wordmark"]["rules"])
    assert "vintage pulp typography" in wordmark
    assert guide["status"] == "draft"
    producer.approve_gate("graphics", "approved", "ron", note="The brand guide can be used.")
    package = build_graphics(production)
    card = package["title_cards"][0]
    assert card["text"] == "YARD LIGHT"
    assert card["design_direction"] == "over the blue dusk landscape. Same vintage pulp typography"
    assert card["text"] not in card["design_direction"]
    assert validate_file(production / "graphics" / "graphics.json").ok


def test_a_same_line_card_is_the_copy_and_a_bare_direction_is_not(tmp_path):
    production, _producer = _ready(tmp_path)
    _screen(
        production,
        "\n".join(
            [
                "TITLE CARD: THREE DAYS LATER",
                "",
                "TITLE CARD over black. Same block lettering.",
                "",
                "FADE OUT.",
                "",
                "EXT. YARD - DAY",
                "",
                "Ada ties the scarf.",
                "",
            ]
        ),
    )
    write_research(production)
    write_guide(production)
    LineProducer.open(production, "run-1").approve_gate("graphics", "approved", "ron", note="Use it.")
    package = build_graphics(production)
    texts = [card["text"] for card in package["title_cards"]]
    assert texts == ["THREE DAYS LATER"]
    assert package["title_cards"][0]["design_direction"] == ""
    research = json.loads((production / "graphics" / "research.json").read_text(encoding="utf-8"))
    directions = [item["text"] for item in research["items"] if item["item_id"].startswith("title-direction-")]
    assert any("over black" in text for text in directions)
    assert not any(card["text"].casefold().startswith("over ") for card in package["title_cards"])


def test_featured_product_rules_reach_the_guide_without_selling(tmp_path):
    production, producer = _ready(tmp_path)
    brief = {
        "production_id": "harbor-night",
        "title": "Harbor Night",
        "concept": "A night worker ties a scarf.",
        "target_runtime_seconds": 60,
        "visual_style": {"description": "Cool fluorescent light."},
        "created_at": "2026-01-01T00:00:00Z",
        "featured_product": {
            "product": "North Lamp",
            "placement_intent": "Subtle. It stays in the story.",
            "rules": [
                "The lamp is readable in one close view tied to the hour.",
                "Never make it ad-like. No logo-forward hero spins.",
                "This is a product shot of the lamp.",
            ],
        },
    }
    (production / "production-brief.json").write_text(json.dumps(brief), encoding="utf-8")
    research = write_research(production)
    rules = [item["text"] for item in research["items"] if item["item_id"].startswith("placement-")]
    assert any("logo-forward hero spins" in text for text in rules)
    assert not any("product shot" in text.casefold() for text in rules)
    guide = write_guide(production)
    blob = json.dumps(guide)
    assert "logo-forward hero spins" in blob
    assert "something for sale" in blob
    assert advertising_phrases(blob) == []
    assert guide["status"] == "draft"
    producer.approve_gate("graphics", "approved", "ron", note="Use it.")
    package = build_graphics(production)
    assert package["key_art"]["placement_rules"]
    assert package["collateral"][0]["placement_rules"] == package["key_art"]["placement_rules"]
    assert advertising_phrases(json.dumps(package)) == []
    assert "product shot" not in json.dumps(package).casefold()


def test_a_matching_pack_is_a_proposal_and_harbor_night_does_not_inherit_it(tmp_path):
    plain, _producer = _ready(tmp_path)
    write_research(plain)
    quiet = write_guide(plain)
    assert quiet["fonts"]["title"]["family"] == "not named"
    assert quiet["fonts"]["credits"]["family"] == "not named"
    assert "blood red" not in {color["name"] for color in quiet["palette"]}
    assert quiet["palette"][0]["value"].startswith("#")
    assert quiet["palette"][0]["provenance"] == "SOURCED FROM PRODUCTION DOCS"
    assert quiet.get("custom_title") is None
    assert quiet["status"] == "draft"
    assert "DESIGNER PROPOSAL" in (plain / "graphics" / "brand-guide.md").read_text(encoding="utf-8")
    assert "SOURCED FROM PRODUCTION DOCS" in (plain / "graphics" / "brand-guide.md").read_text(encoding="utf-8")

    production = _harbor(tmp_path / "west")
    LineProducer.start(production, run_id="run-1").approve_gate(
        "treatment", "approved", "ron", stage_split=proposed_split(500)
    )
    look_path = production / "look" / "look.json"
    look = json.loads(look_path.read_text(encoding="utf-8"))
    look["look_name"] = "spaghetti western"
    look["palette"] = ["red"]
    look_path.write_text(json.dumps(look), encoding="utf-8")
    bible_path = production / "visual-style-bible.json"
    bible = json.loads(bible_path.read_text(encoding="utf-8"))
    bible["color_system"]["palette"] = []
    bible_path.write_text(json.dumps(bible), encoding="utf-8")
    research = write_research(production)
    assert any(item["item_id"].startswith("font-title-rye") for item in research["items"])
    assert any(item["basis"] == "designer-proposal" and item["reference"].startswith("https://") for item in research["items"])
    guide = write_guide(production)
    assert guide["status"] == "draft"
    assert guide["fonts"]["title"]["family"] == "Rye"
    assert guide["fonts"]["title"]["provenance"] == "DESIGNER PROPOSAL"
    assert "SIL Open Font License 1.1" in guide["fonts"]["title"]["licensing"]
    assert {item["family"] for item in guide["fonts"]["title"]["alternates"]} == {"Sancreek"}
    assert guide["fonts"]["credits"]["family"] == "Libre Baskerville"
    assert guide["fonts"]["credits"]["category"] == "serif"
    assert guide["fonts"]["subtitles"]["family"] == "Noto Sans"
    assert guide["fonts"]["marketing"]["family"] == "Alfa Slab One"
    custom = guide["custom_title"]
    assert custom["name"] == "Painted pulp capitals"
    assert custom["built"] is False
    assert custom["provenance"] == "DESIGNER PROPOSAL"
    colors = {color["name"]: color for color in guide["palette"]}
    assert colors["red"]["value"] == "#FF0000"
    assert colors["red"]["provenance"] == "DESIGNER PROPOSAL"
    assert colors["blood red"]["provenance"] == "DESIGNER PROPOSAL"
    assert colors["blood red"]["value"] == "#8C1C13"
    assert guide["surfaces"]["title"]
    assert guide["surfaces"]["poster"]
    assert guide["surfaces"]["key_art"]
    assert guide["surfaces"]["credits"]
    assert any("period face" in rule["text"] for rule in guide["surfaces"]["credits"])
    assert not any("sans-serif" in rule["text"] for rule in guide["surfaces"]["credits"])
    assert "5%" in guide["layout"]["safe_area"]
    assert validate_file(production / "graphics" / "brand-guide.json").ok
    notes = (production / "graphics" / "brand-guide.md").read_text(encoding="utf-8")
    assert "DESIGNER PROPOSAL" in notes
    assert "https://" in notes


def test_every_pack_validates_and_a_credits_face_keeps_its_category(tmp_path):
    schema = load_schema("design-reference")
    folder = repo_root() / "config" / "design-references"
    packs = list(folder.glob("*.json"))
    assert packs
    for path in packs:
        errors = validate_data(json.loads(path.read_text(encoding="utf-8")), schema)
        assert errors == [], path.name
    pack = {
        "id": "period-credits",
        "match": {"always": True},
        "fonts": [
            {
                "role": "credits",
                "family": "Display Only",
                "category": "display",
                "license_name": "SIL Open Font License 1.1",
                "license_url": "https://example.com/ofl",
                "source_url": "https://example.com/face",
                "note": "The pack names the category.",
            }
        ],
    }
    directory = tmp_path / "packs"
    directory.mkdir()
    (directory / "period.json").write_text(json.dumps(pack), encoding="utf-8")
    matched = _matched_packs({}, {}, None, directory)
    assert len(matched) == 1
    font = matched[0][1]["fonts"][0]
    assert font["family"] == "Display Only"
    assert font["category"] == "display"


def test_the_graphics_module_stays_offline_and_generic():
    text = (repo_root() / "movie_swarm" / "graphics.py").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "urllib" not in text
    assert "requests" not in text
    for word in ("leone", "spaghetti", "triumph", "breitling", "baja", "morricone", "1965", "1967"):
        assert word not in text.casefold()
