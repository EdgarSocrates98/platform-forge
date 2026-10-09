"""Phase A — observation foundation tests.

Gate (cycle §246): *partial observation can never prove absence.*
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import pytest

from platformforge.live import (
    CollectorReceipt,
    Coverage,
    Freshness,
    ObservationBudget,
    ObservationEnvelope,
    ObservationScope,
    ObservationStore,
    ObservedObject,
    ProviderCallLedger,
    now_iso,
)
from platformforge.live.envelope import redact_envelope, validate_envelope

NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _env(objects=(), scope=None, cov="complete", captured_at=None,
         fresh_until=None, provider="kubernetes"):
    captured_at = captured_at or now_iso()
    return ObservationEnvelope.new(
        collector="k8s-fixture", version="0.1.0", provider=provider,
        source_type="observed", scope=scope or ObservationScope(
            provider="kubernetes", clusters=["c1"],
            resource_types=["Pod", "Deployment"]),
        captured_at=captured_at, fresh_until=fresh_until or "",
        objects=[o.to_dict() if isinstance(o, ObservedObject) else o
                 for o in objects],
        coverage={"status": cov})


def _pod(uid="u1", name="api", ns="prod", cluster="c1", **kw):
    return ObservedObject(resource_id=f"k8s://{cluster}/{ns}/Pod/{name}",
                          resource_type="Pod", provider="kubernetes",
                          cluster=cluster, namespace=ns, name=name,
                          uid=uid, attributes={"phase": "Running"}, **kw)


# ── model invariants ──────────────────────────────────────────
class TestModels:
    def test_envelope_id_pattern(self):
        env = _env()
        assert env.observation_id.startswith("obs-")

    def test_envelope_roundtrip(self):
        env = _env(objects=[_pod()])
        back = ObservationEnvelope.from_dict(env.to_dict())
        assert back.observation_id == env.observation_id
        assert back.objects == env.objects

    def test_envelope_schema_validates(self):
        assert validate_envelope(_env(objects=[_pod()]).to_dict()) == []

    def test_bad_source_type_rejected(self):
        with pytest.raises(ValueError):
            ObservationEnvelope.new("c", "1", "aws", "bogus")

    def test_bad_coverage_rejected(self):
        with pytest.raises(ValueError):
            Coverage(status="everything-is-fine")

    def test_deleted_requires_evidence(self):
        with pytest.raises(ValueError, match="deletion_evidence"):
            _pod(lifecycle="deleted")

    def test_deleted_with_evidence_ok(self):
        o = _pod(lifecycle="deleted",
                 deletion_evidence="kubernetes:watch:DELETED")
        assert o.lifecycle == "deleted"

    def test_lifecycle_set(self):
        o = _pod()
        assert o.lifecycle == "present"


# ── §9 freshness ──────────────────────────────────────────────
class TestFreshness:
    def test_fresh(self):
        cap = "2026-01-01T00:00:00Z"
        until = "2026-01-01T00:10:00Z"
        f = Freshness(captured_at=cap, fresh_until=until)
        assert f.status_at(NOW + timedelta(minutes=1)) == "fresh"

    def test_aging(self):
        f = Freshness(captured_at="2026-01-01T00:00:00Z",
                      fresh_until="2026-01-01T00:10:00Z")
        assert f.status_at(NOW + timedelta(minutes=8)) == "aging"

    def test_stale_then_expired(self):
        f = Freshness(captured_at="2026-01-01T00:00:00Z",
                      fresh_until="2026-01-01T00:10:00Z")
        assert f.status_at(NOW + timedelta(minutes=15)) == "stale"
        assert f.status_at(NOW + timedelta(minutes=25)) == "expired"

    def test_unknown_without_times(self):
        assert Freshness().status_at(NOW) == "unknown"

    def test_ttl_fallback(self):
        f = Freshness(captured_at="2026-01-01T00:00:00Z")
        assert f.status_at(NOW + timedelta(seconds=30), ttl=120) == "fresh"


# ── §10/§11 absence semantics — THE gate ──────────────────────
class TestAbsenceSemantics:
    TARGET: ClassVar[dict] = {"resource_type": "Pod", "namespace": "prod",
              "cluster": "c1", "name": "ghost"}

    def test_complete_fresh_covering_proves_absence(self):
        cap = (NOW - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        until = (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        env = _env(cov="complete", captured_at=cap, fresh_until=until)
        ok, _why = env.can_conclude_absent(self.TARGET, at=NOW)
        assert ok

    @pytest.mark.parametrize("cov", ["partial", "sampled", "truncated",
                                     "permission-limited", "unsupported",
                                     "unknown"])
    def test_incomplete_coverage_never_proves_absence(self, cov):
        cap = (NOW - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        until = (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        env = _env(cov=cov, captured_at=cap, fresh_until=until)
        ok, why = env.can_conclude_absent(self.TARGET, at=NOW)
        assert not ok and "unresolved" in why

    def test_stale_snapshot_never_proves_absence(self):
        cap = (NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        until = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        env = _env(cov="complete", captured_at=cap, fresh_until=until)
        ok, _ = env.can_conclude_absent(self.TARGET, at=NOW)
        assert not ok

    def test_scope_miss_never_proves_absence(self):
        cap = (NOW - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        until = (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        env = _env(cov="complete", captured_at=cap, fresh_until=until,
                   scope=ObservationScope(provider="kubernetes",
                                          clusters=["other-cluster"]))
        ok, why = env.can_conclude_absent(self.TARGET, at=NOW)
        assert not ok and "scope" in why

    def test_partial_type_detail_beats_global(self):
        cap = (NOW - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        until = (NOW + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        env = _env(captured_at=cap, fresh_until=until,
                   cov="partial")
        env.coverage["per_resource_type"] = {"Pod": "complete"}
        ok, _ = env.can_conclude_absent(self.TARGET, at=NOW)
        assert ok  # Pod coverage complete even though global partial
        env.coverage["per_resource_type"] = {"Pod": "permission-limited"}
        ok, _ = env.can_conclude_absent(self.TARGET, at=NOW)
        assert not ok


# ── §12 tombstones ────────────────────────────────────────────
class TestTombstones:
    def test_watch_deleted_event_is_strong_evidence(self):
        o = _pod(lifecycle="deleted",
                 deletion_evidence="kubernetes:watch:DELETED")
        assert o.lifecycle == "deleted"

    def test_missing_from_partial_is_not_deleted(self):
        # the model-level guard: a missing object can never be minted
        # 'deleted' without an evidence string
        with pytest.raises(ValueError):
            ObservedObject(resource_id="x", resource_type="Pod",
                           lifecycle="deleted")


# ── receipts / budgets ────────────────────────────────────────
class TestReceiptBudget:
    def test_receipt_roundtrip(self):
        r = CollectorReceipt(collector="k8s", collector_version="1",
                             provider="kubernetes",
                             started_at="2026-01-01T00:00:00Z",
                             api_calls=3, pages=5, objects=42,
                             bytes=10_000, throttles=1)
        d = r.to_dict()
        assert d["schema"] == "platformforge/collector-receipt/v1"
        assert CollectorReceipt.from_dict(d).pages == 5

    def test_budget_refusal_not_silent(self):
        b = ObservationBudget(max_objects=10)
        led = ProviderCallLedger(collector="t")
        led.record_call("k8s", objects=11)
        assert b.check(led) == "max_objects"

    def test_budget_within_limits(self):
        b = ObservationBudget(max_objects=100, max_api_calls=50)
        led = ProviderCallLedger(collector="t")
        led.record_call("k8s", objects=10)
        assert b.check(led) == ""

    def test_ledger_accounts(self):
        led = ProviderCallLedger(collector="t")
        led.record_call("aws", pages=2, objects=5, nbytes=100,
                        throttled=True)
        led.record_call("aws", cache_hit=True)
        d = led.to_dict()
        assert d["api_calls"] == 2 and d["throttles"] == 1
        assert d["cache_hits"] == 1 and d["calls_by_service"]["aws"] == 2


# ── store (§206, §209–212) ────────────────────────────────────
class TestStore:
    def test_put_get_roundtrip(self, tmp_path):
        st = ObservationStore(tmp_path)
        env = _env(objects=[_pod()])
        out = st.put(env)
        assert "refusal" not in out
        back = st.get(env.observation_id)
        assert back is not None and back.objects[0]["name"] == "api"

    def test_put_invalid_refused(self, tmp_path):
        st = ObservationStore(tmp_path)
        env = _env()
        env.observation_id = "bogus"
        out = st.put(env)
        assert out["refusal"] == "PF-LIVE-INVALID-ENVELOPE"

    def test_index_queries(self, tmp_path):
        st = ObservationStore(tmp_path)
        env = _env(objects=[_pod(uid="a", name="api"),
                            _pod(uid="b", name="web")])
        st.put(env)
        assert len(st.list(provider="kubernetes")) == 1
        rows = st.find_resource(name="api")
        assert rows and rows[0]["uid" if "uid" in rows[0] else "resource_id"]
        assert st.find_resource(resource_type="Pod")

    def test_identical_snapshot_deduped(self, tmp_path):
        st = ObservationStore(tmp_path)
        env = _env(objects=[_pod()], captured_at="2026-01-01T00:00:00Z")
        o1, o2 = st.put(env), st.put(env)
        assert o1["envelope_hash"] == o2["envelope_hash"]
        assert len(st.list()) == 1

    def test_status_shape(self, tmp_path):
        st = ObservationStore(tmp_path)
        st.put(_env(objects=[_pod()]))
        s = st.status()
        assert s["observations"] == 1 and "kubernetes" in s["providers"]


# ── §207 redaction before persistence ─────────────────────────
class TestRedaction:
    def test_secret_in_attrs_redacted(self):
        env = _env(objects=[_pod()])
        env.objects[0]["attributes"]["conn"] = \
            "postgres://user:Sup3rSecretPass@db:5432/app"
        env, counts = redact_envelope(env)
        assert counts
        assert "Sup3rSecretPass" not in json.dumps(env.objects)

    def test_redacted_envelope_persists_clean(self, tmp_path):
        st = ObservationStore(tmp_path)
        env = _env(objects=[_pod()])
        env.objects[0]["attributes"]["tok"] = "ghp_" + "a" * 30
        env, _c = redact_envelope(env)
        st.put(env)
        raw = (tmp_path / ".platformforge/observations" /
               env.observation_id / "objects.json").read_text()
        assert "ghp_" + "a" * 30 not in raw
        assert "REDACTED" in raw
