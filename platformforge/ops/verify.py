"""Cycle 4 — verification engine (§110–118, ADR-0028).

Execution success ≠ outcome success. Verification compares the
*ExpectedDelta* declared at plan time against the *ObservedDelta*
measured from live evidence (provider state, k8s status, runtime
topology, SLO, alerts) across windows: immediate → stabilization →
extended. SLO degradation after a change is a verification failure —
even when the executor exited 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import age_seconds, now_iso, parse_ts

CONVERGENCE = ("converged", "partially-converged", "not-converged",
               "regressed", "unknown")
WINDOWS = ("immediate", "stabilization", "extended")
DEFAULT_WINDOW_TTLS = {"immediate": 60, "stabilization": 600,
                       "extended": 3600}


@dataclass
class WindowResult:
    window: str
    status: str = "unknown"          # pass|fail|pending|unknown
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"window": self.window, "status": self.status,
                "matched": self.matched, "missing": self.missing,
                "unexpected": self.unexpected, "detail": self.detail}


@dataclass
class VerificationResult:
    convergence: str = "unknown"
    windows: list[WindowResult] = field(default_factory=list)
    slo_gate: dict[str, Any] = field(default_factory=dict)
    checked_at: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"convergence": self.convergence,
                "windows": [w.to_dict() for w in self.windows],
                "slo_gate": self.slo_gate, "checked_at": self.checked_at,
                "evidence": self.evidence}


def _flatten(delta: dict[str, Any]) -> set[str]:
    """Flatten ExpectedDelta {adds|removes|changes: {dim: [...]}} to
    canonical 'dim:item' tokens for comparison."""
    out: set[str] = set()
    for side in ("adds", "removes", "changes"):
        for dim, items in (delta.get(side) or {}).items():
            for it in items or []:
                key = it.get("id") if isinstance(it, dict) else str(it)
                out.add(f"{side}:{dim}:{key}")
    return out


def verify_delta(expected: dict[str, Any], observed: dict[str, Any]
                 ) -> tuple[list[str], list[str], list[str]]:
    """Compare expected vs observed delta token sets. Returns
    (matched, missing, unexpected)."""
    exp, obs = _flatten(expected), _flatten(observed)
    return (sorted(exp & obs), sorted(exp - obs), sorted(obs - exp))


def slo_gate(slo: dict[str, Any] | None,
             metrics: dict[str, Any] | None) -> dict[str, Any]:
    """§117–118 — SLO regression gate. `slo` = contract
    {error_budget_threshold, burn_rate_max}; `metrics` = observed
    {error_rate, burn_rate}. Unknown inputs → unknown, never pass."""
    if not slo or not metrics:
        return {"status": "unknown",
                "detail": "no slo contract or metrics supplied"}
    er = metrics.get("error_rate")
    br = metrics.get("burn_rate")
    if er is None and br is None:
        return {"status": "unknown", "detail": "no error/burn metrics"}
    fails = []
    if er is not None and slo.get("error_rate_max") is not None \
            and er > slo["error_rate_max"]:
        fails.append(f"error_rate {er} > {slo['error_rate_max']}")
    if br is not None and slo.get("burn_rate_max") is not None \
            and br > slo["burn_rate_max"]:
        fails.append(f"burn_rate {br} > {slo['burn_rate_max']}")
    if metrics.get("budget_remaining") == "critical":
        fails.append("error budget critical")
    return {"status": "fail" if fails else "pass", "violations": fails}


def verify(*, expected_delta: dict[str, Any],
           observations: dict[str, Any],
           slo_contract: dict[str, Any] | None = None,
           metrics: dict[str, Any] | None = None,
           windows: list[str] | None = None,
           evidence_refs: list[str] | None = None
           ) -> VerificationResult:
    """`observations` maps window → observed-delta dict (already
    computed by the live layer). A window with no observation is
    `unknown`, never pass."""
    res = VerificationResult(checked_at=now_iso(),
                             evidence=list(evidence_refs or []))
    for w in (windows or list(WINDOWS)):
        obs = observations.get(w)
        wr = WindowResult(window=w)
        if obs is None:
            wr.status = "unknown"
            wr.detail = "no observation for this window"
        else:
            matched, missing, unexpected = verify_delta(expected_delta, obs)
            wr.matched, wr.missing, wr.unexpected = matched, missing, unexpected
            wr.status = "pass" if not missing and not unexpected else "fail"
        res.windows.append(wr)

    res.slo_gate = slo_gate(slo_contract, metrics)

    statuses = [w.status for w in res.windows]
    if "fail" in statuses or res.slo_gate.get("status") == "fail":
        if res.slo_gate.get("status") == "fail" and "fail" not in statuses:
            res.convergence = "regressed"
        elif all(s == "fail" for s in statuses if s != "unknown"):
            res.convergence = "not-converged"
        else:
            res.convergence = "partially-converged"
    elif all(s == "pass" for s in statuses) and statuses:
        res.convergence = ("converged"
                           if res.slo_gate.get("status") in ("pass", "unknown")
                           else "partially-converged")
    elif any(s == "pass" for s in statuses):
        res.convergence = "partially-converged"
    else:
        res.convergence = "unknown"
    return res


def freshness_ok(captured_at: str, window: str, at: str | None = None
                 ) -> bool:
    age = age_seconds(captured_at, parse_ts(at))
    return age is not None and age <= DEFAULT_WINDOW_TTLS.get(window, 3600)
