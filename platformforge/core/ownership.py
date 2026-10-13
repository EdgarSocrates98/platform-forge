"""Ownership resolution (§136–137) + contradictory evidence (§116).

Ownership signals come from multiple sources, each with its own evidence
tier. When two sources disagree for the same subject the result is a named
`ownership.conflicted` fact — never a silently averaged winner.

Signal sources and tiers:
- CODEOWNERS            → T3 repo-config
- Backstage catalog     → T3 repo-config
- workspace member attr → T5 operator-declared
- k8s labels/annotations→ T3 repo-config (manifest) / T1 (provider dump)
- cloud resource tags   → T1 provider-observed
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from platformforge.models.base import EvidenceTier, stable_id

_OWNER_LABEL_KEYS = ("team", "owner", "owner-id",
                     "app.kubernetes.io/managed-by",
                     "app.kubernetes.io/part-of")
_OWNER_TAG_KEYS = ("owner", "team", "cost_center", "cost-center",
                   "Owner", "Team")


def _fact(fkind: str, source: str, location: str, tier: int,
          attrs: dict[str, Any]) -> dict[str, Any]:
    return {"fact_id": stable_id("PF-FACT", fkind, source, location,
                                 json.dumps(attrs, sort_keys=True,
                                            default=str)[:200]),
            "kind": fkind, "source": source, "location": location,
            "tier": int(tier), "attrs": attrs}


def _codeowners_signals(path: Path) -> list[dict[str, Any]]:
    """Parse CODEOWNERS → per-path owner signals."""
    facts = []
    text = path.read_text(errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        pattern, owners = parts[0], [o for o in parts[1:]
                                   if not o.startswith("#")]
        if not owners:
            continue
        facts.append(_fact(
            "ownership.signal", str(path), f"{path}:{i}",
            EvidenceTier.REPO_CONFIG,
            {"subject": pattern, "owners": owners,
             "source_kind": "codeowners"}))
    return facts


def _backstage_signals(path: Path) -> list[dict[str, Any]]:
    facts = []
    try:
        doc = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return facts
    spec = doc.get("spec") or {}
    owner = spec.get("owner")
    if owner:
        meta = doc.get("metadata") or {}
        facts.append(_fact(
            "ownership.signal", str(path),
            f"{doc.get('kind', '?')}/{meta.get('name', '?')}",
            EvidenceTier.REPO_CONFIG,
            {"subject": meta.get("name", path.stem),
             "owners": [str(owner)],
             "source_kind": "backstage",
             "system": spec.get("system")}))
    return facts


def _workspace_signals(root: Path) -> list[dict[str, Any]]:
    ws = root / "workspace.yaml"
    if not ws.is_file():
        return []
    try:
        doc = yaml.safe_load(ws.read_text()) or {}
    except yaml.YAMLError:
        return []
    facts = []
    for m in doc.get("members", []):
        owner = m.get("owner") or (m.get("attrs") or {}).get("owner")
        if owner:
            facts.append(_fact(
                "ownership.signal", str(ws), f"member/{m.get('name')}",
                EvidenceTier.OPERATOR_DECLARED,
                {"subject": m.get("name", "?"), "owners": [str(owner)],
                 "source_kind": "workspace"}))
    return facts


def ownership_signals_from_facts(facts: list[dict[str, Any]]
                                 ) -> list[dict[str, Any]]:
    """Harvest owner signals already present in collected fact attrs —
    k8s labels and cloud tags. Each carries the parent fact's tier."""
    out: list[dict[str, Any]] = []
    for f in facts:
        attrs = f.get("attrs") or {}
        subject = f.get("location") or f.get("fact_id", "?")
        labels = attrs.get("labels") or {}
        found = {k: v for k, v in labels.items() if k in _OWNER_LABEL_KEYS}
        if found:
            out.append(_fact(
                "ownership.signal", f.get("source", "?"), subject,
                int(f.get("tier", 3)),
                {"subject": subject, "owners": sorted(set(found.values())),
                 "source_kind": "k8s_labels", "keys": sorted(found),
                 "parent_fact": f.get("fact_id")}))
        tags = attrs.get("tags") or {}
        found = {k: v for k, v in tags.items() if k in _OWNER_TAG_KEYS}
        if found:
            out.append(_fact(
                "ownership.signal", f.get("source", "?"), subject,
                int(f.get("tier", 1)),
                {"subject": subject, "owners": sorted(set(found.values())),
                 "source_kind": "cloud_tags", "keys": sorted(found),
                 "parent_fact": f.get("fact_id")}))
    return out


