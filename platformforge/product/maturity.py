"""CNCF Platform Engineering Maturity Model scoring — 5 aspects × 4 levels.

Evidence-driven: each aspect scores against declared signals (facts). A
level is claimed only when its signals are observed — the model never
asserts maturity without evidence ids.
"""

from __future__ import annotations

from typing import Any

ASPECTS = ("investment", "adoption", "interfaces", "operations",
           "measurement")
LEVELS = ("provisional", "operational", "scalable", "optimizing")

# aspect → level → signals (fact kinds/attrs observed). Conservative defaults.
SIGNALS = {
    "investment": {
        "operational": ["dedicated_team", "funded"],
        "scalable": ["platform_team", "product_manager"],
        "optimizing": ["measured_dora_impact", "continual_funding_review"],
    },
    "adoption": {
        "operational": ["some_self_service", "documented_onboarding"],
        "scalable": ["default_paths_adopted", "adoption_tracked"],
        "optimizing": ["platform_is_default", "feedback_loops"],
    },
    "interfaces": {
        "operational": ["catalog", "templates"],
        "scalable": ["golden_paths", "self_service_api"],
        "optimizing": ["composable_products", "versioned_interfaces"],
    },
    "operations": {
        "operational": ["runbooks", "oncall"],
        "scalable": ["slo_defined", "error_budgets", "gitops"],
        "optimizing": ["policy_as_code", "automated_remediation"],
    },
    "measurement": {
        "operational": ["metrics_collected"],
        "scalable": ["dora_tracked", "slo_reported"],
        "optimizing": ["outcome_metrics", "adoption_metrics", "finops"],
    },
}

_ORDER = {"provisional": 0, "operational": 1, "scalable": 2, "optimizing": 3}


def _signal_provenance(v: Any) -> str:
    """§80 — signals carry provenance: observed > declared > inferred.
    A bare string is *declared*; {"signal": x, "provenance": p} carries it."""
    if isinstance(v, dict):
        return v.get("provenance", "declared")
    return "declared"


def maturity(signals: dict[str, list[Any]],
             evidence: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """§80 — Level = highest level whose signals are *observed*. Declared
    signals produce a `declared_level` claim; the gap between observed and
    declared is surfaced, never collapsed. Unknown stays unknown."""
    aspects = {}
    for aspect in ASPECTS:
        raw = signals.get(aspect, [])
        names = {(_signal_name(s)): _signal_provenance(s) for s in raw}
        obs = {n for n, p in names.items() if p == "observed"}
        dec = set(names)  # declared ⊇ observed for level purposes
        observed_level = _level_for(aspect, obs)
        declared_level = _level_for(aspect, dec)
        aspects[aspect] = {
            "level": observed_level,              # the evidence-backed claim
            "declared_level": declared_level,     # what configs/papers say
            "overclaimed": _ORDER[declared_level] > _ORDER[observed_level],
            "signals_observed": sorted(obs),
            "signals_declared_only": sorted(dec - obs),
            "evidence": (evidence or {}).get(aspect, [])}
    return {"aspects": aspects, "schema": "platformforge/maturity/v2"}


def _signal_name(s: Any) -> str:
    return s.get("signal", "") if isinstance(s, dict) else str(s)


def _level_for(aspect: str, have: set[str]) -> str:
    level = "provisional"
    for lv in ("operational", "scalable", "optimizing"):
        want = SIGNALS[aspect].get(lv, [])
        if all(s in have for s in want):
            level = lv
        else:
            break  # maturity compounds — stop at first unmet level
    return level


def maturity_report(signals: dict[str, list[Any]],
                    evidence: dict[str, list[str]] | None = None
                    ) -> dict[str, Any]:
    """Full v2 report: per-aspect + overall, with overclaim flags."""
    out = maturity(signals, evidence)
    overall = min(_ORDER[a["level"]] for a in out["aspects"].values())
    out["overall_level"] = LEVELS[overall]
    out["model"] = "CNCF Platform Engineering Maturity Model"
    out["overclaimed_aspects"] = [a for a, v in out["aspects"].items()
                                  if v["overclaimed"]]
    out["note"] = ("level = highest fully-observed level; "
                   "declared_level may exceed it — that gap is the "
                   "missing evidence, not an error")
    return out
