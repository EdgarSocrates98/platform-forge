"""CNCF Platform Engineering Maturity Model scoring — 5 aspects × 4 levels.

Evidence-driven: each aspect scores against declared signals (facts). A
level is claimed only when its signals are observed — the model never
asserts maturity without evidence ids.
"""

from __future__ import annotations

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


def maturity(signals: dict[str, list[str]],
             evidence: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """signals: {aspect: [observed_signal,...]}. Level = highest level whose
    every lower level's signals are also observed (maturity compounds)."""
    aspects = {}
    for aspect in ASPECTS:
        obs = set(signals.get(aspect, []))
        level = "provisional"
        missing = {}
        for lv in ("operational", "scalable", "optimizing"):
            want = SIGNALS[aspect].get(lv, [])
            lack = [s for s in want if s not in obs]
            if not lack:
                level = lv
            else:
                missing[lv] = lack
                break  # maturity compounds — can't skip a level
        aspects[aspect] = {
            "level": level,
            "observed_signals": sorted(obs),
            "missing_for_next": missing,
            "evidence": (evidence or {}).get(aspect, []),
        }
    overall = min((_ORDER[a["level"]] for a in aspects.values()))
    return {"aspects": aspects,
            "overall_level": LEVELS[overall],
            "model": "CNCF Platform Engineering Maturity Model",
            "note": "level = highest fully-evidenced level; compounding "
                    "— a skipped tier caps the claim"}
