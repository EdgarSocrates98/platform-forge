"""Phase D gates — policy engine: decisions, precedence, exceptions,
shadow mode, adapters."""

from platformforge.ops.policy import Policy, PolicyException, adapter_eval, evaluate, simulate_policy


def _pol(pid="p1", decision="allow", priority=100, shadow=False, **when):
    return Policy(policy_id=pid, version="1", priority=priority,
                  shadow=shadow, when=when,
                  then={"decision": decision, "reason": f"{pid}:{decision}"})


def test_allow():
    d = evaluate({"environment": "dev"},
                 [_pol(decision="allow", environment="dev")])
    assert d.decision == "allow"
    assert d.input_hash.startswith("sha256:")
    assert d.evidence


def test_no_policy_is_unresolved_not_allow():
    d = evaluate({"environment": "dev"}, [])
    assert d.decision == "unresolved"
    assert "no applicable" in d.reason


def test_deny_overrides_same_priority():
    d = evaluate({"environment": "prod"}, [
        _pol("a", "allow", 10, environment="prod"),
        _pol("b", "deny", 10, environment="prod")])
    assert d.decision == "deny"
    assert d.policy_id == "b"


def test_priority_order():
    d = evaluate({"environment": "prod"}, [
        _pol("strict", "require-security-review", 5, environment="prod"),
        _pol("loose", "allow", 50, environment="prod")])
    assert d.decision == "require-security-review"
    assert d.policy_id == "strict"


def test_require_dominates_allow():
    d = evaluate({"environment": "prod"}, [
        _pol("a", "allow", 10, environment="prod"),
        _pol("b", "require-approval", 10, environment="prod")])
    assert d.decision == "require-approval"


def test_shadow_never_enforces():
    d = evaluate({"environment": "prod"}, [
        _pol("shadow-pol", "deny", 1, shadow=True, environment="prod")])
    assert d.decision == "deny"
    assert d.effective == "would_deny"
    assert d.shadow


def test_exception_active_expires():
    pol = _pol("deny-prod", "deny", environment="prod")
    ex = PolicyException(exception_id="ex1", policy_id="deny-prod",
                         scope="prod", expires_at="2999-01-01T00:00:00Z",
                         owner="me", approved_by="boss")
    d = evaluate({"environment": "prod"}, [pol], exceptions=[ex])
    assert d.decision == "allow"
    assert d.exception_id == "ex1"
    # expired → back to enforced
    ex2 = PolicyException(exception_id="ex2", policy_id="deny-prod",
                          scope="prod", expires_at="2000-01-01T00:00:00Z")
    d2 = evaluate({"environment": "prod"}, [pol], exceptions=[ex2])
    assert d2.decision == "deny"


def test_exception_without_expiry_inert():
    ex = PolicyException(exception_id="x", policy_id="p")
    assert not ex.is_active()


def test_simulate_over_history():
    hist = [{"environment": "prod"}, {"environment": "dev"}]
    s = simulate_policy(_pol("deny-prod", "deny", environment="prod"), hist)
    assert s["counts"]["would_deny"] == 1
    assert s["counts"]["would_unresolved"] == 1


def test_adapter_maps_error_to_unresolved():
    def boom(inp):
        raise RuntimeError("opa missing")
    d = adapter_eval("opa", {"x": 1}, boom)
    assert d.decision == "unresolved"
    assert "adapter-error" in d.reason


def test_adapter_never_invents_allow():
    d = adapter_eval("opa", {"x": 1},
                     lambda i: {"decision": "garbage", "reason": "?"})
    assert d.decision == "unresolved"


def test_comparators():
    p = Policy(policy_id="big-cost", when={"cost_delta": {"$gte": 100}},
               then={"decision": "require-owner-review"})
    assert p.matches({"cost_delta": 150})
    assert not p.matches({"cost_delta": 50})
