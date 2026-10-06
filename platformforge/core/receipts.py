"""Evidence receipts — every important operation emits one.

Receipts capture operation, inputs, content hashes, tools/versions, produced
fact/finding ids and timings so a run is auditable and replayable.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from platformforge.core.hashing import sha256_obj


@dataclass
class Receipt:
    operation: str
    inputs: list[Any] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    versions: dict[str, str] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    graph: str | None = None
    started_at: float = 0.0
    ended_at: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["started_at"] = _iso(self.started_at)
        d["ended_at"] = _iso(self.ended_at)
        return d

    @property
    def receipt_id(self) -> str:
        return "rcpt-" + sha256_obj(self.to_dict())[:16]


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else ""


class ReceiptWriter:
    """Persists receipts under .platformforge/receipts/ (audit trail)."""

    def __init__(self, root: str | Path):
        self.dir = Path(root) / ".platformforge" / "receipts"
        self.dir.mkdir(parents=True, exist_ok=True)

    def emit(self, receipt: Receipt) -> Path:
        p = self.dir / f"{receipt.receipt_id}.json"
        p.write_text(json.dumps(receipt.to_dict(), indent=2, default=str))
        return p


class timed:
    """Context manager stamping started_at/ended_at on a receipt."""

    def __init__(self, receipt: Receipt):
        self.receipt = receipt

    def __enter__(self) -> Receipt:
        self.receipt.started_at = time.time()
        return self.receipt

    def __exit__(self, *exc) -> None:
        self.receipt.ended_at = time.time()
