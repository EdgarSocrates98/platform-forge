"""Context Gateway (§56–75) + checkpoint/resume (§76–80) +
reconciliation (§81–88)."""

from __future__ import annotations

import pytest

from platformforge.context import (
    AuthorizationDecision,
    ContextCapsule,
    ContextGateway,
    ContextRequest,
    Sufficiency,
)
from platformforge.context.refs import ContextRef
from platformforge.economy.checkpoint import CheckpointStore, EconomyCheckpoint
from platformforge.economy.reconcile import reconcile, savings_claim


@pytest.fixture
def gw(tmp_path):
    return ContextGateway(tmp_path)


REQ = {"task": "review iam", "scope": "repository",
       "facts": [{"fact_id": "PF-IAM-1", "value": "open sg"}],
       "findings": [{"rule_id": "PF-SEC-001", "status": "fail"}],
       "rules": ["PF-SEC-001"], "open_questions": ["prod account?"]}


class TestGateway:
    def test_build_emits_ref_and_sufficiency(self, gw):
        out = gw.build(ContextRequest(**REQ, required_sections=["facts",
                                                              "findings"]))
        assert out["ref"].startswith("context://sha256/")
        assert out["sufficiency"]["state"] == "sufficient"
        assert out["bytes"] > 0

    def test_essential_overflow_refuses(self, gw):
        out = gw.build(ContextRequest(**REQ, budget_bytes=100,
                                      essential_bytes=1000))
        assert out["refusal"] == "PF-CONTEXT-ESSENTIAL"
        assert out["sufficiency"]["state"] == Sufficiency.INSUFFICIENT

    def test_insufficient_not_confident(self, gw):
        out = gw.build(ContextRequest(**REQ, required_sections=["graph"]))
        assert out["sufficiency"]["state"] == "partial"

    def test_dedup_facts(self, gw):
        r = dict(REQ, facts=[{"fact_id": "a"}, {"fact_id": "a"}])
        out = gw.build(ContextRequest(**r))
        assert len(out["capsule"]["facts"]) == 1

    def test_inspect_and_expand(self, gw):
        out = gw.build(ContextRequest(**REQ))
        ref = out["ref"]
        cap = gw.inspect(ref)
        assert cap["task"] == "review iam"
        sec = gw.expand(ref, "facts")
        assert sec["content"][0]["fact_id"] == "PF-IAM-1"
        bad = gw.inspect("context://sha256/" + "0" * 64)
        assert bad["refusal"] == "PF-CONTEXT-REF-UNKNOWN"

    def test_expand_unknown_section_refused(self, gw):
        ref = gw.build(ContextRequest(**REQ))["ref"]
        out = gw.expand(ref, "nope")
        assert out["refusal"] == "PF-CONTEXT-SECTION-UNKNOWN"

    def test_delta_context(self, gw):
        base = gw.build(ContextRequest(**REQ))
        cap2 = ContextCapsule(task="review iam", summary="s",
                              facts=[{"fact_id": "PF-IAM-2"}])
        d = gw.delta(base["ref"], cap2)
        assert "facts" in d["delta"]
        assert "task" in d["reused_sections"]
        assert d["delta_bytes"] < d["full_bytes"]

    def test_role_projection(self, gw):
        ref = gw.build(ContextRequest(**REQ))["ref"]
        v = gw.for_role(ref, "verifier")
        assert "facts" not in v["context"]      # verifier: findings+rules
        assert "findings" in v["context"]
        s = gw.for_role(ref, "specialist")
        assert "facts" in s["context"]

    def test_redaction_before_persist(self, gw):
        r = dict(REQ, facts=[{"fact_id": "x", "password": "hunter2"}])
        ref = gw.build(ContextRequest(**r))["ref"]
        stored = gw.inspect(ref)
        assert stored["facts"][0]["password"] == "[REDACTED]"
        assert stored["warnings"]

    def test_redaction_covers_secret_patterns_inside_values(self, gw):
        secret = "AKIAIOSFODNN7EXAMPLE"
        out = gw.build(ContextRequest(
            task=f"review key={secret}",
            facts=[{"fact_id": "x", "value": secret}],
        ))
        assert secret not in str(out)
        assert secret not in gw.inspect(out["ref"]).__repr__()
        assert gw.inspect(out["ref"])["warnings"]

    def test_ref_hash_matches_persisted_canonical_bytes(self, gw):
        out = gw.build(ContextRequest(**REQ))
        path = gw._store / (out["ref"].rsplit("/", 1)[-1] + ".json")
        import hashlib

        assert hashlib.sha256(path.read_bytes()).hexdigest() == out["ref"].rsplit("/", 1)[-1]

    def test_tampering_is_detected(self, gw):
        out = gw.build(ContextRequest(**REQ))
        path = gw._store / (out["ref"].rsplit("/", 1)[-1] + ".json")
        path.write_text(path.read_text(encoding="utf-8").replace("review iam", "tampered"), encoding="utf-8")
        assert gw.inspect(out["ref"])["refusal"] == "PF-CONTEXT-INTEGRITY"

    def test_protected_expansion_requires_authorization(self, gw):
        req = ContextRequest(**REQ, classification="confidential")
        out = gw.build(req)
        assert out["refusal"] == "PF-CONTEXT-AUTHORIZATION"

        class Authority:
            def authorize(self, **kwargs):
                return AuthorizationDecision(
                    allow=True,
                    principal=kwargs["principal"],
                    workspace_id=kwargs["workspace_id"],
                    session_id=kwargs["session_id"],
                    classifications=(kwargs["classification"],),
                    operations=("build", "inspect", "expand", "project", "delta"),
                )

        secure = ContextGateway(gw.root, authorizer=Authority(), workspace_id="ws-1")
        out = secure.build(ContextRequest(
            **REQ, classification="confidential", principal="reviewer",
            workspace_id="ws-1", session_id="session-1"))
        assert secure.inspect(out["ref"])["refusal"] == "PF-CONTEXT-AUTHORIZATION"
        assert secure.expand(
            out["ref"], "facts", principal="reviewer", workspace_id="ws-1",
            session_id="session-1", allowed_classifications=("internal",),
        )["refusal"] == "PF-CONTEXT-AUTHORIZATION"
        assert secure.expand(
            out["ref"], "facts", principal="reviewer", workspace_id="ws-1",
            session_id="session-1", allowed_classifications=("confidential",),
        )["content"]
        assert secure.for_role(out["ref"], "reviewer")["refusal"] == "PF-CONTEXT-AUTHORIZATION"
        assert secure.for_role(
            out["ref"], "reviewer", principal="reviewer", workspace_id="ws-1",
            session_id="session-1")["context"]

    def test_invalid_context_schema_is_refused(self, gw):
        out = gw.build(ContextRequest(task="", scope="repository"))
        assert out["refusal"] == "PF-CONTEXT-SCHEMA"

    def test_invalid_scope_is_refused_without_persisting(self, gw):
        out = gw.build(ContextRequest(task="review", scope="outside"))
        assert out["refusal"] == "PF-CONTEXT-SCHEMA"
        assert not list(gw._store.glob("*.json"))

    def test_malformed_context_ref_is_refused(self, gw):
        out = gw.inspect("not-a-context-ref")
        assert out["refusal"] == "PF-CONTEXT-REF-SCHEMA"

    def test_ref_parse(self):
        uri = ContextRef.of("evidence", {"a": 1}).uri
        back = ContextRef.parse(uri)
        assert back.scheme == "evidence" and len(back.digest) == 64


