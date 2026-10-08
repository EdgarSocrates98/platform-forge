"""Cycle 5 Phase C — HistoryEngine (§36–48).

Unifies historical sources into one *normalized event stream* — never
mutating the source stores (§298). Windows: 24h/7d/30d/90d/custom
(§39). Patterns are deterministic counts with explicit support +
confidence caps from sample size (§44, §232–233); correlation is
reported, never causality (§41).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from platformforge.analytics.models import HistoricalPattern, confidence_for_support
from platformforge.live.models import parse_ts

WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7),
           "30d": timedelta(days=30), "90d": timedelta(days=90)}

EVENT_KINDS = ("observation", "operation", "drift", "incident",
               "deployment", "policy_decision", "approval", "rollback",
               "golden_path_request", "cost", "slo", "remediation")


@dataclass
class HistoryEvent:
    """Normalized event — `source_ref` points back to the store record."""
    kind: str
    ts: datetime
    subject: str = ""               # resource/service/policy id
    outcome: str = ""
    source: str = ""                # store name
    source_ref: str = ""            # entry hash / event id
    attrs: dict[str, Any] = field(default_factory=dict)


class HistoryEngine:
    """Aggregates normalized events from pluggable sources.

    Sources register as callables returning `HistoryEvent`s; built-in
    adapters cover Observation/Operation stores, drift journal,
    incidents and golden-path requests (§37).
    """

    def __init__(self):
        self._sources: list[tuple[str, Any]] = []
        self._events: list[HistoryEvent] = []

    def register(self, name: str, fn) -> None:
        self._sources.append((name, fn))

    # -- ingest adapters (§37) --------------------------------------
    def ingest_operations(self, store) -> int:
        """OperationStore ledgers → operation/rollback/approval events."""
        n = 0
        for op_id in store.list_operations():
            try:
                led = store.load_ledger(op_id)
            except (OSError, ValueError, KeyError):
                continue
            for ent in led.entries:
                kind = {"step.completed": "operation",
                        "rollback.completed": "rollback",
                        "rollback.failed": "rollback",
                        "created": "operation"}.get(ent.event)
                if kind is None:
                    kind = "operation" if ent.event.startswith(
                        "step.") else None
                if kind is None:
                    continue
                self._events.append(HistoryEvent(
                    kind=kind, ts=parse_ts(ent.ts) or
                    datetime.now(timezone.utc),
                    subject=op_id, outcome=str(ent.data.get("outcome",
                                                            ent.event)),
                    source="operation_store", source_ref=ent.hash,
                    attrs={"event": ent.event, **ent.data}))
                n += 1
        return n

    def ingest_events(self, kind: str, events: list[dict[str, Any]],
                      source: str) -> int:
        """Generic adapter — drift journal, incidents, deploys, SLO…"""
        n = 0
        for ev in events:
            ts = parse_ts(str(ev.get("ts") or ev.get("observed_at") or ""))
            if ts is None:
                continue
            self._events.append(HistoryEvent(
                kind=kind, ts=ts,
                subject=str(ev.get("subject") or ev.get("resource") or ""),
                outcome=str(ev.get("outcome") or ev.get("type") or ""),
                source=source,
                source_ref=str(ev.get("event_id") or ev.get("hash") or ""),
                attrs=ev))
            n += 1
        return n

    # -- queries ----------------------------------------------------
    def events(self, window: str = "30d", *,
               kind: str | None = None, subject: str | None = None,
               now: datetime | None = None,
               since: datetime | None = None,
               until: datetime | None = None) -> list[HistoryEvent]:
        """§39/§299 — strict window filtering."""
        now = now or datetime.now(timezone.utc)
        if since is None:
            since = now - WINDOWS.get(window, WINDOWS["30d"])
        until = until or now
        return [e for e in self._events
                if since <= e.ts <= until
                and (kind is None or e.kind == kind)
                and (subject is None or e.subject == subject)]

    def count_by(self, window: str = "30d", key: str = "kind",
                 **kw) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.events(window, **kw):
            k = getattr(e, key, "") or str(e.attrs.get(key, ""))
            out[k] = out.get(k, 0) + 1
        return out

    # -- patterns (§42–44) ------------------------------------------
    def patterns(self, window: str = "90d", *,
                 group: str = "subject",
                 min_support: int = 2) -> list[HistoricalPattern]:
        """Group (subject, kind, outcome) triples; report support."""
        groups: dict[tuple, list[HistoryEvent]] = {}
        for e in self.events(window):
            k = (getattr(e, group, e.subject), e.kind, e.outcome)
            groups.setdefault(k, []).append(e)
        out = []
        for (subj, kind, outcome), evs in sorted(groups.items()):
            if len(evs) < min_support:
                continue
            evs.sort(key=lambda e: e.ts)
            out.append(HistoricalPattern(
                pattern_id=f"{kind}:{subj}:{outcome}",
                window=window, events=[e.source_ref or e.kind
                                       for e in evs],
                support=len(evs), sample_size=len(evs),
                confidence=confidence_for_support(len(evs)),
                evidence=[e.source_ref for e in evs if e.source_ref],
                scope={"subject": subj},
                hypothesis="",
                limitations=["correlation is not causality",
                             "deterministic count only"]))
        return out

    def before(self, event_kind: str, within: str = "24h",
               window: str = "90d") -> list[HistoricalPattern]:
        """§40 — 'what repeatedly changed before incidents?': for each
        `event_kind` occurrence, count preceding event kinds within
        `within`. Support count only — never a causal claim (§41)."""
        incidents = self.events(window, kind=event_kind)
        delta = WINDOWS.get(within, WINDOWS["24h"])
        counts: dict[str, int] = {}
        for inc in incidents:
            for e in self._events:
                if e is inc:
                    continue
                if inc.ts - delta <= e.ts < inc.ts:
                    counts[e.kind] = counts.get(e.kind, 0) + 1
        return [HistoricalPattern(
            pattern_id=f"precedes:{k}->{event_kind}",
            window=window, support=n, sample_size=n,
            confidence=confidence_for_support(n),
            scope={"preceding_kind": k, "following": event_kind},
            events=[k], evidence=[],
            hypothesis=f"{k} precedes {event_kind} "
                       f"{n}x in {within}",
            limitations=["temporal proximity is not causality",
                         "sample size limits confidence"])
            for k, n in sorted(counts.items(), key=lambda kv: -kv[1])]

    # -- operation/runbook stats (§46–48) ---------------------------
    def operation_stats(self, window: str = "90d") -> dict[str, Any]:
        ops = self.events(window, kind="operation")
        rbs = self.events(window, kind="rollback")
        out: dict[str, Any] = {"operations": len(ops),
                               "rollbacks": len(rbs)}
        by_action: dict[str, dict[str, int]] = {}
        for e in ops:
            action = str(e.attrs.get("action") or
                         e.attrs.get("step_id") or "unknown")
            d = by_action.setdefault(action, {"count": 0, "failed": 0})
            d["count"] += 1
            if "fail" in e.outcome:
                d["failed"] += 1
        out["by_action"] = by_action
        out["sample_size"] = len(ops)
        out["confidence"] = confidence_for_support(len(ops))
        return out

    def runbook_effectiveness(self, window: str = "90d"
                              ) -> dict[str, dict[str, Any]]:
        """§47–48 — decomposed: success/coverage/evidence/freshness/
        rollback rate — never an opaque score."""
        out: dict[str, dict[str, Any]] = {}
        for e in self.events(window, kind="operation"):
            rb = str(e.attrs.get("runbook") or e.attrs.get("runbook_id")
                     or "")
            if not rb:
                continue
            d = out.setdefault(rb, {"selected": 0, "converged": 0,
                                    "failed": 0, "rolled_back": 0,
                                    "manual_intervention": 0})
            d["selected"] += 1
            if e.outcome in ("converged", "step.completed"):
                d["converged"] += 1
            elif "fail" in e.outcome:
                d["failed"] += 1
        for e in self.events(window, kind="rollback"):
            rb = str(e.attrs.get("runbook") or "")
            if rb in out:
                out[rb]["rolled_back"] += 1
        for rb, d in out.items():
            sel = d["selected"] or 1
            d["success_rate"] = round(d["converged"] / sel, 3)
            d["rollback_rate"] = round(d["rolled_back"] / sel, 3)
            d["sample_size"] = d["selected"]
            d["confidence"] = confidence_for_support(d["selected"])
        return out


def engine_from_events(events: list[dict[str, Any]], kind: str,
                       source: str = "fixture") -> HistoryEngine:
    """Test/lab helper."""
    eng = HistoryEngine()
    eng.ingest_events(kind, events, source)
    return eng
