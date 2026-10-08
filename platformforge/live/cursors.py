"""CursorStore — persisted watch/list cursors (resourceVersion et al.).

.platformforge/live/cursors/<collector>/<key>.json — lets a collector
resume a watch instead of relisting; staleness is reported so callers
can decide resnapshot (§27–28, §145 incremental collection).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.core.hashing import sha256_text
from platformforge.live.models import now_iso

CURSORS_DIR = ".platformforge/live/cursors"


class CursorStore:
    def __init__(self, root: str | Path, collector: str = "kubernetes"):
        self.dir = Path(root) / CURSORS_DIR / collector

    def _key(self, name: str) -> Path:
        return self.dir / f"{sha256_text(name)[:24]}.json"

    def put(self, name: str, *, cursor: str,
            watch_state: str = "idle", **extra: Any) -> dict[str, Any]:
        self.dir.mkdir(parents=True, exist_ok=True)
        doc = {"name": name, "cursor": cursor, "watch_state": watch_state,
               "updated_at": now_iso(), **extra}
        self._key(name).write_text(json.dumps(doc, indent=2,
                                              sort_keys=True) + "\n")
        return doc

    def get(self, name: str) -> dict[str, Any] | None:
        p = self._key(name)
        return json.loads(p.read_text()) if p.exists() else None

    def watch_state(self, name: str) -> str:
        c = self.get(name)
        return c.get("watch_state", "unknown") if c else "unknown"

    def all(self) -> list[dict[str, Any]]:
        if not self.dir.exists():
            return []
        return [json.loads(p.read_text())
                for p in sorted(self.dir.glob("*.json"))]
