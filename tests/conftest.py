"""Keep the suite off the machine's film folders and off a repo ``.env``.

``MOVIE_SWARM_ASSET_ROOT`` and ``MOVIE_SWARM_FILMS_ROOT`` change where delivery
files and named productions go. A developer machine often sets them in the
shell or in ``.env``. Tests that do not opt in see neither.
"""

from __future__ import annotations

import pytest

ASSET_ROOT = "MOVIE_SWARM_ASSET_ROOT"
FILMS_ROOT = "MOVIE_SWARM_FILMS_ROOT"
SKIP_ENV_FILE = "MOVIE_SWARM_SKIP_ENV_FILE"


@pytest.fixture(autouse=True)
def isolate_film_roots(monkeypatch, request):
    """Clear the film-root variables and skip ``.env`` auto-load.

    A test opts in with ``@pytest.mark.use_envfile`` when it needs
    ``load_env()`` to read the repo file. A test can still set either root
    for itself: this fixture runs first, and a later assignment replaces it.
    """
    if request.node.get_closest_marker("use_envfile"):
        yield
        return
    monkeypatch.delenv(ASSET_ROOT, raising=False)
    monkeypatch.delenv(FILMS_ROOT, raising=False)
    monkeypatch.setenv(SKIP_ENV_FILE, "1")
    yield