class TestCheckpoint:
    def test_resume_preserves_spend(self, tmp_path):
        store = CheckpointStore(tmp_path)
        store.save(EconomyCheckpoint(
            run_id="r1", spent_budget={"input_tokens": 500},
            remaining_budget={"input_tokens": 500},
            routing_profile="deep",
            deps={"artifact_hash": "a1", "policy_version": "p1"}))
        out = store.resume("r1", {"artifact_hash": "a1",
                                  "policy_version": "p1"})
        assert out["resumed"] and out["spent_budget"]["input_tokens"] == 500
        assert out["profile"] == "deep" and not out["needs_revalidation"]

    def test_resume_no_downgrade(self, tmp_path):
        store = CheckpointStore(tmp_path)
        store.save(EconomyCheckpoint(run_id="r1", routing_profile="deep"))
        out = store.resume("r1", {}, requested_profile="economy")
        assert out["refusal"] == "PF-CHECKPOINT-DOWNGRADE"

    def test_resume_stale_deps_flagged(self, tmp_path):
        store = CheckpointStore(tmp_path)
        store.save(EconomyCheckpoint(
            run_id="r1", deps={"policy_version": "p1"}))
        out = store.resume("r1", {"policy_version": "p2"})
        assert out["needs_revalidation"]
        assert "policy_version" in out["stale_deps"]

    def test_resume_missing_checkpoint(self, tmp_path):
        out = CheckpointStore(tmp_path).resume("ghost", {})
        assert out["refusal"] == "PF-CHECKPOINT-MISSING"


class TestReconciliation:
    def test_planned_vs_observed(self):
        r = reconcile({"tokens": 1000, "tools": 4},
                      {"tokens": 1600, "tools": 4}, run_id="r1")
        assert r.axes["tokens"].state == "over"
        assert r.axes["tokens"].error_pct == 60.0
        assert r.axes["tools"].state == "ok"

    def test_unobserved_is_unresolved_not_zero(self):
        r = reconcile({"tokens": 1000}, {"tokens": None})
        assert r.axes["tokens"].state == "unresolved"
        assert "tokens" in r.to_dict()["unresolved_axes"]

    def test_no_fake_savings(self):
        assert savings_claim(None, True)["claim"] == "unresolved"
        out = savings_claim(50, False)
        assert out["code"] == "PF-ECONOMY-PRICING-MISSING"
        assert savings_claim(50, True)["claim"] == "supported"
