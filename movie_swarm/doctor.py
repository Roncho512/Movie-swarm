"""Check the machine before a film run. This does not spend money.

No network call is made unless ``--ping`` is passed. A ping is a free
read-only request. fal has no free auth check in this repo, so it is not
pinged. HTTP bodies are not printed. Key values are not printed.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

from movie_swarm.assets import ASSET_ROOT_ENV, load_asset_config
from movie_swarm.envfile import load_env
from movie_swarm.films import films_root_line, production_line
from movie_swarm.paths import repo_root
from movie_swarm.redact import KEY_NAMES


_IMPORT_NAMES = {
    "rfc3339-validator": "rfc3339_validator",
    "python-docx": "docx",
    "fal-client": "fal_client",
}

ANTHROPIC_MODELS = "https://api.anthropic.com/v1/models"
ELEVEN_VOICES = "https://api.elevenlabs.io/v1/voices"
FAL_PING = "fal: not checked, needs a paid test shot"


def main(argv: list[str] | None = None, *, env_path: str | Path | None = None, transport=None) -> int:
    parser = argparse.ArgumentParser(description="Check this machine. Does not spend.")
    parser.add_argument(
        "--ping",
        action="store_true",
        help="Free read-only checks for Anthropic and ElevenLabs. Prints the HTTP status only.",
    )
    parser.add_argument(
        "--production",
        help="Production name or folder to check. A name uses the films root. The path is not printed.",
    )
    args = parser.parse_args(argv)
    env_file = Path(env_path) if env_path is not None else repo_root() / ".env"
    loaded = load_env(env_file)
    lines, failed = report(
        env_file=env_file,
        ping=args.ping,
        transport=transport,
        loaded_names=loaded,
        production=args.production,
    )
    print("\n".join(lines))
    return 1 if failed else 0


def report(
    *,
    env_file: Path,
    ping: bool = False,
    transport=None,
    loaded_names: list[str] | None = None,
    production: str | None = None,
) -> tuple[list[str], bool]:
    """The check lines, and whether a required import is missing."""
    lines = [f"Python: {sys.version.split()[0]}"]
    missing = missing_requirements()
    if missing:
        lines.append("requirements: missing " + ", ".join(missing))
    else:
        lines.append("requirements: ok")
    ffmpeg = shutil.which("ffmpeg")
    lines.append(f"ffmpeg: yes ({ffmpeg})" if ffmpeg else "ffmpeg: no")
    lines.append(".env: found" if env_file.is_file() else ".env: not found")
    for name in KEY_NAMES:
        present = "yes" if os_value(name) else "no"
        lines.append(f"{name}: {present}")
    lines.append(asset_root_line(loaded_names=loaded_names))
    lines.append(films_root_line(loaded_names=loaded_names))
    production_failed = False
    if production:
        line = production_line(production)
        lines.append(line)
        production_failed = line != "production: folder exists"
    if ping:
        lines.extend(ping_lines(transport or urllib_status))
    return lines, bool(missing) or production_failed


def missing_requirements(requirements: Path | None = None) -> list[str]:
    """Import names from requirements.txt that this interpreter cannot import."""
    path = requirements or (repo_root() / "requirements.txt")
    missing = []
    for dist in requirement_distributions(path):
        module = _IMPORT_NAMES.get(dist, dist.replace("-", "_"))
        if module in missing:
            continue
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(module)
    return missing


def requirement_distributions(path: Path) -> list[str]:
    """Distribution names in a requirements file, following ``-r`` includes."""
    names: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return names
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            names.extend(requirement_distributions(path.parent / line[3:].strip()))
            continue
        name = line.split(";", 1)[0].strip()
        for mark in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
            if mark in name:
                name = name.split(mark, 1)[0].strip()
                break
        if name:
            names.append(name)
    return names


def asset_root_line(*, loaded_names: list[str] | None = None) -> str:
    """Where the asset root came from, and whether that folder is there.

    The path is not printed. ``loaded_names`` is what ``.env`` set on this
    run. A name that was already in the shell is not in that list.
    """
    loaded = set(loaded_names or [])
    value = os_value(ASSET_ROOT_ENV)
    source = ""
    folder = None
    if value and ASSET_ROOT_ENV not in loaded:
        source = "shell"
        folder = Path(value).expanduser()
    elif value and ASSET_ROOT_ENV in loaded:
        source = ".env"
        folder = Path(value).expanduser()
    else:
        try:
            config = load_asset_config()
        except Exception:
            return "asset root: not set"
        raw = config.get("asset_root")
        if not raw:
            return "asset root: not set"
        source = "config/assets.json"
        folder = Path(str(raw)).expanduser()
    state = "folder exists" if folder.is_dir() else "folder missing"
    if source == "config/assets.json":
        return f"asset root: set from config/assets.json, {state}"
    return f"asset root: set from {source} ({ASSET_ROOT_ENV}), {state}"


def ping_lines(transport) -> list[str]:
    """HTTP status only. fal is not called."""
    lines = [
        _ping(
            "Anthropic",
            "ANTHROPIC_API_KEY",
            ANTHROPIC_MODELS,
            lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01"},
            transport,
        ),
        _ping(
            "ElevenLabs",
            "ELEVENLABS_API_KEY",
            ELEVEN_VOICES,
            lambda key: {"xi-api-key": key},
            transport,
        ),
        FAL_PING,
    ]
    return lines


def urllib_status(method: str, url: str, headers: dict, body, timeout: float) -> int:
    """One GET. Returns the HTTP status. The body is discarded."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def _ping(label: str, key_name: str, url: str, headers_for, transport) -> str:
    key = os_value(key_name)
    if not key:
        return f"{label}: not checked, {key_name} is not set"
    try:
        status = transport("GET", url, headers_for(key), None, 10)
    except urllib.error.URLError:
        return f"{label}: could not be reached"
    except OSError:
        return f"{label}: could not be reached"
    except Exception:
        return f"{label}: could not be reached"
    if not isinstance(status, int):
        return f"{label}: could not be reached"
    return f"{label}: HTTP {status}"


def os_value(name: str) -> str:
    return os.environ.get(name, "").strip()
