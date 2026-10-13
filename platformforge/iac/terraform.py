"""Terraform/OpenTofu HCL analyzer — static, offline, deterministic.

Emits facts of kind `iac.resource` / `iac.module` / `iac.data` with graph
contributions: terraform_resource / terraform_module nodes and depends_on
edges derived from `type.name` references and explicit depends_on blocks.
Values pass through the redactor before becoming fact attrs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import hcl2

from platformforge.core.redaction import redact_obj
from platformforge.models.base import stable_id

_SKIP_PREFIXES = {"var", "local", "data", "module", "each", "count", "self",
                  "path", "terraform", "provider"}
_REF_RE = re.compile(r"\b([a-z][a-z0-9_]*\.[A-Za-z0-9_-]+)\b")
_CLOUD_RE = re.compile(r"^(aws|azurerm|google|kubernetes|helm|random|tls|"
                       r"http|external|null|local|time|archive)")


def _refs(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, str):
        for m in _REF_RE.finditer(value):
            ref = m.group(1)
            if ref.split(".")[0] not in _SKIP_PREFIXES:
                out.add(ref)
    elif isinstance(value, dict):
        for v in value.values():
            out |= _refs(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            out |= _refs(v)
    return out


def _iter_blocks(doc: dict[str, Any], key: str):
    for blk in doc.get(key, []) or []:
        if not isinstance(blk, dict):
            continue
        for rtype, bodies in blk.items():
            if not isinstance(bodies, dict):
                continue
            for name, body in bodies.items():
                yield rtype, name, (body or {})


def analyze_hcl(path: str | Path) -> dict[str, Any]:
    """Analyze a .tf file or a directory of them → facts document."""
    root = Path(path)
    files = sorted(root.rglob("*.tf")) if root.is_dir() else [root]
    facts: list[dict[str, Any]] = []
    for f in files:
        try:
            doc = hcl2.load(f.open())
        except Exception as exc:  # noqa: BLE001 — parse failure is a fact, not a crash
            facts.append({"fact_id": stable_id("PF-IAC", "iac.parse_error",
                                               str(f), str(exc)[:64]),
                          "kind": "iac.parse_error", "source": str(f),
                          "location": str(f), "tier": 3,
                          "attrs": {"error": str(exc)[:200]}})
            continue
        rel = str(f)
        # resources
        for rtype, name, body in _iter_blocks(doc, "resource"):
            address = f"{rtype}.{name}"
            m = _CLOUD_RE.match(rtype)
            attrs = redact_obj(body)
            graph_edges = []
            for ref in sorted(_refs(body)):
                graph_edges.append(
                    {"src_kind": "terraform_resource", "src": address,
                     "dst_kind": "terraform_resource", "dst": ref,
                     "kind": "depends_on"})
            facts.append({
                "fact_id": stable_id("PF-IAC", "iac.resource", rel, address),
                "kind": "iac.resource", "source": rel, "location": rel,
                "tier": 3,
                "attrs": {"type": rtype, "name": name, "address": address,
                          "cloud": m.group(1) if m else "other",
                          "body": attrs,
                          "tags": attrs.get("tags"),
                          "graph": {
                              "nodes": [{"kind": "terraform_resource",
                                         "label": address,
                                         "attrs": {"type": rtype,
                                                   "file": rel}}],
                              "edges": graph_edges}}})
        # modules — hcl2 emits {"module": [{"name": {body}}]}, one level
        for name, body in (
                (n, b) for blk in doc.get("module", []) or []
                for n, b in (blk.items() if isinstance(blk, dict) else [])):
            facts.append({
                "fact_id": stable_id("PF-IAC", "iac.module", rel, name),
                "kind": "iac.module", "source": rel, "location": rel,
                "tier": 3,
                "attrs": {"name": name, "source": body.get("source"),
                          "version": body.get("version"),
                          "graph": {"nodes": [{"kind": "terraform_module",
                                               "label": name,
                                               "attrs": {
                                                   "source": body.get("source"),
                                                   "version": body.get("version"),
                                                   "file": rel}}]}}})
        # data sources
        for rtype, name, body in _iter_blocks(doc, "data"):
            address = f"data.{rtype}.{name}"
            facts.append({
                "fact_id": stable_id("PF-IAC", "iac.data", rel, address),
                "kind": "iac.data", "source": rel, "location": rel,
                "tier": 3,
                "attrs": {"type": rtype, "name": name, "address": address,
                          "body": redact_obj(body)}})
        # explicit depends_on lands inside body already via _refs? no —
        # depends_on is a list of refs; covered by _refs walk.
    return {"facts": facts,
            "counts": {"files": len(files), "facts": len(facts)}}
