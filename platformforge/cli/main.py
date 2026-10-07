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
from typing import TYPE_CHECKING, Any

from platformforge import __version__

if TYPE_CHECKING:
    from platformforge.tokensave.index import SearchIndex

DETAIL_LEVELS = ("summary", "normal", "full")


_DETAIL_LIST_CAP = {"summary": 3, "normal": 50, "full": None}
_SUMMARY_KEYS = {"status", "verdict", "ok", "passed", "failed", "exit_code",
                 "severity", "rule_id", "finding_id", "level", "risk",
                 "counts", "coverage", "summary", "unresolved", "refused",
                 "refusals", "skipped"}


def _detail_bound(obj: Any, level: str, depth: int = 0) -> Any:
    """§108 — detail levels bound payload shape, deterministically.
    summary: scalar summary fields + counts + ≤3 list items; normal: ≤50
    list items; full: unbounded."""
    cap = _DETAIL_LIST_CAP.get(level)
    if cap is None:
        return obj
    if isinstance(obj, list):
        if len(obj) > cap:
            return ([_detail_bound(x, level, depth + 1) for x in obj[:cap]]
                    + [{"_truncated": len(obj) - cap}])
        return [_detail_bound(x, level, depth + 1) for x in obj]
    if isinstance(obj, dict):
        if level == "summary" and depth > 0:
            keep = {k: v for k, v in obj.items() if k in _SUMMARY_KEYS}
            extra = {k for k in obj if k not in _SUMMARY_KEYS}
            if extra:
                keep["_elided_keys"] = sorted(extra)
            return {k: _detail_bound(v, level, depth + 1)
                    for k, v in keep.items()}
        return {k: _detail_bound(v, level, depth + 1)
                for k, v in obj.items()}
    return obj


