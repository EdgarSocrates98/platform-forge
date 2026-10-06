"""Phase 1 gate: deterministic core — models, hashing, store, receipts,
redaction, source freshness, rule engine. All offline."""

import json
from pathlib import Path

import pytest

from platformforge.core.hashing import sha256_obj, sha256_text
from platformforge.core.receipts import Receipt, ReceiptWriter, timed
from platformforge.core.redaction import redact_obj, redact_text, contains_secret
from platformforge.core.store import ArtifactStore
from platformforge.core.workspace import init_workspace, load_workspace
from platformforge.knowledge.registry import SourceRegistry
from platformforge.models import EvidenceTier, Fact, Finding, Refusal, Recommendation
from platformforge.rules import RuleEngine, load_catalog

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def test_fact_deterministic_id_and_tier_gate():
    f = Fact(kind="k8s.workload.deployment", source="deployment.yaml",
             location="apps/payments/deployment.yaml",
             tier=EvidenceTier.REPO_CONFIG)
    assert f.fact_id.startswith("PF-K8S-")
    same = Fact(kind="k8s.workload.deployment", source="deployment.yaml",
                location="apps/payments/deployment.yaml")
    assert f.fact_id == same.fact_id  # stable across runs


def test_fact_rejects_llm_tier():
    with pytest.raises(ValueError):
        Fact(kind="x", source="s", location="l", tier=EvidenceTier.LLM_INFERENCE)


def test_finding_requires_evidence():
    with pytest.raises(ValueError):
        Finding(rule_id="PF-K8S-001", severity="high", status="violated", evidence=[])


def test_recommendation_blocks_unmeasured_gain():
    f = Fact(kind="x", source="s", location="l")
    with pytest.raises(ValueError):
        Recommendation(title="t", severity="low", confidence="low",
                       evidence=[f.fact_id], proposed_change=[], risks=[],
                       validation=[], rollback=[],
                       basis={"observed": [], "declared": [], "inferred": [],
                              "unknown": []},
                       expected_effect="saves 30% cost")


def test_refusal_named_unresolved():
    r = Refusal(code="platform.slo.unresolved", field="window",
                unlock="provide >=7d metrics")
    assert r.to_dict()["code"].endswith(".unresolved")


def test_artifact_store_roundtrip(tmp_path):
    store = ArtifactStore(tmp_path)
    sha = store.put_text("hello platform")
    assert store.has(sha)
    assert store.get_text(sha) == "hello platform"
    assert store.put_text("hello platform") == sha  # dedup by content
    assert store.stats()["artifacts"] == 1


def test_receipt_written(tmp_path):
    rw = ReceiptWriter(tmp_path)
    rc = Receipt(operation="analyze", inputs=["x"])
    with timed(rc):
        rc.facts.append("PF-K8S-000000000001")
    p = rw.emit(rc)
    data = json.loads(p.read_text())
    assert data["operation"] == "analyze" and data["facts"]


def test_redaction_scrubs_aws_key_and_connstring():
    text = "key=AKIAIOSFODNN7EXAMPLE dsn=postgres://u:p@db:5432/x password: hunter22"
    out = redact_text(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "postgres://u:p@" not in out
    assert "hunter22" not in out
    assert contains_secret(text) and not contains_secret(out)
    assert redact_obj({"a": [text]})["a"][0] == out


def test_source_freshness_classification():
    reg = SourceRegistry.default()
    report = {r["id"]: r["status"] for r in reg.check()}
    assert report["cncf-maturity-model"] in ("current", "fresh")
    assert report["slsa-spec"] in ("current", "fresh")


def test_rule_engine_violation_and_version_gate(tmp_path):
    cat = tmp_path / "rules.yaml"
    cat.write_text("""rules:
  - rule_id: PF-K8S-001
    title: missing cpu requests
    domain: kubernetes
    severity: medium
    applies_to: {fact_kind: k8s.workload.deployment}
    versions: {kubernetes: ">=1.20"}
    conditions:
      all: [{path: "attrs.containers[*].resources.requests.cpu", op: absent}]
    sources: [kubernetes-docs]
""")
    rules = load_catalog(tmp_path)
    f = Fact(kind="k8s.workload.deployment", source="d.yaml", location="d.yaml",
             attrs={"containers": [{"resources": {"limits": {}}}]})
    findings, skipped = RuleEngine(rules, versions={"kubernetes": "1.31"}).evaluate([f])
    assert findings[0].status == "violated" and findings[0].evidence == [f.fact_id]
    # version mismatch -> skipped, not applied
    findings2, skipped2 = RuleEngine(rules, versions={"kubernetes": "1.10"}).evaluate([f])
    assert not findings2 and skipped2[0]["reason"] == "version-mismatch"


def test_contracts_validate_models():
    jsonschema = pytest.importorskip("jsonschema")
    f = Fact(kind="k8s.workload.deployment", source="d.yaml", location="d.yaml")
    finding = Finding(rule_id="PF-K8S-001", severity="high", status="violated",
                      evidence=[f.fact_id])
    jsonschema.validate(f.to_dict(), json.loads((CONTRACTS / "fact.schema.json").read_text()))
    jsonschema.validate(finding.to_dict(),
                        json.loads((CONTRACTS / "finding.schema.json").read_text()))


def test_workspace_init_and_load(tmp_path):
    init_workspace(tmp_path, name="ws")
    ws = load_workspace(tmp_path)
    assert ws.name == "ws" and (tmp_path / ".platformforge" / "store").is_dir()
