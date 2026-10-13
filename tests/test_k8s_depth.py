"""Cycle 2 Phase E — k8s depth: gateway API, cilium, autoscaling, helm,
kustomize, hubble, delivery graph."""
from __future__ import annotations

import json
import shutil

from platformforge.graph.build import GraphBuilder
from platformforge.k8s import analyze_k8s
from platformforge.k8s.helm import analyze_helm, analyze_kustomize
from platformforge.k8s.hubble import analyze_hubble


def _write(tmp_path, name, doc):
    import yaml
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(doc))
    return p


def test_gateway_route_chain(tmp_path):
    """§65 — Gateway → Route → Service → Workload edges."""
    _write(tmp_path, "gw.yaml", {
        "apiVersion": "gateway.networking.k8s.io/v1", "kind": "Gateway",
        "metadata": {"name": "web"}, "spec": {
            "gatewayClassName": "cilium",
            "listeners": [{"port": 80, "protocol": "HTTP"}]}})
    _write(tmp_path, "rt.yaml", {
        "apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute",
        "metadata": {"name": "api"}, "spec": {
            "parentRefs": [{"name": "web"}],
            "rules": [{"backendRefs": [{"name": "api-svc"}]}]}})
    _write(tmp_path, "svc.yaml", {
        "apiVersion": "v1", "kind": "Service",
        "metadata": {"name": "api-svc"}, "spec": {"selector": {"app": "api"}}})
    out = analyze_k8s(tmp_path)
    kinds = {f["kind"] for f in out["facts"]}
    assert {"k8s.gateway", "k8s.route", "k8s.service"} <= kinds
    gw = next(f for f in out["facts"] if f["kind"] == "k8s.gateway")
    assert gw["attrs"]["has_plain_http_listener"] is True
    rt = next(f for f in out["facts"] if f["kind"] == "k8s.route")
    edge_kinds = {e["kind"] for e in rt["attrs"]["graph"]["edges"]}
    assert {"attached_to", "routes_to"} <= edge_kinds


def test_cilium_policy_and_rbac_depth(tmp_path):
    _write(tmp_path, "cnp.yaml", {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {"name": "l7"},
        "spec": {
            "endpointSelector": {"matchLabels": {"app": "api"}},
            "egress": [{
                "toEndpoints": [{"matchLabels": {"app": "db"}}],
                "toPorts": [{
                    "ports": [{"port": "5432"}],
                    "rules": {"l7": {}},
                }],
            }],
        },
    })
    _write(tmp_path, "rbac.yaml", {
        "apiVersion": "rbac.authorization.k8s.io/v1", "kind": "ClusterRole",
        "metadata": {"name": "wild"},
        "rules": [{"verbs": ["*"], "resources": ["*"]}]})
    out = analyze_k8s(tmp_path)
    cnp = next(f for f in out["facts"] if f["kind"] == "k8s.cilium_policy")
    assert cnp["attrs"]["l7_rules"] is True
    rbac = next(f for f in out["facts"] if f["kind"] == "k8s.rbac")
    assert rbac["attrs"]["wildcard_verbs"] is True


def test_hpa_join_and_keda(tmp_path):
    """§68 — HPA fact carries joined target_has_requests."""
    _write(tmp_path, "dep.yaml", {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": "api"}, "spec": {
            "replicas": 2, "template": {"spec": {
                "containers": [{"name": "c", "image": "img:1"}]}}}})
    _write(tmp_path, "hpa.yaml", {
        "apiVersion": "autoscaling/v2", "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": "api"}, "spec": {
            "scaleTargetRef": {"kind": "Deployment", "name": "api"},
            "minReplicas": 2, "maxReplicas": 10,
            "metrics": [{"type": "Resource"}]}})
    _write(tmp_path, "keda.yaml", {
        "apiVersion": "keda.sh/v1alpha1", "kind": "ScaledObject",
        "metadata": {"name": "q"}, "spec": {
            "scaleTargetRef": {"name": "worker"},
            "triggers": [{"type": "kafka"}]}})
    out = analyze_k8s(tmp_path)
    hpa = next(f for f in out["facts"] if f["kind"] == "k8s.hpa")
    assert hpa["attrs"]["target_known"] is True
    assert hpa["attrs"]["target_has_requests"] is False
    keda = next(f for f in out["facts"] if f["kind"] == "k8s.keda")
    assert keda["attrs"]["triggers"] == ["kafka"]


def test_helm_offline_unresolved(tmp_path):
    """§63 — Chart declared facts regardless; render only if helm exists."""
    _write(tmp_path, "mychart/Chart.yaml", {
        "apiVersion": "v2", "name": "mychart", "version": "1.0.0",
        "dependencies": [{"name": "redis"}]})
    out = analyze_helm(tmp_path)
    assert out["counts"]["charts"] == 1
    chart = next(f for f in out["facts"] if f["kind"] == "helm.chart")
    assert chart["attrs"]["dependencies"] == ["redis"]
    if not shutil.which("helm"):
        assert out["unresolved"][0]["capability"] == "helm-render"


def test_kustomize_overlay_facts(tmp_path):
    _write(tmp_path, "overlays/prod/kustomization.yaml", {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization", "namespace": "prod",
        "resources": ["../../base", "https://github.com/x/repo"],
        "images": [{"name": "app", "newName": "app:v2"}]})
    out = analyze_kustomize(tmp_path)
    ov = out["facts"][0]
    assert ov["attrs"]["remote_bases"] == ["https://github.com/x/repo"]
    assert ov["attrs"]["images"] == ["app:v2"]


def test_hubble_observed_tier(tmp_path):
    """§67 — hubble flows are T1, never merged with T3 config facts."""
    flows = [{"flow": {"source": {"pod_name": "a"}, "verdict": "FORWARDED",
                       "destination": {"pod_name": "b"}, "IP": {}}},
             {"flow": {"source": {"pod_name": "a"},
                       "destination": {"pod_name": "b"},
                       "verdict": "DROPPED", "IP": {}}}]
    p = tmp_path / "hubble.jsonl"
    p.write_text("\n".join(json.dumps(f) for f in flows))
    out = analyze_hubble(tmp_path)
    assert out["counts"]["pairs"] == 1
    f = out["facts"][0]
    assert f["tier"] == 1 and f["attrs"]["dropped"] == 1


def test_delivery_graph_joins(tmp_path):
    """§72 — argocd dest_namespace joins to workloads in that ns."""
    _write(tmp_path, "dep.yaml", {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": "api", "namespace": "prod"}, "spec": {
            "template": {"spec": {"containers": [{"name": "c",
                                                 "image": "x:1"}]}}}})
    facts = analyze_k8s(tmp_path)["facts"]
    facts.append({"fact_id": "PF-GITOPS-1", "kind": "gitops.argocd_app",
                  "source": "t", "location": "t", "tier": 3,
                  "attrs": {"dest_namespace": "prod",
                            "source_repos": ["https://x/api.git"]}})
    g = GraphBuilder().from_facts(facts).graph
    de = [e for e in g.edges.values() if e.attrs.get("via") ==
          "dest_namespace"]
    assert de and de[0].kind == "deploys_to"
    assert set(de[0].source_fact_ids) == {"PF-GITOPS-1",
                                          facts[0]["fact_id"]}
