"""Tool dispatch — same core as the CLI, output bounded by capability.

Oversized results are written to the artifact store and returned as a
reference + summary instead of a wall of text (MCP output stays bounded)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.core.store import ArtifactStore
from platformforge.mcp.registry import CAPABILITIES


def _dispatch(handler: str, inp: dict[str, Any], repo: str) -> Any:
    """Resolve handler to the same functions cmd_* use."""
    if handler == "cli:inspect":
        from platformforge.cli.main import cmd_inspect
        import argparse
        ns = argparse.Namespace(repo=inp.get("repo", repo), format="json",
                                strict=False)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_inspect(ns)
        return json.loads(buf.getvalue())
    if handler == "cli:analyze":
        return _analyze(inp.get("domain"), inp.get("path"))
    if handler == "cli:judge":
        from platformforge.models import Fact
        from platformforge.rules import RuleEngine, load_catalog
        doc = json.loads(Path(inp["facts_path"]).read_text())
        facts = [Fact.from_dict(f) for f in doc.get("facts", doc)]
        rules = load_catalog(Path(repo).parent / "rules" / "catalog"
                             if (Path(repo).parent / "rules").exists()
                             else _default_catalog())
        findings, skipped = RuleEngine(rules).evaluate(facts)
        return {"findings": [f.to_dict() for f in findings],
                "skipped": skipped}
    if handler == "cli:graph":
        return _graph(inp, repo)
    if handler == "cli:observe_slo":
        from platformforge.observe import SloContract, error_budget
        c = SloContract.load(inp["contract"])
        return error_budget(c, **(inp.get("sli") or {}))
    if handler == "cli:economy":
        from platformforge.economy import EconomyEngine
        return EconomyEngine(repo).report()
    if handler == "cli:product_maturity":
        from platformforge.product import maturity
        return maturity(inp["signals"])
    if handler == "cli:agents_list":
        from platformforge.agents import AGENTS
        return {"agents": [a.to_dict() for a in AGENTS.values()]}
    raise ValueError(f"no handler {handler}")


def _default_catalog() -> Path:
    return Path(__file__).resolve().parents[2] / "rules" / "catalog"


def _analyze(domain: str, path: str) -> Any:
    if domain in ("iac",):
        from platformforge.iac import analyze_hcl
        return analyze_hcl(path)
    if domain == "plan":
        from platformforge.iac import analyze_plan
        return analyze_plan(path)
    if domain == "state":
        from platformforge.iac import analyze_state
        return analyze_state(path)
    if domain == "k8s":
        from platformforge.k8s import analyze_k8s
        return analyze_k8s(path)
    if domain == "gitops":
        from platformforge.cicd import analyze_gitops
        return analyze_gitops(path)
    if domain == "gha":
        from platformforge.cicd import analyze_gha
        return analyze_gha(path)
    if domain == "iam":
        from platformforge.security import analyze_iam_policy
        return analyze_iam_policy(path)
    if domain == "sbom":
        from platformforge.security import analyze_sbom
        return analyze_sbom(path)
    if domain == "secrets":
        from platformforge.security import scan_secrets
        return scan_secrets(path)
    if domain == "supply":
        from platformforge.security import analyze_supply
        return analyze_supply(path)
    if domain == "catalog":
        from platformforge.product import analyze_catalog
        return analyze_catalog(path)
    if domain == "crossplane":
        from platformforge.product import analyze_crossplane
        return analyze_crossplane(path)
    raise ValueError(f"unknown domain {domain}")


def _graph(inp: dict[str, Any], repo: str) -> Any:
    from platformforge import graph as G
    g = G.load(repo)
    q = inp["query"]
    if q == "deps":
        return G.dependencies(g, inp["node"])
    if q == "dependents":
        return G.dependents(g, inp["node"])
    if q == "blast":
        return G.blast_radius(g, inp["node"])
    if q == "paths":
        return G.paths(g, inp["src"], inp["dst"])
    if q == "gaps":
        return G.gaps(g)
    if q == "cycles":
        return {"cycles": G.cycles(g)}
    if q == "stats":
        return g.stats()
    raise ValueError(f"unknown graph query {q}")


def _bound(result: Any, cap, repo: str) -> dict[str, Any]:
    """Enforce output bounds; oversize → artifact ref."""
    text = json.dumps(result, default=str)
    if len(text.encode()) <= cap.max_bytes:
        return {"result": result, "bounded": False}
    store = ArtifactStore(repo)
    sha = store.put(text.encode(), meta={"kind": "mcp-result"})
    ref = f"artifact://sha256/{sha}"
    summary = result
    if isinstance(result, dict):
        summary = {k: v for k, v in result.items()
                   if not isinstance(v, (list, dict)) or len(
                       json.dumps(v, default=str)) < 2000}
    return {"bounded": True,
            "artifact_ref": ref,
            "summary": summary,
            "note": f"result exceeded {cap.max_bytes}B — full output "
                    f"in artifact store"}


def call_tool(name: str, arguments: dict[str, Any] | None = None,
              repo: str = ".") -> dict[str, Any]:
    cap = CAPABILITIES.get(name)
    if not cap:
        return {"error": "platform.tool.unresolved",
                "unlock": "tools/list — unknown tool", "tool": name}
    inp = dict(arguments or {})
    detail = inp.pop("detail_level", "normal")
    if detail not in cap.detail_levels:
        detail = "normal"
    try:
        result = _dispatch(cap.handler, inp, repo)
    except FileNotFoundError as e:
        return {"refusal": "platform.evidence.unresolved",
                "detail": str(e), "tool": name}
    except Exception as e:  # bounded error, never traceback over MCP
        return {"error": type(e).__name__, "detail": str(e)[:500],
                "tool": name}
    out = _bound(result, cap, repo)
    out["detail_level"] = detail
    return out
