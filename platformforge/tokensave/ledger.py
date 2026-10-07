"""Token ledger — append-only JSONL accounting per run.

Records context requested/delivered/reused/skipped/compressed, provider tokens
when observed, estimates when estimated, cache hits/misses. Three honesty
states: observed | estimated | unknown.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LedgerEntry:
    """§29 — v2 fields: requested/candidate/selected/delivered/reused/
    cached/compressed/skipped + essential/optional split. Provider-side
    tokens stay None unless a host transcript observes them."""
    operation: str
    context_requested: int = 0      # estimated tokens requested
    context_candidate: int = 0      # ranked candidates before budget
    context_selected: int = 0       # selected after ranking
    context_delivered: int = 0
    context_reused: int = 0         # served from cache/content-address
    context_cached: int = 0
    context_skipped: int = 0
    context_compressed: int = 0
    essential_tokens: int = 0       # evidence that must not be dropped
    optional_tokens: int = 0
    input_tokens: int | None = None   # observed (provider transcript)
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: float | None = None
    input_tokens_est: int | None = None  # estimated
    output_tokens_est: int | None = None
    cache_hits: int = 0
    cache_misses: int = 0
    # §42 — deterministic vs model split. Deterministic bytes are the local
    # working set (never billed as model spend); model_context_* counts only
    # the payload a model/agent receives. Provider counts stay None when no
    # transcript observed them (`unknown`).
    deterministic_input_bytes: int = 0
    deterministic_fact_count: int = 0
    model_context_bytes: int = 0
    model_context_tokens: int | None = None
    model_output_tokens: int | None = None
    cache_tokens: int = 0
    latency_ms: float = 0.0
    token_basis: str = "unknown"   # observed | estimated | unknown
    ts: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TokenLedger:
    def __init__(self, root: str | Path):
        self.dir = Path(root) / ".platformforge" / "ledger"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "tokens.jsonl"

    def record(self, entry: LedgerEntry) -> None:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(entry.to_dict(), default=str) + "\n")

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def report(self) -> dict[str, Any]:
        ents = self.entries()
        tot = lambda k: sum(e.get(k) or 0 for e in ents)
        hits, misses = tot("cache_hits"), tot("cache_misses")
        return {
            "operations": len(ents),
            "context_requested": tot("context_requested"),
            "context_delivered": tot("context_delivered"),
            "context_reused": tot("context_reused"),
            "context_skipped": tot("context_skipped"),
            "context_compressed": tot("context_compressed"),
            "cache_hit_ratio": (hits / (hits + misses)) if (hits + misses) else None,
            "input_tokens_observed": tot("input_tokens"),
            "output_tokens_observed": tot("output_tokens"),
            "input_tokens_estimated": tot("input_tokens_est"),
            "output_tokens_estimated": tot("output_tokens_est"),
            "deterministic_input_bytes": tot("deterministic_input_bytes"),
            "deterministic_fact_count": tot("deterministic_fact_count"),
            "model_context_bytes": tot("model_context_bytes"),
            "cache_tokens": tot("cache_tokens"),
            "basis_counts": {
                b: sum(1 for e in ents if e.get("token_basis") == b)
                for b in ("observed", "estimated", "unknown")
            },
        }
