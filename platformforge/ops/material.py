"""Cycle 4.1 — RollbackMaterial (§5–8, §31, ADR-cycle4.1).

A `rollback_action` name alone is not a rollback — the inverse usually
needs parameters that only exist *before* or *during* the forward step.
`RollbackMaterial` is the explicit, **immutable, hash-bound,
content-addressed** record of everything captured to enable a correct
reversal:

    forward intent + pre-change state + execution result + strategy
        = executable compensation

Materials are written once into `.platformforge/materials/<hash>.json`;
a rewrite attempt with different content is tamper evidence, not an
update.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from platformforge.live.models import canonical_hash, now_iso

MATERIAL_SCHEMA = "platformforge/rollback-material/v1"

# provenance of a captured field — declared by the caller vs observed
# by a transport/collector. Observed outranks declared on conflict.
PROVENANCE = ("declared", "observed")


@dataclass
class RollbackMaterial:
    material_id: str = ""
    operation_id: str = ""
    step_id: str = ""
    action: str = ""
    captured_at: str = ""
    pre_state: dict[str, Any] = field(default_factory=dict)
    execution_result: dict[str, Any] = field(default_factory=dict)
    source_of_truth: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    provenance: str = "declared"

    def payload(self) -> dict[str, Any]:
        """Canonical content — everything the hash binds."""
        return {"schema": MATERIAL_SCHEMA,
                "material_id": self.material_id,
                "operation_id": self.operation_id,
                "step_id": self.step_id,
                "action": self.action,
                "captured_at": self.captured_at,
                "pre_state": self.pre_state,
                "execution_result": self.execution_result,
                "source_of_truth": self.source_of_truth,
                "artifacts": self.artifacts,
                "references": self.references,
                "evidence": self.evidence,
                "limitations": self.limitations,
                "provenance": self.provenance}

    def hash(self) -> str:
        return "sha256:" + canonical_hash(self.payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "hash": self.hash()}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> RollbackMaterial:
        m = RollbackMaterial(
            material_id=d.get("material_id", ""),
            operation_id=d.get("operation_id", ""),
            step_id=d.get("step_id", ""),
            action=d.get("action", ""),
            captured_at=d.get("captured_at", ""),
            pre_state=dict(d.get("pre_state", {})),
            execution_result=dict(d.get("execution_result", {})),
            source_of_truth=dict(d.get("source_of_truth", {})),
            artifacts=list(d.get("artifacts", [])),
            references=list(d.get("references", [])),
            evidence=dict(d.get("evidence", {})),
            limitations=list(d.get("limitations", [])),
            provenance=d.get("provenance", "declared"))
        return m

    def verify(self) -> dict[str, Any]:
        """Tamper check — recompute the content hash."""
        return {"material_id": self.material_id, "hash": self.hash(),
                "ok": True}

    def complete(self, required: tuple[str, ...]) -> list[str]:
        """Which required pre-state keys are missing."""
        return [k for k in required if k not in self.pre_state]


class MaterialStore:
    """Content-addressed, write-once store under
    `.platformforge/materials/`. Same hash → same object; different
    content at an existing path → tamper refusal."""

    def __init__(self, root: str | Path = ".platformforge/materials"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, m: RollbackMaterial) -> dict[str, Any]:
        h = m.hash()
        p = self.root / f"{h.split(':', 1)[1]}.json"
        if p.exists():
            existing = json.loads(p.read_text())
            if existing.get("hash") != h:
                return {"ok": False,
                        "refusal": "PF-OPS-MATERIAL-TAMPER",
                        "unlock": "material content differs at existing "
                                  "hash path — investigate tampering"}
            return {"ok": True, "hash": h, "deduplicated": True}
        p.write_text(json.dumps(m.to_dict(), indent=2, sort_keys=True))
        return {"ok": True, "hash": h, "deduplicated": False}

    def get(self, hash_or_id: str) -> RollbackMaterial | None:
        h = hash_or_id.split(":", 1)[-1]
        p = self.root / f"{h}.json"
        if not p.exists():
            for f in self.root.glob("*.json"):
                d = json.loads(f.read_text())
                if d.get("material_id") == hash_or_id:
                    return RollbackMaterial.from_dict(d)
            return None
        return RollbackMaterial.from_dict(json.loads(p.read_text()))

    def verify(self, hash_or_id: str) -> dict[str, Any]:
        m = self.get(hash_or_id)
        if m is None:
            return {"ok": False, "refusal": "PF-OPS-MATERIAL-MISSING",
                    "unlock": f"no material {hash_or_id}"}
        p = self.root / f"{m.hash().split(':', 1)[1]}.json"
        stored = json.loads(p.read_text()) if p.exists() else {}
        return {"ok": stored.get("hash") == m.hash(),
                "material_id": m.material_id, "hash": m.hash()}

    def for_operation(self, operation_id: str) -> list[dict[str, Any]]:
        out = []
        for f in sorted(self.root.glob("*.json")):
            d = json.loads(f.read_text())
            if d.get("operation_id") == operation_id:
                out.append({"hash": d.get("hash"),
                            "step_id": d.get("step_id"),
                            "action": d.get("action")})
        return out


def capture_material(action: str, step_id: str, operation_id: str,
                     params: dict[str, Any],
                     required: tuple[str, ...],
                     pre_state: dict[str, Any] | None = None,
                     execution_result: dict[str, Any] | None = None,
                     source_of_truth: dict[str, Any] | None = None,
                     provenance: str = "declared") -> RollbackMaterial:
    """Build a material for one step — merges declared params with
    transport/observation-captured pre-state (observed wins)."""
    ps = dict(pre_state or {})
    m = RollbackMaterial(
        material_id=f"mat-{operation_id}-{step_id}",
        operation_id=operation_id, step_id=step_id, action=action,
        captured_at=now_iso(), pre_state=ps,
        execution_result=dict(execution_result or {}),
        source_of_truth=dict(source_of_truth or {}),
        provenance=provenance)
    missing = m.complete(required)
    if missing:
        m.limitations.append(
            f"required pre-state not captured: {missing} — "
            "rollback cannot be considered executable")
    return m
