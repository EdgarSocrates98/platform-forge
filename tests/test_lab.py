"""Phase 14 gate: Forge Lab scenario framework + bundled demo."""

from platformforge.lab import list_scenarios, run
from platformforge.lab.runner import run_all


def test_list_scenarios():
    sc = list_scenarios()
    assert any(s["id"] == "demo-platform" for s in sc)


def test_demo_platform_passes():
    out = run("demo-platform")
    assert out["analyzer_errors"] == []
    assert out["passed"], out["failures"]
    assert out["counts"]["violated"] >= 5


def test_run_all_and_missing():
    assert run_all()["failed"] == 0
    out = run("nonexistent")
    assert out["refusal"] == "platform.scenario.unresolved"
