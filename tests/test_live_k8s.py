"""Phase C gates — Kubernetes collector: metadata-first projection,
pagination ledger, Forbidden→permission-limited coverage, watch
410→resnapshot, read-only RBAC, cursor store, transport allowlist."""

import json

import pytest

from platformforge.live.budget import ObservationBudget
from platformforge.live.collectors import k8s_transport
from platformforge.live.collectors.k8s import (
    K8sCollector,
    kind_of,
    project_object,
    required_rbac,
)
from platformforge.live.cursors import CursorStore
from platformforge.live.models import ObservationScope


def _pod(name="web", ns="prod", uid="u1", rv="100"):
    return {"apiVersion": "v1", "kind": "Pod",
            "metadata": {"name": name, "namespace": ns, "uid": uid,
                         "resourceVersion": rv,
                         "labels": {"app": "web"},
                         "creationTimestamp": "2025-01-01T00:00:00Z"},
            "spec": {"serviceAccountName": "web-sa"},
            "status": {"phase": "Running"}}


def _list(items, rv="900"):
    return json.dumps({"kind": "List", "items": items,
                       "metadata": {"resourceVersion": rv}})


def fake_transport(calls):
    """Replay transport: records args, returns canned responses."""
    def t(args):
        calls.append(args)
        cmd = " ".join(args)
        if "api-resources" in cmd:
            return 0, "pods\nservices\ndeployments.apps\n", ""
        if "auth can-i" in cmd:
            return 0, "yes\n", ""
        if args[0] == "get" or " get " in cmd:
            if "secrets" in cmd:
                return 1, "", ("secrets is forbidden: User "
                               "'pf' cannot list resource 'secrets'")
            return 0, _list([_pod()]), ""
        return 0, "{}", ""
    return t


def test_projection_strips_secret_payload():
    obj = {"apiVersion": "v1", "kind": "Secret",
           "metadata": {"name": "s", "namespace": "prod", "uid": "u9"},
           "type": "Opaque",
           "data": {"password": "c2VjcmV0"}}
    o = project_object(obj, cluster="c1", observed_at="t")
    assert o.attributes["secret_payload_blank"] is True
    assert "password" not in json.dumps(o.attributes)
    assert o.attributes["secret_type"] == "Opaque"


def test_projection_identity_and_canonical_id():
    o = project_object(_pod(), cluster="c1", observed_at="t")
    assert o.resource_type == "k8s:Pod"
    assert o.resource_id == "k8s://c1/prod/Pod/web#u1"
    assert o.uid == "u1" and o.lifecycle == "present"
    assert kind_of("apps/v1", "Deployment") == "k8s:apps/Deployment"


def test_collect_metadata_first_complete():
    calls = []
    c = K8sCollector(transport=fake_transport(calls), context="c1")
    env = c.collect(ObservationScope(resource_types=["pods"]))
    assert env.coverage["status"] == "complete"
    assert env.coverage["per_resource_type"]["pods"] == "complete"
    assert env.objects[0]["resource_id"] == "k8s://c1/prod/Pod/web#u1"
    assert env.receipt["metadata_only"] is True
    assert env.receipt["api_calls"] >= 1
    assert env.pagination["pods"]["resource_version"] == "900"


def test_collect_forbidden_is_permission_limited_not_error():
    calls = []
    c = K8sCollector(transport=fake_transport(calls), context="c1")
    env = c.collect(ObservationScope(
        resource_types=["pods", "secrets"]))
    assert env.coverage["per_resource_type"]["secrets"] == \
        "permission-limited"
    assert env.coverage["per_resource_type"]["pods"] == "complete"
    assert env.coverage["status"] == "partial"
    denied = env.receipt["permission_denied"]
    assert denied and denied[0]["resource_type"] == "secrets"
    # absence of secrets is NOT provable — coverage gate
    ok, why = env.can_conclude_absent(
        {"cluster": "c1", "resource_type": "secrets", "namespace": "prod",
         "name": "x"})
    assert not ok and "coverage" in why


def test_budget_truncates_and_reports():
    calls = []
    c = K8sCollector(transport=fake_transport(calls), context="c1")
    env = c.collect(ObservationScope(resource_types=["pods", "services"]),
                    budget=ObservationBudget(max_api_calls=1))
    assert env.coverage["status"] in ("partial", "truncated")
    assert any("budget" in r for r in env.coverage["reasons"])


def test_watch_events_and_410_resnapshot():
    def wt(args):
        ev = [{"type": "ADDED", "object": _pod(rv="101")},
              {"type": "ERROR", "object": {"code": 410,
                                           "reason": "Expired"}}]
        return 0, "\n".join(json.dumps(e) for e in ev), ""
    c = K8sCollector(transport=wt, context="c1")
    out = c.watch("pods", resource_version="100")
    assert out["cursor"] == "101"
    assert out["resnapshot"] is True           # 410 → relist, no gap
    assert out["events"][0]["type"] == "ADDED"


def test_watch_normal_cursor_advance():
    def wt(args):
        ev = [{"type": "MODIFIED", "object": _pod(rv="105")}]
        return 0, "\n".join(json.dumps(e) for e in ev), ""
    c = K8sCollector(transport=wt, context="c1")
    out = c.watch("pods", resource_version="100")
    assert out["cursor"] == "105" and out["resnapshot"] is False


def test_rbac_is_read_only_never_admin():
    r = required_rbac()
    assert r["cluster_admin"] is False
    verbs = {v for rule in r["manifest"]["rules"] for v in rule["verbs"]}
    assert verbs == {"get", "list", "watch"}
    r2 = required_rbac(namespaced_only=True)
    assert r2["manifest"]["kind"] == "Role"


def test_transport_allowlist_blocks_mutation(monkeypatch):
    monkeypatch.setattr(k8s_transport.shutil, "which", lambda x: "/bin/kubectl")
    rc, _, err = k8s_transport.kubectl(["delete", "pod", "x"])
    assert rc == 2 and "refused" in err
    rc, _, err = k8s_transport.kubectl(
        ["get", "pods", "--token", "abc"])
    assert rc == 2 and "credential" in err


def test_transport_no_transport_raises():
    c = K8sCollector()
    with pytest.raises(RuntimeError, match="transport"):
        c.collect(ObservationScope(resource_types=["pods"]))


def test_cursor_store_roundtrip(tmp_path):
    cs = CursorStore(tmp_path)
    cs.put("pods/prod", cursor="1234", watch_state="watching")
    c = cs.get("pods/prod")
    assert c["cursor"] == "1234" and c["watch_state"] == "watching"
    assert cs.watch_state("missing") == "unknown"
    assert len(cs.all()) == 1


def test_can_i_preflight():
    c = K8sCollector(transport=fake_transport([]), context="c1")
    out = c.can_i()
    assert out["granted"] == ["get", "list", "watch"]
    assert out["cluster_admin_required"] is False


def test_absence_gate_fresh_complete(tmp_path):
    calls = []
    c = K8sCollector(transport=fake_transport(calls), context="c1")
    env = c.collect(ObservationScope(
        resource_types=["pods"], namespaces=["prod"]))
    env.coverage["status"] = "complete"
    ok, _ = env.can_conclude_absent(
        {"cluster": "c1", "namespace": "prod", "resource_type": "pods",
         "name": "ghost"})
    # fresh + complete + covering → absence is a valid conclusion
    assert ok
