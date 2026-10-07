"""Sandboxed change verification — copy repository → apply patch →
analyze before/after → compare findings and graph.

Read-only contract: the original tree is opened read-only; all writes go
to a temp copy under .platformforge/sandbox/ (or tmp)."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Sandbox:
    root: Path
    workdir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.workdir = Path(tempfile.mkdtemp(prefix="pf-sandbox-"))

    def __enter__(self) -> Sandbox:  # noqa: PYI034 - typing.Self is 3.11+; no typing_extensions dep
        return self

    def __exit__(self, *exc) -> None:
        self.destroy()

    def copy(self) -> Path:
        dst = self.workdir / "repo"
        ignore = shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".platformforge",
            "node_modules", "graphify-out")
        shutil.copytree(self.root, dst, ignore=ignore)
        return dst

    def apply_patch(self, patch_text: str, dst: Path) -> dict[str, Any]:
        """Apply a unified diff via `patch` if present, else fail closed."""
        patch_file = self.workdir / "change.patch"
        patch_file.write_text(patch_text)
        import subprocess
        r = subprocess.run(["patch", "-p1", "-d", str(dst), "-i",
                            str(patch_file)],
                           capture_output=True, text=True, check=False)
        return {"applied": r.returncode == 0, "stdout": r.stdout[-2000:],
                "stderr": r.stderr[-2000:]}

    def write_file(self, rel: str, content: str, dst: Path) -> Path:
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def destroy(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


def _analyze_tree(tree: Path, analyzers: dict[str, Any]) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    errors = []
    for dom, fn in analyzers.items():
        try:
            facts += fn(str(tree))["facts"]
        except Exception as e:  # noqa: BLE001 — analyzer failure is data
            errors.append(f"{dom}: {e}")
    return {"facts": facts, "errors": errors}


def _default_analyzers() -> dict[str, Any]:
    from platformforge.cicd import analyze_gha
    from platformforge.iac import analyze_hcl
    from platformforge.k8s import analyze_k8s
    return {"iac": analyze_hcl, "k8s": analyze_k8s, "gha": analyze_gha}


def sandbox_analyze(repo: str | Path,
                    patch: str | None = None,
                    files: dict[str, str] | None = None,
                    analyzers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full §86 loop: copy → apply → analyze before/after → compare."""
    analyzers = analyzers or _default_analyzers()
    before = _analyze_tree(Path(repo), analyzers)
    with Sandbox(repo) as sb:
        dst = sb.copy()
        applied = {}
        if patch:
            applied = sb.apply_patch(patch, dst)
            if not applied["applied"]:
                return {"refusal": "platform.sandbox.patch_failed",
                        "detail": applied["stderr"], "before": before}
        for rel, content in (files or {}).items():
            sb.write_file(rel, content, dst)
        after = _analyze_tree(dst, analyzers)
    return {"before": before, "after": after,
            "delta": compare_runs(before, after), "applied": applied,
            "semantic": semantic_delta(before, after)}


def compare_runs(before: dict[str, Any],
                 after: dict[str, Any]) -> dict[str, Any]:
    """Fact-kind and rule-facing delta between two analyzer outputs."""
    def kinds(run):
        out: dict[str, int] = {}
        for f in run["facts"]:
            out[f["kind"]] = out.get(f["kind"], 0) + 1
        return out
    kb, ka = kinds(before), kinds(after)
    added = {k: ka[k] for k in ka if k not in kb}
    removed = {k: kb[k] for k in kb if k not in ka}
    changed = {k: {"before": kb[k], "after": ka[k]}
               for k in ka if k in kb and ka[k] != kb[k]}
    ids_b = {f["fact_id"] for f in before["facts"]}
    ids_a = {f["fact_id"] for f in after["facts"]}
    return {"fact_kinds_added": added, "fact_kinds_removed": removed,
            "fact_kinds_changed_count": changed,
            "facts_added": len(ids_a - ids_b),
            "facts_removed": len(ids_b - ids_a)}


def semantic_delta(before: dict[str, Any], after: dict[str, Any]
                   ) -> dict[str, Any]:
    """§106 — graph-aware delta: build graphs from both runs, diff
    semantically, score the risk change. Never returns just a count."""
    from platformforge.graph.build import GraphBuilder
    from platformforge.graph.diff import diff as graph_diff
    try:
        gb = GraphBuilder().from_facts(before["facts"]).graph
        ga = GraphBuilder().from_facts(after["facts"]).graph
        gdiff = graph_diff(gb, ga)
    except Exception as exc:  # noqa: BLE001 — delta failure is data
        return {"graph_diff": None, "error": str(exc)}
    # risk delta: new security/exposure edges vs removed ones
    exposure = (gdiff.get("semantic") or {}).get("exposure") or {}
    sec = (gdiff.get("semantic") or {}).get("security") or {}
    return {"graph_diff": gdiff,
            "exposure_added": any(e.startswith("+")
                                  for e in exposure.get("edge_changes", [])),
            "security_edges_changed": sec.get("changed", False),
            "nodes_added": len(gdiff.get("nodes_added") or []),
            "nodes_removed": len(gdiff.get("nodes_removed") or []),
            "note": "semantic delta over graph, not just fact counts"}