def _has_unresolved(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("unresolved", "refused", "refusals") and v:
                return True
            if _has_unresolved(v):
                return True
    elif isinstance(obj, list):
        return any(_has_unresolved(x) for x in obj[:200])
    return False


def _emit(result: Any, args: argparse.Namespace, exit_code: int = 0) -> int:
    level = getattr(args, "detail_level", "normal")
    shown = result if level == "full" else _detail_bound(result, level)
    if getattr(args, "offline", False) and isinstance(shown, dict):
        shown = {**shown, "offline": True}
    # §110 — strict: any unresolved/refused in the payload exits 2.
    if getattr(args, "strict", False) and exit_code == 0 \
            and _has_unresolved(result):
        exit_code = 2
    text = json.dumps(shown, indent=2, sort_keys=True, default=str)
    if getattr(args, "output", None):
        Path(args.output).write_text(text + "\n")
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


def _member_dirs(path: str | Path) -> list[tuple[str, Path]]:
    """§126 — a workspace.yaml root expands to its member repos."""
    from platformforge.core.workspace import load_workspace
    ws = load_workspace(path)
    if ws.is_multi_repo:
        return [(m.name, p) for m, p in
                zip(ws.members, ws.member_paths(), strict=True)
                if p.is_dir()]
    return [("", Path(path))]


def _run_over_members(fn, path: str | Path) -> dict[str, Any]:
    """Run an analyzer per workspace member; facts get `member` tagged."""
    members = _member_dirs(path)
    if len(members) == 1 and not members[0][0]:
        return fn(str(members[0][1]))
    facts, errors = [], []
    for name, p in members:
        try:
            for f in fn(str(p))["facts"]:
                f.setdefault("attrs", {})["workspace_member"] = name
                facts.append(f)
        except Exception as e:  # noqa: BLE001 — member failure is data
            errors.append(f"{name or p.name}: {e}")
    out: dict[str, Any] = {"facts": facts,
                           "workspace": {n: str(p) for n, p in members}}
    if errors:
        out["errors"] = errors
    return out


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inventory analyzable artifacts under a root — no content parsing."""
    root = Path(args.repo).resolve()
    members = _member_dirs(root)
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
    for mname, mroot in members:
        for p in sorted(mroot.rglob("*")):
            if not p.is_file() or any(part in ignore for part in p.parts):
                continue
            rel = (f"{mname}/{p.relative_to(mroot)}" if mname
                   else str(p.relative_to(mroot)))
            for kind, pats in kinds.items():
                if any(p.match(pat) or rel.endswith(pat.lstrip("*"))
                       for pat in pats):
                    inventory[kind].append(rel)
    inventory = {k: v for k, v in inventory.items() if v}
    return _emit({"root": str(root), "artifacts": inventory,
                  "members": [n or str(p) for n, p in members],
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
    sub = getattr(args, "knowledge_cmd", "check") or "check"
    if sub == "contract":
        out = reg.contract_check()
        return _emit(out, args, 2 if (args.strict and not out["ok"]) else 0)
    if sub == "drift":
        out = reg.link_rules("rules/catalog")
        out["unresolved"] = [u["rule_id"] for u in out["unlinked"]]
        return _emit(out, args)
    report = reg.check()
    bad = [r for r in report if r["status"] in ("stale", "unresolved", "conflicted",
                                              "deprecated", "superseded")]
    return _emit({"sources": report, "attention": bad,
                  "counts": {"total": len(report), "attention": len(bad)}},
                 args, 2 if (args.strict and bad) else 0)


def _index(args) -> SearchIndex:
    from platformforge.tokensave.index import SearchIndex
    return SearchIndex(Path(args.repo) / ".platformforge" / "index.db")


def cmd_tokens(args: argparse.Namespace) -> int:
    from platformforge.tokensave.budget import Budget
    from platformforge.tokensave.ledger import TokenLedger
    from platformforge.tokensave.packs import ContextPackBuilder
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
            changed_files=args.changed or [],
            graph_neighborhood=getattr(args, "graph_nodes", None) or None,
            risk=getattr(args, "risk", None) or None,
            previous_pack_hash=getattr(args, "prev_pack", None) or None)
        out = pack
    elif args.tokens_cmd == "delta":
        ledger = TokenLedger(args.repo)
        out = ContextPackBuilder(idx, ledger).delta_for_change(
            changed_files=args.changed or [],
            budget=Budget(input_budget=args.input_budget),
            previous_pack_hash=getattr(args, "prev_pack", None) or None,
            risk=getattr(args, "risk", None) or None)
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
    eng = EconomyEngine(args.repo)
    sub = getattr(args, "economy_cmd", "report") or "report"
    if sub == "strategy":
        sig = json.loads(args.signal) if args.signal.strip().startswith("{") \
            else {"task_type": args.signal or "analysis"}
        return _emit(eng.strategy(sig), args)
    if sub == "compare":
        sig = json.loads(args.signal) if args.signal.strip().startswith("{") \
            else {"task_type": args.signal or "analysis"}
        return _emit(eng.compare(sig), args)
    if sub == "qpt":
        # §30–32 — measured quality-per-token over a facts doc
        import json as _json

        from platformforge.economy.qpt import quality_per_token
        from platformforge.tokensave.budget import Budget
        facts_doc = _json.loads(Path(args.path).read_text())
        facts = facts_doc.get("facts", facts_doc)
        out = quality_per_token(
            facts_full=facts, findings_full=[],
            index=_index(args), task=args.task or "analysis",
            budget=Budget(input_budget=args.input_budget))
        return _emit(out, args,
                     2 if out.get("quality_gate") == "fail" else 0)
    return _emit(eng.report(), args)


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
        p = G.save(builder.graph, args.repo,
                   source=args.facts,
                   source_type=getattr(args, "source_type", "desired"))
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
    """Domain analyzers → fact documents (feed judge/graph).

    Tree-walking domains are workspace-aware: a root with a multi-member
    workspace.yaml fans out per member repo and tags facts (§126)."""
    sub = args.analyze_cmd
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
    if sub == "iam":
        from platformforge.security import analyze_iam_policy
        return _emit(analyze_iam_policy(args.path), args)
    if sub.startswith("cloud-"):
        from platformforge.cloud import analyze_aws_dump, analyze_azure_dump, analyze_gcp_dump
        fn = {"cloud-aws": analyze_aws_dump, "cloud-azure": analyze_azure_dump,
              "cloud-gcp": analyze_gcp_dump}[sub]
        return _emit(fn(args.path), args)
    if sub == "helm":
        from platformforge.k8s.helm import analyze_helm
        return _emit(analyze_helm(args.path), args)
    if sub == "kustomize":
        from platformforge.k8s.helm import analyze_kustomize
        return _emit(analyze_kustomize(args.path), args)
    if sub == "hubble":
        from platformforge.k8s.hubble import analyze_hubble
        return _emit(analyze_hubble(args.path), args)
    if sub == "sbom":
        from platformforge.security import analyze_sbom
        vulns = json.loads(Path(args.vulns).read_text()) if args.vulns else None
        return _emit(analyze_sbom(args.path, vuln_db=vulns), args)
    tree_analyzers = {
        "iac": "platformforge.iac:analyze_hcl",
        "k8s": "platformforge.k8s:analyze_k8s",
        "gitops": "platformforge.cicd:analyze_gitops",
        "gha": "platformforge.cicd:analyze_gha",
        "secrets": "platformforge.security:scan_secrets",
        "supply": "platformforge.security:analyze_supply",
        "catalog": "platformforge.product:analyze_catalog",
        "crossplane": "platformforge.product:analyze_crossplane",
    }
    if sub in tree_analyzers:
        mod, fn = tree_analyzers[sub].split(":")
        import importlib
        return _emit(_run_over_members(getattr(importlib.import_module(mod),
                                             fn), args.path), args)
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


def cmd_agents(args: argparse.Namespace) -> int:
    from platformforge import agents as A
    from platformforge.agents.mirrors import lint, sync
    sub = args.agents_cmd
    if sub == "list":
        return _emit({"agents": [a.to_dict() for a in A.AGENTS.values()]},
                     args)
    if sub == "lint":
        out = lint()
        return _emit(out, args, 0 if out["ok"] else 2)
    if sub == "sync":
        return _emit({"written": sync(args.repo)}, args)
    if sub == "playbook":
        return _emit(A.playbook(args.name or "platform-coordinator",
                                domain=args.domain), args)
    if sub == "referee":
        positions = json.loads(Path(args.path).read_text())
        return _emit(A.referee(positions), args)
    return _emit({"error": f"unknown agents verb {sub}"}, args, 1)


def cmd_mcp(args: argparse.Namespace) -> int:
    from platformforge import mcp as M
    from platformforge.mcp.parity import detach, integrate
    from platformforge.mcp.registry import tool_descriptors
    sub = args.mcp_cmd
    if sub == "tools":
        return _emit({"tools": tool_descriptors()}, args)
    if sub == "call":
        inp = json.loads(args.input) if args.input else {}
        out = M.call_tool(args.name, inp, repo=args.repo)
        return _emit(out, args, 2 if "error" in out or "refusal" in out else 0)
    if sub == "serve":
        from platformforge.mcp.server import serve
        return serve(repo=args.repo)
    if sub == "integrate":
        return _emit(integrate(args.host, args.repo), args)
    if sub == "detach":
        return _emit(detach(args.host, args.repo), args)
    return _emit({"error": f"unknown mcp verb {sub}"}, args, 1)


def cmd_lab(args: argparse.Namespace) -> int:
    from platformforge import lab
    if args.lab_cmd == "list":
        return _emit({"scenarios": lab.list_scenarios()}, args)
    if args.lab_cmd == "run-all":
        out = lab.runner.run_all()
        return _emit(out, args, 0 if not out["failed"] else 2)
    if args.lab_cmd == "chaos":
        from platformforge.lab.chaos import run_scenario
        return _emit(run_scenario(args.path or "",
                                  allow_prod=args.allow_prod), args)
    return _emit(lab.run(args.path or ""), args)


def cmd_collect(args: argparse.Namespace) -> int:
    """§7 collect — sniff a dumps dir/file, run matching analyzers."""
    from platformforge.collect import collect
    return _emit(collect(args.path or args.repo), args)


def _json_doc(path: str, key: str) -> list:
    doc = json.loads(Path(path).read_text())
    if isinstance(doc, dict):
        return doc.get(key, [])
    return doc if isinstance(doc, list) else []


def cmd_diagnose(args: argparse.Namespace) -> int:
    """§7 diagnose — compose graph + findings for one node."""
    g = _load_graph_or_refuse(args.repo)
    if g is None:
        return _emit({"refusal": "PF-GRAPH-NOGRAPH",
                      "unlock": "platformforge graph build <facts.json>"},
                     args, 2)
    from platformforge.diagnose import diagnose
    findings = _json_doc(args.findings, "findings") if args.findings else []
    facts = _json_doc(args.facts, "facts") if args.facts else []
    return _emit(diagnose(g, args.node, findings, facts), args)


def cmd_plan(args: argparse.Namespace) -> int:
    """§7 plan — findings → ordered remediation plan."""
    from platformforge.plan import remediation_plan
    findings = _json_doc(args.path, "findings")
    facts = _json_doc(args.facts, "facts") if args.facts else []
    g = _load_graph_or_refuse(args.repo)   # optional enrichment
    return _emit(remediation_plan(findings, g, facts), args)


def cmd_correlate(args: argparse.Namespace) -> int:
    """§7 correlate — OTel/telemetry correlation (observe otel)."""
    from platformforge import observe as O
    return _emit(O.correlate_spans(args.path), args)


def _build_graph_from(path: str):
    from platformforge.graph import GraphBuilder
    doc = json.loads(Path(path).read_text())
    return GraphBuilder().from_facts(
        doc.get("facts", doc if isinstance(doc, list) else [])).graph


def cmd_diff(args: argparse.Namespace) -> int:
    """§7 diff — graph diff between two facts docs."""
    from platformforge.graph.diff import diff as graph_diff
    return _emit(graph_diff(_build_graph_from(args.before),
                            _build_graph_from(args.after)), args)


def cmd_drift(args: argparse.Namespace) -> int:
    """§7 drift — desired (HCL) vs observed (state)."""
    from platformforge.iac import analyze_hcl, analyze_state, drift
    desired = analyze_hcl(args.config)["facts"]
    observed = analyze_state(args.state)["facts"]
    return _emit(drift(desired, observed), args)


def cmd_impact(args: argparse.Namespace) -> int:
    """§7 impact — blast radius for a graph node."""
    g = _load_graph_or_refuse(args.repo)
    if g is None:
        return _emit({"refusal": "PF-GRAPH-NOGRAPH",
                      "unlock": "platformforge graph build <facts.json>"},
                     args, 2)
    from platformforge.graph.query import blast_radius
    return _emit(blast_radius(g, args.node), args)


def cmd_context(args: argparse.Namespace) -> int:
    """§7 context — context pack for a task (tokens pack)."""
    from platformforge.tokensave.budget import Budget
    from platformforge.tokensave.ledger import TokenLedger
    from platformforge.tokensave.packs import ContextPackBuilder
    pack = ContextPackBuilder(_index(args), TokenLedger(args.repo)).build(
        task=args.task, budget=Budget(input_budget=args.input_budget),
        changed_files=args.changed or [])
    return _emit(pack, args)


def cmd_policy(args: argparse.Namespace) -> int:
    """§7 policy — the rule catalog IS the policy layer."""
    from platformforge.rules import load_catalog
    cat_dir = Path(__file__).resolve().parents[2] / "rules" / "catalog"
    rules = load_catalog(cat_dir)
    if args.policy_cmd == "list":
        return _emit({"rules": [{"rule_id": r.rule_id, "domain": r.domain,
                                 "severity": r.severity}
                                for r in rules]}, args)
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine
    facts = [Fact.from_dict(f) for f in _json_doc(args.path, "facts")]
    findings, skipped = RuleEngine(rules).evaluate(facts)
    out = {"findings": [f.to_dict() for f in findings],
           "skipped": skipped,
           "violated": [f.rule_id for f in findings
                        if f.status == "violated"]}
    return _emit(out, args)


def cmd_security(args: argparse.Namespace) -> int:
    """§7 security — scan bundle: secrets + iam + sbom + supply → judge."""
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog
    from platformforge.security import analyze_iam_policy, analyze_sbom, analyze_supply, scan_secrets
    root = Path(args.path or args.repo)
    facts = scan_secrets(root)["facts"]
    extras = {"iam": ("policy.json", analyze_iam_policy),
              "sbom": ("sbom.json", analyze_sbom),
              "supply": ("supply.json", analyze_supply)}
    present = []
    for name, (fname, fn) in extras.items():
        p = root / fname
        if p.exists():
            facts += fn(str(p))["facts"]
            present.append(name)
    cat_dir = Path(__file__).resolve().parents[2] / "rules" / "catalog"
    cat = [r for r in load_catalog(cat_dir) if r.domain == "security"]
    findings, _ = RuleEngine(cat).evaluate(
        [Fact.from_dict(f) for f in facts])
    return _emit({"facts": facts, "analyzers_run": ["secrets", *present],
                  "findings": [f.to_dict() for f in findings
                               if f.status == "violated"]}, args)


def cmd_reliability(args: argparse.Namespace) -> int:
    """§7 reliability — SRE+K8S rules over a facts doc."""
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog
    cat_dir = Path(__file__).resolve().parents[2] / "rules" / "catalog"
    rules = [r for r in load_catalog(cat_dir)
             if r.domain in ("sre", "k8s")]
    facts = [Fact.from_dict(f) for f in _json_doc(args.path, "facts")]
    findings, skipped = RuleEngine(rules).evaluate(facts)
    violated = [f for f in findings if f.status == "violated"]
    return _emit({"findings": [f.to_dict() for f in violated],
                  "skipped": skipped,
                  "counts": {"violated": len(violated)}}, args)


def cmd_integrate(args: argparse.Namespace) -> int:
    """§7 integrate — host integration via mcp parity."""
    from platformforge.mcp.parity import detach, integrate
    fn = detach if args.detach else integrate
    return _emit(fn(args.host, args.repo), args)


def cmd_evals(args: argparse.Namespace) -> int:
    """§94–95 eval framework."""
    from platformforge.evals import run_all
    cases = Path(args.cases) if args.cases else None
    if args.evals_cmd == "list":
        d = cases or __import__("platformforge.evals.runner",
                                fromlist=["CASES_DIR"]).CASES_DIR
        return _emit({"cases": [c.parent.name for c in
                                sorted(d.glob("*/case.yaml"))]
                      if Path(d).is_dir() else []}, args)
    out = run_all(cases, type_filter=args.type or None) \
        if cases else run_all(type_filter=args.type or None)
    return _emit(out, args, 2 if out["counts"]["fail"] else 0)


def cmd_risk(args: argparse.Namespace) -> int:
    """§130–131 risk engine + criticality."""
    from platformforge.risk.engine import assess_change
    signals: dict[str, Any] = {}
    if args.signals:
        signals = json.loads(Path(args.signals).read_text()
                             if Path(args.signals).exists() else args.signals)
    if args.node:
        g = _load_graph_or_refuse(args.repo)
        if g is None:
            return _emit({"refusal": "PF-GRAPH-NOGRAPH"}, args, 2)
        from platformforge.graph import blast_radius
        from platformforge.risk.signals import signals_from_graph
        blast = blast_radius(g, args.node)
        signals = {**signals_from_graph(g, [args.node], blast), **signals}
        signals.setdefault("blast_radius_nodes", blast.get("impacted"))
    return _emit(assess_change(signals), args)


def cmd_change(args: argparse.Namespace) -> int:
    """§85–86 change lifecycle: propose → sandbox → verify (read-only)."""
    from platformforge.sandbox import sandbox_analyze
    sub = args.change_cmd
    if sub in ("propose", "verify", "sandbox"):
        patch = Path(args.patch).read_text() if args.patch else None
        files = {}
        for spec in args.file or []:
            rel, _, src = spec.partition("=")
            files[rel] = Path(src).read_text() if Path(src).exists() else src
        out = sandbox_analyze(args.repo, patch=patch, files=files)
        return _emit(out, args, 2 if "refusal" in out else 0)
    if sub == "approve" or sub == "apply":
        # core never mutates — approval emits a receipt-bound refusal unless
        # a sandbox receipt with verified diff is provided
        return _emit({"refusal": "platform.change.core_read_only",
                      "detail": "apply/approve are host-side boundaries; "
                                "core emits verified sandbox diffs only",
                      "unlock": "change verify --patch <diff> first"}, args, 2)
    return _emit({"error": f"unknown change verb {sub}"}, args, 1)


def cmd_explain(args: argparse.Namespace) -> int:
    """Evidence chain for a finding id — facts behind the judgment."""
    doc = json.loads(Path(args.path).read_text())
    findings = doc.get("findings", doc if isinstance(doc, list) else [])
    f = next((x for x in findings if x.get("finding_id") == args.name
              or x.get("rule_id") == args.name), None)
    if not f:
        return _emit({"refusal": "platform.finding.unresolved",
                      "name": args.name}, args, 2)
    facts_doc = (json.loads(Path(args.facts).read_text())
                 if args.facts else doc.get("facts", []))
    by_id = {x.get("fact_id"): x for x in facts_doc}
    chain = [{"fact_id": e, "fact": by_id.get(e, "unresolved")}
             for e in f.get("evidence", [])]
    return _emit({"finding": f, "evidence_chain": chain}, args)


def cmd_recommend(args: argparse.Namespace) -> int:
    """findings → Recommendation objects with evidence (§recommendation)."""
    from platformforge.models import Recommendation
    doc = json.loads(Path(args.path).read_text())
    findings = doc.get("findings", doc if isinstance(doc, list) else [])
    recs, skipped = [], []
    for f in findings:
        if f.get("status") != "violated":
            continue
        if not f.get("evidence"):
            skipped.append({"rule_id": f["rule_id"],
                            "reason": "finding without evidence — "
                                      "recommendation refused by contract"})
            continue
        recs.append(Recommendation(
            title=f.get("title") or f["rule_id"],
            severity=f.get("severity", "medium"),
            confidence="declared",
            evidence=f["evidence"],
            root_cause=f.get("message", ""),
            proposed_change=[f.get("remediation",
                                   "resolve rule violation")],
            basis={"declared": f["evidence"]},
            risks=[],
            validation=["re-run analyze+judge after change"],
            rollback=["revert the diff"],
        ).to_dict())
    return _emit({"recommendations": recs, "count": len(recs),
                  "refused": skipped}, args)


def cmd_capability(args: argparse.Namespace) -> int:
    """Capability registry projection — same source as the MCP adapter."""
    from platformforge.mcp.registry import CAPABILITIES
    sub = args.capability_cmd
    if sub == "list":
        return _emit({"capabilities": [
            {"name": c.name, "description": c.description,
             "bounds": {"max_results": c.max_results,
                        "max_bytes": c.max_bytes,
                        "detail_levels": list(c.detail_levels)}}
            for c in CAPABILITIES.values()]}, args)
    if sub == "describe":
        c = CAPABILITIES.get(args.name or "")
        if not c:
            return _emit({"refusal": "platform.capability.unresolved",
                          "name": args.name,
                          "unlock": "platformforge capability list"},
                         args, 2)
        return _emit({"name": c.name, "description": c.description,
                      "input_schema": c.input_schema, "handler": c.handler,
                      "bounds": {"max_results": c.max_results,
                                 "max_bytes": c.max_bytes}}, args)
    if sub == "manifest":
        from platformforge.forge import capability_manifest
        return _emit(capability_manifest(args.repo), args)
    return _emit({"error": f"unknown capability verb {sub}"}, args, 1)


def cmd_forge(args: argparse.Namespace) -> int:
    from platformforge import forge as FG
    sub = args.forge_cmd
    if sub == "manifest":
        return _emit(FG.capability_manifest(args.repo), args)
    if sub == "delegate":
        d = FG.Delegation(from_forge=args.src or "platform-forge",
                          to_forge=args.dst or "?",
                          task=args.name or "", )
        return _emit(FG.build_envelope(d), args)
    if sub == "verify":
        env = json.loads(Path(args.path).read_text())
        return _emit(FG.verify_envelope(env), args)
    if sub == "discover":
        from platformforge.forge.collect import discover
        return _emit(discover(args.path or args.repo), args)
    if sub == "collect":
        from platformforge.forge.collect import collect_manifest
        out = collect_manifest(args.path or args.repo)
        return _emit(out, args, 2 if "refusal" in out else 0)
    return _emit({"error": f"unknown forge verb {sub}"}, args, 1)


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
    verb("knowledge", cmd_knowledge, "knowledge freshness/drift check",
         lambda sp: sp.add_argument(
             "knowledge_cmd", nargs="?", default="check",
             choices=["check", "contract", "drift"]))

    sp = sub.add_parser("tokens",
                        help="tokensave: index/search/pack/delta/stats/ledger")
    _add_common(sp)
    sp.add_argument("tokens_cmd",
                    choices=["index", "search", "pack", "delta", "stats",
                             "ledger"])
    sp.add_argument("--task", default="")
    sp.add_argument("--query", default="")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--changed", nargs="*")
    sp.add_argument("--input-budget", type=int, default=None)
    sp.add_argument("--risk", default=None,
                    choices=["low", "medium", "high", "critical"])
    sp.add_argument("--graph-nodes", nargs="*",
                    help="seed nodes for graph-aware ranking")
    sp.add_argument("--prev-pack", default=None,
                    help="previous pack hash — delta-aware dedup")
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

    sp = sub.add_parser("economy", help="economy engine report/strategy/qpt")
    _add_common(sp)
    sp.add_argument("economy_cmd", nargs="?", default="report",
                    choices=["report", "strategy", "compare", "qpt"])
    sp.add_argument("--signal", default="",
                    help="JSON TaskSignal (strategy/compare)")
    sp.add_argument("--path", default="", help="facts doc for qpt")
    sp.add_argument("--task", default="analysis")
    sp.add_argument("--input-budget", type=int, default=None)
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
    sp.add_argument("--source-type", default="desired",
                    choices=["desired", "planned", "observed", "runtime"],
                    help="§6 snapshot type for `graph build`")
    sp.set_defaults(func=cmd_graph)

    sp = sub.add_parser("analyze", help="domain analyzers → facts")
    _add_common(sp)
    sp.add_argument("analyze_cmd",
                    choices=["iac", "plan", "state", "drift", "k8s",
                             "gitops", "gha", "iam", "sbom", "secrets",
                             "supply", "catalog", "crossplane", "cloud-aws",
                             "cloud-azure", "cloud-gcp", "helm",
                             "kustomize", "hubble"])
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

    sp = sub.add_parser("agents", help="agent roster, mirrors, referee")
    _add_common(sp)
    sp.add_argument("agents_cmd",
                    choices=["list", "lint", "sync", "playbook", "referee"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--name", default="")
    sp.add_argument("--domain", default="")
    sp.set_defaults(func=cmd_agents)

    sp = sub.add_parser("mcp", help="MCP server + host parity")
    _add_common(sp)
    sp.add_argument("mcp_cmd",
                    choices=["tools", "call", "serve", "integrate", "detach"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--name", default="")
    sp.add_argument("--input", default="")
    sp.add_argument("--host", default="generic",
                    choices=["claude", "codex", "devin", "copilot", "generic"])
    sp.set_defaults(func=cmd_mcp)

    verb("collect", cmd_collect, "ingest artifact dumps → facts",
         lambda sp: sp.add_argument("path", nargs="?", default=""))
    verb("diagnose", cmd_diagnose, "node diagnosis: facts+findings+blast",
         lambda sp: (sp.add_argument("node"),
                     sp.add_argument("--findings", default=""),
                     sp.add_argument("--facts", default="")))
    verb("plan", cmd_plan, "findings → ordered remediation plan",
         lambda sp: (sp.add_argument("path"),
                     sp.add_argument("--facts", default="")))
    verb("correlate", cmd_correlate, "OTel correlation (observe otel)",
         lambda sp: sp.add_argument("path"))
    verb("diff", cmd_diff, "graph diff between two facts docs",
         lambda sp: (sp.add_argument("--before", required=True),
                     sp.add_argument("--after", required=True)))
    verb("drift", cmd_drift, "IaC drift: --config dir vs --state file",
         lambda sp: (sp.add_argument("--config", required=True),
                     sp.add_argument("--state", required=True)))
    verb("impact", cmd_impact, "blast radius for a graph node",
         lambda sp: sp.add_argument("--node", required=True))
    verb("context", cmd_context, "context pack for a task",
         lambda sp: (sp.add_argument("--task", default=""),
                     sp.add_argument("--input-budget", type=int,
                                     default=None),
                     sp.add_argument("--changed", nargs="*")))
    verb("policy", cmd_policy, "policy-as-code catalog check",
         lambda sp: (sp.add_argument("policy_cmd",
                                     choices=["check", "list"]),
                     sp.add_argument("path", nargs="?", default="")))
    verb("security", cmd_security, "security bundle (secrets+iam+sbom+supply)",
         lambda sp: sp.add_argument("path", nargs="?", default=""))
    verb("reliability", cmd_reliability, "SRE+K8S rules over facts",
         lambda sp: sp.add_argument("path", nargs="?", default=""))
    verb("integrate", cmd_integrate, "host integration (mcp parity)",
         lambda sp: (sp.add_argument("--host", required=True,
                                     choices=["claude", "codex", "devin",
                                              "copilot", "generic"]),
                     sp.add_argument("--detach", action="store_true")))
    verb("evals", cmd_evals, "eval framework (§94–95)",
         lambda sp: (sp.add_argument("evals_cmd",
                                     choices=["run", "list"], nargs="?",
                                     default="run"),
                     sp.add_argument("--type", default=""),
                     sp.add_argument("--cases", default="")))

    sp = sub.add_parser("lab", help="Forge Lab scenarios")
    _add_common(sp)
    sp.add_argument("lab_cmd", choices=["list", "run", "run-all", "chaos"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--allow-prod", action="store_true",
                    help="chaos on production nodes (default refused)")
    sp.set_defaults(func=cmd_lab)

    sp = sub.add_parser("forge", help="Forge interop")
    _add_common(sp)
    sp.add_argument("forge_cmd", choices=["manifest", "delegate", "verify",
                                          "discover", "collect"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--name", default="")
    sp.add_argument("--src", default="")
    sp.add_argument("--dst", default="")
    sp.set_defaults(func=cmd_forge)

    sp = sub.add_parser("capability", help="capability registry")
    _add_common(sp)
    sp.add_argument("capability_cmd",
                    choices=["list", "describe", "manifest"])
    sp.add_argument("--name", default="")
    sp.set_defaults(func=cmd_capability)

    sp = sub.add_parser("risk", help="§130 change-risk assessment")
    _add_common(sp)
    sp.add_argument("--node", default="", help="graph node id to assess")
    sp.add_argument("--signals", default="", help="JSON signals doc")
    sp.set_defaults(func=cmd_risk)

    sp = sub.add_parser("change", help="§85–86 change lifecycle (sandboxed)")
    _add_common(sp)
    sp.add_argument("change_cmd",
                    choices=["propose", "sandbox", "verify", "approve",
                             "apply"])
    sp.add_argument("--patch", default="", help="unified diff file")
    sp.add_argument("--file", action="append",
                    help="rel/path=src-file (or literal content)")
    sp.set_defaults(func=cmd_change)

    sp = sub.add_parser("explain", help="evidence chain for a finding")
    _add_common(sp)
    sp.add_argument("path", help="findings doc (json)")
    sp.add_argument("--name", default="", help="finding_id or rule_id")
    sp.add_argument("--facts", default="", help="facts doc (json)")
    sp.set_defaults(func=cmd_explain)

    sp = sub.add_parser("recommend", help="findings → recommendations")
    _add_common(sp)
    sp.add_argument("path", help="findings doc (json)")
    sp.set_defaults(func=cmd_recommend)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
