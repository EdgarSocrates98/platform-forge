"""Phase I gates — observation↔observation drift: appeared/disappeared/
changed classes, deletion proof honesty, dedup noise control."""

from platformforge.live.drift import dedup_events, diff_observations
from platformforge.live.models import ObservationEnvelope, ObservationScope, now_iso


def _env(objects, coverage="complete", captured=None):
    env = ObservationEnvelope.new(
        collector="k", version="t", provider="kubernetes",
        source_type="observed",
        scope=ObservationScope(provider="kubernetes"),
        captured_at=captured or now_iso())
    env.objects = objects
    env.coverage = {"status": coverage}
    return env


def _obj(rid, attrs=None):
    from platformforge.live.models import canonical_hash
    attrs = attrs or {}
    return {"resource_id": rid, "resource_type": "k8s:Deployment",
            "namespace": "prod", "name": rid.rsplit("/", 1)[-1],
            "attributes": attrs,
            "content_hash": canonical_hash(attrs) if attrs else "",
            "lifecycle": "present"}


def test_appeared_is_out_of_band():
    b = _env([_obj("k8s://c/prod/Deployment/a")])
    a = _env([_obj("k8s://c/prod/Deployment/a"),
              _obj("k8s://c/prod/Deployment/new")])
    out = diff_observations(b, a)
    assert out["counts"]["observed-out-of-band"] == 1
    assert out["drift"][0]["resource_id"].endswith("new")


def test_disappeared_proven_only_complete_fresh_covering():
    b = _env([_obj("k8s://c/prod/Deployment/gone")])
    a = _env([])                       # complete + fresh + covering
    out = diff_observations(b, a)
    assert out["counts"]["desired-missing-observed"] == 1
    assert "deletion_evidence" in out["drift"][0]["after"]

    a_partial = _env([], coverage="partial")
    out2 = diff_observations(b, a_partial)
    assert "desired-missing-observed" not in out2["counts"]
    assert out2["unresolved"]            # honest, not silent


def test_content_change_is_config_drift():
    b = _env([_obj("r1", {"replicas": 2})])
    a = _env([_obj("r1", {"replicas": 5})])
    out = diff_observations(b, a)
    assert out["counts"]["config-drift"] == 1
    diff = out["drift"][0]["after"]["diff"]
    assert diff["replicas"] == {"before": 2, "after": 5}


def test_identical_snapshots_no_drift():
    objs = [_obj("r1", {"replicas": 2})]
    out = diff_observations(_env(objs), _env(objs))
    assert out["drift"] == []


def test_dedup_suppresses_repeat_events():
    ev = [{"resource_id": "r1", "drift_class": "config-drift",
           "after": {"content_hash": "h1"}}]
    kept, sup = dedup_events(ev, [])
    assert len(kept) == 1 and sup == 0
    kept, sup = dedup_events(ev, ev)
    assert kept == [] and sup == 1


def test_window_reported():
    b = _env([], captured="2025-01-01T00:00:00Z")
    a = _env([], captured="2025-01-02T00:00:00Z")
    out = diff_observations(b, a)
    assert out["window"] == {"start": "2025-01-01T00:00:00Z",
                             "end": "2025-01-02T00:00:00Z"}
