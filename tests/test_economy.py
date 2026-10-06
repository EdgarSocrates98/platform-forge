"""Phase 2 gate: TokenSave, RTK, Caveman, routing, economy."""

from pathlib import Path

from platformforge.caveman import compress
from platformforge.core.store import ArtifactStore
from platformforge.economy import EconomyEngine
from platformforge.routing import TaskSignal, route
from platformforge.rtk import compact_output, detect_command
from platformforge.rtk.compact import expand
from platformforge.tokensave import Budget, ContextPackBuilder, SearchIndex, TokenLedger
from platformforge.tokensave.budget import check_input_budget


def _mk_ws(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("def deploy_app():\n    return 42\n" * 50)
    (tmp_path / "b.tf").write_text('resource "aws_s3_bucket" "data" {}\n' * 30)
    (tmp_path / "README.md").write_text("# deploy guide for payments service\n")
    return tmp_path


def test_index_incremental_and_search(tmp_path):
    _mk_ws(tmp_path)
    idx = SearchIndex(tmp_path / "index.db")
    s1 = idx.index_workspace(tmp_path)
    assert s1["indexed"] == 3
    s2 = idx.index_workspace(tmp_path)
    assert s2["indexed"] == 0 and s2["reused"] == 3  # content-addressed reuse
    hits = idx.search("deploy_app")
    assert hits and hits[0]["path"] == "a.py"
    assert idx.symbol("deploy_app")
    (tmp_path / "b.tf").unlink()
    s3 = idx.index_workspace(tmp_path)
    assert s3["removed"] == 1


def test_context_pack_budget_and_ledger(tmp_path):
    _mk_ws(tmp_path)
    idx = SearchIndex(tmp_path / "index.db")
    idx.index_workspace(tmp_path)
    ledger = TokenLedger(tmp_path)
    pack = ContextPackBuilder(idx, ledger).build(
        "add deploy pipeline for payments",
        budget=Budget(input_budget=100))
    assert pack["est_input_tokens"] <= 100
    rep = ledger.report()
    assert rep["operations"] == 1 and rep["context_delivered"] > 0
    assert rep["basis_counts"]["estimated"] == 1


def test_budget_refuses_below_essential():
    v = check_input_budget(Budget(input_budget=10), estimated_tokens=500,
                           min_essential=400)
    assert v.decision == "refuse"
    assert "unresolved" in (v.reduced_scope or "")


def test_rtk_compact_pytest(tmp_path):
    out = ("test_a.py::test_x PASSED\nFAILED tests/test_b.py::test_y - assert 1==2\n"
           + "\n".join(f"line{i}" for i in range(600))
           + "\n===== 1 failed, 1 passed in 0.5s =====\n")
    store = ArtifactStore(tmp_path)
    res = compact_output("pytest", out, exit_code=1, store=store)
    d = res.to_dict()
    assert d["exit_code"] == 1
    assert any("test_y" in str(e) for e in d["errors"])
    assert d["raw_artifact"].startswith("artifact://sha256/")
    # lazy expand retrieves raw
    exp = expand(store, d["raw_artifact"], pattern="FAILED")
    assert any("test_y" in l for l in exp["lines"])


def test_rtk_detect_and_terraform_plan(tmp_path):
    assert detect_command("terraform plan -out=tfplan") == "terraform plan"
    assert detect_command("kubectl get pods -n x") == "kubectl get"
    out = "# aws_s3_bucket.a will be created\nPlan: 1 to add, 0 to change, 0 to destroy.\n"
    res = compact_output("terraform plan", out)
    assert res.summary["add"] == 1
    assert any("aws_s3_bucket.a" in c for c in res.changed)


def test_rtk_kubectl_get(tmp_path):
    out = ("NAME READY STATUS\nweb-1 1/1 Running\n"
           "api-2 0/1 CrashLoopBackOff\n")
    res = compact_output("kubectl get pods", out)
    assert res.summary["not_ready"] == 1
    assert res.interesting == ["api-2"]


def test_caveman_protects_spans_and_receipts():
    text = ("Please note that it is important to note that the deployment "
            "`kubectl apply -f app.yaml` failed with error code PF-K8S-001 at "
            "https://example.com/docs and version v1.31.2 remains supported.")
    out, rc = compress(text, mode="full")
    assert "kubectl apply -f app.yaml" in out      # protected command
    assert "PF-K8S-001" in out                      # protected id
    assert "v1.31.2" in out                         # protected version
    assert rc.compression_ratio > 0
    assert rc.protected_spans >= 2
    assert rc.before_chars > rc.after_chars


def test_caveman_auto_security_context():
    text = "There was a security incident. The pod was deleted from production."
    out, rc = compress(text, mode="auto", context_risk="security-incident")
    assert rc.mode == "off" and out == text


def test_route_incident_and_security():
    inc = route(TaskSignal(task_type="incident", domains=["kubernetes"],
                           production=True))
    assert inc["mode"] == "coordinated"
    assert "incident-coordinator" in inc["agents"]
    sec = route(TaskSignal(task_type="review", security_sensitive=True))
    assert "security-reviewer" in sec["agents"]
    lint = route(TaskSignal(task_type="lint"))
    assert lint["mode"] == "deterministic" and not lint["agents"]


def test_economy_cheapest_sufficient(tmp_path):
    eng = EconomyEngine(tmp_path)
    assert eng.cheapest_sufficient("lint")["deterministic"] is True
    r = eng.cheapest_sufficient("explain-architecture", evidence_ready=False)
    assert r["cost_class"] == "unresolved"
