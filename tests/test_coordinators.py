"""Phase D — coordinators: bounded domain-scoped dispatch, collection,
loop mapping. Coordinators dispatch; they never analyze or execute."""

from __future__ import annotations

from platformforge.agents import AgentRefusal, plan, review, seal
from platformforge.agents.coordinators import COORDINATOR_LOOPS, collect, coordinator_loop, dispatch_plan
from platformforge.agents.roster import AGENTS, resolve


def sealed(intent="analyze the platform", **kw):
    return seal(review(plan(intent, **kw)))


def test_five_coordinators_exist_with_right_role():
    for name in COORDINATOR_LOOPS:
        a = resolve(name)
        assert a is not None and a.role == "coordinator", name
        assert a.verifier == "platform-verifier"
        assert a.delegates_to, name


def test_dispatch_only_domain_matching_delegates():
    spec = sealed("slo regression on the cluster",
                  domains=("sre", "k8s"))
    out = dispatch_plan("platform-incident-coordinator", spec)
    assert "refusal" not in out
    # only delegated specialists whose domains intersect the task's
    assert "platform-sre-specialist" in out["dispatched"]
    assert "platform-kubernetes-specialist" in out["dispatched"]
    assert "platform-finops-specialist" not in out["dispatched"]
    assert out["loop"] == "incident"
    assert all(h["from"] == "platform-incident-coordinator"
               for h in out["handoffs"])
    assert all(h["task_id"] == spec.task_id for h in out["handoffs"])


def test_dispatch_bounded_by_max_parallelism():
    spec = sealed("fleet-wide everything",
                  domains=("fleet", "finops", "capacity", "sre",
                           "security", "policy", "product"))
    out = dispatch_plan("platform-fleet-coordinator", spec)
    coord = resolve("platform-fleet-coordinator")
    assert len(out["dispatched"]) <= coord.max_parallelism
    if not out["bounded"]:
        assert out["queued"]


def test_non_coordinator_cannot_dispatch():
    spec = sealed("check terraform", domains=("iac",))
    out = dispatch_plan("platform-iac-specialist", spec)
    assert out["refusal"] == AgentRefusal.HOST_CAPABILITY
    out2 = dispatch_plan("platform-ghost", spec)
    assert out2["refusal"] == AgentRefusal.UNKNOWN_AGENT


def test_dispatch_no_domain_coverage_refuses():
    spec = sealed("costs only", domains=("finops",))
    out = dispatch_plan("platform-incident-coordinator", spec)
    assert out["refusal"] == AgentRefusal.ROUTE_UNRESOLVED


def test_collect_merges_without_minting():
    out = collect([
        {"completed": ["s1"], "evidence": ["F-1", "F-2"],
         "unresolved": ["q1"], "open_questions": ["o1"]},
        {"completed": ["s2"], "evidence": ["F-2", "F-3"],
         "unresolved": [], "open_questions": []}])
    assert out["completed"] == ["s1", "s2"]
    assert out["evidence"] == ["F-1", "F-2", "F-3"]
    assert out["unresolved"] == ["q1"]
    assert out["responded"] == 2


def test_coordinator_loop_mapping():
    assert coordinator_loop("platform-incident-coordinator") == "incident"
    assert coordinator_loop("platform-change-coordinator") == "change"
    assert coordinator_loop("platform-fleet-coordinator") == "fleet"
    assert coordinator_loop("platform-optimization-coordinator") \
        == "optimization"
    assert coordinator_loop("platform-orchestrator") == "platform-audit"


def test_coordinator_contract_lint_clean():
    for name in COORDINATOR_LOOPS:
        assert AGENTS[name].contract_errors() == [], name
