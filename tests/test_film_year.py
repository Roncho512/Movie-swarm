"""The Last Marker is set in 1967. The Triumph stays a 1965."""

from __future__ import annotations

from movie_swarm.paths import repo_root


def test_no_film_year_1966_in_this_production():
    root = repo_root()
    offenders = []
    folder = root / "productions" / "the-last-marker"
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "1966" in text:
            offenders.append(str(path.relative_to(root)))
    skill = (root / "agents" / "03-art-director" / "skill.md").read_text(encoding="utf-8")
    assert "1966" not in skill
    assert "1967" in skill
    assert offenders == []
    screenplay = (
        root / "productions" / "the-last-marker" / "screenplay" / "Pilot_-_the_last_marker_screenplay.md"
    ).read_text(encoding="utf-8")
    assert "1965 Triumph" in screenplay
    assert "1967" in screenplay
