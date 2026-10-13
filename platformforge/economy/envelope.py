"""Context envelopes — the measured payload IS the consumed payload.

Cycle 2.1 §34–50: the bytes a judge/model actually receives are the bytes
the estimator counts. `serialize()` is the single canonical serializer for
both the full and the optimized context, so `measured == evaluated` by
construction. Deterministic working sets (facts the local engine reads)
are `kind="deterministic"` and are never counted as model tokens unless
someone serializes them into a `kind="model"` envelope.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from platformforge.tokensave.estimate import estimate_tokens


@dataclass
class ContextEnvelope:
    """Serializable context payload.

    kind: "model" (would be sent to a model/agent) | "deterministic"
          (local engine working set — not token spend).
    """
    kind: str = "model"
    files: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    graph: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "files": self.files, "facts": self.facts,
                "findings": self.findings, "rules": self.rules,
                "graph": self.graph, "metadata": self.metadata}

    def serialize(self) -> bytes:
        """Canonical wire format — one serializer for every envelope kind."""
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(",", ":"), default=str).encode()

    @property
    def byte_size(self) -> int:
        return len(self.serialize())

    @property
    def estimated_tokens(self) -> int:
        """Local estimate — labeled `estimated`, never `observed`."""
        return estimate_tokens(self.serialize())

    def ledger_fields(self) -> dict[str, Any]:
        """Fields for TokenLedger rows (§42)."""
        if self.kind == "deterministic":
            return {"deterministic_input_bytes": self.byte_size,
                    "deterministic_fact_count": len(self.facts)}
        return {"model_context_bytes": self.byte_size,
                "model_context_tokens": self.estimated_tokens,
                "deterministic_fact_count": 0}
