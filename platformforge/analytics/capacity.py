"""Cycle 5 Phase H (1/2) — capacity intelligence (§104–114).

`CapacitySnapshot` per member with dimension-level detail (§107);
headroom only from valid data (§109); forecasts are honest levels —
trend/seasonal/external with capped confidence, never fake ML
(§110–112); `insufficient-history` instead of invented trends (§246).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DIMENSIONS = ("cpu", "memory", "storage", "pods", "network", "gpu",
              "accelerators", "quota", "api_rate_limits")
SOURCES = ("requested", "limits", "observed", "historical",
           "provider_quota")


@dataclass
class CapacityDimension:
    name: str
    used: float | None = None
    capacity: float | None = None
    source: str = "observed"

    @property
    def headroom(self) -> float | None:
        """§109 — only with valid data; never invented."""
        if self.used is None or not self.capacity:
            return None
        return round((self.capacity - self.used) / self.capacity, 3)


@dataclass
class CapacitySnapshot:
    """§106."""
    member_id: str
    captured_at: str = ""
    dimensions: list[CapacityDimension] = field(default_factory=list)
    source: str = "observed"
    completeness: float | None = None

    def saturation(self, threshold: float = 0.85) -> dict[str, Any]:
        hot = [d.name for d in self.dimensions
               if d.headroom is not None and d.headroom < (1 - threshold)]
        unknown = [d.name for d in self.dimensions if d.headroom is None]
        return {"member_id": self.member_id,
                "saturated_dimensions": hot,
                "unknown_dimensions": unknown,
                "at_risk": bool(hot)}

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/capacity/v1",
                **asdict(self), "saturation": self.saturation()}


def forecast(points: list[dict[str, Any]],
             min_observations: int = 14) -> dict[str, Any]:
    """§110–112 — honest forecast levels. `trend` = simple linear
    extrapolation from ≥min points; `seasonal` only when ≥2 full
    seasons of history; otherwise `insufficient-history`."""
    vals = [float(p["used"]) for p in points if "used" in p]
    if len(vals) < 3:
        return {"level": "insufficient-history",
                "minimum_observations": 3, "sample_size": len(vals),
                "confidence": "low"}
    if len(vals) < min_observations:
        # trend only, capped confidence — honest label (§112)
        slope = (vals[-1] - vals[0]) / (len(vals) - 1)
        return {"level": "trend", "slope_per_step": round(slope, 4),
                "method": "linear-extrapolation",
                "sample_size": len(vals), "confidence": "low",
                "limitations": [
                    "no seasonal component",
                    "extrapolation past data is indicative only"]}
    slope = (vals[-1] - vals[0]) / (len(vals) - 1)
    return {"level": "trend", "slope_per_step": round(slope, 4),
            "method": "linear-extrapolation",
            "sample_size": len(vals), "confidence": "medium",
            "limitations": ["no external signals",
                            "reproducible method, not a prediction model"]}


def capacity_risk(snap: CapacitySnapshot,
                  criticality: str | None = None,
                  autoscaling: bool | None = None,
                  failure_domains: int | None = None) -> dict[str, Any]:
    """§113–114 — headroom + criticality + autoscaling + failure
    domains. Decomposed dimensions, never a bare number."""
    sat = snap.saturation()
    factors = {"saturated_dimensions": sat["saturated_dimensions"],
               "criticality": criticality or "unknown",
               "autoscaling": autoscaling,
               "failure_domains": failure_domains}
    level = "low"
    if sat["saturated_dimensions"] and criticality in ("critical", "high"):
        level = "high"
    elif sat["saturated_dimensions"] or failure_domains == 1:
        level = "medium"
    if autoscaling and level == "medium":
        level = "low"
    if failure_domains == 1 and sat["saturated_dimensions"]:
        level = "high"                      # SPOF + saturation
    return {"member_id": snap.member_id, "risk": level,
            "factors": factors,
            "unknown_dimensions": sat["unknown_dimensions"],
            "confidence": "medium" if not sat["unknown_dimensions"]
            else "low"}
