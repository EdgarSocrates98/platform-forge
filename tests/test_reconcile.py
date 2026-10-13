"""Phase F gates — reconciliation: drift classes, coverage/freshness
honesty, temporal alignment, accepted drift."""

from platformforge.live.models import ObservationEnvelope, ObservationScope
from platformforge.live.reconcile import (
    norm_facts,
    norm_observed,
    norm_runtime_edges,
    reconcile,
)


def _desired(rid="arn:aws:s3:::b1", attrs=None, name="b1"):
    return [{"fact_id": "f1", "kind": "aws_s3_bucket", "location": rid,
             "source": "t", "tier": 3,
             "attrs": attrs or {"arn": rid, "name": name}}]


def _env(objects, coverage="complete", captured=None):
    from platformforge.live.models import now_iso
    env = ObservationEnvelope.new(
        collector="aws", version="t", provider="aws",
        source_type="observed", scope=ObservationScope(provider="aws"),
        captured_at=captured or now_iso())
    env.objects = objects
    env.coverage = {"status": coverage}
    return env


def _obj(rid="arn:aws:s3:::b1", attrs=None):
    return {"resource_id": rid, "resource_type": "aws:s3/bucket",
            "provider": "aws", "name": "b1",
            "attributes": attrs or {"arn": rid}}


def test_converged_when_matching():
    out = reconcile(desired=norm_facts(_desired(), "desired"),
                    observed=norm_observed(_env([_obj()])))
    assert out["counts"]["converged"] == 1
    assert out["alignment"]["comparable"] is True


def test_config_drift_on_attr_change():
    o = _obj(attrs={"arn": "arn:aws:s3:::b1", "encryption": "off"})
    out = reconcile(
        desired=norm_facts(
            _desired(attrs={"arn": "arn:aws:s3:::b1",
                            "encryption": "on"}), "desired"),
        observed=norm_observed(_env([o])))
    # encryption maps to the security category (§104 semantic classes)
    assert out["counts"].get("security-drift") == 1
    ev = out["drift"][0]
    assert ev["drift_class"] == "security-drift" and "f1" in ev["facts"]


def test_security_drift_on_exposure_attr():
    o = _obj(attrs={"arn": "arn:aws:s3:::b1", "public": True})
    out = reconcile(
        desired=norm_facts(
            _desired(attrs={"arn": "arn:aws:s3:::b1", "public": False}),
            "desired"),
        observed=norm_observed(_env([o])))
    cls = out["drift"][0]["drift_class"]
    assert cls in ("security-drift", "config-drift")


def test_missing_with_complete_fresh_scope_is_drift():
    env = _env([], coverage="complete")
    env.scope = ObservationScope(provider="aws").to_dict()
    out = reconcile(desired=norm_facts(_desired(), "desired"),
                    observed=norm_observed(env))
    assert out["counts"]["desired-missing-observed"] == 1


def test_missing_with_partial_coverage_is_unresolved_not_drift():
    env = _env([], coverage="permission-limited")
    out = reconcile(desired=norm_facts(_desired(), "desired"),
                    observed=norm_observed(env))
    assert "desired-missing-observed" not in out["counts"]
    assert out["unresolved"][0]["drift_class"] == "permission-unknown"


def test_stale_observation_degrades_comparisons():
    env = _env([_obj()], captured="2020-01-01T00:00:00Z")
    out = reconcile(desired=norm_facts(_desired(), "desired"),
                    observed=norm_observed(env))
    assert out["counts"]["stale-observed" if False else
               "stale-observation"] == 1
    assert out["alignment"]["comparable"] is False


def test_observed_orphan_detected():
    env = _env([_obj("arn:aws:s3:::stray", {"arn": "arn:aws:s3:::stray"})])
    out = reconcile(desired=norm_facts(_desired(), "desired"),
                    observed=norm_observed(env))
    assert out["counts"]["observed-orphan"] == 1


def test_planned_not_applied():
    planned = [{"fact_id": "p1", "kind": "aws_s3_bucket",
                "location": "arn:aws:s3:::new", "source": "plan",
                "tier": 2,
                "attrs": {"arn": "arn:aws:s3:::new"}}]
    env = _env([_obj()])
    out = reconcile(desired=norm_facts(_desired(), "desired"),
                    planned=norm_facts(planned, "planned"),
                    observed=norm_observed(env))
    assert out["counts"]["planned-not-applied"] == 1


def test_runtime_undeclared_edge():
    rt = norm_runtime_edges(edges=[{"src": "w/a", "dst": "db/x",
                                    "kind": "calls", "edge_id": "e1"}])
    out = reconcile(desired=norm_facts(_desired(), "desired"),
                    observed=norm_observed(_env([_obj()])),
                    runtime=rt)
    assert out["counts"]["runtime-undeclared"] == 1


def test_accepted_drift_marked_not_counted():
    o = _obj(attrs={"arn": "arn:aws:s3:::b1", "encryption": "off"})
    out = reconcile(
        desired=norm_facts(
            _desired(attrs={"arn": "arn:aws:s3:::b1",
                            "encryption": "on"}), "desired"),
        observed=norm_observed(_env([o])),
        accepted=[{"resource_id": "*", "drift_class": "security-drift",
                   "reason": "team decision"}])
    assert out["accepted"] == 1
    assert out["drift"][0]["owner"] == "accepted"


def test_scope_mismatch_when_outside_scope():
    env = _env([], coverage="complete")
    env.scope = ObservationScope(provider="aws",
                                 regions=["eu-west-1"]).to_dict()
    d = _desired()
    d[0]["attrs"]["region"] = "us-east-1"
    d[0]["attrs"]["arn"] = "arn:aws:s3:::b1"
    out = reconcile(desired=norm_facts(d, "desired"),
                    observed=norm_observed(env))
    assert out["counts"]["scope-mismatch"] == 1
