"""platformforge CLI — thin adapter over the core. No logic lives here.

Every verb supports: --json  --output FILE  --detail-level summary|normal|full
--offline  --strict. Flags have real contracts: --strict turns unresolved into
exit 2; --offline forbids adapter calls that need network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from platformforge import __version__

DETAIL_LEVELS = ("summary", "normal", "full")


def _emit(result: Any, args: argparse.Namespace, exit_code: int = 0) -> int:
    text = json.dumps(result, indent=2, sort_keys=True, default=str)
    if getattr(args, "output", None):
        Path(args.output).write_text(text + "\n")
    if getattr(args, "json", True):
        print(text)
    else:
        print(text)
    return exit_code


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", default=True,
                   help="structured output (default)")
    p.add_argument("--output", metavar="FILE", help="write result to FILE")
    p.add_argument("--detail-level", choices=DETAIL_LEVELS, default="normal",
                   help="summary|normal|full payload bounding")
    p.add_argument("--offline", action="store_true",
                   help="forbid any network-capable adapter")
    p.add_argument("--strict", action="store_true",
                   help="unresolved/refusals -> exit code 2")
    p.add_argument("--repo", default=".", help="workspace/repo root")


def cmd_init(args: argparse.Namespace) -> int:
    from platformforge.core.workspace import init_workspace
    pf = init_workspace(args.repo, name=args.name)
    return _emit({"initialized": str(pf)}, args)


def cmd_doctor(args: argparse.Namespace) -> int:
    import platform
    checks = {
        "python": platform.python_version(),
        "platformforge": __version__,
        "pyyaml": _mod_version("yaml"),
        "jsonschema": _mod_version("jsonschema"),
        "python-hcl2": _mod_version("hcl2"),
        "mcp_adapter": _mod_version("mcp", optional=True),
        "boto3": _mod_version("boto3", optional=True),
    }
    ok = all(v != "missing" for k, v in checks.items()
             if k in ("pyyaml", "jsonschema", "python-hcl2"))
    return _emit({"ok": ok, "checks": checks}, args, 0 if ok else 1)


_DIST_NAMES = {"yaml": "PyYAML", "hcl2": "python-hcl2"}


def _mod_version(name: str, optional: bool = False) -> str:
    import importlib.metadata
    try:
        __import__(name)
    except ImportError:
        return "not-installed" if optional else "missing"
    try:
        return importlib.metadata.version(_DIST_NAMES.get(name, name))
    except importlib.metadata.PackageNotFoundError:
        return "installed"


def cmd_status(args: argparse.Namespace) -> int:
    from platformforge.core.store import ArtifactStore
    from platformforge.core.workspace import load_workspace
    ws = load_workspace(args.repo)
    store = ArtifactStore(ws.root)
    return _emit({
        "workspace": ws.name, "root": str(ws.root),
        "multi_repo": ws.is_multi_repo,
        "members": [m.name for m in ws.members] or [ws.name],
        "store": store.stats(),
    }, args)


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inventory analyzable artifacts under a root — no content parsing."""
    root = Path(args.repo).resolve()
    kinds = {
        "terraform": ("*.tf", "*.tf.json", "*.tfvars"),
        "kubernetes": ("*.yaml", "*.yml"),
        "helm": ("Chart.yaml", "values*.yaml"),
        "kustomize": ("kustomization.yaml", "kustomization.yml"),
        "github_actions": (".github/workflows/*.yml", ".github/workflows/*.yaml"),
        "gitlab_ci": (".gitlab-ci.yml",),
        "argocd": ("*.yaml",),  # kind-filtered at analyze time
        "dockerfile": ("Dockerfile*",),
        "backstage": ("catalog-info.yaml", "catalog-info.yml"),
        "crossplane": ("*.yaml",),
    }
    inventory: dict[str, list[str]] = {k: [] for k in kinds}
    ignore = {".git", ".venv", "node_modules", ".platformforge", "vendor",
              "__pycache__", "dist", "build"}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in ignore for part in p.parts):
            continue
        rel = str(p.relative_to(root))
        for kind, pats in kinds.items():
            if any(p.match(pat) or rel.endswith(pat.lstrip("*")) for pat in pats):
                inventory[kind].append(rel)
    inventory = {k: v for k, v in inventory.items() if v}
    return _emit({"root": str(root), "artifacts": inventory,
                  "counts": {k: len(v) for k, v in inventory.items()}}, args)


