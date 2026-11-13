"""Names used in movie_swarm must be defined.

Phase 8.16 dropped an import and the boards died with NameError on a real
film. The tests never took that branch. This check reads the source. It does
not run the film.
"""

from __future__ import annotations

import builtins
import symtable
from pathlib import Path

from movie_swarm.paths import repo_root


_BUILTINS = set(dir(builtins))


def _defined(table: symtable.SymbolTable) -> set[str]:
    names = set()
    for symbol in table.get_symbols():
        if symbol.is_imported() or symbol.is_assigned() or symbol.is_parameter() or symbol.is_namespace():
            names.add(symbol.get_name())
    return names


def _undefined(table: symtable.SymbolTable, enclosing: set[str], module_globals: set[str]) -> list[str]:
    local = _defined(table)
    if table.get_type() == "module":
        visible = local | _BUILTINS
        next_enclosing = local
        next_globals = local
    else:
        visible = local | enclosing | module_globals | _BUILTINS
        next_enclosing = local | enclosing
        next_globals = module_globals
    missing = []
    for symbol in table.get_symbols():
        if not symbol.is_referenced():
            continue
        name = symbol.get_name()
        if name in visible or name.startswith("__"):
            continue
        missing.append(f"{table.get_name()}: {name}")
    for child in table.get_children():
        missing.extend(_undefined(child, next_enclosing, next_globals))
    return missing


def test_movie_swarm_does_not_use_an_undefined_name():
    root = repo_root() / "movie_swarm"
    problems = []
    for path in sorted(root.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        table = symtable.symtable(source, str(path), "exec")
        for name in _undefined(table, set(), set()):
            problems.append(f"{path.name}: {name}")
    assert problems == []
