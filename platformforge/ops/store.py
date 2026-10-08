"""Cycle 4 phase V — operation store.

Append-only JSONL store under `.platformforge/operations/`. Each
operation gets a directory-free design: one `<op_id>.ledger.jsonl` +
`<op_id>.op.json` snapshot. Schema versioned; `verify()` re-checks
every hash chain; `load()` migrates older schema versions forward.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.live.models import canonical_hash, now_iso
from platformforge.ops.operation import (LedgerEntry, Operation,
                                         OperationLedger)

STORE_SCHEMA_VERSION = 2


class OperationStore:
    def __init__(self, root: str | Path = ".platformforge/operations"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        mv = self.root / "_schema_version"
        if not mv.exists():
            mv.write_text(str(STORE_SCHEMA_VERSION))
        elif int(mv.read_text().strip()) > STORE_SCHEMA_VERSION:
            raise ValueError(f"operation store schema "
                             f"{mv.read_text().strip()} newer than "
                             f"supported {STORE_SCHEMA_VERSION}")
        elif int(mv.read_text().strip()) < STORE_SCHEMA_VERSION:
            self._migrate(int(mv.read_text().strip()))

    def _migrate(self, from_v: int) -> None:
        # v1 → v2: ledger files gained a schema field; nothing else moves
        for f in self.root.glob("*.ledger.jsonl"):
            lines = [json.loads(line) for line in
                     f.read_text().splitlines() if line.strip()]
            for rec in lines:
                rec.setdefault("schema", 1)
            f.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                 for r in lines))
        (self.root / "_schema_version").write_text(
            str(STORE_SCHEMA_VERSION))

    def save(self, op: Operation, ledger: OperationLedger) -> Path:
        """Append new ledger entries + write op snapshot."""
        op_path = self.root / f"{op.operation_id}.op.json"
        led_path = self.root / f"{op.operation_id}.ledger.jsonl"
        existing = 0
        if led_path.exists():
            existing = sum(1 for _ in led_path.open())
        with led_path.open("a") as f:
            for e in ledger.entries[existing:]:
                rec = e.to_dict()
                rec["schema"] = STORE_SCHEMA_VERSION
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        snap = op.to_dict() if hasattr(op, "to_dict") else {
            "operation_id": op.operation_id, "state": op.state}
        snap["schema"] = STORE_SCHEMA_VERSION
        snap["stored_at"] = now_iso()
        op_path.write_text(json.dumps(snap, indent=2, sort_keys=True))
        return op_path

    def load_ledger(self, operation_id: str) -> OperationLedger:
        led = OperationLedger()
        p = self.root / f"{operation_id}.ledger.jsonl"
        if not p.exists():
            return led
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            e = LedgerEntry(seq=r["seq"], event=r["event"],
                            operation_id=r["operation_id"],
                            actor=r.get("actor", "system"),
                            at=r.get("at", ""),
                            data=dict(r.get("data", {})),
                            prev_hash=r.get("prev_hash", ""))
            e.entry_hash = r.get("entry_hash", e.entry_hash)
            led.entries.append(e)
            led._tip = e.entry_hash
        return led

    def verify(self, operation_id: str) -> dict[str, Any]:
        led = self.load_ledger(operation_id)
        return {"operation_id": operation_id,
                "entries": len(led.entries),
                "chain_valid": led.verify_chain(),
                "tip": led.tip}

    def list_operations(self) -> list[str]:
        return sorted(p.stem[:-3] for p in self.root.glob("*.op.json"))

    def audit_digest(self) -> str:
        """Digest of every stored ledger tip — tamper-evident index."""
        tips = {op: self.load_ledger(op).tip
                for op in self.list_operations()}
        return "sha256:" + canonical_hash(tips)
