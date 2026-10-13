"""EconomyWasteDetector (§112–116) — reads the ledgers and reports waste
as findings. Recommendations only — never auto-fixes routing (§115)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

WASTE_TYPES = ("duplicate_context", "duplicate_tool_call",
               "repeated_graph_build", "unused_agent", "overrouting",
               "repeated_provider_call", "unused_expansion",
               "cache_bypass", "oversized_context",
               "unnecessary_verification")


@dataclass
class WasteFinding:
    """§114 — the output shape."""
    waste_type: str
    estimated_impact: str            # low|medium|high — never fake bytes
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: str = "medium"
    recommended_fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EconomyWasteDetector:
    """Scans `.platformforge/ledger/*.jsonl` and reports waste."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _read(self, name: str) -> list[dict[str, Any]]:
        import json
        p = self.root / ".platformforge" / "ledger" / name
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text().splitlines()
                if l.strip()]

    def detect(self) -> dict[str, Any]:
        findings: list[WasteFinding] = []

        tokens = self._read("tokens.jsonl")
        econ = self._read("economy.jsonl")
        runs = self._read("agent-runs.jsonl")

        # duplicate tool call: same tool+input_bytes hash row repeated
        tool_rows = [e for e in econ if e.get("entry_type") == "tool"]
        seen_tool: dict[str, int] = {}
        for e in tool_rows:
            k = f"{e.get('tool')}:{e.get('input_bytes')}:{e.get('run_id')}"
            seen_tool[k] = seen_tool.get(k, 0) + 1
        dups = {k: n for k, n in seen_tool.items() if n > 1}
        if dups:
            findings.append(WasteFinding(
                "duplicate_tool_call", "medium",
                {"calls": dups}, "high",
                "route through the cache layer or dedup identical calls"))

        # repeated provider call
        prov = [e for e in econ if e.get("entry_type") == "provider"]
        by_coll: dict[str, int] = {}
        for e in prov:
            k = f"{e.get('collector')}:{e.get('service')}"
            by_coll[k] = by_coll.get(k, 0) + e.get("api_calls", 0)
        if prov and all(e.get("cache_hits", 0) == 0 for e in prov) \
                and any(n > 50 for n in by_coll.values()):
            findings.append(WasteFinding(
                "repeated_provider_call", "high",
                {"calls_by_service": by_coll}, "medium",
                "enable provider call caching or widen observation reuse"))

        # cache bypass: token rows that delivered but never reused
        delivered = sum(e.get("context_delivered", 0) for e in tokens)
        reused = sum(e.get("context_reused", 0) for e in tokens)
        if len(tokens) >= 5 and delivered and reused == 0:
            findings.append(WasteFinding(
                "cache_bypass", "high",
                {"operations": len(tokens), "delivered": delivered,
                 "reused": 0}, "medium",
                "route context builds through CacheStore"))

        # overrouting: runs with fanout>1 for deterministic task types
        over = [r for r in runs
                if r.get("mode") in ("multi-specialist", "coordinated")
                and r.get("extra", {}).get("task_type") in
                ("lint", "inventory", "policy", "diff")]
        if over:
            findings.append(WasteFinding(
                "overrouting", "medium",
                {"runs": [r.get("run_id") for r in over]}, "medium",
                "simple tasks route deterministic/single-specialist "
                "(§123)"))

        # oversized context: delivered > 32k est tokens repeatedly
        big = [e for e in tokens
               if (e.get("context_delivered") or 0) > 32000]
        if len(big) >= 3:
            findings.append(WasteFinding(
                "oversized_context", "medium",
                {"deliveries_over_32k": len(big)}, "medium",
                "tighten context budget or use delta context (§74)"))

        # unused expansion: tool expanded_bytes>0 but output small
        unused_exp = [e for e in tool_rows
                      if e.get("expanded_bytes", 0) > 0
                      and e.get("output_bytes", 0) < 200]
        if unused_exp:
            findings.append(WasteFinding(
                "unused_expansion", "low",
                {"entries": len(unused_exp)}, "low",
                "expand-on-demand may have fetched unneeded detail"))

        return {"waste_findings": [f.to_dict() for f in findings],
                "scanned": {"token_rows": len(tokens),
                            "economy_rows": len(econ),
                            "agent_runs": len(runs)},
                "note": "recommendations only — routing is never "
                        "auto-modified (§115)"}
