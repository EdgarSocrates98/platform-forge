"""Bundled data resolution — one contract for checkout and installed wheel.

Data directories (`rules/`, `knowledge/`, `contracts/`, `evals/`, `lab/`) live
at the repository root in development. In the wheel they are force-included
under ``platformforge/data/`` (see pyproject.toml), so an installed package is
self-contained: every loader resolves through :func:`data_path` and never
depends on the checkout being present.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def data_path(*parts: str) -> Path:
    """Resolve a bundled data path.

    Order: ``platformforge/data/<parts>`` inside an installed wheel first,
    then the repository root (development checkout / editable install where
    no bundled ``data/`` tree exists inside the package).

    ``platformforge/data/`` also exists in a checkout — it ships
    ``portable_skills`` as regular package content — so the wheel probe
    checks a force-included sentinel (``data/rules``) rather than ``data``
    itself.
    """
    probe = parts if parts else ("rules",)
    try:
        pkg = resources.files("platformforge")
        installed = pkg.joinpath("data", *probe)
        if installed.is_dir() or installed.is_file():
            return Path(str(pkg.joinpath("data", *parts)))
    except (ModuleNotFoundError, TypeError, FileNotFoundError):
        pass
    return Path(__file__).resolve().parents[1].joinpath(*parts)
