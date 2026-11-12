"""Phase 8.9: doctor checks the machine and does not spend or print keys."""

from __future__ import annotations

import os

from movie_swarm.doctor import FAL_PING, main, report
from movie_swarm.redact import KEY_NAMES


SECRET = "doctor-test-key-do-not-leak"


class Transport:
    def __init__(self, status=200):
        self.status = status
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": dict(headers)})
        return self.status


def test_doctor_reports_presence_without_values_or_network(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    monkeypatch.setenv("FAL_KEY", "")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("MOVIE_SWARM_ASSET_ROOT", str(tmp_path / "drive"))
    env = tmp_path / ".env"
    env.write_text("ELEVENLABS_API_KEY=eleven-from-file-do-not-leak\nFAL_KEY=from-file\n", encoding="utf-8")
    transport = Transport()
    code = main([], env_path=env, transport=transport)
    captured = capsys.readouterr()
    assert code == 0
    assert transport.calls == []
    text = captured.out
    assert "Python:" in text
    assert "requirements: ok" in text
    assert "ffmpeg:" in text
    assert ".env: found" in text
    assert "ANTHROPIC_API_KEY: yes" in text
    assert "FAL_KEY: no" in text
    # An empty shell value is set, so the file must not replace it.
    assert os.environ["FAL_KEY"] == ""
    assert "ELEVENLABS_API_KEY: yes" in text
    assert "asset root: set (MOVIE_SWARM_ASSET_ROOT)" in text
    assert SECRET not in text
    assert "eleven-from-file" not in text
    assert str(tmp_path / "drive") not in text
    assert "HTTP" not in text


def test_ping_is_read_only_and_skips_fal(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "eleven-" + SECRET)
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("MOVIE_SWARM_ASSET_ROOT", raising=False)
    transport = Transport(200)
    code = main(["--ping"], env_path=tmp_path / "missing.env", transport=transport)
    text = capsys.readouterr().out
    assert code == 0
    assert "Anthropic: HTTP 200" in text
    assert "ElevenLabs: HTTP 200" in text
    assert FAL_PING in text
    assert SECRET not in text
    urls = [call["url"] for call in transport.calls]
    assert urls == [
        "https://api.anthropic.com/v1/models",
        "https://api.elevenlabs.io/v1/voices",
    ]
    assert all(call["method"] == "GET" for call in transport.calls)
    assert transport.calls[0]["headers"]["x-api-key"] == SECRET
    assert transport.calls[1]["headers"]["xi-api-key"] == "eleven-" + SECRET
    assert "fal.run" not in text
    for name in KEY_NAMES:
        assert name in text


def test_ping_skips_a_provider_when_its_key_is_missing(tmp_path, monkeypatch, capsys):
    for name in KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    transport = Transport()
    lines, failed = report(env_file=tmp_path / "missing.env", ping=True, transport=transport)
    assert transport.calls == []
    text = "\n".join(lines)
    assert "Anthropic: not checked, ANTHROPIC_API_KEY is not set" in text
    assert "ElevenLabs: not checked, ELEVENLABS_API_KEY is not set" in text
    assert FAL_PING in text
    assert failed is False
    assert capsys.readouterr().out == ""


def test_missing_imports_fail_the_report(tmp_path, monkeypatch):
    monkeypatch.setattr("movie_swarm.doctor.missing_requirements", lambda requirements=None: ["fal_client"])
    lines, failed = report(env_file=tmp_path / "missing.env")
    assert failed is True
    assert "requirements: missing fal_client" in "\n".join(lines)


def test_a_missing_requirement_fails_the_check(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("not-a-real-package-xyz>=1\n", encoding="utf-8")
    from movie_swarm.doctor import missing_requirements

    missing = missing_requirements(requirements)
    assert missing == ["not_a_real_package_xyz"]
    monkeypatch.delenv("MOVIE_SWARM_ASSET_ROOT", raising=False)
