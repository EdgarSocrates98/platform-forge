"""Local search index — SQLite FTS5, incremental by content hash.

Indexes file content + extracted symbols. Unchanged files (same sha256) are
never re-indexed. No embeddings, no external service.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from platformforge.core.hashing import sha256_file, sha256_text

IGNORE_DIRS = {".git", ".venv", "node_modules", ".platformforge", "vendor",
               "__pycache__", "dist", "build", ".terraform", ".idea", ".vscode"}
TEXT_EXT = {".py", ".tf", ".tfvars", ".yaml", ".yml", ".json", ".md", ".go",
            ".ts", ".js", ".java", ".rb", ".rs", ".sh", ".toml", ".hcl",
            ".sql", ".j2", ".tpl", ".rego", ".cel", ".xml", ".gradle",
            ".properties", ".txt", ".cfg", ".ini", ".env.example"}
MAX_FILE_BYTES = 2_000_000

SYMBOL_PATTERNS = {
    ".py": [re.compile(r"^\s*(?:class|def|async def)\s+([A-Za-z_][\w]*)", re.M)],
    ".go": [re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)", re.M),
            re.compile(r"^\s*type\s+([A-Za-z_][\w]*)", re.M)],
    ".java": [re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_][\w]*)")],
    ".tf": [re.compile(r'\bresource\s+"([^"]+)"\s+"([^"]+)"'),
            re.compile(r'\bmodule\s+"([^"]+)"'),
            re.compile(r'\b(?:variable|output|data|provider)\s+"?([A-Za-z_][\w]*)"?')],
    ".hcl": [re.compile(r'\bresource\s+"([^"]+)"\s+"([^"]+)"')],
    ".yaml": [re.compile(r"^\s*name:\s*([A-Za-z0-9_.\-/]+)", re.M)],
    ".yml": [re.compile(r"^\s*name:\s*([A-Za-z0-9_.\-/]+)", re.M)],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  path TEXT PRIMARY KEY, sha256 TEXT, kind TEXT, bytes INTEGER, symbols TEXT);
CREATE TABLE IF NOT EXISTS facts_idx(
  fact_id TEXT PRIMARY KEY, kind TEXT, location TEXT, doc TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS content USING fts5(
  path UNINDEXED, body, tokenize='porter unicode61');
"""


class SearchIndex:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.db_path))
        self.db.executescript(SCHEMA)
        self.db.commit()

    # ── indexing ──────────────────────────────────────────────
    def _iter_files(self, root: Path) -> Iterable[Path]:
        for p in sorted(root.rglob("*")):
            if not p.is_file() or any(part in IGNORE_DIRS for part in p.parts):
                continue
            if p.suffix in TEXT_EXT and p.stat().st_size <= MAX_FILE_BYTES:
                yield p

    def index_workspace(self, root: str | Path) -> dict[str, int]:
        """Incremental: only changed/new files are parsed and re-indexed."""
        root = Path(root)
        stats = {"indexed": 0, "reused": 0, "removed": 0}
        seen = set()
        for p in self._iter_files(root):
            rel = str(p.relative_to(root))
            seen.add(rel)
            sha = sha256_file(p)
            row = self.db.execute(
                "SELECT sha256 FROM files WHERE path=?", (rel,)).fetchone()
            if row and row[0] == sha:
                stats["reused"] += 1
                continue
            body = p.read_text(errors="replace")
            symbols = sorted({m for pat in SYMBOL_PATTERNS.get(p.suffix, [])
                              for m in pat.findall(body)
                              for m in (m if isinstance(m, tuple) else (m,))})
            self.db.execute(
                "INSERT OR REPLACE INTO files VALUES(?,?,?,?,?)",
                (rel, sha, p.suffix.lstrip("."), p.stat().st_size,
                 " ".join(symbols)))
            self.db.execute("DELETE FROM content WHERE path=?", (rel,))
            self.db.execute("INSERT INTO content(path, body) VALUES(?,?)",
                            (rel, body))
            stats["indexed"] += 1
        stale = {r[0] for r in self.db.execute(
            "SELECT path FROM files")} - seen
        for rel in stale:
            self.db.execute("DELETE FROM files WHERE path=?", (rel,))
            self.db.execute("DELETE FROM content WHERE path=?", (rel,))
            stats["removed"] += 1
        self.db.commit()
        return stats

    def index_fact(self, fact_id: str, kind: str, location: str, doc: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO facts_idx VALUES(?,?,?,?)",
                        (fact_id, kind, location, doc))
        self.db.commit()

    # ── queries ───────────────────────────────────────────────
    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """FTS5 literal/phrase search."""
        try:
            rows = self.db.execute(
                "SELECT path, snippet(content,1,'«','»','…',12) FROM content "
                "WHERE content MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [{"path": p, "snippet": s} for p, s in rows]

    def search_regex(self, pattern: str, limit: int = 50) -> list[dict[str, Any]]:
        rx = re.compile(pattern)
        hits = []
        for path, in self.db.execute("SELECT path FROM files"):
            body_rows = self.db.execute(
                "SELECT body FROM content WHERE path=?", (path,)).fetchall()
            if body_rows and rx.search(body_rows[0][0] or ""):
                hits.append({"path": path})
                if len(hits) >= limit:
                    break
        return hits

    def symbol(self, name: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT path, symbols FROM files WHERE symbols LIKE ?",
            (f"%{name}%",)).fetchall()
        return [{"path": p, "symbols": s.split() if s else []} for p, s in rows]

    def by_path(self, glob: str) -> list[str]:
        like = glob.replace("*", "%").replace("?", "_")
        return [r[0] for r in self.db.execute(
            "SELECT path FROM files WHERE path LIKE ?", (like,))]

    def by_kind(self, kind: str) -> list[str]:
        return [r[0] for r in self.db.execute(
            "SELECT path FROM files WHERE kind=?", (kind,))]

    def read(self, path: str) -> str | None:
        row = self.db.execute(
            "SELECT body FROM content WHERE path=?", (path,)).fetchone()
        return row[0] if row else None

    def stats(self) -> dict[str, int]:
        files = self.db.execute("SELECT COUNT(*), COALESCE(SUM(bytes),0) "
                                "FROM files").fetchone()
        return {"files": files[0], "bytes": files[1]}

    def fingerprint(self) -> str:
        return sha256_text(",".join(
            f"{r[0]}:{r[1]}" for r in self.db.execute(
                "SELECT path, sha256 FROM files ORDER BY path")))
