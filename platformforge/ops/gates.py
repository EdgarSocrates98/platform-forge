"""Cycle 4 phase Q — FinOps cost delta + security gates.

CostDelta is an estimate, not a guess: current/planned/delta/basis/
confidence/source. Security gates are deterministic checks over
declared change context (IAM, exposure, provenance, vulnerabilities);
each returns pass|fail|unknown — unknown blocks production paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import now_iso

GATE_STATUS = ("pass", "fail", "unknown", "skipped")


@dataclass
class CostDelta:
    current_monthly: float | None = None
    planned_monthly: float | None = None
    currency: str = "USD"
    basis: str = ""               # estimate|observed-billing|unit-price
    confidence: str = "unknown"   # high|medium|low|unknown
    source: str = ""              # finops-db|aws-pricing|manual|…
    notes: list[str] = field(default_factory=list)

    @property
    def delta(self) -> float | None:
        if self.current_monthly is None or self.planned_monthly is None:
            return None
        return round(self.planned_monthly - self.current_monthly, 2)

    def gate(self, *, budget_increase_max: float | None = None,
             increase_pct_max: float | None = None) -> dict[str, Any]:
        """Budget guard: exceeds → fail; no estimate → unknown
        (never silently pass)."""
        if self.delta is None:
            return {"gate": "cost", "status": "unknown",
                    "detail": "no cost estimate — unknown ≠ zero"}
        if budget_increase_max is not None \
                and self.delta > budget_increase_max:
            return {"gate": "cost", "status": "fail",
                    "detail": f"+{self.delta} > budget "
                              f"{budget_increase_max}"}
        if increase_pct_max is not None and self.current_monthly:
            pct = self.delta / self.current_monthly * 100
            if pct > increase_pct_max:
                return {"gate": "cost", "status": "fail",
                        "detail": f"+{pct:.1f}% > {increase_pct_max}%"}
        return {"gate": "cost", "status": "pass",
                "delta": self.delta, "confidence": self.confidence}

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/cost-delta/v1",
                "current_monthly": self.current_monthly,
                "planned_monthly": self.planned_monthly,
                "delta": self.delta, "currency": self.currency,
                "basis": self.basis, "confidence": self.confidence,
                "source": self.source, "notes": self.notes,
                "at": now_iso()}


# --- security gates ------------------------------------------------------

def gate_iam_change(diff: dict[str, Any]) -> dict[str, Any]:
    """IAM gate — wildcard actions/resources or admin policy adds fail;
    no IAM diff → skipped."""
    adds = ((diff.get("adds") or {}).get("iam") or [])
    if not adds and not ((diff.get("changes") or {}).get("iam")):
        return {"gate": "iam", "status": "skipped"}
    bad = [p for p in adds if isinstance(p, dict)
           and ("*" in str(p.get("actions", ""))
                or "*" in str(p.get("resources", ""))
                or p.get("admin"))]
    return {"gate": "iam",
            "status": "fail" if bad else "pass",
            "violations": bad}


def gate_network_exposure(diff: dict[str, Any]) -> dict[str, Any]:
    """Exposure gate — new 0.0.0.0/0 ingress or public LB fails."""
    adds = ((diff.get("adds") or {}).get("network") or [])
    if not adds:
        return {"gate": "exposure", "status": "skipped"}
    bad = [n for n in adds if isinstance(n, dict)
           and (n.get("cidr") in ("0.0.0.0/0", "::/0")
                or n.get("public") is True)]
    return {"gate": "exposure",
            "status": "fail" if bad else "pass",
            "violations": bad}


def gate_provenance(ctx: dict[str, Any]) -> dict[str, Any]:
    """Artifact provenance — image/artifact must declare signature +
    SBOM + source ref when artifacts are touched."""
    artifacts = ctx.get("artifacts") or []
    if not artifacts:
        return {"gate": "provenance", "status": "skipped"}
    bad = [a.get("ref", "?") for a in artifacts
           if not (a.get("signed") and a.get("sbom"))]
    if not artifacts:
        return {"gate": "provenance", "status": "unknown"}
    return {"gate": "provenance",
            "status": "fail" if bad else "pass",
            "violations": bad}


def gate_vulnerabilities(vuln_scan: dict[str, Any] | None
                         ) -> dict[str, Any]:
    """Vuln gate — critical/high new findings fail; no scan → unknown."""
    if vuln_scan is None:
        return {"gate": "vulnerabilities", "status": "unknown",
                "detail": "no scan supplied — unknown ≠ clean"}
    new = vuln_scan.get("new_findings") or []
    sev = [v for v in new if v.get("severity") in ("critical", "high")]
    return {"gate": "vulnerabilities",
            "status": "fail" if sev else "pass",
            "violations": [v.get("id") for v in sev]}


def security_gates(diff: dict[str, Any] | None = None,
                   ctx: dict[str, Any] | None = None,
                   vuln_scan: dict[str, Any] | None = None
                   ) -> dict[str, Any]:
    """Run all applicable gates; verdict = worst status
    (fail > unknown > skipped > pass)."""
    diff = diff or {}
    ctx = ctx or {}
    gates = [gate_iam_change(diff), gate_network_exposure(diff),
             gate_provenance(ctx), gate_vulnerabilities(vuln_scan)]
    rank = {"fail": 3, "unknown": 2, "skipped": 1, "pass": 0}
    verdict = max(gates, key=lambda g: rank.get(g["status"], 2))["status"]
    return {"verdict": verdict, "gates": gates, "at": now_iso()}
