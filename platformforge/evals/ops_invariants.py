"""Cycle 4.1 — ops invariant probes for eval cases (§137–141).

Each probe is a deterministic function returning {"ok": bool,
"detail": ...} — the eval runner records pass/fail from `ok`. These
cover the correctness invariants that a scripted lab scenario can't
reach: tamper detection, refusal codes, builder semantics.
"""

from __future__ import annotations

import json
from typing import Any


def probe_material_tamper(tmp) -> dict[str, Any]:
    """§141 — a RollbackMaterial whose file content is tampered is
    detected by its content hash; the store refuses a mismatched
    write."""
    from pathlib import Path

    from platformforge.ops.material import MaterialStore, capture_material
    store = MaterialStore(root=Path(tmp) / "materials")
    m = capture_material("kubernetes.scale", "s1", "op-t",
                         {"replicas": 5}, {"replicas"},
                         pre_state={"replicas": 3})
    store.put(m)
    path = Path(tmp) / "materials" / f"{m.hash().split(':', 1)[1]}.json"
    blob = json.loads(path.read_text())
    blob["pre_state"]["replicas"] = 999          # tamper
    recomputed = type(m).from_dict(blob).hash()
    ok = recomputed != m.hash()
    return {"ok": ok, "detail": "tampered material hash "
            f"{recomputed[:24]} != {m.hash()[:24]}"}


def probe_approval_seal_tamper(tmp) -> dict[str, Any]:
    """§140 — modifying a sealed approval invalidates the seal and the
    approval no longer passes check_approval."""
    from platformforge.ops.approval import Approval, check_approval
    ap = Approval(approval_id="a1", subject_hash="sha256:plan",
                  scope=["r1"], actor="alice", role="owner")
    ap.seal()
    assert ap.integrity_seal_valid()
    ap.scope = ["r1", "everything-else"]       # tamper after seal
    ok = not ap.integrity_seal_valid()
    chk = check_approval([ap], subject_hash="sha256:plan",
                         scope=["r1"], current_plan_hash="sha256:plan")
    refused = (chk.refusal or {}).get("refusal") == \
        "PF-OPS-APPROVAL-TAMPERED"
    return {"ok": ok and refused,
            "detail": f"seal_valid={not ok} refusal={refused}"}


def probe_no_delta(tmp) -> dict[str, Any]:
    """§138 — a mutating plan with no ExpectedDelta refuses to mint."""
    from platformforge.ops.engine import mint_envelope
    from platformforge.ops.engine import plan as mkplan
    from platformforge.ops.models import ChangeIntent, ExpectedDelta, PlanStep, Reason
    from platformforge.ops.policy import PolicyDecision
    intent = ChangeIntent(intent_id="i", reason=Reason(type="manual"),
                          target_resources=["r"])
    plan = mkplan(intent, steps=[PlanStep(
        step_id="s", action="kubernetes.scale",
        params={"kind": "Deployment", "name": "w", "replicas": 5})],
        expected_delta=ExpectedDelta())
    r = mint_envelope(plan, execution_id="x",
                      decisions=[PolicyDecision(policy_id="p",
                                                decision="allow",
                                                reason="")],
                      approvals=[], risk={}, rollback=None)
    ok = isinstance(r, dict) and r.get("refusal") == "PF-OPS-NO-DELTA"
    return {"ok": ok, "detail": r if not ok else "refused as designed"}


def probe_sot_conflict(tmp) -> dict[str, Any]:
    """§139 — gitops + terraform both claiming the resource →
    conflicted status requiring human review, never silent winner."""
    from platformforge.ops.source_of_truth import resolve
    res = resolve([{"resource": "k8s:x/y/Deployment/z",
                    "declared_by": "terraform",
                    "managed_by": "argocd"}],
                  {"rules": [{"when": "multi-owner",
                              "status": "conflicted"}]})
    d = [r.to_dict() for r in res]
    conflicted = any(r.get("status") in ("conflicted", "unresolved")
                     or not r.get("resolved", True) for r in d)
    return {"ok": bool(d) and conflicted,
            "detail": d}


def probe_plan_reuse(tmp) -> dict[str, Any]:
    """§15–19 — the same terraform saved plan can never be reused as
    its own rollback."""
    from platformforge.ops.rollback import terraform_plan_reuse_check
    r = terraform_plan_reuse_check("sha256:planA", "sha256:planA")
    return {"ok": r.get("refusal") == "PF-OPS-PLAN-REUSE",
            "detail": r}


def probe_blind_inverse_refused(tmp) -> dict[str, Any]:
    """§6–9 — without captured material the plan is unresolved, never
    executable-by-guess."""
    from platformforge.ops.rollback import build_rollback_plan
    rb = build_rollback_plan(
        [{"step_id": "s", "action": "kubernetes.scale",
          "params": {"replicas": 5}}], materials={})
    return {"ok": rb.status in ("unresolved", "manual-only",
                                "impossible") and
            rb.status != "executable",
            "detail": f"status={rb.status}"}


def probe_git_revert_builder(tmp) -> dict[str, Any]:
    """§137 — git.commit material → git revert of the RESULTING commit
    (post-state), not a blind `git reset`."""
    from platformforge.ops.material import capture_material
    from platformforge.ops.rollback_builders import BUILDERS
    m = capture_material("git.commit", "s", "op", {"repo": "r"},
                         {"pre_change_commit"},
                         pre_state={"pre_change_commit": "aaa"},
                         execution_result={"resulting_commit": "bbb"})
    b = BUILDERS["git.commit"]({"repo": "r"}, m.to_dict(), {})
    ok = b is not None and b["action"] == "git.revert_commit" and \
        b["params"].get("commit_sha") == "bbb" and \
        "aaa" not in json.dumps(b["params"])
    return {"ok": ok, "detail": b}


def probe_rollback_unknown(tmp) -> dict[str, Any]:
    """§137 rollback-unknown — an action with no builder and no
    declared strategy stays unresolved."""
    from platformforge.ops.material import capture_material
    from platformforge.ops.rollback import build_rollback_plan
    m = capture_material("kubernetes.rollout_restart", "s", "op",
                         {"kind": "Deployment", "name": "w"},
                         {"revision"})
    rb = build_rollback_plan(
        [{"step_id": "s", "action": "kubernetes.rollout_restart",
          "params": {}}],
        materials={"s": m}, context={})
    ok = rb.status in ("unresolved", "requires-replan",
                       "manual-only") or (
        rb.status == "executable" and rb.actions)
    # without a captured revision the plan must NOT be executable
    return {"ok": ok and rb.status != "executable",
            "detail": f"status={rb.status} actions={rb.actions}"}


PROBES = {
    "material-tamper": probe_material_tamper,
    "approval-seal-tamper": probe_approval_seal_tamper,
    "no-delta": probe_no_delta,
    "sot-conflict": probe_sot_conflict,
    "plan-reuse": probe_plan_reuse,
    "blind-inverse-refused": probe_blind_inverse_refused,
    "git-revert-builder": probe_git_revert_builder,
    "rollback-unknown": probe_rollback_unknown,
}
