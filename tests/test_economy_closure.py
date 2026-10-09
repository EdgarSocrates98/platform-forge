"""Economy closure polish tests (prompt_evo_polish §70–89, P1–P10).

Receipt integrity, gate-taxonomy parity, reproduce-path liveness,
single routing authority, doctor stale detection, honest status
vocabulary. These are the gates that close the economy cycle — they
exist so a reviewer can prove the receipt means what it claims.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "docs/economy-parity/VALIDATION-RECEIPT.json"
RECEIPT_SCHEMA = "platformforge/economy-validation-receipt/v1"


def _canonical_economy_gates() -> set[str]:
    sys.path.insert(0, str(REPO / "scripts"))
    import validate as v
    return {n for n in v.GATES if n.startswith("economy-")}


def _head(rev: str = "HEAD") -> str:
    return subprocess.run(["git", "rev-parse", rev], cwd=REPO,
                          capture_output=True, text=True,
                          check=False).stdout.strip()


def _receipt() -> dict:
    assert RECEIPT.is_file(), "closure receipt missing — generate via " \
        "scripts/validate.py --economy-receipt"
    return json.loads(RECEIPT.read_text())


# --- receipt semantics (§70, §62–65) ---------------------------------------

class TestReceiptSemantics:
    def test_schema_is_versioned(self):
        assert _receipt()["schema"] == RECEIPT_SCHEMA

    def test_validated_sha_is_explicit_not_ambiguous(self):
        r = _receipt()
        assert r.get("validated_sha")
        assert "sha" not in r or isinstance(r["sha"], str)

    def test_validated_sha_binds_head_or_parent(self):
        """Option A (§5): receipt binds the functional commit; the
        receipt-only closure commit may sit on top (HEAD~1)."""
        vs = _receipt()["validated_sha"]
        head, head1 = _head(), _head("HEAD~1")
        assert vs in (head, head1), \
            f"receipt binds {vs[:12]} but HEAD is {head[:12]}"

    def test_closure_sha_null_in_committed_file(self):
        """§65 — the receipt-only commit cannot contain its own hash."""
        assert _receipt()["closure_sha"] is None

    def test_metadata_fields(self):
        r = _receipt()
        for f in ("cycle", "spec", "exception", "generated_at",
                  "validator", "validator_version", "known_gaps",
                  "remote_ci", "verdict"):
            assert f in r, f"missing receipt field {f}"


# --- gate taxonomy parity (§71, §9–11) --------------------------------------

class TestGateNameParity:
    def test_receipt_gates_are_canonical(self):
        r = _receipt()
        canon = _canonical_economy_gates()
        assert set(r["gates"]) == canon, (
            f"receipt gates {sorted(set(r['gates']) - canon)} are not "
            "canonical — aliases are forbidden (§11)")

    def test_no_handwritten_alias_gates(self):
        r = _receipt()
        aliases = {"economy-gateway", "economy-pricing-verify",
                   "economy-cli", "economy-mcp", "economy-doctor",
                   "economy-fleet-qpt"}
        assert not set(r["gates"]) & aliases


# --- reproduce commands (§72, §14–19) ---------------------------------------

class TestReproduceCommands:
    def test_every_reproduce_test_path_exists(self):
        r = _receipt()
        dead = [(g, t) for g, e in r["gates"].items()
                for t in re.findall(r"tests/\S+\.py",
                                    str(e.get("reproduce") or ""))
                if not (REPO / t).is_file()]
        assert not dead, f"dead reproduce paths: {dead}"

    def test_reproduce_is_real_command_not_prose(self):
        for g, e in _receipt()["gates"].items():
            rep = e.get("reproduce") or ""
            assert rep.strip(), f"{g} has empty reproduce"
            assert rep.split()[0] in ("pytest", "platformforge",
                                      sys.executable, "python",
                                      "python3", "ruff") or \
                rep.startswith(sys.executable), \
                f"{g} reproduce is not a runnable command: {rep[:60]}"


# --- routing single authority (§73–74, §20–29) ------------------------------

class TestRoutingSingleAuthority:
    def test_decide_is_canonical_producer(self):
        from platformforge.routing.decision import RoutingDecision, RoutingRequest, decide
        req = RoutingRequest(task="audit iac", risk="high",
                             signal={"task_type": "analysis",
                                     "domains": ["iac"]})
        dec = decide(req)
        assert isinstance(dec, RoutingDecision)
        assert dec.schema == "platformforge/routing-decision/v1"
        assert dec.policy_version == "platformforge/routing/v2"
        assert dec.profile == req.effective_profile() == "deep"

    def test_economy_engine_is_advisory(self):
        from platformforge.economy.engine import EconomyEngine
        eng = EconomyEngine(REPO)
        out = eng.advice({"task_type": "analysis"})
        assert out["schema"] == "platformforge/economy-advice/v1"
        assert out["advisory"] is True
        # deprecated alias returns the same advisory shape
        assert eng.strategy({"task_type": "analysis"})["schema"] \
            == out["schema"]

    def test_advice_cannot_activate_orchestration(self):
        """§28/P4 — EconomyEngine output refused by prepare()."""
        from platformforge.agents import plan, prepare, review, seal
        from platformforge.economy.engine import EconomyEngine
        spec = seal(review(plan("x", domains=("iac",))))
        advice = EconomyEngine(REPO).advice({"task_type": "analysis"})
        out = prepare(spec, loop_name="x", router_decision=advice,
                      loops={"x": {"stages": []}})
        assert out.refusal_doc is not None
        assert "routing-decision" in out.refusal_doc["why"]

    def test_canonical_decision_accepted(self):
        from platformforge.agents import plan, prepare, review, seal
        from platformforge.routing.decision import RoutingRequest, decide
        spec = seal(review(plan("x", domains=("iac",))))
        dec = decide(RoutingRequest(task="x", signal={
            "task_type": "analysis", "domains": ["iac"]}))
        out = prepare(spec, loop_name="x",
                      router_decision=dec.to_dict(),
                      loops={"x": {"coordinator": "platform-orchestrator",
                                   "stages": [
                                       {"id": "v", "agent":
                                        "platform-verifier"}]}})
        assert out.refusal_doc is None
        assert out.run.router_decision["schema"] == \
            "platformforge/routing-decision/v1"


# --- doctor stale receipt (§75) ----------------------------------------------

class TestDoctorClosureChecks:
    def test_stale_receipt_flagged(self, tmp_path):
        from platformforge.economy.doctor import doctor
        d = tmp_path / "docs" / "economy-parity"
        d.mkdir(parents=True)
        (d / "VALIDATION-RECEIPT.json").write_text(json.dumps({
            "schema": RECEIPT_SCHEMA, "validated_sha": "0" * 40,
            "gates": {}}))
        rep = doctor(tmp_path)
        check = next(c for c in rep["checks"]
                     if c["check"] == "receipt-fresh")
        assert check["state"] == "warn"
        assert check["evidence"]["code"] == "PF-ECONOMY-RECEIPT-STALE"

    def test_missing_receipt_is_unresolved_not_healthy(self, tmp_path):
        from platformforge.economy.doctor import doctor
        rep = doctor(tmp_path)
        check = next(c for c in rep["checks"]
                     if c["check"] == "receipt-fresh")
        assert check["state"] == "unresolved"
        assert check["evidence"]["code"] == "PF-ECONOMY-RECEIPT-STALE"
        assert rep["overall"] != "ok"

    def test_doctor_reports_closure_checks(self, tmp_path):
        from platformforge.economy.doctor import doctor
        rep = doctor(tmp_path)
        names = {c["check"] for c in rep["checks"]}
        assert {"receipt-fresh", "routing-authority", "qpt"} <= names


# --- honest status vocabulary (§76, §33–34) ----------------------------------

class TestHonestStatuses:
    def test_matrix_uses_closure_vocabulary(self):
        m = (REPO / "docs/economy-parity/FINAL-MATRIX.md").read_text()
        assert "validated" in m
        assert "externally-unverified" in m
        assert "fully production" not in m.lower()
        assert "fully-production" not in m.lower()

    def test_report_answers_closure_questions(self):
        r = (REPO / "docs/economy-parity/FINAL-REPORT.md").read_text()
        for needle in ("validated_sha", "remote_ci", "known gap"):
            assert needle in r, f"FINAL-REPORT missing {needle}"

    def test_report_does_not_claim_ci_green(self):
        r = (REPO / "docs/economy-parity/FINAL-REPORT.md").read_text()
        assert "CI green" not in r and "ci: green" not in r.lower()


# --- money unknown (§77, §60–61) ----------------------------------------------

class TestMoneyUnknown:
    def test_missing_pricing_is_unresolved_never_zero(self):
        from platformforge.economy.pricing import cost
        out = cost([], "anthropic", "claude", 100, 50)
        assert out["state"] == "unresolved"
        assert "cost_usd" not in out or out.get("cost_usd") is None

    def test_unobserved_usage_unresolved(self):
        from platformforge.economy.pricing import cost
        out = cost([], "anthropic", "claude", None, None)
        assert out["state"] == "unresolved"
        assert out["code"] == "PF-ECONOMY-USAGE-UNOBSERVED"


# --- MCP read-only (§79, §47–48) ----------------------------------------------

class TestMCPReadOnly:
    def test_no_routing_activation_tool(self):
        from platformforge.mcp.registry import tool_descriptors
        names = {t["name"] for t in tool_descriptors()}
        assert not any("activate" in n or "promote" in n or
                       "routing_apply" in n for n in names), names

    def test_economy_tools_present_and_bounded(self):
        from platformforge.mcp.registry import tool_descriptors
        names = {t["name"] for t in tool_descriptors()}
        for want in ("platformforge_economy_explain",
                     "platformforge_context_inspect",
                     "platformforge_context_expand",
                     "platformforge_routing_explain"):
            assert want in names, f"missing {want}"


# --- adversarial P1–P10 (§80–89) ----------------------------------------------

class TestAdversarial:
    def test_p1_receipt_cannot_claim_different_head(self):
        """P1 — a receipt bound to a foreign SHA fails the gate's
        sha check (validated_sha ∉ {HEAD, HEAD~1})."""
        r = _receipt()
        foreign = "0" * 40
        assert r["validated_sha"] != foreign
        assert r["validated_sha"] in (_head(), _head("HEAD~1"))

    def test_p2_no_dead_test_paths(self):
        """P2 — every reproduce path resolves (same check, adversarial
        framing: a renamed test must break this)."""
        r = _receipt()
        for g, e in r["gates"].items():
            for t in re.findall(r"tests/\S+\.py",
                                str(e.get("reproduce") or "")):
                assert (REPO / t).is_file(), (g, t)

    def test_p3_alias_cannot_hide_failed_gate(self):
        """P3 — receipt keys are canonical; a failed canonical gate
        cannot hide behind a handwritten pass."""
        r = _receipt()
        canon = _canonical_economy_gates()
        assert set(r["gates"]) == canon
        failed = [g for g, e in r["gates"].items() if not e["ok"]]
        assert not failed, failed

    def test_p4_economy_engine_cannot_route_around_decision(self):
        """P4 — economy advice is not a routing-decision schema."""
        from platformforge.economy.engine import EconomyEngine
        adv = EconomyEngine(REPO).advice({"task_type": "analysis"})
        assert adv["schema"] != "platformforge/routing-decision/v1"

    def test_p5_challenger_never_activates_via_verdict(self):
        """P5 — promote_verdict never returns active promotion without
        human review."""
        from platformforge.routing.decision import promote_verdict
        out = promote_verdict(
            {"id": "c"}, {"id": "n", "quality_pass": True,
                          "safety_unchanged": True,
                          "economy_better": True},
            human_approved=False)
        assert out["verdict"] == "awaiting_human"
        assert out["champion_kept"] is True

    def test_p6_missing_pricing_never_zero_cost(self):
        from platformforge.economy.pricing import cost
        out = cost([], "x", "y", 1, 1)
        assert out["state"] == "unresolved"

    def test_p7_report_cannot_claim_unverified_ci(self):
        r = _receipt()
        ci = str(r.get("remote_ci", "")).lower()
        assert "green" not in ci or "not" in ci

    def test_p8_stale_receipt_blocks_doctor_health(self, tmp_path):
        from platformforge.economy.doctor import doctor
        d = tmp_path / "docs" / "economy-parity"
        d.mkdir(parents=True)
        (d / "VALIDATION-RECEIPT.json").write_text(json.dumps({
            "schema": "old", "validated_sha": "deadbeef",
            "gates": {"bogus-alias": {"ok": True,
                                      "reproduce": "pytest x.py"}}}))
        rep = doctor(tmp_path)
        fresh = next(c for c in rep["checks"]
                     if c["check"] == "receipt-fresh")
        tax = next(c for c in rep["checks"]
                   if c["check"] == "gate-taxonomy")
        assert fresh["state"] == "warn"
        assert tax["state"] == "warn"
        assert rep["overall"] in ("warn", "fail")

    def test_p9_analysis_cache_miss_on_policy_change(self, tmp_path):
        """P9 — analysis/decision entries bind policy + risk context."""
        from platformforge.economy.cache import CacheStore
        store = CacheStore(tmp_path / "cache")
        # analysis binds policy_hash (§LAYER_DEPS)
        deps = {"rule_catalog_hash": "r1", "knowledge_hash": "k1",
                "engine_version": "e1", "policy_hash": "p1"}
        store.put("analysis", "q", {"v": 1}, deps)
        dec, _ = store.get("analysis", "q", deps)
        assert dec.state == "hit"
        dec, _ = store.get("analysis", "q", {**deps, "policy_hash": "p2"})
        assert dec.state != "hit"
        # decision binds policy_version + risk_profile (§53)
        ddeps = {"evidence_hash": "e", "policy_version": "p1",
                 "risk_profile": "low"}
        store.put("decision", "q", {"v": 1}, ddeps)
        dec, _ = store.get("decision", "q", ddeps)
        assert dec.state == "hit"
        dec, _ = store.get("decision", "q",
                         {**ddeps, "risk_profile": "high"})
        assert dec.state != "hit"

    def test_p10_qpc_floors_gate_savings(self):
        """P10 — quality floor regression turns the verdict off even
        with measured cost reduction."""
        from platformforge.economy.qpt import quality_per_cost
        qpt_bad = {"verdict": "fail",
                   "baseline": {"estimated_tokens": 100},
                   "optimized": {"estimated_tokens": 10}}
        out = quality_per_cost(
            qpt_bad,
            baseline_usage={"tool_calls": 4, "model_calls": 2},
            optimized_usage={"tool_calls": 1, "model_calls": 1})
        assert out["quality_floors_ok"] is False
        assert "no savings claim" in out["honest_claim"]
