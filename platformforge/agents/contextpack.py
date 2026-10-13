"""AgentContextPack — the bounded, measured payload an agent receives
(§109–116). Never the whole repository: task summary + relevant evidence
+ graph neighborhood + rules + knowledge refs + recent operations +
open questions, fitted to the run's budget class.

A pack is immutable once built. Follow-up agents receive
`previous_hash + delta` instead of a re-shipped context (§116) — the
shared evidence section is reused by reference, not re-sent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from platformforge.tokensave.estimate import estimate_tokens


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      default=str).encode()


@dataclass
class AgentContextPack:
    """§110/111 — everything an agent needs, nothing it doesn't."""
    task_summary: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    graph_neighborhood: dict[str, Any] = field(default_factory=dict)
    rules: list[dict[str, Any]] = field(default_factory=list)
    knowledge_refs: list[str] = field(default_factory=list)
    recent_operations: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    budget_class: str = "standard"

    def to_dict(self) -> dict[str, Any]:
        return {"task_summary": self.task_summary,
                "evidence": self.evidence,
                "graph_neighborhood": self.graph_neighborhood,
                "rules": self.rules,
                "knowledge_refs": self.knowledge_refs,
                "recent_operations": self.recent_operations,
                "open_questions": self.open_questions,
                "budget_class": self.budget_class}

    def serialize(self) -> bytes:
        return _canon(self.to_dict())

    @property
    def byte_size(self) -> int:
        return len(self.serialize())

    @property
    def estimated_tokens(self) -> int:
        return estimate_tokens(self.serialize())

    @property
    def content_hash(self) -> str:
        """Content-address — handoffs carry this, not the body (§73)."""
        return hashlib.sha256(self.serialize()).hexdigest()[:16]

    def fits(self, max_context_bytes: int) -> dict[str, Any]:
        """Measured bytes vs the run's context ceiling — no guessing."""
        return {"context_bytes": self.byte_size,
                "max_context_bytes": max_context_bytes,
                "fits": self.byte_size <= max_context_bytes,
                "estimated_tokens": self.estimated_tokens,
                "hash": self.content_hash}


def build_pack(task_summary: str, *, evidence=None, graph_neighborhood=None,
               rules=None, knowledge_refs=None, recent_operations=None,
               open_questions=None, budget_class: str = "standard",
               max_context_bytes: int | None = None,
               ) -> dict[str, Any]:
    """Assemble a pack, dropping *optional* sections first when it
    exceeds the byte ceiling. Evidence and open questions are
    essential — a pack that can't carry them reports `fits: False`
    rather than silently truncating."""
    optional_order = ["recent_operations", "knowledge_refs",
                      "graph_neighborhood", "rules"]
    pack = AgentContextPack(
        task_summary=task_summary, evidence=list(evidence or []),
        graph_neighborhood=dict(graph_neighborhood or {}),
        rules=list(rules or []),
        knowledge_refs=list(knowledge_refs or []),
        recent_operations=list(recent_operations or []),
        open_questions=list(open_questions or []),
        budget_class=budget_class)
    dropped = []
    if max_context_bytes:
        for section in optional_order:
            if pack.byte_size <= max_context_bytes:
                break
            cur = getattr(pack, section)
            setattr(pack, section, {} if isinstance(cur, dict) else [])
            dropped.append(section)
    fit = pack.fits(max_context_bytes or 2**63)
    return {"pack": pack.to_dict(), "hash": pack.content_hash,
            "context_bytes": pack.byte_size,
            "estimated_tokens": pack.estimated_tokens,
            "dropped_optional": dropped,
            "fits": fit["fits"],
            "note": ("essential content (evidence + open questions) exceeds "
                     "budget — narrow the task, don't truncate"
                     if not fit["fits"] else "ok")}


def delta_pack(previous_hash: str, previous: dict[str, Any],
               current: AgentContextPack) -> dict[str, Any]:
    """§116 — follow-up context: previous hash + only what changed."""
    prev = previous or {}
    cur = current.to_dict()
    delta: dict[str, Any] = {}
    for key, cur_v in cur.items():
        if key == "budget_class":
            continue
        prev_v = prev.get(key)
        if prev_v == cur_v:
            continue
        if isinstance(cur_v, list) and isinstance(prev_v, list):
            prev_set = {json.dumps(i, sort_keys=True, default=str)
                        for i in prev_v}
            delta[key] = [i for i in cur_v
                          if json.dumps(i, sort_keys=True, default=str)
                          not in prev_set]
        else:
            delta[key] = cur_v
    delta_bytes = len(_canon(delta))
    full_bytes = current.byte_size
    return {"base_hash": previous_hash, "delta": delta,
            "delta_bytes": delta_bytes, "full_bytes": full_bytes,
            "reused_bytes": max(0, full_bytes - delta_bytes),
            "savings_pct": round(100 * (1 - delta_bytes / full_bytes), 1)
            if full_bytes else 0.0}
