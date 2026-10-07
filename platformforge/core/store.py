"""Content-addressed artifact store.

Raw tool output, large evidence blobs and intermediate state live here —
referenced by hash, so context packs carry pointers, not payloads.

Layout:  .platformforge/store/<sha[:2]>/<sha>   (+ .json sidecar metadata)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from platformforge.core.hashing import sha256_bytes

STORE_DIR = ".platformforge/store"


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root) / STORE_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha: str) -> Path:
        return self.root / sha[:2] / sha

    def put(self, data: bytes, meta: dict[str, Any] | None = None) -> str:
        sha = sha256_bytes(data)
        p = self._path(sha)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(data)
            p.with_suffix(p.suffix + ".meta.json").write_text(
                json.dumps(
                    {"sha256": sha, "bytes": len(data), "stored_at": time.time(),
                     **(meta or {})},
                    indent=2, default=str,
                )
            )
        return sha

    def put_text(self, text: str, meta: dict[str, Any] | None = None) -> str:
        return self.put(text.encode("utf-8"), meta)

    def put_obj(self, obj: Any, meta: dict[str, Any] | None = None) -> str:
        return self.put_text(
            json.dumps(obj, indent=2, sort_keys=True, default=str), meta
        )

    def get(self, sha: str) -> bytes | None:
        p = self._path(sha)
        return p.read_bytes() if p.exists() else None

    def get_text(self, sha: str) -> str | None:
        b = self.get(sha)
        return b.decode("utf-8") if b is not None else None

    def get_obj(self, sha: str) -> Any | None:
        t = self.get_text(sha)
        return json.loads(t) if t is not None else None

    def has(self, sha: str) -> bool:
        return self._path(sha).exists()

    def meta(self, sha: str) -> dict[str, Any] | None:
        mp = self._path(sha).with_suffix(".meta.json")
        return json.loads(mp.read_text()) if mp.exists() else None

    def stats(self) -> dict[str, int]:
        blobs = [p for p in self.root.glob("*/*") if not p.name.endswith(".meta.json")]
        return {"artifacts": len(blobs),
                "bytes": sum(p.stat().st_size for p in blobs)}

    def gc(self, keep_days: float = 30.0,
           referenced: set[str] | None = None,
           dry_run: bool = True) -> dict[str, Any]:
        """§151 — garbage-collect stale blobs.

        Never deletes a hash in `referenced` (receipts, packs, ledger rows).
        `dry_run=True` reports candidates without touching the store.
        """
        ref = referenced or set()
        cutoff = time.time() - keep_days * 86400
        stale: list[dict[str, Any]] = []
        kept = 0
        for blob in self.root.glob("*/*"):
            if blob.name.endswith(".meta.json"):
                continue
            sha = blob.name
            meta = self.meta(sha) or {}
            stored_at = float(meta.get("stored_at") or blob.stat().st_mtime)
            if sha in ref or stored_at > cutoff:
                kept += 1
                continue
            stale.append({"sha256": sha, "bytes": blob.stat().st_size,
                          "stored_at": stored_at})
        removed_bytes = 0
        if not dry_run:
            for s in stale:
                p = self._path(s["sha256"])
                mp = p.with_suffix(".meta.json")
                removed_bytes += p.stat().st_size
                p.unlink(missing_ok=True)
                mp.unlink(missing_ok=True)
        return {"dry_run": dry_run, "keep_days": keep_days,
                "candidates": len(stale),
                "candidate_bytes": sum(s["bytes"] for s in stale),
                "removed": 0 if dry_run else len(stale),
                "removed_bytes": removed_bytes,
                "kept": kept,
                "referenced_protected": len(ref),
                "stale": stale if dry_run else []}


def ref(sha: str) -> str:
    """Artifact reference used in context packs and receipts."""
    return f"artifact://sha256/{sha}"
