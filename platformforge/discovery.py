# platformforge/discovery.py
"""Offline retrieval for the install-2.0 §6.2/§6.4 discovery ops (lf-0037).

Rules come from ``rules.engine.load_catalog(data_path("rules","catalog"))``;
knowledge docs from ``data_path("knowledge")`` (bundled in the wheel or the
repo checkout); skills/agents from the same bundled-data resolution the
installer uses. Absence degrades to explicit empty state — never invented.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from platformforge import __version__, discovery_ops
from platformforge.resources import data_path

INDEX_FIELDS = ("rule_id", "domain", "title", "severity")
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
_SNIPPET_MAX = 3
_SNIPPET_WIDTH = 160


class DiscoveryError(ValueError):
    """Refused retrieval input (cursor/path)."""


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


def _cursor_offset(cursor: str | None) -> int:
    if cursor in (None, ""):
        return 0
    try:
        offset = int(str(cursor), 10)
    except ValueError:
        raise DiscoveryError(f"cursor invalido: {cursor!r}") from None
    if offset < 0:
        raise DiscoveryError(f"cursor invalido: {cursor!r}")
    return offset


def _page(items: list[Any], limit: int | None, cursor: str | None) -> dict[str, Any]:
    off = _cursor_offset(cursor)
    lim = _clamp_limit(limit)
    nxt = off + lim if off + lim < len(items) else None
    return {
        "items": items[off : off + lim],
        "total": len(items),
        "limit": lim,
        "next_cursor": str(nxt) if nxt is not None else None,
    }


def _sha256_of(path: Path) -> str | None:
    try:
        d = hashlib.sha256()
        with path.open("rb") as h:
            for chunk in iter(lambda: h.read(1 << 20), b""):
                d.update(chunk)
        return d.hexdigest()
    except OSError:
        return None


def _rules() -> list[Any]:
    from platformforge.rules import load_catalog

    try:
        return list(load_catalog(data_path("rules", "catalog")))
    except (ValueError, OSError):
        return []


def _rule_index(r: Any) -> dict[str, Any]:
    return {k: getattr(r, k, None) for k in INDEX_FIELDS} | {"id": r.rule_id}


def rules_search(
    *,
    query: str | None = None,
    rule_id: str | None = None,
    domain: str | None = None,
    severity: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    index: bool = False,
) -> dict[str, Any]:
    rules = _rules()
    if rule_id:
        rules = [r for r in rules if r.rule_id == rule_id]
    if domain:
        px = discovery_ops.domain_prefixes(domain)
        rules = [
            r
            for r in rules
            if any(p in (r.domain or "").lower() or p in r.rule_id.lower() for p in px)
        ]
    if severity:
        sev = severity.lower()
        rules = [r for r in rules if str(r.severity).lower() == sev]
    if query:
        q = query.lower()
        rules = [
            r
            for r in rules
            if q in " ".join([r.rule_id, r.title or "", r.domain or ""]).lower()
        ]
    rules = sorted(rules, key=lambda r: r.rule_id)
    items = [
        _rule_index(r) if index else {"id": r.rule_id, **_rule_index(r)}
        for r in rules
    ]
    page = _page(items, limit, cursor)
    return {
        "status": "ok",
        "forge": "platformforge",
        "catalog_dir": str(data_path("rules", "catalog")),
        "filters_applied": {
            k: v
            for k, v in {
                "query": query, "id": rule_id, "domain": domain, "severity": severity
            }.items()
            if v is not None
        },
        "rules": page["items"],
        "total": page["total"],
        "next_cursor": page["next_cursor"],
    }


def rules_get(rule_id: str) -> dict[str, Any]:
    for r in _rules():
        if r.rule_id == rule_id:
            return {"status": "ok", "found": True, "rule": _rule_index(r)}
    return {
        "status": "ok",
        "found": False,
        "rule": None,
        "detail": f"{rule_id} absent from the catalog — nothing invented",
    }


def _knowledge_root() -> Path:
    return data_path("knowledge")


def _knowledge_docs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".yaml", ".yml")
    )


def _doc_meta(root: Path, path: Path, *, term: str | None = None) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    meta: dict[str, Any] = {"ref": rel, "sha256": _sha256_of(path), "bytes": path.stat().st_size}
    if term is None:
        return meta
    text = path.read_text(encoding="utf-8", errors="replace")
    needle = term.lower()
    hits = [
        (n, l.strip())
        for n, l in enumerate(text.splitlines(), 1)
        if needle in l.lower()
    ]
    meta["matched_lines"] = len(hits)
    meta["name_hit"] = needle in rel.lower()
    meta["snippets"] = [{"line": n, "text": s[:_SNIPPET_WIDTH]} for n, s in hits[:_SNIPPET_MAX]]
    meta["snippets_truncated"] = len(hits) > _SNIPPET_MAX
    return meta


def knowledge_search(
    term: str,
    *,
    domain: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    root = _knowledge_root()
    px = discovery_ops.domain_prefixes(domain) if domain else None
    needle = term.lower()
    matched: list[Path] = []
    for path in _knowledge_docs(root):
        rel = path.relative_to(root).as_posix()
        if px and not any(rel.split("/", 1)[0].startswith(p) or p in rel.lower() for p in px):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if needle in rel.lower() or needle in text.lower():
            matched.append(path)
    off = _cursor_offset(cursor)
    lim = _clamp_limit(limit)
    nxt = off + lim if off + lim < len(matched) else None
    return {
        "status": "ok",
        "knowledge_root": str(root),
        "term": term,
        "domain": domain,
        "documents_total": len(matched),
        "documents": [_doc_meta(root, p, term=term) for p in matched[off : off + lim]],
        "limit": lim,
        "next_cursor": str(nxt) if nxt is not None else None,
    }


def knowledge_get(file: str) -> dict[str, Any]:
    root = _knowledge_root().resolve()
    target = (root / file).resolve()
    if not str(target).startswith(str(root) + "/"):
        raise DiscoveryError(f"path escapes knowledge root: {file!r}")
    if not target.is_file():
        raise DiscoveryError(f"{file!r} not present in knowledge root {root}")
    return {
        "status": "ok",
        "knowledge_root": str(root),
        "document": {
            "ref": target.relative_to(root).as_posix(),
            "path": str(target),
            "sha256": _sha256_of(target),
            "bytes": target.stat().st_size,
        },
    }


def capabilities() -> dict[str, Any]:
    rules = _rules()
    root = _knowledge_root()
    docs = _knowledge_docs(root)
    skills_root = data_path("portable_skills")
    skills = (
        sorted(d.name for d in skills_root.iterdir() if d.is_dir())
        if skills_root.is_dir()
        else []
    )
    agents_root = data_path("agents")
    agents = sorted(p.stem for p in agents_root.glob("*.md")) if agents_root.is_dir() else []
    return {
        "status": "ok",
        "forge": "platformforge",
        "version": __version__,
        "cli": discovery_ops.CLI,
        "offline": True,
        "rules": {
            "count": len(rules),
            "domains": sorted({r.domain for r in rules}),
            "index_fields": list(INDEX_FIELDS),
        },
        "knowledge": {"root": str(root), "documents": len(docs)},
        "skills": {"count": len(skills), "ids": skills},
        "agents": {"count": len(agents), "ids": agents},
        "domains": list(discovery_ops.DOMAINS),
        "protocols": list(discovery_ops.PROTOCOLS),
        "interfaces": {"mcp": discovery_ops.MCP_INTERFACE},
        "operations": discovery_ops.ops_expanded(),
    }


def context_pack(
    domain: str | None = None,
    *,
    rules_limit: int | None = None,
    knowledge_limit: int | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    px = discovery_ops.domain_prefixes(domain) if domain else None
    rules = _rules()
    if px:
        rules = [
            r
            for r in rules
            if any(p in (r.domain or "").lower() or p in r.rule_id.lower() for p in px)
        ]
    rlim = _clamp_limit(rules_limit)
    root = _knowledge_root()
    docs = _knowledge_docs(root)
    if px:
        docs = [
            d
            for d in docs
            if any(d.relative_to(root).parts[0].startswith(p) or p in d.name.lower() for p in px)
        ]
    klim = _clamp_limit(knowledge_limit)
    pack: dict[str, Any] = {
        "schema": "forge/context-pack/v1",
        "forge": "platformforge",
        "version": __version__,
        "domain": domain,
        "domain_prefixes": list(px) if px else None,
        "rules": [_rule_index(r) for r in sorted(rules, key=lambda r: r.rule_id)[:rlim]],
        "rules_total": len(rules),
        "rules_truncated": len(rules) > rlim,
        "knowledge": {
            "root": str(root),
            "documents": [_doc_meta(root, d) for d in docs[:klim]],
            "documents_total": len(docs),
            "truncated": len(docs) > klim,
        },
        "protocols": list(discovery_ops.PROTOCOLS),
        "operations": discovery_ops.ops(),
        "offline": True,
    }
    if as_of:
        pack["as_of"] = as_of
    pack["pack_sha256"] = hashlib.sha256(
        json.dumps(pack, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return pack