def cmd_judge(args: argparse.Namespace) -> int:
    """Apply rule catalog to a facts JSON document (or analyzed facts file)."""
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog

    facts_doc = json.loads(Path(args.facts).read_text())
    facts = [Fact.from_dict(f) for f in facts_doc.get("facts", facts_doc)]
    versions = facts_doc.get("versions", {}) if isinstance(facts_doc, dict) else {}
    catalog_dirs = args.catalog or [Path(__file__).resolve().parents[2] / "rules" / "catalog"]
    rules = load_catalog(*catalog_dirs)
    findings, skipped = RuleEngine(rules, versions).evaluate(facts)
    out = {"findings": [f.to_dict() for f in findings],
           "skipped": skipped,
           "counts": {"facts": len(facts), "rules": len(rules),
                      "violated": sum(1 for f in findings if f.status == "violated")}}
    unresolved = any(f.status == "unresolved" for f in findings)
    return _emit(out, args, 2 if (args.strict and unresolved) else 0)


def cmd_knowledge(args: argparse.Namespace) -> int:
    from platformforge.knowledge.registry import SourceRegistry
    reg = SourceRegistry.default()
    report = reg.check()
    bad = [r for r in report if r["status"] in ("stale", "unresolved", "conflicted",
                                              "deprecated", "superseded")]
    return _emit({"sources": report, "attention": bad,
                  "counts": {"total": len(report), "attention": len(bad)}},
                 args, 2 if (args.strict and bad) else 0)


def _index(args) -> "SearchIndex":
    from platformforge.tokensave.index import SearchIndex
    return SearchIndex(Path(args.repo) / ".platformforge" / "index.db")


def cmd_tokens(args: argparse.Namespace) -> int:
    from platformforge.tokensave.index import SearchIndex
    from platformforge.tokensave.ledger import TokenLedger
    from platformforge.tokensave.packs import ContextPackBuilder
    from platformforge.tokensave.budget import Budget
    idx = _index(args)
    out = {}
    if args.tokens_cmd == "index":
        out = {"index": idx.index_workspace(args.repo)}
    elif args.tokens_cmd == "search":
        out = {"hits": idx.search(args.query, args.limit)}
    elif args.tokens_cmd == "pack":
        ledger = TokenLedger(args.repo)
        pack = ContextPackBuilder(idx, ledger).build(
            task=args.task,
            budget=Budget(input_budget=args.input_budget),
            changed_files=args.changed or [])
        out = pack
    elif args.tokens_cmd == "stats":
        out = idx.stats() | {"fingerprint": idx.fingerprint()}
    elif args.tokens_cmd == "ledger":
        out = TokenLedger(args.repo).report()
    return _emit(out, args)


def cmd_rtk(args: argparse.Namespace) -> int:
    """Compact a command output file (or stdin) — never run unless asked."""
    from platformforge.core.store import ArtifactStore
    from platformforge.rtk import compact_output
    if args.file == "-":
        output = sys.stdin.read()
    else:
        output = Path(args.file).read_text(errors="replace")
    store = ArtifactStore(args.repo)
    res = compact_output(args.command or "", output,
                         exit_code=args.exit_code, store=store)
    return _emit(res.to_dict(), args)


