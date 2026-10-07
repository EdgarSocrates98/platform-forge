"""Knowledge packs — operational knowledge, not a provenance registry
(cycle 2.1 §60–68).

A pack is a YAML document under ``knowledge/<domain>/<id>.yaml``:

```yaml
schema: platformforge/knowledge/v1
id: kubernetes-api-deprecations
domain: kubernetes
applies_to: {versions: [kubernetes]}
sources: [kubernetes-docs]
claims:
  - id: k8s-dep-v122
    statement: "..."
    versions: {kubernetes: ">=1.22"}
used_by:
  rules: [PF-K8S-030]
  analyzers: [k8s]
```

Consumption is checked, not asserted: ``contract_check`` resolves every
``sources`` id against the source registry, every ``used_by.rules`` against
the rule catalog, and every ``used_by.analyzers`` against the analyzer
registry — a pack nothing consumes is dead weight (§63/§136). Each pack
carries a ``content_hash`` (sha256 of the canonical claim set) so consumers
detect drift when content changes (§68).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "platformforge/knowledge/v1"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    versions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Pack:
    pack_id: str
    domain: str
    applies_to: dict[str, Any]
    sources: tuple[str, ...]
    claims: tuple[Claim, ...]
    used_by: dict[str, list[str]]
    path: str = ""

    @property
    def content_hash(self) -> str:
        """§68 — sha256 over the canonical claim set; drift detectable."""
        blob = json.dumps({
            "id": self.pack_id,
            "claims": [{"id": c.claim_id, "statement": c.statement,
                        "versions": c.versions} for c in self.claims],
        }, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.pack_id, "domain": self.domain,
                "path": self.path, "content_hash": self.content_hash,
                "sources": list(self.sources),
                "claims": [{"id": c.claim_id, "statement": c.statement,
                            "versions": c.versions} for c in self.claims],
                "used_by": self.used_by}

    @classmethod
    def from_dict(cls, d: dict[str, Any], path: str = "") -> Pack:
        if d.get("schema") != SCHEMA:
            raise ValueError(f"{path or d.get('id')}: schema must be "
                             f"{SCHEMA}")
        missing = [k for k in ("id", "domain", "sources", "claims")
                   if k not in d]
        if missing:
            raise ValueError(f"{d.get('id', path)}: missing {missing}")
        claims = tuple(Claim(str(c["id"]), str(c["statement"]),
                             dict(c.get("versions") or {}))
                       for c in d["claims"])
        return cls(pack_id=str(d["id"]), domain=str(d["domain"]),
                   applies_to=dict(d.get("applies_to") or {}),
                   sources=tuple(str(s) for s in d["sources"]),
                   claims=claims,
                   used_by=dict(d.get("used_by") or {}), path=path)


class PackRegistry:
    def __init__(self, root: str | Path | None = None):
        if root is None:
            from platformforge.resources import data_path
            root = data_path("knowledge")
        self.root = Path(root)
        self.packs: dict[str, Pack] = {}
        if self.root.is_dir():
            for f in sorted(self.root.rglob("*.yaml")):
                if f.name == "sources.yaml":
                    continue
                d = yaml.safe_load(f.read_text())
                if not isinstance(d, dict) or d.get("schema") != SCHEMA:
                    continue
                p = Pack.from_dict(d, path=str(f.relative_to(self.root)))
                self.packs[p.pack_id] = p

    @classmethod
    def default(cls) -> PackRegistry:
        return cls()

    def for_rule(self, rule_id: str) -> list[Pack]:
        return [p for p in self.packs.values()
                if rule_id in (p.used_by.get("rules") or [])]

    def for_analyzer(self, name: str) -> list[Pack]:
        return [p for p in self.packs.values()
                if name in (p.used_by.get("analyzers") or [])]

    def contract_check(self) -> dict[str, Any]:
        """Every pack consumed by something real: sources resolve against
        the registry, rules against the catalog, analyzers against the lab
        analyzer table."""
        from platformforge.knowledge.registry import SourceRegistry
        from platformforge.lab.runner import _ANALYZERS
        from platformforge.resources import data_path
        from platformforge.rules import load_catalog
        sources = SourceRegistry.default().entries
        rules = {r.rule_id
                 for r in load_catalog(data_path("rules", "catalog"))}
        problems: list[dict[str, Any]] = []
        consumed = 0
        for p in sorted(self.packs.values(), key=lambda x: x.pack_id):
            bad_src = [s for s in p.sources if s not in sources]
            bad_rules = [r for r in p.used_by.get("rules", [])
                         if r not in rules]
            bad_an = [a for a in p.used_by.get("analyzers", [])
                      if a not in _ANALYZERS]
            if not p.used_by.get("rules") and not p.used_by.get("analyzers"):
                problems.append({"pack": p.pack_id, "issue": "unconsumed"})
            else:
                consumed += 1
            for kind, ids in (("unknown_source", bad_src),
                              ("unknown_rule", bad_rules),
                              ("unknown_analyzer", bad_an)):
                for i in ids:
                    problems.append({"pack": p.pack_id, "issue": kind,
                                     "ref": i})
            if not p.claims:
                problems.append({"pack": p.pack_id, "issue": "no_claims"})
        return {"packs": len(self.packs), "consumed": consumed,
                "problems": problems, "ok": not problems}
