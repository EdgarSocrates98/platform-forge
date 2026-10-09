"""Observation Economy (cycle §133–146) — budgets are refusals, never
silent sampling (§136). ProviderCallLedger is the measured record that
feeds Economy V3 (§140); monetary cost is only reported with trusted
pricing input (§141 — never invented)."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ObservationBudget:
    """§134 — user-tunable ceilings enforced inside collectors."""
    max_objects: int = 0        # 0 = unlimited
    max_events: int = 0
    max_bytes: int = 0
    max_api_calls: int = 0
    max_duration_s: float = 0.0
    max_clusters: int = 0
    max_accounts: int = 0
    max_regions: int = 0
    max_pages_per_call: int = 200

    def check(self, ledger: ProviderCallLedger) -> str:
        """Return the violated budget key, or "" when within limits."""
        if self.max_api_calls and ledger.api_calls >= self.max_api_calls:
            return "max_api_calls"
        if self.max_objects and ledger.objects >= self.max_objects:
            return "max_objects"
        if self.max_bytes and ledger.bytes >= self.max_bytes:
            return "max_bytes"
        if self.max_events and ledger.events >= self.max_events:
            return "max_events"
        if self.max_pages_per_call and \
                ledger.pages_since_reset >= self.max_pages_per_call:
            return "max_pages_per_call"
        if self.max_duration_s and \
                (time.monotonic() - ledger.started_monotonic) >= self.max_duration_s:
            return "max_duration_s"
        return ""


@dataclass
class ProviderCallLedger:
    """§140 — measured record of provider usage for one collection."""
    collector: str
    started_monotonic: float = field(default_factory=time.monotonic)
    started_at: str = ""
    api_calls: int = 0
    pages: int = 0
    objects: int = 0
    bytes: int = 0
    events: int = 0
    retries: int = 0
    throttles: int = 0
    cache_hits: int = 0
    calls_by_service: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    pages_since_reset: int = 0

    def record_call(self, service: str = "", *, pages: int = 0,
                    objects: int = 0, nbytes: int = 0,
                    retries: int = 0, throttled: bool = False,
                    cache_hit: bool = False) -> None:
        self.api_calls += 1
        self.pages += pages
        self.pages_since_reset += pages
        self.objects += objects
        self.bytes += nbytes
        self.retries += retries
        if throttled:
            self.throttles += 1
        if cache_hit:
            self.cache_hits += 1
        if service:
            self.calls_by_service[service] = \
                self.calls_by_service.get(service, 0) + 1

    def record_event(self, n: int = 1, nbytes: int = 0) -> None:
        self.events += n
        self.bytes += nbytes

    def duration_s(self) -> float:
        return time.monotonic() - self.started_monotonic

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("started_monotonic", None)
        d["duration_s"] = round(self.duration_s(), 3)
        return d