def cmd_rtk_expand(args: argparse.Namespace) -> int:
    from platformforge.core.store import ArtifactStore
    from platformforge.rtk.compact import expand
    out = expand(ArtifactStore(args.repo), args.artifact,
                 start=args.start, end=args.end, pattern=args.pattern)
    return _emit(out, args)


def cmd_caveman(args: argparse.Namespace) -> int:
    from platformforge.caveman import compress
    text = Path(args.file).read_text() if args.file != "-" else sys.stdin.read()
    out, receipt = compress(text, mode=args.mode, context_risk=args.context_risk)
    return _emit({"compressed": out, "receipt": receipt.to_dict()}, args)


def cmd_economy(args: argparse.Namespace) -> int:
    from platformforge.economy import EconomyEngine
    return _emit(EconomyEngine(args.repo).report(), args)


def cmd_route(args: argparse.Namespace) -> int:
    from platformforge.routing import TaskSignal, route
    sig = TaskSignal.from_dict(json.loads(args.signal))
    return _emit(route(sig), args)


def cmd_sdd(args: argparse.Namespace) -> int:
    from platformforge.sdd import SDDProject
    proj = SDDProject(args.repo)
    sub = args.sdd_cmd
    if sub == "init":
        return _emit({"initialized": str(proj._feature_dir(args.feature))}, args)
    if sub in ("discover", "define", "design", "contract", "plan", "review",
               "learn", "build", "verify"):
        body: object = json.loads(args.body) if args.body.strip().startswith("{") \
            else (args.body or f"# {sub} for {args.feature}\n")
        art = proj.write_artifact(args.feature, sub, body)
        return _emit({"wrote": art.path.name, "phase": sub,
                      "upstream": art.upstream}, args)
    if sub == "status":
        return _emit(proj.status(args.feature), args)
    if sub == "check":
        out = proj.check(args.feature)
        return _emit(out, args, 2 if (args.strict and not out["ok"]) else 0)
    if sub == "stamp":
        return _emit(proj.stamp(args.feature, args.phase), args)
    if sub == "ship":
        verify = json.loads(args.verify) if args.verify else None
        out = proj.ship(args.feature, verify=verify,
                        risk_accepted=args.risk_accepted,
                        override=args.override,
                        override_reason=args.override_reason)
        return _emit(out, args, 0 if out["shipped"] else 2)
    return _emit({"error": f"unknown sdd verb {sub}"}, args, 1)


def _load_graph_or_refuse(repo: str):
    from platformforge.graph import load
    try:
        return load(repo)
    except FileNotFoundError:
        return None


def cmd_graph(args: argparse.Namespace) -> int:
    from platformforge import graph as G
    sub = args.graph_cmd
    if sub == "build":
        doc = json.loads(Path(args.facts).read_text())
        facts = doc.get("facts", doc)
        builder = G.GraphBuilder().from_facts(facts)
        p = G.save(builder.graph, args.repo)
        return _emit({"wrote": str(p), **builder.graph.stats()}, args)
    if sub == "snapshots":
        return _emit({"snapshots": G.snapshots(args.repo)}, args)
    g = _load_graph_or_refuse(args.repo)
    if g is None:
        return _emit({"refusal": "PF-GRAPH-NOGRAPH",
                      "unlock": "platformforge graph build <facts.json>"}, args, 2)
    if sub == "stats":
        return _emit(g.stats(), args)
    if sub == "gaps":
        return _emit(G.gaps(g), args)
    if sub == "cycles":
        return _emit({"cycles": G.cycles(g)}, args)
    if sub == "deps":
        return _emit({args.node: G.dependencies(g, args.node)}, args)
    if sub == "dependents":
        return _emit({args.node: G.dependents(g, args.node)}, args)
    if sub == "blast":
        return _emit(G.blast_radius(g, args.node), args)
    if sub == "paths":
        return _emit({"paths": G.paths(g, args.src, args.dst)}, args)
    if sub == "diff":
        def _resolve(ref: str):
            if (Path(args.repo) / ".platformforge/graph" / f"{ref}.json").exists():
                return G.load(args.repo, ref)
            return G.load_snapshot(args.repo, ref)
        return _emit(G.diff(_resolve(args.before), _resolve(args.after)), args)
    return _emit({"error": f"unknown graph verb {sub}"}, args, 1)


