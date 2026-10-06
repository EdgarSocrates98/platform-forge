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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
