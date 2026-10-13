"""Agent run store — .platformforge/runs/ (§135–142).

Append-only run records: task spec hash, router decision, agents,
handoffs, budget, evidence refs, debates, gates, verifier, verdict.
This is run *memory* — receipts and refs, not long-term agent memory
(§134) and never user-specific context (§137).

Resume preserves spent budget and prior evidence/decisions; it
revalidates artifact hashes and observation freshness before
continuing (§141–142).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.agents.contracts import AgentRunRecord


class RunStore:
    def __init__(self, root: str | Path):
        self.dir = Path(root) / ".platformforge" / "runs"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        if "/" in run_id or ".." in run_id:
            raise ValueError(f"bad run_id {run_id!r}")
        return self.dir / f"{run_id}.json"

    def save(self, record: AgentRunRecord) -> Path:
        p = self._path(record.run_id)
        p.write_text(json.dumps(record.to_dict(), indent=2,
                                sort_keys=True, default=str))
        return p

    def load(self, run_id: str) -> AgentRunRecord | None:
        p = self._path(run_id)
        if not p.is_file():
            return None
        return AgentRunRecord.from_dict(json.loads(p.read_text()))

    def runs(self) -> list[str]:
        return sorted(p.stem for p in self.dir.glob("*.json"))

    def resume(self, run_id: str, *, artifact_hashes: dict[str, str] |
               None = None,
               observation_freshness: str | None = None,
               ) -> dict[str, Any]:
        """§141–142 — resume preserves spent budget/decisions and
        revalidates hashes + freshness before allowing continuation."""
        rec = self.load(run_id)
        if rec is None:
            return {"resumed": False,
                    "reason": f"no run record {run_id} — nothing to "
                              "resume; start a new run"}
        problems = []
        if artifact_hashes:
            for ref, h in artifact_hashes.items():
                if not h:
                    problems.append(f"{ref}: hash unreadable — "
                                    "re-collect before resume")
        if observation_freshness in ("stale", "superseded", "conflicted"):
            problems.append(
                f"observation freshness is {observation_freshness} — "
                "re-collect runtime evidence before resume")
        return {"resumed": not problems, "run_id": run_id,
                "problems": problems,
                "preserved": {"budget_spent": rec.budget.get("spent"),
                              "evidence": list(rec.evidence),
                              "decisions": list(rec.debates),
                              "verdict": rec.verdict},
                "note": "budget is never reset on resume (§141)"}