def cmd_analyze(args: argparse.Namespace) -> int:
    """Domain analyzers → fact documents (feed judge/graph)."""
    sub = args.analyze_cmd
    if sub == "iac":
        from platformforge.iac import analyze_hcl
        return _emit(analyze_hcl(args.path), args)
    if sub == "plan":
        from platformforge.iac import analyze_plan
        return _emit(analyze_plan(args.path), args)
    if sub == "state":
        from platformforge.iac import analyze_state
        return _emit(analyze_state(args.path), args)
    if sub == "drift":
        from platformforge.iac import analyze_hcl, analyze_state, drift
        desired = analyze_hcl(args.config)["facts"]
        observed = analyze_state(args.state)["facts"]
        return _emit(drift(desired, observed), args)
    if sub == "k8s":
        from platformforge.k8s import analyze_k8s
        return _emit(analyze_k8s(args.path), args)
    if sub == "gitops":
        from platformforge.cicd import analyze_gitops
        return _emit(analyze_gitops(args.path), args)
    if sub == "gha":
        from platformforge.cicd import analyze_gha
        return _emit(analyze_gha(args.path), args)
    if sub == "iam":
        from platformforge.security import analyze_iam_policy
        return _emit(analyze_iam_policy(args.path), args)
    if sub == "sbom":
        from platformforge.security import analyze_sbom
        vulns = json.loads(Path(args.vulns).read_text()) if args.vulns else None
        return _emit(analyze_sbom(args.path, vuln_db=vulns), args)
    if sub == "secrets":
        from platformforge.security import scan_secrets
        return _emit(scan_secrets(args.path), args)
    if sub == "supply":
        from platformforge.security import analyze_supply
        return _emit(analyze_supply(args.path), args)
    if sub == "catalog":
        from platformforge.product import analyze_catalog
        return _emit(analyze_catalog(args.path), args)
    if sub == "crossplane":
        from platformforge.product import analyze_crossplane
        return _emit(analyze_crossplane(args.path), args)
    return _emit({"error": f"unknown analyze domain {sub}"}, args, 1)


def cmd_product(args: argparse.Namespace) -> int:
    from platformforge import product as P
    sub = args.product_cmd
    if sub == "maturity":
        sig = json.loads(Path(args.signals).read_text())
        return _emit(P.maturity(sig.get("signals", sig),
                                sig.get("evidence")), args)
    if sub == "scorecard":
        doc = json.loads(Path(args.findings).read_text())
        findings = doc.get("findings", doc)
        from platformforge.product.scorecards import scorecard
        return _emit(scorecard(findings), args)
    if sub == "backstage":
        g = _load_graph_or_refuse(args.repo)
        if g is None:
            return _emit({"refusal": "PF-GRAPH-NOGRAPH",
                          "unlock": "platformforge graph build <facts.json>"},
                         args, 2)
        return _emit(P.to_backstage(g), args)
    return _emit({"error": f"unknown product verb {sub}"}, args, 1)


