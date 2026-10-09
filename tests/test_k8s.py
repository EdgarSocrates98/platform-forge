"""Phase 6 gate: Kubernetes manifests → facts, coverage joins, PF-K8S rules."""

from platformforge.graph import GraphBuilder
from platformforge.k8s import analyze_k8s
from platformforge.models import Fact
from platformforge.rules import RuleEngine, load_catalog

MANIFEST = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments
  namespace: prod
spec:
  replicas: 1
  selector: {matchLabels: {app: payments}}
  template:
    metadata:
      labels: {app: payments}
    spec:
      serviceAccountName: pay-sa
      containers:
        - name: app
          image: registry/payments:latest
          securityContext: {privileged: true}
          env:
            - name: DB_PASSWORD
              value: "s3cr3t!"
            - name: CREDS
              valueFrom: {secretKeyRef: {name: db-creds, key: pass}}
---
apiVersion: v1
kind: Service
metadata:
  name: payments
  namespace: prod
spec:
  selector: {app: payments}
  ports: [{port: 80}]
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: payments
  namespace: prod
spec:
  rules:
    - host: pay.example.com
      http:
        paths:
          - path: /
            backend: {service: {name: payments, port: {number: 80}}}
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pay-sa
  namespace: prod
---
apiVersion: v1
kind: Secret
metadata:
  name: db-creds
  namespace: prod
data:
  pass: czNjcjN0IQ==
"""


def _facts(tmp_path):
    (tmp_path / "app.yaml").write_text(MANIFEST)
    return analyze_k8s(tmp_path)


def test_workload_facts(tmp_path):
    doc = _facts(tmp_path)
    wl = [f for f in doc["facts"] if f["kind"] == "k8s.workload"]
    assert len(wl) == 1
    ps = wl[0]["attrs"]["pod_spec"]
    assert ps["latest_tag"] and ps["privileged"] and ps["no_limits"] == 1
    assert ps["env_hardcoded_secret"] == ["DB_PASSWORD"]
    assert ps["secrets_used"] == ["db-creds"]
    assert wl[0]["attrs"]["pdb_count"] == 0


def test_secret_redacted(tmp_path):
    doc = _facts(tmp_path)
    sec = next(f for f in doc["facts"] if f["kind"] == "k8s.secret")
    # payload never enters attrs — only key names
    assert sec["attrs"]["keys"] == ["pass"]
    assert "czNjcjN0" not in str(sec)


def test_graph_wiring(tmp_path):
    g = GraphBuilder().from_facts(_facts(tmp_path)["facts"]).graph
    assert "workload/prod-payments" in g.nodes or \
        "workload/prod/payments" in g.nodes
    svc_edges = [e for e in g.edges.values() if e.kind == "routes_to"]
    assert any("k8s_service" in e.src for e in svc_edges)
    assert any(e.kind == "uses_secret" for e in g.edges.values())
    assert any(e.kind == "exposes" for e in g.edges.values())


def test_k8s_rules(tmp_path):
    doc = _facts(tmp_path)
    facts = [Fact.from_dict(x) for x in doc["facts"]]
    rules = load_catalog(
        __import__("pathlib").Path(__file__).parents[1] / "rules/catalog")
    findings, _skipped = RuleEngine(rules).evaluate(facts)
    v = {f.rule_id for f in findings if f.status == "violated"}
    for rid in ("PF-K8S-001", "PF-K8S-002", "PF-K8S-003", "PF-K8S-004",
                "PF-K8S-005", "PF-K8S-007", "PF-K8S-008", "PF-K8S-009",
                "PF-K8S-010", "PF-K8S-011", "PF-K8S-012"):
        assert rid in v, rid
