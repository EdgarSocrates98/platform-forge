"""Phase E gates — approval hash-binding, TTL, scope, bounds, break-glass."""

from platformforge.ops.approval import Approval, BreakGlass, check_approval


def _ap(**kw):
    base = {"approval_id": "a1", "subject_hash": "sha256:abc",
            "scope": ["res-1"], "actor": "alice", "role": "owner",
            "type": "single-human"}
    base.update(kw)
    return Approval(**base)


def test_hash_bound_approval_ok():
    c = check_approval([_ap()], subject_hash="sha256:abc",
                     scope=["res-1"])
    assert c.ok and not c.used_break_glass


def test_wrong_hash_no_match():
    c = check_approval([_ap()], subject_hash="sha256:xyz",
                     scope=["res-1"])
    assert not c.ok
    assert c.refusal["refusal"] == "PF-OPS-NO-APPROVAL"


def test_plan_changed_invalidates():
    c = check_approval([_ap()], subject_hash="sha256:abc",
                       scope=["res-1"], current_plan_hash="sha256:xyz")
    assert c.refusal["refusal"] == "PF-OPS-APPROVAL-STALE-PLAN"


def test_expired_approval_rejected():
    c = check_approval([_ap(expires_at="2000-01-01T00:00:00Z")],
                       subject_hash="sha256:abc", scope=["res-1"])
    assert c.refusal["refusal"] == "PF-OPS-APPROVAL-EXPIRED"


def test_scope_mismatch_rejected():
    c = check_approval([_ap(scope=["res-1"])], subject_hash="sha256:abc",
                       scope=["res-1", "res-2"])
    assert c.refusal["refusal"] == "PF-OPS-APPROVAL-SCOPE"


def test_parameter_bounds():
    ap = _ap(parameter_bounds={"replicas": [3, 5]})
    ok = check_approval([ap], subject_hash="sha256:abc",
                        scope=["res-1"], params={"replicas": 5})
    assert ok.ok
    bad = check_approval([ap], subject_hash="sha256:abc",
                         scope=["res-1"], params={"replicas": 50})
    assert bad.refusal["refusal"] == "PF-OPS-APPROVAL-BOUNDS"


def test_break_glass_ok_and_scoped():
    bg = BreakGlass(break_glass_id="bg1", invocation_reason="sev1",
                    actor="oncall", scope=["res-1"],
                    expires_at="2999-01-01T00:00:00Z",
                    incident_ref="inc-9")
    assert bg.validate() == []
    c = check_approval([], subject_hash="sha256:abc", scope=["res-1"],
                     break_glass=bg)
    assert c.ok and c.used_break_glass


def test_break_glass_requires_reason_actor_ttl_scope():
    bg = BreakGlass()
    errs = {e["refusal"] for e in bg.validate()}
    assert {"PF-OPS-BG-NO-REASON", "PF-OPS-BG-NO-ACTOR",
            "PF-OPS-BG-NO-TTL", "PF-OPS-BG-NO-SCOPE"} <= errs


def test_break_glass_expired():
    bg = BreakGlass(invocation_reason="s", actor="a", scope=["r"],
                    expires_at="2000-01-01T00:00:00Z")
    c = check_approval([], subject_hash="sha256:x", scope=["r"],
                     break_glass=bg)
    assert c.refusal["refusal"] == "PF-OPS-BG-EXPIRED"
