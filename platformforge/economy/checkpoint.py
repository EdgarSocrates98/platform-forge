"""EconomyCheckpoint (§76–80) — run state persisted so a stopped run
resumes with its spend intact.

Invariants: resume never resets spend (§78/§290 north star); resume
revalidates artifact hashes, knowledge freshness, observation freshness,
policy version and operation state (§79); a profile cannot downgrade on
resume — `deep` never becomes `cheap` because the run paused (§80).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "platformforge/checkpoint/v1"

PROFILE_ORDER = {"offline": 0, "economy": 1, "balanced": 2,
                 "deep": 3, "strict": 4}


@dataclass
class EconomyCheckpoint:
    """§77 — canonical fields."""
    schema: str = SCHEMA
    run_id: str = ""
    spent_budget: dict[str, float] = field(default_factory=dict)
    remaining_budget: dict[str, float] = field(default_factory=dict)
    context_refs: list[str] = field(default_factory=list)
    cache_refs: list[str] = field(default_factory=list)
    agent_state: dict[str, Any] = field(default_factory=dict)
    routing_profile: str = "balanced"
    risk_profile: str = "low"
    tool_spend: dict[str, float] = field(default_factory=dict)
    provider_spend: dict[str, float] = field(default_factory=dict)
    deps: dict[str, str] = field(default_factory=dict)
    # artifact_hash / knowledge_hash / policy_version — revalidated §79
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CheckpointStore:
    """`.platformforge/checkpoints/<run_id>.json`."""

    def __init__(self, root: str | Path):
        self.dir = Path(root) / ".platformforge" / "checkpoints"
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, cp: EconomyCheckpoint) -> str:
        path = self.dir / f"{cp.run_id}.json"
        path.write_text(json.dumps(cp.to_dict(), sort_keys=True,
                                   default=str, indent=1))
        return str(path)

    def load(self, run_id: str) -> EconomyCheckpoint | None:
        p = self.dir / f"{run_id}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        return EconomyCheckpoint(**{
            k: v for k, v in d.items()
            if k in EconomyCheckpoint.__dataclass_fields__})

    def list(self) -> list[str]:
        return sorted(p.stem for p in self.dir.glob("*.json"))

    def resume(self, run_id: str, current_deps: dict[str, str],
               requested_profile: str = ""
               ) -> dict[str, Any]:
        """§78–80 — resume with spend intact; revalidate the world;
        refuse profile downgrade."""
        cp = self.load(run_id)
        if cp is None:
            return {"refusal": "PF-CHECKPOINT-MISSING",
                    "reason": f"no checkpoint for {run_id}",
                    "unlock": "start a fresh run — spend unknown"}

        # §79 — revalidation: every dep that drifted is reported, and a
        # stale dep means the resume must re-verify, not silently reuse.
        stale = {k: {"was": v, "now": current_deps.get(k, "")}
                 for k, v in cp.deps.items()
                 if current_deps.get(k, "") != v}
        needs_revalidation = bool(stale)

        # §80 — profile cannot downgrade on resume.
        eff_profile = requested_profile or cp.routing_profile
        if PROFILE_ORDER.get(eff_profile, -1) < \
                PROFILE_ORDER.get(cp.routing_profile, 0):
            return {"refusal": "PF-CHECKPOINT-DOWNGRADE",
                    "reason": f"cannot resume {cp.routing_profile!r} run "
                              f"as {eff_profile!r} — profile cannot "
                              "downgrade on resume (§80)",
                    "unlock": "resume at the stored profile or higher"}

        return {"run_id": run_id, "resumed": True,
                "profile": eff_profile,
                "spent_budget": cp.spent_budget,      # §78 — carries over
                "remaining_budget": cp.remaining_budget,
                "context_refs": cp.context_refs,
                "cache_refs": cp.cache_refs,
                "tool_spend": cp.tool_spend,
                "provider_spend": cp.provider_spend,
                "risk_profile": cp.risk_profile,
                "needs_revalidation": needs_revalidation,
                "stale_deps": stale,
                "note": ("spend preserved; re-verify sections whose deps "
                         "changed" if needs_revalidation else
                         "spend preserved; all deps fresh")}
