"""SLO contracts + error budgets per contracts/slo-contract.schema.json.

Budget = (1 − target) × total events. Burn rate = observed error ratio ÷
allowed error ratio. Unresolved inputs produce unresolved outputs — never a
hedged number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import stable_id

_WINDOW_RE = re.compile(r"^(\d+)([dhm])$")
_WINDOW_SECONDS = {"d": 86400, "h": 3600, "m": 60}


@dataclass
class SloContract:
    service: str
    sli: str
    target: float
    window: str
    burn_rate_alerts: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SloContract:
        if not _WINDOW_RE.match(d.get("window", "")):
            raise ValueError(f"bad window: {d.get('window')!r} (use 30d/24h/60m)")
        return cls(service=d["service"], sli=d["sli"], target=float(d["target"]),
                   window=d["window"],
                   burn_rate_alerts=d.get("burn_rate_alerts") or [])

    @classmethod
    def load(cls, path: str | Path) -> SloContract:
        doc = yaml.safe_load(Path(path).read_text())
        return cls.from_dict(doc)

    @property
    def window_seconds(self) -> int:
        n, u = _WINDOW_RE.match(self.window).groups()
        return int(n) * _WINDOW_SECONDS[u]

    @property
    def allowed_error_ratio(self) -> float:
        return 1.0 - self.target / 100.0


def error_budget(contract: SloContract,
                 good_events: int | None = None,
                 bad_events: int | None = None,
                 total_events: int | None = None) -> dict[str, Any]:
    """Budget math over measured events. Missing events → unresolved fields."""
    if total_events is None and good_events is not None \
            and bad_events is not None:
        total_events = good_events + bad_events
    if bad_events is None and good_events is not None \
            and total_events is not None:
        bad_events = total_events - good_events
    if total_events is None or total_events <= 0 or bad_events is None:
        return {"service": contract.service, "sli": contract.sli,
                "status": "unresolved",
                "unresolved": "platform.slo.unresolved",
                "missing": ["good_events|bad_events|total_events"]}
    allowed_total = contract.allowed_error_ratio * total_events
    consumed = bad_events
    remaining = allowed_total - consumed
    observed_ratio = bad_events / total_events
    burn = (observed_ratio / contract.allowed_error_ratio
            if contract.allowed_error_ratio > 0 else float("inf"))
    status = "exhausted" if remaining <= 0 else \
        ("at_risk" if burn >= 1.0 else "ok")
    # time-to-exhaustion at current burn (window remaining fraction)
    alerts = []
    for a in contract.burn_rate_alerts:
        if burn >= a.get("burn_rate", 0):
            alerts.append({"window": a["window"], "burn_rate": a["burn_rate"],
                           "firing": True})
    return {
        "service": contract.service, "sli": contract.sli,
        "target": contract.target, "window": contract.window,
        "status": status,
        "total_events": total_events, "bad_events": bad_events,
        "observed_error_ratio": round(observed_ratio, 6),
        "allowed_error_ratio": round(contract.allowed_error_ratio, 6),
        "burn_rate": round(burn, 4),
        "budget": {"total_allowed_events": round(allowed_total, 2),
                   "consumed_events": consumed,
                   "remaining_events": round(remaining, 2),
                   "remaining_fraction": round(
                       remaining / allowed_total, 4) if allowed_total else 0},
        "burn_alerts_firing": alerts,
        "fact_id": stable_id("PF-SLO", contract.service, contract.sli,
                             str(total_events), str(bad_events)),
    }


def multi_window_burn(contract: SloContract,
                      windows: dict[str, dict[str, int]]) -> dict[str, Any]:
    """§87 — multi-window burn rate (Google SRE alerting shape):
    {window: {good, bad}} per window; each window reports its own burn
    and only windows with data produce verdicts."""
    results = {}
    for w, ev in sorted(windows.items()):
        good, bad = ev.get("good_events"), ev.get("bad_events")
        if good is None or bad is None or (good + bad) <= 0:
            results[w] = {"status": "unresolved",
                          "missing": ["good_events|bad_events"]}
            continue
        total = good + bad
        ratio = bad / total
        burn = (ratio / contract.allowed_error_ratio
                if contract.allowed_error_ratio else float("inf"))
        results[w] = {"total_events": total, "burn_rate": round(burn, 4),
                      "status": "firing" if burn >= 1 else "ok"}
    firing = [w for w, r in results.items() if r.get("status") == "firing"]
    return {"service": contract.service, "sli": contract.sli,
            "windows": results, "firing_windows": firing,
            "note": "burn is per-window measured; unresolved windows are "
                    "not smoothed into a verdict"}
