"""§78–§80 — context audit: what an agent actually needed vs what it
would have received. Compares full / graph-aware / delta context per
case; the unused_context_ratio is measured from fixture bytes, never
estimated from vibes."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from platformforge.cases.casefile import CaseFile, discover_cases


def _fixture_bytes(c: CaseFile) -> dict[str, int]:
    """bytes per artifact file in the case fixture tree."""
    from platformforge.cases.replay import _fixture_dir
    d = _fixture_dir(c)
    if not d.is_dir():
        return {}
    return {str(p.relative_to(d)): p.stat().st_size
            for p in sorted(d.rglob("*")) if p.is_file()}


def audit_case(c: CaseFile) -> dict[str, Any]:
    files = _fixture_bytes(c)
    input_bytes = sum(files.values())
    # relevant bytes = files an analyzer actually consumes for this
    # case's domains — everything else would be dead context
    consumed_suffixes = _consumed(c)
    relevant = sum(b for n, b in files.items()
                   if "*" in consumed_suffixes
                   or any(n.endswith(s) for s in consumed_suffixes))
    duplicate = _duplicate_bytes(files, c)
    unused = input_bytes - relevant
    ratio = round(unused / input_bytes, 4) if input_bytes else 0.0
    return {
        "schema": "platformforge/context-audit/v1",
        "case": c.id, "tier": c.tier,
        "input_bytes": input_bytes,
        "relevant_bytes": relevant,
        "unused_bytes": unused,
        "retrieval_count": len(files),
        "duplicate_bytes": duplicate,
        "unused_context_ratio": ratio,
        "strategies": _strategies(input_bytes, relevant, files),
        "note": "relevant bytes are files the case's analyzers read — "
                "graph-aware context ≈ relevant-only; full context = "
                "everything (§79 comparison)"}


def _consumed(c: CaseFile) -> tuple[str, ...]:
    """File suffixes each analyzer reads (mirrors lab/runner._FILE_INPUTS
    plus the whole-tree analyzers)."""
    file_inputs = {"iam": ("policy.json",), "supply": ("supply.json",),
                   "finops": ("costs.json",), "plan": ("plan.json",),
                   "state": ("state.json",), "cosign": ("sig.json",),
                   "sbom": ("sbom.json",), "slsa": ("slsa.json",),
                   "slo": ("slo.yaml", "events.yaml"),
                   "capacity": ("capacity.json",),
                   # secrets scans arbitrary file types (.env, .pem, …)
                   "secrets": ("*",)}
    out: list[str] = []
    for dom in c.analyzers:
        out += list(file_inputs.get(dom, ()))
    # whole-tree analyzers consume yaml/json/tf/manifests
    if not out:
        out = [".yaml", ".yml", ".json", ".tf", ".hcl"]
    return tuple(out)


def _duplicate_bytes(files: dict[str, int], c: CaseFile) -> int:
    from platformforge.cases.replay import _fixture_dir
    d = _fixture_dir(c)
    seen: dict[str, int] = {}
    dup = 0
    for rel, size in files.items():
        p = d / rel
        try:
            h = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
        if h in seen:
            dup += size
        seen[h] = size
    return dup


def _strategies(full: int, relevant: int,
                files: dict[str, int]) -> dict[str, Any]:
    """§79 — the four context strategies scored on bytes for this case.
    delta context assumes a prior run shipped the unchanged files;
    measured as 'only changed files' — here all files change on first
    run so delta == relevant."""
    return {
        "full": {"bytes": full},
        "graph_aware": {"bytes": relevant,
                        "savings_bytes": full - relevant},
        "tokensave": {"bytes": relevant,
                      "note": "TokenSave retrieval == relevant file set "
                              "for analyzer-scoped tasks"},
        "delta": {"bytes": relevant,
                  "note": "first run — no previous pack hash; savings "
                          "only measurable on re-runs"}}


def audit_corpus(root: str | Path = ".platformforge/cases"
                 ) -> dict[str, Any]:
    cases = discover_cases(root)
    audits = [audit_case(c) for c in cases]
    tot_in = sum(a["input_bytes"] for a in audits)
    tot_rel = sum(a["relevant_bytes"] for a in audits)
    avg_ratio = round(sum(a["unused_context_ratio"] for a in audits)
                      / len(audits), 4) if audits else 0.0
    return {"schema": "platformforge/context-audit-corpus/v1",
            "cases": audits, "totals": {
                "input_bytes": tot_in, "relevant_bytes": tot_rel,
                "unused_bytes": tot_in - tot_rel,
                "avg_unused_context_ratio": avg_ratio},
            "note": "economy changes that cut bytes while raising "
                    "false negatives are rejected (§80) — the replay "
                    "gate grades correctness, this audit grades cost"}


def write_back(c: CaseFile, audit: dict[str, Any]) -> None:
    """Stamp measured context_cost into the case.yaml (§54 field)."""
    import yaml
    doc = yaml.safe_load(c.path.read_text()) or {}
    doc["context_cost"] = {
        "input_bytes": audit["input_bytes"],
        "relevant_bytes": audit["relevant_bytes"],
        "unused_context_ratio": audit["unused_context_ratio"],
        "duplicate_bytes": audit["duplicate_bytes"]}
    c.path.write_text(yaml.safe_dump(doc, sort_keys=False,
                                     allow_unicode=True))