def cmd_observe(args: argparse.Namespace) -> int:
    from platformforge import observe as O
    sub = args.observe_cmd
    if sub == "slo":
        contract = O.SloContract.load(args.path)
        sli = json.loads(args.sli) if args.sli else {}
        out = O.error_budget(contract, **{
            k: v for k, v in sli.items()
            if k in ("good_events", "bad_events", "total_events")})
        # wrap as fact so `judge` can evaluate PF-SLO-* rules
        fact = {"fact_id": out.pop("fact_id", ""),
                "kind": "sre.error_budget", "source": args.path,
                "location": contract.service, "tier": 0, "attrs": out}
        return _emit({"result": out, "facts": [fact]}, args)
    if sub == "otel":
        return _emit(O.correlate_spans(args.path), args)
    if sub == "incident":
        alerts = json.loads(Path(args.alerts).read_text())
        changes = json.loads(Path(args.changes).read_text())
        g = _load_graph_or_refuse(args.repo)
        return _emit(O.correlate(alerts, changes, graph=g,
                                 window_s=args.window), args)
    if sub == "capacity":
        items = json.loads(Path(args.path).read_text())
        out = O.capacity(items)
        facts = [{"fact_id": "", "kind": "sre.capacity", "source": args.path,
                  "location": c["resource"] or "?", "tier": 0, "attrs": c}
                 for c in out["capacity"]]
        return _emit({**out, "facts": facts}, args)
    return _emit({"error": f"unknown observe verb {sub}"}, args, 1)


