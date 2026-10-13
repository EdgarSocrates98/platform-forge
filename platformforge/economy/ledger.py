"""Unified economy accounting (§25–34).

Three ledgers already existed in silos: TokenLedger (context tokens),
ProviderCallLedger (live calls), AgentRunLedger (agentic spend). This
module adds the missing fourth (ToolUsageEntry, §31) and the unified
view (§34) that reads all of them — one `economy report` that answers
token + tool + provider + agent spend together.

Honesty invariants (§27–28): observed and estimated are NEVER summed as
equivalents; `unknown` stays unknown. An `observed` row still requires a
`transcript_ref` — unfalsifiable numbers are fabricated.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ECONOMY_SCHEMA = "platformforge/economy-entry/v2"
TOOL_SCHEMA = "platformforge/tool-usage/v1"
PROVIDER_SCHEMA = "platformforge/provider-call/v1"


@dataclass
class TokenAccounting:
    """§26 — per-dimension accounting with basis separation (§27).
    observed and estimated are distinct fields forever."""
    observed_input_tokens: int = 0
    observed_output_tokens: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    unknown_entries: int = 0
    basis: str = "unknown"           # observed|estimated|unknown|mixed
    provider: str = ""
    model: str = ""
    agent: str = ""
    task: str = ""
    phase: str = ""

    def basis_state(self) -> str:
        obs = self.observed_input_tokens + self.observed_output_tokens
        est = self.estimated_input_tokens + self.estimated_output_tokens
        if obs and est:
            return "mixed"           # reported split, never summed
        if obs:
            return "observed"
        if est:
            return "estimated"
        return "unknown"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["basis"] = self.basis_state()
        d["total_observed"] = self.observed_input_tokens + \
            self.observed_output_tokens
        d["total_estimated"] = self.estimated_input_tokens + \
            self.estimated_output_tokens
        return d


@dataclass
class ToolUsageEntry:
    """§31–32 — tool call economy: cost is bytes + calls + duration,
    not just calls."""
    tool: str
    calls: int = 1
    input_bytes: int = 0
    output_bytes: int = 0
    expanded_bytes: int = 0          # §109 — expand-on-demand cost
    duration_ms: float = 0.0
    cache_hit: bool = False
    run_id: str = ""
    task: str = ""
    agent: str = ""
    phase: str = ""
    schema: str = TOOL_SCHEMA
    entry_type: str = "tool"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderCallEntry:
    """§33 — canonical provider-call row, foldable from
    `live/budget.ProviderCallLedger.to_dict()`."""
    provider: str                    # e.g. aws|datadog|github
    service: str = ""
    api_calls: int = 0
    pages: int = 0
    objects: int = 0
    nbytes: int = 0
    retries: int = 0
    throttles: int = 0
    cache_hits: int = 0
    duration_s: float = 0.0
    cost_usd: float | None = None    # None = unresolved (§86/§293)
    pricing_ref: str = ""
    run_id: str = ""
    collector: str = ""
    schema: str = PROVIDER_SCHEMA
    entry_type: str = "provider"
    ts: float = field(default_factory=time.time)

    @classmethod
    def from_live_ledger(cls, ledger_dict: dict[str, Any],
                         provider: str = "", run_id: str = ""
                         ) -> ProviderCallEntry:
        """§33 — unify live/budget.py output into the economy ledger."""
        return cls(
            provider=provider or "unknown",
            service=", ".join(sorted(ledger_dict.get(
                "calls_by_service", {}).keys())),
            api_calls=ledger_dict.get("api_calls", 0),
            pages=ledger_dict.get("pages", 0),
            objects=ledger_dict.get("objects", 0),
            nbytes=ledger_dict.get("bytes", 0),
            retries=ledger_dict.get("retries", 0),
            throttles=ledger_dict.get("throttles", 0),
            cache_hits=ledger_dict.get("cache_hits", 0),
            duration_s=ledger_dict.get("duration_s", 0.0),
            run_id=run_id,
            collector=ledger_dict.get("collector", ""))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EconomyLedger:
    """Append-only economy ledger — `.platformforge/ledger/economy.jsonl`.

    TokenLedger rows (context engineering) keep their own file; rows here
    carry tool/provider/economy-scoped spend. The unified view joins all
    of them on read (§34)."""

    def __init__(self, root: str | Path):
        self.dir = Path(root) / ".platformforge" / "ledger"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "economy.jsonl"

    def record(self, entry: ToolUsageEntry | ProviderCallEntry
               | dict[str, Any]) -> None:
        d = entry.to_dict() if hasattr(entry, "to_dict") else dict(entry)
        d.setdefault("schema", ECONOMY_SCHEMA)
        with open(self.path, "a") as fh:
            fh.write(json.dumps(d, sort_keys=True, default=str) + "\n")

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in
                self.path.read_text().splitlines() if line.strip()]

    def by_type(self, entry_type: str) -> list[dict[str, Any]]:
        return [e for e in self.entries()
                if e.get("entry_type") == entry_type]


def unified_view(root: str | Path) -> dict[str, Any]:
    """§34 — ONE ECONOMY VIEW: token + tool + provider + agent spend,
    observed/estimated/unknown separated throughout."""
    root = Path(root)
    out: dict[str, Any] = {"basis_counts": {"observed": 0, "estimated": 0,
                                            "unknown": 0}}

    tok_path = root / ".platformforge" / "ledger" / "tokens.jsonl"
    toks = ([json.loads(l) for l in tok_path.read_text().splitlines()
             if l.strip()] if tok_path.exists() else [])
    acc = TokenAccounting()
    for e in toks:
        acc.observed_input_tokens += e.get("input_tokens") or 0
        acc.observed_output_tokens += e.get("output_tokens") or 0
        acc.observed_output_tokens += e.get("reasoning_tokens") or 0
        acc.estimated_input_tokens += e.get("input_tokens_est") or 0
        acc.estimated_output_tokens += e.get("output_tokens_est") or 0
        if e.get("token_basis") == "unknown":
            acc.unknown_entries += 1
    out["tokens"] = acc.to_dict()
    out["tokens"]["operations"] = len(toks)
    out["tokens"]["context_delivered"] = sum(
        e.get("context_delivered") or 0 for e in toks)
    out["tokens"]["context_reused"] = sum(
        e.get("context_reused") or 0 for e in toks)

    econ = EconomyLedger(root).entries()
    tools = [e for e in econ if e.get("entry_type") == "tool"]
    prov = [e for e in econ if e.get("entry_type") == "provider"]
    out["tools"] = {
        "calls": sum(e.get("calls", 0) for e in tools),
        "input_bytes": sum(e.get("input_bytes", 0) for e in tools),
        "output_bytes": sum(e.get("output_bytes", 0) for e in tools),
        "expanded_bytes": sum(e.get("expanded_bytes", 0) for e in tools),
        "cache_hits": sum(1 for e in tools if e.get("cache_hit")),
        "by_tool": {t: sum(e.get("calls", 0) for e in tools
                           if e.get("tool") == t)
                    for t in sorted({e.get("tool", "") for e in tools})},
    }
    out["provider_calls"] = {
        "api_calls": sum(e.get("api_calls", 0) for e in prov),
        "bytes": sum(e.get("nbytes", 0) for e in prov),
        "cache_hits": sum(e.get("cache_hits", 0) for e in prov),
        "cost_usd": (None if any(e.get("cost_usd") is None for e in prov)
                     else sum(e["cost_usd"] for e in prov))
        if prov else None,
        "cost_basis": ("unresolved" if prov and any(
            e.get("cost_usd") is None for e in prov)
            else ("declared" if prov else "none")),
    }

    run_path = root / ".platformforge" / "ledger" / "agent-runs.jsonl"
    runs = ([json.loads(l) for l in run_path.read_text().splitlines()
             if l.strip()] if run_path.exists() else [])
    out["agents"] = {
        "runs": len(runs),
        "model_calls": sum(e.get("model_calls", 0) for e in runs),
        "context_bytes": sum(e.get("context_bytes", 0) for e in runs),
        "output_bytes": sum(e.get("output_bytes", 0) for e in runs),
        "tool_calls": sum(e.get("tool_calls", 0) for e in runs),
        "fanout": sum(e.get("fanout", 0) for e in runs),
        "cache_reuse_bytes": sum(e.get("cache_reuse_bytes", 0)
                                 for e in runs),
        "delta_bytes": sum(e.get("delta_bytes", 0) for e in runs),
    }
    for e in list(toks) + list(runs):
        b = e.get("token_basis", "unknown")
        if b in out["basis_counts"]:
            out["basis_counts"][b] += 1
    return out
