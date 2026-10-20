"""The wheel must carry every force-included runtime asset.

`pyproject.toml` force-includes `rules`, `knowledge`, `contracts` and `evals`
under `platformforge/data/` — `platformforge/resources.py` resolves them via
`importlib.resources`. Config inspection proves intent, not result: only a
real wheel build catches a silent drop of the packaged data layer.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def wheel(tmp_path_factory) -> zipfile.ZipFile:
    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"`python -m build` unavailable or failed: {result.stderr[-400:]}")
    built = sorted(out.glob("*.whl"))
    assert built, "build succeeded without producing a wheel"
    return zipfile.ZipFile(built[0])


def _names(wheel: zipfile.ZipFile, prefix: str) -> list[str]:
    return [n for n in wheel.namelist() if n.startswith(prefix)]


class TestWheelCarriesDataLayer:
    def test_rules(self, wheel):
        assert _names(wheel, "platformforge/data/rules/")

    def test_knowledge(self, wheel):
        assert _names(wheel, "platformforge/data/knowledge/")

    def test_contracts(self, wheel):
        assert _names(wheel, "platformforge/data/contracts/")

    def test_evals(self, wheel):
        assert _names(wheel, "platformforge/data/evals/")

    def test_data_layer_nonempty(self, wheel):
        data = _names(wheel, "platformforge/data/")
        assert data
        assert any(n.endswith((".yaml", ".json", ".md")) for n in data)
