"""Phase 11 gate: catalog, maturity, scorecards, Backstage, Crossplane."""

from platformforge.graph import GraphBuilder
from platformforge.models import Fact
from platformforge.product import analyze_catalog, analyze_crossplane, maturity, to_backstage
from platformforge.product.scorecards import scorecard
from platformforge.rules import RuleEngine, load_catalog

CATALOG = """
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: payments
  namespace: prod
spec:
  type: service
  lifecycle: production
  owner: pay-team
  system: checkout
  providesApis: [payments-api]
  dependsOn: [resource:orders-db]
"""

XRD = """
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata: {name: xdbs.example.io}
spec:
  group: example.io
  claimNames: {kind: DB, plural: dbs}
  versions: [{name: v1alpha1, served: true}]
"""


def test_catalog(tmp_path):
    (tmp_path / "catalog-info.yaml").write_text(CATALOG)
    doc = analyze_catalog(tmp_path)
    f = doc["facts"][0]
    assert f["kind"] == "catalog.entity"
    assert f["attrs"]["owner"] == "pay-team"
    edges = f["attrs"]["graph"]["edges"]
    kinds = {e["kind"] for e in edges}
    assert {"owns", "depends_on", "contained_by", "exposes"} <= kinds


def test_maturity_compounds():
    out = maturity({"investment": ["dedicated_team", "funded",
                                   "platform_team", "product_manager"],
                    "adoption": ["some_self_service"],
                    "operations": ["runbooks", "oncall", "slo_defined",
                                   "error_budgets", "gitops"]})
    inv = out["aspects"]["investment"]
    # v2: bare signals are declared claims, not observed maturity
    assert inv["declared_level"] == "scalable"
    assert inv["overclaimed"] is True
    assert out["aspects"]["adoption"]["declared_level"] == "provisional"
    assert out["aspects"]["adoption"]["signals_declared_only"] == \
        ["some_self_service"]
    assert out["aspects"]["operations"]["declared_level"] == "scalable"
    assert out["aspects"]["measurement"]["declared_level"] == "provisional"


def test_scorecard():
    findings = [
        {"status": "violated", "severity": "critical", "rule_id": "PF-K8S-004",
         "location": "prod/payments"},
        {"status": "violated", "severity": "medium", "rule_id": "PF-K8S-002",
         "location": "prod/payments"},
        {"status": "passed", "severity": "info", "rule_id": "PF-K8S-001",
         "location": "prod/payments"},
    ]
    out = scorecard(findings)
    c = out["scorecards"]["prod/payments"]
    # v2: nine axes, each measured (score) or unknown — never inferred
    assert c["axes"]["reliability"]["score"] == 82  # 100 - 15 - 3
    assert "PF-K8S-004" in c["axes"]["reliability"]["driving_findings"]
    assert c["axes"]["security"]["status"] == "unknown"
    assert c["overall"] == 82
    assert c["total_violations"] == 6


def test_backstage_projection():
    b = GraphBuilder()
    b.add_edge("team", "pay-team", "workload", "prod/payments", "owns")
    b.add_edge("workload", "prod/payments", "api", "payments-api", "exposes")
    out = to_backstage(b.graph)
    comp = next(e for e in out["entities"] if e["kind"] == "Component")
    assert comp["metadata"]["name"] == "payments"
    assert comp["spec"]["owner"] == "pay-team"
    assert comp["spec"]["providesApis"] == ["payments-api"]


def test_crossplane(tmp_path):
    (tmp_path / "xrd.yaml").write_text(XRD)
    doc = analyze_crossplane(tmp_path)
    f = doc["facts"][0]
    assert f["kind"] == "platform.xrd"
    assert f["attrs"]["kind_claim"] == "DB"


def test_product_rules(tmp_path):
    (tmp_path / "catalog-info.yaml").write_text(
        CATALOG.replace("  owner: pay-team\n", ""))
    facts = [Fact.from_dict(x) for x in analyze_catalog(tmp_path)["facts"]]
    rules = load_catalog(
        __import__("pathlib").Path(__file__).parents[1] / "rules/catalog")
    findings, _ = RuleEngine(rules).evaluate(facts)
    v = {f.rule_id for f in findings if f.status == "violated"}
    assert "PF-CAT-001" in v