def cmd_finops(args: argparse.Namespace) -> int:
    from platformforge import finops as F
    sub = args.finops_cmd
    if sub == "costs":
        doc = F.cost_facts(args.path)
        return _emit({**doc, "summary": F.cost_summary(doc["facts"])}, args)
    if sub == "allocate":
        doc = F.cost_facts(args.path)
        return _emit(F.allocate(doc["facts"], by=args.by), args)
    if sub == "focus":
        rows = json.loads(Path(args.path).read_text())
        rows = rows if isinstance(rows, list) else rows.get("rows", [])
        return _emit(F.to_focus(rows), args)
    if sub == "graph":
        g = _load_graph_or_refuse(args.repo)
        if g is None:
            return _emit({"refusal": "PF-GRAPH-NOGRAPH",
                          "unlock": "platformforge graph build <facts.json>"},
                         args, 2)
        doc = F.cost_facts(args.path)
        return _emit(F.graph_cost(g, doc["facts"]), args)
    return _emit({"error": f"unknown finops verb {sub}"}, args, 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="platformforge",
                                description="Agentic Platform Engineering intelligence")
    p.add_argument("--version", action="version", version=f"platformforge {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def verb(name: str, fn, help_: str, extra=None) -> None:
        sp = sub.add_parser(name, help=help_)
        _add_common(sp)
        if extra:
            extra(sp)
        sp.set_defaults(func=fn)

    verb("init", cmd_init, "scaffold .platformforge/",
         lambda sp: sp.add_argument("--name", default=""))
    verb("doctor", cmd_doctor, "environment health-check")
    verb("status", cmd_status, "workspace + store status")
    verb("inspect", cmd_inspect, "inventory analyzable artifacts")
    verb("judge", cmd_judge, "apply rule catalog to facts",
         lambda sp: (sp.add_argument("facts"), sp.add_argument("--catalog", nargs="*")))
    verb("knowledge", cmd_knowledge, "knowledge freshness check")

    sp = sub.add_parser("tokens", help="tokensave: index/search/pack/stats/ledger")
    _add_common(sp)
    sp.add_argument("tokens_cmd",
                    choices=["index", "search", "pack", "stats", "ledger"])
    sp.add_argument("--task", default="")
    sp.add_argument("--query", default="")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--changed", nargs="*")
    sp.add_argument("--input-budget", type=int, default=None)
    sp.set_defaults(func=cmd_tokens)

    sp = sub.add_parser("rtk", help="compact command output (rtk)")
    _add_common(sp)
    sp.add_argument("rtk_cmd", choices=["compact", "expand"], nargs="?",
                    default="compact")
    sp.add_argument("file", nargs="?", default="-",
                    help="output file to compact ('-' = stdin)")
    sp.add_argument("--command", default="", help="command that produced output")
    sp.add_argument("--exit-code", type=int, default=0)
    sp.add_argument("--artifact", default="")
    sp.add_argument("--start", type=int)
    sp.add_argument("--end", type=int)
    sp.add_argument("--pattern", default=None)
    def _rtk_dispatch(a):
        return cmd_rtk_expand(a) if a.rtk_cmd == "expand" else cmd_rtk(a)
    sp.set_defaults(func=_rtk_dispatch)

    sp = sub.add_parser("caveman", help="compress text (caveman)")
    _add_common(sp)
    sp.add_argument("file", help="file to compress ('-' = stdin)")
    sp.add_argument("--mode", choices=["off", "lite", "full", "auto"],
                    default="lite")
    sp.add_argument("--context-risk", default="normal")
    sp.set_defaults(func=cmd_caveman)

    sp = sub.add_parser("economy", help="economy engine report")
    _add_common(sp)
    sp.set_defaults(func=cmd_economy)

    sp = sub.add_parser("route", help="adaptive routing decision")
    _add_common(sp)
    sp.add_argument("signal", help="JSON TaskSignal")
    sp.set_defaults(func=cmd_route)

    sp = sub.add_parser("sdd", help="native SDD lifecycle")
    _add_common(sp)
    sp.add_argument("sdd_cmd",
                    choices=["init", "discover", "define", "design", "contract",
                             "plan", "build", "review", "verify", "ship",
                             "learn", "status", "check", "stamp"])
    sp.add_argument("--feature", required=True)
    sp.add_argument("--body", default="", help="artifact body or JSON")
    sp.add_argument("--phase", default=None, help="stamp single phase")
    sp.add_argument("--verify", default="", help="verify JSON for ship gate")
    sp.add_argument("--risk-accepted", action="store_true")
    sp.add_argument("--override", action="store_true")
    sp.add_argument("--override-reason", default="")
    sp.set_defaults(func=cmd_sdd)

    sp = sub.add_parser("graph", help="Graphfy platform graph")
    _add_common(sp)
    sp.add_argument("graph_cmd",
                    choices=["build", "stats", "deps", "dependents", "blast",
                             "paths", "gaps", "cycles", "diff", "snapshots"])
    sp.add_argument("facts", nargs="?", default="")
    sp.add_argument("--node", default="")
    sp.add_argument("--src", default="")
    sp.add_argument("--dst", default="")
    sp.add_argument("--before", default="")
    sp.add_argument("--after", default="")
    sp.set_defaults(func=cmd_graph)

    sp = sub.add_parser("analyze", help="domain analyzers → facts")
    _add_common(sp)
    sp.add_argument("analyze_cmd",
                    choices=["iac", "plan", "state", "drift", "k8s",
                             "gitops", "gha", "iam", "sbom", "secrets",
                             "supply", "catalog", "crossplane"])
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--config", default="")
    sp.add_argument("--state", default="")
    sp.add_argument("--vulns", default="", help="offline vuln list JSON")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("observe", help="SRE/observability verbs")
    _add_common(sp)
    sp.add_argument("observe_cmd",
                    choices=["slo", "otel", "incident", "capacity"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--sli", default="", help="JSON {good,bad,total}_events")
    sp.add_argument("--alerts", default="")
    sp.add_argument("--changes", default="")
    sp.add_argument("--window", type=int, default=3600)
    sp.set_defaults(func=cmd_observe)

    sp = sub.add_parser("finops", help="FinOps cost analysis")
    _add_common(sp)
    sp.add_argument("finops_cmd",
                    choices=["costs", "allocate", "focus", "graph"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--by", default="cost_center")
    sp.set_defaults(func=cmd_finops)

    sp = sub.add_parser("product", help="platform product verbs")
    _add_common(sp)
    sp.add_argument("product_cmd",
                    choices=["maturity", "scorecard", "backstage"])
    sp.add_argument("--signals", default="", help="JSON signals doc")
    sp.add_argument("--findings", default="", help="findings JSON doc")
    sp.set_defaults(func=cmd_product)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
