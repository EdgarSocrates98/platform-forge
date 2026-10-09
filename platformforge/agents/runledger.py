"""Agent run ledger — per-run economy accounting (§117).

Every agent invocation appends one row: model calls, context bytes,
output bytes, tool calls, agents used, fanout, duration, cache reuse.
Separate from TokenLedger (which tracks context engineering); this
tracks *agentic* spend so quality-per-token can be compared across
single-specialist vs coordinated strategies (§118–121).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentRunRow:
    run_id: str
    agent: str
    mode: str = "single-specialist"     # router mode for comparability
    model_calls: int = 0
    context_bytes: int = 0
    output_bytes: int = 0
    tool_calls: int = 0
    agents: int = 1
    fanout: int = 0
    duration_ms: float = 0.0
    cache_reuse_bytes: int = 0          # §115 shared-pack reuse
    delta_bytes: int = 0                # §116 delta-context savings
    token_basis: str = "unknown"        # observed|estimated|unknown
    transcript_ref: str | None = None
    ts: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.token_basis not in ("observed", "estimated", "unknown"):
            raise ValueError(f"bad token_basis {self.token_basis!r}")
        if self.token_basis == "observed" and not self.transcript_ref:
            raise ValueError(
                "observed token counts require transcript_ref")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentRunLedger:
    def __init__(self, root: str | Path):
        self.dir = Path(root) / ".platformforge" / "ledger"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "agent-runs.jsonl"

    def record(self, row: AgentRunRow) -> None:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(row.to_dict(), default=str) + "\n")

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines()
                if l.strip()]

    def report(self) -> dict[str, Any]:
        rows = self.rows()
        def tot(k): return sum(r.get(k) or 0 for r in rows)
        by_mode: dict[str, dict[str, Any]] = {}
        for r in rows:
            m = by_mode.setdefault(r.get("mode", "?"), {
                "runs": 0, "model_calls": 0, "context_bytes": 0,
                "tool_calls": 0, "duration_ms": 0.0,
                "cache_reuse_bytes": 0})
            m["runs"] += 1
            for k in ("model_calls", "context_bytes", "tool_calls",
                      "duration_ms", "cache_reuse_bytes"):
                m[k] += r.get(k) or 0
        return {"runs": len(rows), "agents_invoked": tot("agents"),
                "model_calls": tot("model_calls"),
                "context_bytes": tot("context_bytes"),
                "output_bytes": tot("output_bytes"),
                "tool_calls": tot("tool_calls"),
                "cache_reuse_bytes": tot("cache_reuse_bytes"),
                "delta_savings_bytes": tot("delta_bytes"),
                "by_mode": by_mode}
