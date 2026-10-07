"""Secret scanning — detect credential patterns in files. Reports locations
and pattern labels only; values are never emitted (redaction markers only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platformforge.core.redaction import PATTERNS
from platformforge.models.base import stable_id

_SKIP_DIRS = {".git", ".venv", "node_modules", ".platformforge",
              "__pycache__", "dist"}
_SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".whl",
             ".so", ".pyc", ".jar"}


def scan_secrets(path: str | Path, max_files: int = 5000) -> dict[str, Any]:
    root = Path(path)
    files = [root] if root.is_file() else [
        p for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix.lower() not in _SKIP_EXT
        and not any(part in _SKIP_DIRS for part in p.parts)][:max_files]
    facts: list[dict[str, Any]] = []
    hits_total = 0
    for f in files:
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        hits = []
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pat in PATTERNS:
                if pat.search(line):
                    hits.append({"line": lineno, "label": label})
        # multi-line patterns (private keys) never match per-line —
        # run them against the whole file body.
        for label, pat in PATTERNS:
            if "[\\s\\S]" not in pat.pattern:
                continue
            for m in pat.finditer(text):
                lineno = text.count("\n", 0, m.start()) + 1
                hit = {"line": lineno, "label": label}
                if hit not in hits:
                    hits.append(hit)
        if hits:
            hits_total += len(hits)
            facts.append({"fact_id": stable_id("PF-SEC", "scan", str(f)),
                          "kind": "security.secret_leak",
                          "source": str(root), "location": str(f),
                          "tier": 2,
                          "attrs": {"hits": hits, "hit_count": len(hits)}})
    return {"facts": facts,
            "counts": {"files_scanned": len(files), "files_with_hits":
                       len(facts), "hits": hits_total},
            "note": "values never emitted — labels and line numbers only"}