def detect_conflicts(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same subject, different owner sets across sources → conflicted fact."""
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for s in signals:
        by_subject.setdefault(str(s["attrs"].get("subject")), []).append(s)
    out = []
    for subject, sigs in sorted(by_subject.items()):
        owner_sets = {tuple(sorted(s["attrs"].get("owners", [])))
                      for s in sigs}
        if len(owner_sets) <= 1:
            continue
        out.append(_fact(
            "ownership.conflicted", "platformforge.ownership", subject,
            EvidenceTier.REPO_CONFIG,
            {"subject": subject,
             "claims": [{"owners": s["attrs"].get("owners"),
                         "source_kind": s["attrs"].get("source_kind"),
                         "tier": s.get("tier"),
                         "location": s.get("location")}
                        for s in sigs],
             "resolution": "unresolved — declared vs declared/observed "
                           "disagree; needs human adjudication"}))
    return out


def analyze_ownership(root: str | Path,
                      facts: list[dict[str, Any]] | None = None
                      ) -> dict[str, Any]:
    """Collect ownership signals under `root` + from existing fact attrs."""
    root = Path(root)
    signals: list[dict[str, Any]] = []
    checked: list[str] = []
    for name in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
        p = root / name
        if p.is_file():
            signals.extend(_codeowners_signals(p))
            checked.append(name)
    for cat in root.rglob("catalog-info.y*ml"):
        signals.extend(_backstage_signals(cat))
        checked.append(str(cat))
    signals.extend(_workspace_signals(root))
    if facts:
        signals.extend(ownership_signals_from_facts(facts))
    conflicts = detect_conflicts(signals)
    return {"facts": signals + conflicts,
            "summary": {"signals": len(signals), "conflicts": len(conflicts),
                        "sources_checked": checked},
            "boundary": "ownership signals are claims; conflicts are named, "
                        "never averaged"}


def detect_contradictions(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """§116 — declared vs observed disagreement on the same subject+attr.

    Pairs facts sharing an identity (kind + location) where a comparable
    attr is asserted differently by a declared source (T2+... here T3 repo
    config / T5 operator) vs an observed source (T0/T1). Result is a named
    `state.contradiction` fact carrying both states — never a winner."""
    _DECLARED = (int(EvidenceTier.GENERATED_PLAN),
                 int(EvidenceTier.REPO_CONFIG),
                 int(EvidenceTier.OPERATOR_DECLARED))
    _OBSERVED = (int(EvidenceTier.MEASURED_RUNTIME),
                 int(EvidenceTier.PROVIDER_OBSERVED))
    out: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for f in facts:
        groups.setdefault((f.get("kind", ""), f.get("location", "")),
                          []).append(f)
    for (kind, loc), fs in sorted(groups.items()):
        declared = [f for f in fs if int(f.get("tier", 3)) in _DECLARED]
        observed = [f for f in fs if int(f.get("tier", 3)) in _OBSERVED]
        if not declared or not observed:
            continue
        d_attrs = declared[0].get("attrs") or {}
        o_attrs = observed[0].get("attrs") or {}
        diffs = {k: {"declared": d_attrs[k], "observed": o_attrs[k]}
                 for k in set(d_attrs) & set(o_attrs)
                 if d_attrs[k] != o_attrs[k]
                 and isinstance(d_attrs[k], (str, int, float, bool))
                 and not k.startswith(("api_", "labels", "tags"))}
        if diffs:
            out.append(_fact(
                "state.contradiction", "platformforge.contradictions", loc,
                EvidenceTier.REPO_CONFIG,
                {"kind": kind, "subject": loc, "diffs": diffs,
                 "declared_fact": declared[0].get("fact_id"),
                 "observed_fact": observed[0].get("fact_id"),
                 "status": "drift confirmed — both states reported"}))
    return out
