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
        import argparse

        from platformforge.cli.main import cmd_inspect
        ns = argparse.Namespace(repo=inp.get("repo", repo), format="json",
                                strict=False)
        import contextlib
        import io
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
    if handler == "cli:collect":
        from platformforge.collect import collect
        return collect(inp["path"])
    if handler == "cli:diagnose":
        from platformforge import graph as G
        from platformforge.diagnose import diagnose
        g = G.load(repo)
        findings = json.loads(Path(inp["findings"]).read_text()) \
            if inp.get("findings") else []
        facts = json.loads(Path(inp["facts"]).read_text()) \
            if inp.get("facts") else []
        return diagnose(g, inp["node"],
                        findings.get("findings", findings),
                        facts.get("facts", facts))
    if handler == "cli:plan":
        from platformforge.plan import remediation_plan
        doc = json.loads(Path(inp["findings_path"]).read_text())
        findings = doc.get("findings", doc if isinstance(doc, list) else [])
        facts = doc.get("facts", [])
        try:
            from platformforge import graph as G
            g = G.load(repo)
        except FileNotFoundError:
            g = None
        return remediation_plan(findings, g, facts)
    if handler == "cli:risk":
        from platformforge.risk.engine import assess_change
        signals = dict(inp.get("signals") or {})
        if inp.get("node"):
            from platformforge import graph as G
            from platformforge.graph.query import blast_radius
            from platformforge.risk.signals import signals_from_graph
            g = G.load(repo)
            blast = blast_radius(g, inp["node"])
            signals = {**signals_from_graph(g, [inp["node"]], blast),
                       **signals}
        return assess_change(signals)
    if handler == "cli:explain":
        doc = json.loads(Path(inp["findings_path"]).read_text())
        findings = doc.get("findings", doc if isinstance(doc, list) else [])
        f = next((x for x in findings
                  if x.get("finding_id") == inp["name"]
                  or x.get("rule_id") == inp["name"]), None)
        if not f:
            return {"refusal": "platform.finding.unresolved",
                    "name": inp["name"]}
        facts = json.loads(Path(inp["facts_path"]).read_text()) \
            if inp.get("facts_path") else doc.get("facts", [])
        by_id = {x.get("fact_id"): x
                 for x in (facts.get("facts", facts)
                           if isinstance(facts, dict) else facts)}
        return {"finding": f,
                "evidence_chain": [{"fact_id": e,
                                    "fact": by_id.get(e, "unresolved")}
                                   for e in f.get("evidence", [])]}
    if handler == "cli:recommend":
        import argparse
        import contextlib
        import io

        from platformforge.cli.main import cmd_recommend
        ns = argparse.Namespace(path=inp["findings_path"], format="json",
                                strict=False, repo=repo, output=None,
                                detail_level="normal", offline=False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_recommend(ns)
        return json.loads(buf.getvalue())
    if handler == "cli:security":
        import argparse
        import contextlib
        import io

        from platformforge.cli.main import cmd_security
        ns = argparse.Namespace(path=inp["path"], repo=repo, format="json",
                                strict=False, output=None,
                                detail_level="normal", offline=False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_security(ns)
        return json.loads(buf.getvalue())
    if handler == "cli:reliability":
        import argparse
        import contextlib
        import io

        from platformforge.cli.main import cmd_reliability
        ns = argparse.Namespace(path=inp["facts_path"], repo=repo,
                                format="json", strict=False, output=None,
                                detail_level="normal", offline=False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_reliability(ns)
        return json.loads(buf.getvalue())
    if handler == "cli:drift":
        from platformforge.iac import analyze_hcl, analyze_state, drift
        return drift(analyze_hcl(inp["config"])["facts"],
                     analyze_state(inp["state"])["facts"])
    if handler == "cli:change_verify":
        from platformforge.sandbox import sandbox_analyze
        return sandbox_analyze(inp["root"], patch=inp.get("patch"),
                               files=inp.get("files"))
    if handler == "cli:change_review":
        from platformforge.sandbox import review_change
        return review_change(inp["root"], patch=inp.get("patch"),
                             files=inp.get("files"),
                             signals=inp.get("signals"))
    if handler == "cli:finops":
        from platformforge import finops as F
        sub = inp.get("op", "costs")
        if sub == "costs":
            doc = F.cost_facts(inp["path"])
            return {**doc, "summary": F.cost_summary(doc["facts"])}
        if sub == "allocate":
            return F.allocate(F.cost_facts(inp["path"])["facts"],
                              by=inp.get("by", "cost_center"))
        if sub == "focus":
            rows = json.loads(Path(inp["path"]).read_text())
            return F.to_focus(rows if isinstance(rows, list)
                              else rows.get("rows", []))
        if sub == "focus-validate":
            rows = json.loads(Path(inp["path"]).read_text())
            return F.validate_focus(rows if isinstance(rows, list)
                                    else rows.get("rows", []))
        if sub == "unit":
            doc = F.cost_facts(inp["path"])
            return F.unit_economics(doc["facts"],
                                    inp.get("denominators") or {})
        if sub == "ingest":
            return F.ingest_billing(inp["path"])
        if sub == "report":
            doc = F.cost_facts(inp["path"])
            extra = inp.get("denominators") or {}
            return F.finops_report(
                doc["facts"], utilization=extra.get("utilization"),
                requested_vs_used=extra.get("requested_vs_used"),
                committed=extra.get("committed"),
                split=extra.get("split"))
        raise ValueError(f"unknown finops op {sub}")
    if handler == "cli:observe":
        return _observe(inp)
    if handler == "cli:evals":
        from platformforge.evals import run_all
        return run_all(inp["cases"] if inp.get("cases") else
                       __import__("platformforge.evals.runner",
                                  fromlist=["CASES_DIR"]).CASES_DIR,
                       type_filter=inp.get("type") or None)
    if handler == "cli:lab_chaos":
        from platformforge.lab.chaos import run_scenario
        return run_scenario(inp["scenario"],
                            allow_prod=bool(inp.get("allow_prod")))
    if handler == "cli:correlate":
        from platformforge import observe as O
        return O.correlate_spans(inp["path"])
    if handler == "cli:policy":
        from platformforge.rules import load_catalog
        rules = load_catalog(_default_catalog())
        if inp["op"] == "list":
            return {"rules": [{"rule_id": r.rule_id, "domain": r.domain,
                               "severity": r.severity} for r in rules]}
        from platformforge.models import Fact
        from platformforge.rules import RuleEngine
        doc = json.loads(Path(inp["facts_path"]).read_text())
        facts = [Fact.from_dict(f)
                 for f in doc.get("facts", doc if isinstance(doc, list)
                                  else [])]
        findings, skipped = RuleEngine(rules).evaluate(facts)
        return {"findings": [f.to_dict() for f in findings],
                "skipped": skipped,
                "violated": [f.rule_id for f in findings
                             if f.status == "violated"]}
    if handler == "cli:integrate":
        from platformforge.mcp.parity import detach, integrate
        return detach(inp["host"], repo) if inp.get("detach") \
            else integrate(inp["host"], repo)
    if handler == "cli:capability":
        from platformforge.forge import capability_manifest
        return capability_manifest()
    raise ValueError(f"no handler {handler}")


def _observe(inp: dict[str, Any]) -> Any:
    """Observe sub-verbs — same functions cmd_observe calls."""
    from platformforge import observe as O
    sub = inp.get("op", "slo-burn")
    if sub == "slo":
        c = O.SloContract.load(inp["contract"])
        return O.error_budget(c, **(inp.get("sli") or {}))
    if sub == "slo-burn":
        c = O.SloContract.load(inp["contract"])
        return O.multi_window_burn(c, inp.get("windows") or {})
    if sub == "otel":
        return O.correlate_spans(inp["path"])
    if sub == "semconv":
        return O.analyze_semconv(inp["path"])
    if sub == "timeline":
        return O.timeline(json.loads(Path(inp["path"]).read_text()))
    if sub == "postmortem":
        inc = json.loads(Path(inp["incident"]).read_text())
        return O.postmortem(inc, inc.get("hypotheses"))
    if sub == "dr":
        doc = json.loads(Path(inp["facts"]).read_text())
        return O.dr_model(doc.get("facts", doc))
    if sub == "prometheus":
        return O.analyze_prometheus(inp["path"])
    if sub == "grafana":
        return O.analyze_grafana(inp["path"])
    if sub == "incident":
        alerts = json.loads(Path(inp["alerts"]).read_text())
        changes = json.loads(Path(inp["changes"]).read_text())
        return O.correlate(alerts, changes,
                           window_s=int(inp.get("window", 3600)))
    if sub == "capacity":
        items = json.loads(Path(inp["path"]).read_text())
        return O.capacity(items)
    raise ValueError(f"unknown observe op {sub}")


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
    if domain == "helm":
        from platformforge.k8s.helm import analyze_helm
        return analyze_helm(path)
    if domain == "kustomize":
        from platformforge.k8s.helm import analyze_kustomize
        return analyze_kustomize(path)
    if domain == "hubble":
        from platformforge.k8s.hubble import analyze_hubble
        return analyze_hubble(path)
    if domain == "kyverno":
        from platformforge.security.kyverno import analyze_kyverno
        return analyze_kyverno(path)
    if domain == "cosign":
        from platformforge.security.cosign import analyze_cosign
        return analyze_cosign(path)
    if domain == "slsa":
        from platformforge.security.slsa import slsa_assess
        doc = json.loads(Path(path).read_text())
        return slsa_assess(doc.get("provenance", doc),
                           evidence=doc.get("evidence")
                           if isinstance(doc, dict) else None)
    if domain == "cloud-aws":
        from platformforge.cloud import analyze_aws_dump
        return analyze_aws_dump(path)
    if domain == "cloud-azure":
        from platformforge.cloud import analyze_azure_dump
        return analyze_azure_dump(path)
    if domain == "cloud-gcp":
        from platformforge.cloud import analyze_gcp_dump
        return analyze_gcp_dump(path)
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
    if q.startswith("identity"):
        from platformforge.security.identity import (
            compromise_blast,
            who_can_access,
            who_can_become,
            workloads_using_identity,
        )
        target = inp.get("node") or inp.get("dst") or inp.get("src")
        fn = {"identity-become": who_can_become,
              "identity-access": who_can_access,
              "identity-workloads": workloads_using_identity,
              "identity-blast": compromise_blast}.get(q)
        if not fn:
            raise ValueError(f"unknown graph query {q}")
        return fn(g, target)
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
    except Exception as e:  # noqa: BLE001 — bounded error, never traceback over MCP
        return {"error": type(e).__name__, "detail": str(e)[:500],
                "tool": name}
    out = _bound(result, cap, repo)
    out["detail_level"] = detail
    return out
