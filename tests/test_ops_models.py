"""Phase B gates — operational models + source-of-truth resolution."""

from platformforge.ops.models import (
    ChangeIntent,
    ChangePlan,
    ExpectedDelta,
    PlanStep,
    Reason,
    dumps,
    loads_intent,
    loads_plan,
)
from platformforge.ops.source_of_truth import resolve, resolve_one


def _intent(**kw):
    base = {"intent_id": "fix-replicas", "owner": "team-a",
            "reason": Reason(type="drift", drift_ids=["d1"]),
            "target_resources": ["k8s:prod/apps/Deployment/web"],
            "desired_change": {"replicas": 3}}
    base.update(kw)
    return ChangeIntent(**base)


def test_intent_without_evidence_refuses():
    v = _intent(reason=Reason(type="other"))
    codes = {x["refusal"] for x in v.validate()}
    assert "PF-OPS-NO-EVIDENCE" in codes
    assert all("unlock" in x for x in v.validate())


def test_intent_valid_and_hashable():
    i = _intent()
    assert i.validate() == []
    assert i.hash().startswith("sha256:")
    d = i.to_dict()
    assert d["schema"] == "platformforge/change-intent/v1"
    assert d["reason"]["drift_ids"] == ["d1"]
    assert loads_intent(dumps(i)).hash() == i.hash()


def test_intent_expired():
    i = _intent(expires_at="2020-01-01T00:00:00Z")
    assert i.is_expired()
    i2 = _intent(expires_at="2999-01-01T00:00:00Z")
    assert not i2.is_expired()


def test_plan_dag_topo_and_waves():
    p = ChangePlan(plan_id="p1", intent_id="fix-replicas", steps=[
        PlanStep(step_id="edit", action="git.apply_patch"),
        PlanStep(step_id="ci", action="ci.validate", depends_on=["edit"]),
        PlanStep(step_id="sec", action="policy.check", depends_on=["edit"]),
        PlanStep(step_id="pr", action="git.open_pr",
                 depends_on=["ci", "sec"])])
    assert p.validate() == []
    assert p.topo_order() == ["edit", "ci", "sec", "pr"]
    assert p.waves() == [["edit"], ["ci", "sec"], ["pr"]]


def test_plan_cycle_detected():
    p = ChangePlan(plan_id="p1", intent_id="i", steps=[
        PlanStep(step_id="a", action="x", depends_on=["b"]),
        PlanStep(step_id="b", action="x", depends_on=["a"])])
    codes = {x["refusal"] for x in p.validate()}
    assert "PF-OPS-PLAN-CYCLE" in codes


def test_plan_dangling_dep():
    p = ChangePlan(plan_id="p1", intent_id="i", steps=[
        PlanStep(step_id="a", action="x", depends_on=["ghost"])])
    codes = {x["refusal"] for x in p.validate()}
    assert "PF-OPS-PLAN-DANGLING-DEP" in codes


def test_expected_delta_dimensions():
    d = ExpectedDelta(changes={"resources": [{"id": "dep/web",
                                              "replicas": [5, 3]}]},
                      adds={"network": []})
    assert not d.is_empty
    assert d.diff("resources")["change"]
    assert d.diff("slo") == {"add": [], "remove": [], "change": []}
    assert loads_plan(dumps(ChangePlan(
        plan_id="p", intent_id="i", expected_delta=d,
        steps=[PlanStep(step_id="s", action="a")]))).expected_delta.changes


def test_sot_argocd_to_git():
    r = resolve_one({"resource_id": "k8s:prod/apps/Deployment/web",
                     "argocd_app": "prod-web"},
                    {"gitops_apps": {"prod-web": {
                        "repository": "git@org/infra", "path": "apps/web",
                        "ref": "main"}}})
    assert r.resolved
    assert r.source.type == "gitops"
    assert r.source.repository == "git@org/infra"
    assert r.preferred_path == "gitops"


def test_sot_terraform():
    r = resolve_one({"resource_id": "aws-vpc-1",
                     "tf_address": "module.net.aws_vpc.main",
                     "tf_repo": "git@org/tf", "tf_path": "modules/net"})
    assert r.source.type == "terraform"
    assert r.preferred_path == "terraform"


def test_sot_crossplane_and_helm():
    cx = resolve_one({"resource_id": "mr-1", "claim": "db-claim",
                      "crossplane_managed": True})
    assert cx.source.type == "crossplane"
    hl = resolve_one({"resource_id": "rel-1", "helm_release": "api",
                      "labels": {"app.kubernetes.io/managed-by": "Helm"}})
    assert hl.source.type == "helm"


def test_sot_unknown_refuses():
    r = resolve_one({"resource_id": "aws-s3-mystery"})
    assert not r.resolved
    assert r.unresolved["refusal"] == "PF-OPS-SOURCE-UNKNOWN"
    rep = resolve([{"resource_id": "x"}])[0].unresolved
    assert rep["refusal"] == "PF-OPS-SOURCE-UNKNOWN"


def test_sot_conflict_recorded():
    r = resolve_one({"resource_id": "x", "argocd_app": "a",
                     "tf_address": "aws_x.y"},
                    {"gitops_apps": {"a": {"repository": "git@r"}}})
    assert r.source.type == "gitops"
    assert r.conflicts == ["also-managed-by:terraform"]


def test_sot_unmanaged_provider_low_confidence():
    r = resolve_one({"resource_id": "aws-1", "managed_by": "console"})
    assert r.resolved
    assert r.source.type == "provider-api"
    assert r.preferred_path == "direct-with-review"
