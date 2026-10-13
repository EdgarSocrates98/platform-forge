"""§11/§129 — docs must not claim verbs the CLI lacks, and every parser
verb must be documented in CAPABILITIES.md or README."""
from __future__ import annotations

import re
from pathlib import Path

from platformforge.cli.main import build_parser

ROOT = Path(__file__).resolve().parent.parent


def _parser_verbs() -> set[str]:
    p = build_parser()
    sub = next(a for a in p._actions if hasattr(a, "choices") and a.choices)
    return set(sub.choices)


def test_doc_verbs_exist():
    text = (ROOT / "README.md").read_text() + \
        (ROOT / "CAPABILITIES.md").read_text()
    claimed = set(re.findall(r"platformforge\s+([a-z][a-z0-9_-]*)", text))
    verbs = _parser_verbs()
    bogus = {v for v in claimed if v not in verbs and
             v not in {"<verb>", "run-all"}}
    assert bogus == set(), f"docs claim non-existent verbs: {bogus}"


def test_all_verbs_documented():
    text = (ROOT / "CAPABILITIES.md").read_text() + \
        (ROOT / "README.md").read_text()
    missing = {v for v in _parser_verbs() if v not in text}
    assert missing == set(), f"verbs missing from docs: {missing}"


def test_cli_surface_is_current():
    """docs/CLI-SURFACE.md is generated — regenerate with
    `python scripts/gen_cli_surface.py --write` after any parser change."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_cli_surface", ROOT / "scripts" / "gen_cli_surface.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    expected = mod.generate()
    actual = (ROOT / "docs" / "CLI-SURFACE.md").read_text(encoding="utf-8")
    assert actual == expected, \
        "docs/CLI-SURFACE.md stale — run gen_cli_surface.py --write"
