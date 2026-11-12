"""Where a film's working folder lives.

The studio repo holds the engine. A film's files live in their own folder.
That folder may sit outside this repo. A name such as ``my-film``
means ``<films root>/<name>``. The films root is ``MOVIE_SWARM_FILMS_ROOT``.
When that is unset, the commands use ``MOVIE_SWARM_ASSET_ROOT``. Each one can
come from the shell, from ``.env``, or from ``config/assets.json``.

An absolute path is used as given. A relative path is used as given. Neither
is rewritten into this repo. Paths are not printed by the doctor lines in
this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from movie_swarm.assets import ASSET_ROOT_ENV, configured_asset_root, load_asset_config
from movie_swarm.budget import DEFAULT_TOTAL, proposed_document, write_film_budget
from movie_swarm.paths import repo_root


FILMS_ROOT_ENV = "MOVIE_SWARM_FILMS_ROOT"
CHECKSUM_NAME = "export-checksums.sha256"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

MEDIA_GITIGNORE = """\
# Media stays in this folder and out of git.
# The studio repo's git-lfs rules apply only to files committed there.
# This film repo does not store those files, so it does not need those paths.
*.mp4
*.webm
*.mov
*.wav
*.mp3
*.flac
*.aac
*.png
*.jpg
*.jpeg
*.tiff
*.webp
*.psd
*.ai
"""


class FilmsError(Exception):
    """A film folder could not be resolved or created. The message says why."""


def configured_films_root() -> Path | None:
    """The films root, or None when neither setting is present.

    The shell and ``.env`` are already merged in the environment. The shell
    wins, because ``.env`` does not override it. Config is next. The asset
    root is the fallback, with the same order.
    """
    env = os.environ.get(FILMS_ROOT_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    raw = _config().get("films_root")
    if raw:
        return Path(str(raw)).expanduser()
    return configured_asset_root()


def films_root_line(*, loaded_names: list[str] | None = None) -> str:
    """Where the films root came from, and whether that folder is there.

    The path is not included. ``loaded_names`` is what ``.env`` set on this
    run. A name that was already in the shell is not in that list.
    """
    loaded = set(loaded_names or [])
    folder, source = _named_setting(FILMS_ROOT_ENV, "films_root", loaded)
    if folder is not None:
        return f"films root: set from {source}, {_place(folder)}"
    folder, source = _named_setting(ASSET_ROOT_ENV, "asset_root", loaded)
    if folder is not None:
        return f"films root: asset root from {source}, {_place(folder)}"
    return "films root: not set"


def resolve_production(value: str) -> Path:
    """A production folder from a name or a path.

    An absolute path is that folder, including one outside this repo. A value
    with a slash is a path relative to the current directory. A plain name is
    ``<films root>/<name>``.
    """
    raw = (value or "").strip()
    if not raw:
        raise FilmsError("Pass a production name or a path to the production folder.")
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded
    if raw in {".", ".."} or "/" in raw or "\\" in raw:
        return Path(raw).expanduser()
    root = configured_films_root()
    if root is None:
        raise FilmsError(
            "A production name needs a films root. "
            "Set MOVIE_SWARM_FILMS_ROOT, or set MOVIE_SWARM_ASSET_ROOT, "
            "or pass the production folder's path."
        )
    return root / raw


def production_line(value: str) -> str:
    """Whether the named production folder is there. The path is not included."""
    try:
        folder = resolve_production(value)
    except FilmsError:
        return "production: films root is not set"
    if folder.is_dir():
        return "production: folder exists"
    return "production: folder missing"


def resolve_alongside(production: str | Path, value: str | None) -> str | None:
    """A file next to a production that may live outside this repo.

    An absolute path is kept. A relative path that already exists from the
    current directory is kept. Any other relative path is inside the
    production folder.
    """
    if value is None or value == "":
        return value
    expanded = Path(value).expanduser()
    if expanded.is_absolute():
        return str(expanded)
    if Path(value).exists():
        return str(Path(value))
    return str(Path(production) / value)


def create_film(name: str, *, total_usd: float | None = None, git: bool = False) -> Path:
    """Create a clean production folder under the films root.

    ``total_usd`` is the budget total when it was asked. When it is omitted,
    the calculator default is written and the note says the total was not asked.
    ``git`` runs ``git init`` in the new folder. It does not add a remote and
    it does not push.
    """
    film_name = _check_name(name)
    root = configured_films_root()
    if root is None:
        raise FilmsError(
            "A new film needs a films root. "
            "Set MOVIE_SWARM_FILMS_ROOT, or set MOVIE_SWARM_ASSET_ROOT."
        )
    if not root.is_dir():
        raise FilmsError("The films root folder is missing. Create that folder, then run this again.")
    if _inside_repo(root):
        raise FilmsError(
            "The films root is inside the studio repo. "
            "Set it to a folder outside this repo. Nothing was written."
        )
    folder = root / film_name
    if folder.exists():
        raise FilmsError(f"The film folder {film_name} already exists. Nothing was written.")
    folder.mkdir()
    _write_skeleton(folder, film_name, total_usd)
    if git:
        _git_init(folder)
    return folder


def export_film(source: str, destination: str) -> dict:
    """Copy a production folder and check a checksum list.

    The source is left in place. The destination must be outside this repo
    and must not already exist.
    """
    src = _export_source(source)
    dest = resolve_production(destination)
    if not src.is_dir():
        raise FilmsError("The source production folder is missing. Nothing was copied.")
    if _inside_repo(dest):
        raise FilmsError(
            "The destination is inside the studio repo. "
            "Choose a folder outside it. Nothing was copied."
        )
    if dest.exists():
        raise FilmsError("The destination already exists. Nothing was copied, and the source was not deleted.")
    if not dest.parent.is_dir():
        raise FilmsError("The destination's parent folder is missing. Nothing was copied.")
    shutil.copytree(src, dest)
    source_hashes = file_checksums(src)
    dest_hashes = file_checksums(dest)
    if source_hashes != dest_hashes:
        raise FilmsError(
            "The copied files do not match the source checksums. "
            "The source was not deleted."
        )
    checksum_path = write_checksum_list(dest, dest_hashes)
    verified = verify_checksum_list(dest, checksum_path)
    if not verified or not src.is_dir():
        raise FilmsError("The checksum list did not match the copied files. The source was not deleted.")
    return {
        "files": len(source_hashes),
        "checksums": checksum_path.name,
        "source_remains": src.is_dir(),
    }


def file_checksums(folder: Path) -> dict[str, str]:
    """SHA-256 for each file, keyed by the path relative to ``folder``.

    The checksum list itself is not included. Keys never include the studio
    repo or the films root.
    """
    hashes: dict[str, str] = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.resolve().relative_to(folder.resolve()).as_posix()
        if relative == CHECKSUM_NAME:
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def write_checksum_list(folder: Path, hashes: dict[str, str]) -> Path:
    path = folder / CHECKSUM_NAME
    lines = [f"{digest}  {relative}" for relative, digest in sorted(hashes.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def verify_checksum_list(folder: Path, checksum_path: Path) -> bool:
    """True when every line in the list matches the file now on disk."""
    try:
        text = checksum_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        if not line.strip():
            continue
        if "  " not in line:
            return False
        digest, relative = line.split("  ", 1)
        file_path = folder / relative
        if not file_path.is_file():
            return False
        if hashlib.sha256(file_path.read_bytes()).hexdigest() != digest:
            return False
    return True


def _export_source(value: str) -> Path:
    raw = (value or "").strip()
    if not raw:
        raise FilmsError("Pass --from with the production folder to copy.")
    expanded = Path(raw).expanduser()
    if expanded.is_absolute() or "/" in raw or "\\" in raw or raw in {".", ".."}:
        return expanded
    return repo_root() / "productions" / raw


def _check_name(name: str) -> str:
    film_name = (name or "").strip()
    if not _NAME.match(film_name):
        raise FilmsError("A film name is lowercase letters, numbers, and hyphens. Example: my-film.")
    return film_name


def _write_skeleton(folder: Path, name: str, total_usd: float | None) -> None:
    asked = total_usd is not None
    total = DEFAULT_TOTAL if total_usd is None else total_usd
    if asked:
        note = (
            f"Total asked: ${total:.2f}. Calculator defaults. "
            "The trailer is off. Contingency is 10 percent. "
            "Marketing is 10 percent when the trailer is turned on."
        )
    else:
        note = (
            "Total was not asked. This is the calculator default of $500. "
            "Confirm the total before the treatment gate. "
            "The trailer is off. Contingency is 10 percent. "
            "Marketing is 10 percent when the trailer is turned on."
        )
    document = proposed_document(total, trailer_on=False, note=note)
    write_film_budget(folder, document)
    inputs = {
        "title": name,
        "logline": "Replace this with one or two sentences: who, what they want, and what is in the way.",
        "note": "Stub. Intake can read this file. It does not approve the treatment gate.",
    }
    treatment = folder / "treatment"
    treatment.mkdir()
    (treatment / "inputs.json").write_text(
        _json(inputs),
        encoding="utf-8",
    )
    (folder / ".gitignore").write_text(MEDIA_GITIGNORE, encoding="utf-8")
    (folder / "README.md").write_text(_readme(name, asked), encoding="utf-8")


def _readme(name: str, asked: bool) -> str:
    total_line = (
        "The total in `budget.json` was asked on the command."
        if asked
        else "The total in `budget.json` was not asked. It is the calculator default, and the note says so."
    )
    return (
        f"# {name}\n\n"
        "Working folder for this film. It lives outside the studio repo.\n\n"
        "The studio reads and writes this folder. Story facts stay here.\n\n"
        f"{total_line}\n\n"
        "`treatment/inputs.json` is a stub. Intake can read it. "
        "It does not approve the treatment gate.\n\n"
        "Media files are listed in `.gitignore`. "
        "This folder can be its own git repo. It has no remote until one is added.\n\n"
        "From the studio repo, pass `--production` with this folder's name, "
        "or pass the path to this folder. The commands are in START-HERE.\n"
    )


def _git_init(folder: Path) -> None:
    init = subprocess.run(
        ["git", "init"],
        cwd=folder,
        check=False,
        capture_output=True,
        text=True,
    )
    if init.returncode != 0:
        raise FilmsError("git init failed. The film files were written. No remote was added.")
    remotes = subprocess.run(
        ["git", "remote"],
        cwd=folder,
        check=False,
        capture_output=True,
        text=True,
    )
    if remotes.returncode != 0 or remotes.stdout.strip():
        raise FilmsError("The new film repo has a remote. Remove it. Nothing was pushed.")


def _json(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"


def _config() -> dict:
    try:
        loaded = load_asset_config()
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _named_setting(env_name: str, config_key: str, loaded: set[str]) -> tuple[Path | None, str]:
    value = os.environ.get(env_name, "").strip()
    if value and env_name not in loaded:
        return Path(value).expanduser(), f"shell ({env_name})"
    if value and env_name in loaded:
        return Path(value).expanduser(), f".env ({env_name})"
    raw = _config().get(config_key)
    if raw:
        return Path(str(raw)).expanduser(), "config/assets.json"
    return None, ""


def _place(folder: Path) -> str:
    if not folder.is_dir():
        return "folder missing"
    if _inside_repo(folder):
        return "folder exists, inside the studio repo"
    return "folder exists"


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root().resolve())
    except ValueError:
        return False
    return True
