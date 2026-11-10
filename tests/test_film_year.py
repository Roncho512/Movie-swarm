"""The Last Marker is set in 1967. The Triumph stays a 1965."""

from __future__ import annotations

import json

from movie_swarm.paths import repo_root


def test_no_film_year_1966_in_this_production():
    root = repo_root()
    offenders = []
    folder = root / "productions" / "the-last-marker"
    rejected = _rejected_phrases(folder)
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for phrase in rejected:
            text = text.replace(phrase, "")
        if "1966" in text:
            offenders.append(str(path.relative_to(root)))
    skill = (root / "agents" / "03-art-director" / "skill.md").read_text(encoding="utf-8")
    assert "1966" not in skill
    assert "1967" not in skill
    brief = json.loads((folder / "production-brief.json").read_text(encoding="utf-8"))
    assert brief["setting"]["year"] == "1967"
    assert offenders == []
    screenplay = (
        root / "productions" / "the-last-marker" / "screenplay" / "Pilot_-_the_last_marker_screenplay.md"
    ).read_text(encoding="utf-8")
    assert "1965 Triumph" in screenplay
    assert "1967" in screenplay


def _rejected_phrases(folder) -> list[str]:
    """Phrases a prop lock tells the checker to reject. Naming them is not the story year."""
    phrases = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "forbidden_phrases" and isinstance(value, list):
                    phrases.extend(str(item) for item in value if "1966" in str(item))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for path in folder.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        walk(data)
    return phrases
