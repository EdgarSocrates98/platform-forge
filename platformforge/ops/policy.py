"""Cycle 4 — operation policy engine V2 (§40–52, ADR-0030).

Governs *actions*, not just resources. The canonical contract is
`PolicyDecision`; external engines (OPA/Kyverno/CEL) are adapters that
feed it — never truth themselves.

Precedence rules (explicit, no coin flips):
- policies carry {owner, authority, priority, scope}; evaluation runs in
  declared priority order;
- equal-priority allow vs deny → **deny dominates**;
- `require-*` decisions dominate plain `allow`;
- unresolved input → `unresolved` decision which fails closed for
  mutations (never silently denied, never silently allowed).

Shadow policies evaluate identically but emit `would_*` verdicts — they
can never enforce (§50–52, 275).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso, parse_ts

DECISION_SCHEMA = "platformforge/policy-decision/v1"
EXCEPTION_SCHEMA = "platformforge/policy-exception/v1"

DECISIONS = ("allow", "deny", "require-approval",
             "require-additional-evidence", "require-simulation",
             "require-security-review", "require-owner-review",
             "defer", "unresolved")
ENFORCING = {"deny", "require-approval", "require-additional-evidence",
             "require-simulation", "require-security-review",
             "require-owner-review", "defer", "unresolved"}

# Rank for combining equal-priority decisions: higher wins.
_DECISION_RANK = {"deny": 90, "require-security-review": 80,
                  "require-owner-review": 75, "require-approval": 70,
                  "require-simulation": 65,
                  "require-additional-evidence": 60, "defer": 50,
                  "unresolved": 40, "allow": 10}


@dataclass
class PolicyException:
    """§47–49 — scoped, owned, expiring bypass. Never permanent."""
    exception_id: str = ""
    policy_id: str = ""
    scope: str = ""
    resource: str = ""
    reason: str = ""
    owner: str = ""
    approved_by: str = ""
    created_at: str = ""
    expires_at: str = ""
    compensating_controls: list[str] = field(default_factory=list)

    def is_active(self, at: str | None = None) -> bool:
        exp = parse_ts(self.expires_at)
        if exp is None:
            return False   # §48 — exceptions without expiry are inert
        ref = parse_ts(at) if at else parse_ts(now_iso())
        return bool(ref and ref <= exp)

    def applies_to(self, policy_id: str, scope: str,
                   resource: str) -> bool:
        if self.policy_id and self.policy_id != policy_id:
            return False
        if self.scope and self.scope != scope:
            return False
        return not (self.resource and self.resource != resource)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": EXCEPTION_SCHEMA,
                "exception_id": self.exception_id,
                "policy_id": self.policy_id, "scope": self.scope,
                "resource": self.resource, "reason": self.reason,
                "owner": self.owner, "approved_by": self.approved_by,
                "created_at": self.created_at or now_iso(),
                "expires_at": self.expires_at,
                "compensating_controls": self.compensating_controls}


@dataclass
class PolicyDecision:
    """§42–44 — canonical decision + receipt fields."""
    decision: str = "unresolved"     # allow|deny|require-*|defer|unresolved
    policy_id: str = ""
    policy_version: str = ""
    combining: str = "deny-overrides"
    reason: str = ""
    input_hash: str = ""
    evidence: list[str] = field(default_factory=list)
    timestamp: str = ""
    shadow: bool = False             # §50 — would_* semantics
    exception_id: str = ""
    evaluated: list[str] = field(default_factory=list)

    @property
    def effective(self) -> str:
        """The decision as enforced — shadow policies only *record*."""
        if self.shadow:
            return f"would_{self.decision}"
        return self.decision

    def to_dict(self) -> dict[str, Any]:
        return {"schema": DECISION_SCHEMA,
                "policy_id": self.policy_id,
                "policy_version": self.policy_version,
                "combining": self.combining,
                "input_hash": self.input_hash,
                "decision": self.decision,
                "effective": self.effective,
                "shadow": self.shadow,
                "reason": self.reason, "evidence": self.evidence,
                "evaluated": self.evaluated,
                "exception_id": self.exception_id,
                "timestamp": self.timestamp or now_iso()}


@dataclass
class Policy:
    """Native rule form. `when` = predicates over the policy input;
    `then` = decision + reason."""
    policy_id: str = ""
    version: str = "1"
    owner: str = ""
    authority: str = ""
    priority: int = 100
    scope: str = "*"
    shadow: bool = False
    when: dict[str, Any] = field(default_factory=dict)
    then: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def matches(self, inp: dict[str, Any]) -> bool:
        for k, want in self.when.items():
            got = inp.get(k)
            if isinstance(want, list):
                if got not in want:
                    return False
            elif isinstance(want, dict):
                # comparators: {"$in": [...]}, {"$gte": n}, {"$ne": v}
                if "$in" in want and got not in want["$in"]:
                    return False
                if "$gte" in want and not (got is not None
                                           and got >= want["$gte"]):
                    return False
                if "$lte" in want and not (got is not None
                                           and got <= want["$lte"]):
                    return False
                if "$ne" in want and got == want["$ne"]:
                    return False
            elif got != want:
                return False
        return True


def _scope_match(policy_scope: str, inp_scope: str) -> bool:
    return policy_scope in ("*", "", inp_scope) or \
        inp_scope.startswith(policy_scope.rstrip("*"))


def evaluate(inp: dict[str, Any], policies: list[Policy],
             exceptions: list[PolicyException] | None = None,
             at: str | None = None) -> PolicyDecision:
    """Deterministic evaluation: scope → priority → deny-overrides."""
    inp_hash = "sha256:" + canonical_hash(inp)
    scope = inp.get("scope") or inp.get("environment") or "*"
    applicable = [p for p in sorted(policies, key=lambda p: p.priority)
                  if _scope_match(p.scope, scope) and p.matches(inp)]

    hits: list[tuple[Policy, str]] = []
    for p in applicable:
        dec = p.then.get("decision", "unresolved")
        if dec not in DECISIONS:
            dec = "unresolved"
        hits.append((p, dec))

    exceptions = exceptions or []
    active_ex: list[PolicyException] = []

    if not hits:
        # §33 analog — no applicable policy means "unresolved", not allow
        return PolicyDecision(decision="unresolved", input_hash=inp_hash,
                              reason="no applicable policy",
                              evidence=[], timestamp=at or now_iso())

    for pol, dec in hits:
        for ex in exceptions:
            if ex.is_active(at) and ex.applies_to(
                    pol.policy_id, scope,
                    inp.get("resource", "") or ""):
                active_ex.append(ex)

    enforcing = [(p, d) for p, d in hits if d != "allow"]
    shadow_only = all(p.shadow for p, _ in hits)
    if enforcing:
        # deny dominates; among equal-priority, strongest require-* wins
        top_pri = min(p.priority for p, d in enforcing)
        top = [(p, d) for p, d in enforcing if p.priority == top_pri]
        top.sort(key=lambda pd: -_DECISION_RANK.get(pd[1], 0))
        pol, dec = top[0]
    else:
        pol, dec = hits[0][0], "allow"

    if active_ex and dec in ENFORCING:
        return PolicyDecision(
            decision="allow", policy_id=pol.policy_id,
            policy_version=pol.version, reason=(
                f"exception:{active_ex[0].exception_id} "
                f"overrides {pol.policy_id} until {active_ex[0].expires_at}"),
            input_hash=inp_hash,
            evidence=[f"policy:{p.policy_id}@{p.version}"
                      for p, _ in hits],
            timestamp=at or now_iso(), shadow=pol.shadow or shadow_only,
            exception_id=active_ex[0].exception_id,
            evaluated=[p.policy_id for p, _ in hits])

    conflict = dec == "allow" and any(d == "deny" for _, d in hits)
    if conflict:
        dec, reason_extra = "deny", " [conflict→deny-overrides]"
    else:
        reason_extra = ""

    return PolicyDecision(
        decision=dec, policy_id=pol.policy_id, policy_version=pol.version,
        reason=(pol.then.get("reason") or pol.description or dec)
               + reason_extra,
        input_hash=inp_hash,
        evidence=[f"policy:{p.policy_id}@{p.version}" for p, _ in hits],
        timestamp=at or now_iso(), shadow=pol.shadow or shadow_only,
        evaluated=[p.policy_id for p, _ in hits])


def simulate_policy(policy: Policy, history: list[dict[str, Any]],
                    exceptions: list[PolicyException] | None = None
                    ) -> dict[str, Any]:
    """§52 — what would this policy have blocked/require on history."""
    counts: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    for i, inp in enumerate(history):
        d = evaluate(inp, [policy], exceptions=exceptions)
        d.shadow = True                    # simulation is never enforcement
        key = d.effective
        counts[key] = counts.get(key, 0) + 1
        records.append({"i": i, "decision": key, "reason": d.reason})
    return {"policy_id": policy.policy_id, "shadow": True,
            "evaluated": len(history), "counts": counts,
            "records": records}


def adapter_eval(engine: str, input_: dict[str, Any],
                 runner: Callable[[dict[str, Any]], dict[str, Any]]
                 ) -> PolicyDecision:
    """§45–46 — external engines are adapters emitting canonical shape.
    `runner` is a host-side callable (opa eval, kyverno apply) returning
    {decision, reason, policy_id, version, evidence}; undefined/errored
    engine output must map to `unresolved`, never to allow."""
    try:
        out = runner(input_)
    except Exception as exc:  # noqa: BLE001 — adapter failure → unresolved (fail closed)
        return PolicyDecision(decision="unresolved",
                              reason=f"{engine}-adapter-error:{exc}",
                              input_hash="sha256:" + canonical_hash(input_))
    dec = out.get("decision", "unresolved")
    if dec not in DECISIONS:
        dec = "unresolved"
    return PolicyDecision(decision=dec, policy_id=out.get("policy_id", engine),
                          policy_version=out.get("version", ""),
                          reason=out.get("reason", ""),
                          input_hash="sha256:" + canonical_hash(input_),
                          evidence=list(out.get("evidence", [])))
