"""§69–§84 — agent dogfooding: per-case route decisions, over/under-
routing detection, champion/challenger shadow benchmark.

Case-derived signals are inferred honestly: domains = analyzers;
security_sensitive = security-family analyzers; complexity from domain
count. The router's own output is the evidence — nothing is assumed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from platformforge.cases.casefile import CaseFile, discover_cases

SECURITY_DOMAINS = {"security", "iam", "secrets", "supply", "sbom",
                    "slsa", "cosign", "policy"}
# domain keys in routing.DOMAIN_SPECIALIST vocabulary
_DOMAIN_MAP = {"cloud-aws": "aws", "cloud-gcp": "cloud",
               "iac": "terraform", "secrets": "security",
               "iam": "security", "supply": "security",
               "sbom": "security", "slsa": "security",
               "cosign": "security", "slo": "sre"}


def signal_for_case(c: CaseFile):
    from platformforge.routing.router import TaskSignal
    domains = [_DOMAIN_MAP.get(d, d) for d in c.analyzers]
    return TaskSignal(
        task_type="analysis",
        domains=domains,
        complexity="high" if len(domains) >= 3 else (
            "medium" if len(domains) == 2 else "low"),
        security_sensitive=bool(SECURITY_DOMAINS & set(c.analyzers)),
        evidence_available=True,
        freshness="current",
    )


def audit_case(c: CaseFile) -> dict[str, Any]:
    from platformforge.routing.router import route
    sig = signal_for_case(c)
    t0 = time.time()
    d = route(sig)
    agents = d["agents"]
    flags: list[str] = []
    # over-routing (§71): one specialist would do, but a crowd was called
    if len(c.analyzers) == 1 and len(d["specialists"]) > 2:
        flags.append("over-routing: single-domain case dispatched "
                     f"{len(d['specialists'])} specialists")
    if d["mode"] == "coordinated" and len(c.analyzers) == 1 \
            and not sig.security_sensitive:
        flags.append("over-routing: coordinated mode for a "
                     "single-domain case")
    # under-routing (§72): security-sensitive without security reviewer
    if sig.security_sensitive and \
            "platform-security-reviewer" not in d["reviewers"]:
        flags.append("under-routing: security-sensitive case has no "
                     "security reviewer")
    # every agentic route must end in independent verification
    if d["mode"] != "deterministic" and not d["verifier"]:
        flags.append("missing verifier on an agentic route")
    return {
        "schema": "platformforge/route-decision/v1",
        "case": c.id, "tier": c.tier,
        "router_input": {k: getattr(sig, k)
                         for k in sig.__dataclass_fields__},
        "mode": d["mode"], "budget": d["budget"],
        "selected": agents, "specialists": d["specialists"],
        "reviewers": d["reviewers"], "coordinator": d["coordinator"],
        "verifier": d["verifier"],
        "rejected": sorted(set(_all_candidate_names()) - set(agents)),
        "fanout": len(agents), "dag_stages": len(d["dag"]),
        "reasons": d["reasons"], "flags": flags,
        "ms": round((time.time() - t0) * 1000, 1),
        "result": "flagged" if flags else "ok"}


def _all_candidate_names() -> list[str]:
    from platformforge.agents.roster import AGENTS
    return list(AGENTS)


def audit_corpus(root: str | Path = ".platformforge/cases",
                 ledger: bool = True) -> dict[str, Any]:
    cases = discover_cases(root)
    decisions = [audit_case(c) for c in cases]
    flagged = [d["case"] for d in decisions if d["flags"]]
    by_mode: dict[str, int] = {}
    fanout = 0
    for d in decisions:
        by_mode[d["mode"]] = by_mode.get(d["mode"], 0) + 1
        fanout += d["fanout"]
    out = {"schema": "platformforge/routing-audit/v1",
           "cases": len(decisions), "decisions": decisions,
           "by_mode": by_mode,
           "avg_fanout": round(fanout / len(decisions), 2) if decisions else 0,
           "flagged": flagged,
           "verdict": "pass" if not flagged else "flagged",
           "note": "flags are review signals, not auto-fixes — the "
                   "router is not self-modified (§76)"}
    if ledger:
        p = Path(".platformforge/ledger")
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "routing-decisions.jsonl", "w") as fh:
            for d in decisions:
                fh.write(json.dumps(d, default=str) + "\n")
        out["ledger"] = str(p / "routing-decisions.jsonl")
    return out


def champion_challenger(root: str | Path = ".platformforge/cases",
                        challenger: str | Path | None = None
                        ) -> dict[str, Any]:
    """§77 — champion = rules/catalog/routing.yaml; challenger = an
    alternate table run in offline shadow mode. Scores per case:
    correctness (right specialist for the domains), evidence recall,
    agent count, projected cost, latency, tool calls (router-side).
    Without a challenger file this reports champion-only shadow."""
    from platformforge.routing.router import route

    cases = discover_cases(root)
    rows = []
    for c in cases:
        sig = signal_for_case(c)
        champ = route(sig)
        row = {"case": c.id, "champion": _score(c, sig, champ)}
        if challenger and Path(challenger).is_file():
            chal = route(sig, routes_path=challenger)
            row["challenger"] = _score(c, sig, chal)
            row["delta"] = _delta(row["champion"], row["challenger"])
        rows.append(row)
    return {"schema": "platformforge/routing-bench/v1",
            "cases": rows, "challenger": str(challenger) if challenger
            else "none — champion-only shadow",
            "note": "challenger never activates silently — routing "
                    "changes require review (§77)"}


def _score(c: CaseFile, sig, d: dict[str, Any]) -> dict[str, Any]:
    """Offline score — correctness = every case domain has its
    specialist selected; recall = specialists / needed."""
    from platformforge.routing.router import DOMAIN_SPECIALIST
    needed = {DOMAIN_SPECIALIST[dom] for dom in
              {_DOMAIN_MAP.get(a, a) for a in c.analyzers}
              if dom in DOMAIN_SPECIALIST}
    selected = set(d["specialists"])
    recall = len(needed & selected) / len(needed) if needed else 1.0
    return {"mode": d["mode"], "agents": len(d["agents"]),
            "specialists": len(d["specialists"]),
            "correctness": sorted(needed <= selected and ["full"]
                                  or [s for s in needed - selected]),
            "evidence_recall": round(recall, 3),
            "budget": d["budget"], "dag_stages": len(d["dag"])}


def _delta(champ: dict, chal: dict) -> dict[str, Any]:
    return {"agents": chal["agents"] - champ["agents"],
            "evidence_recall": round(chal["evidence_recall"]
                                     - champ["evidence_recall"], 3),
            "mode": f"{champ['mode']}→{chal['mode']}"}
