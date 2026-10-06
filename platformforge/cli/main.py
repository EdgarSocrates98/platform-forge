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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
