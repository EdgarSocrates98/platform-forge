"""platformforge CLI — thin adapter over the core. No logic lives here.

Every verb supports: --json  --output FILE  --detail-level summary|normal|full
--offline  --strict. Flags have real contracts: --strict turns unresolved into
exit 2; --offline forbids adapter calls that need network.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from platformforge import __version__

if TYPE_CHECKING:
    from platformforge.tokensave.index import SearchIndex

DETAIL_LEVELS = ("summary", "normal", "full")

from platformforge.resources import data_path

REPO_ROOT = data_path()


_DETAIL_LIST_CAP = {"summary": 3, "normal": 50, "full": None}
_SUMMARY_KEYS = {
    "status",
    "verdict",
    "ok",
    "passed",
    "failed",
    "exit_code",
    "severity",
    "rule_id",
    "finding_id",
    "level",
    "risk",
    "counts",
    "coverage",
    "summary",
    "unresolved",
    "refused",
    "refusals",
    "skipped",
}


def _detail_bound(obj: Any, level: str, depth: int = 0) -> Any:
    """§108 — detail levels bound payload shape, deterministically.
    summary: scalar summary fields + counts + ≤3 list items; normal: ≤50
    list items; full: unbounded."""
    cap = _DETAIL_LIST_CAP.get(level)
    if cap is None:
        return obj
    if isinstance(obj, list):
        if len(obj) > cap:
            return [_detail_bound(x, level, depth + 1) for x in obj[:cap]] + [{"_truncated": len(obj) - cap}]
        return [_detail_bound(x, level, depth + 1) for x in obj]
    if isinstance(obj, dict):
        if level == "summary" and depth > 0:
            keep = {k: v for k, v in obj.items() if k in _SUMMARY_KEYS}
            extra = {k for k in obj if k not in _SUMMARY_KEYS}
            if extra:
                keep["_elided_keys"] = sorted(extra)
            return {k: _detail_bound(v, level, depth + 1) for k, v in keep.items()}
        return {k: _detail_bound(v, level, depth + 1) for k, v in obj.items()}
    return obj


def _has_unresolved(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("unresolved", "refused", "refusals") and v:
                return True
            # findings/refusals carry status fields — strict must catch them
            if k == "status" and v in ("unresolved", "refused"):
                return True
            if _has_unresolved(v):
                return True
    elif isinstance(obj, list):
        return any(_has_unresolved(x) for x in obj)
    return False


_RUN_STARTED = 0.0


def _pf_code(code: str) -> str:
    """Canonical PF-* alias for a legacy `platform.*` refusal code —
    the repo contract requires a PF-* code on every refusal; dotted
    codes are preserved for compat and aliased deterministically."""
    if not isinstance(code, str) or not code.startswith("platform."):
        return code
    body = code[len("platform."):].replace("_", "-").replace(".", "-")
    return "PF-" + body.upper()


def _annotate_pf(obj: Any) -> Any:
    """Attach pf_code next to every legacy refusal code in a payload."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("refusal", "unresolved") and isinstance(v, str) \
                    and v.startswith("platform."):
                out[k] = v
                out["pf_code"] = _pf_code(v)
            elif k in ("refusals",) and isinstance(v, list):
                out[k] = [
                    ({**e, "pf_code": _pf_code(e.get("code", ""))}
                     if isinstance(e, dict)
                     and str(e.get("code", "")).startswith("platform.")
                     else e) for e in v]
            else:
                out[k] = _annotate_pf(v)
        return out
    if isinstance(obj, list):
        return [_annotate_pf(x) for x in obj]
    return obj


def _emit(result: Any, args: argparse.Namespace, exit_code: int = 0) -> int:
    level = getattr(args, "detail_level", "normal")
    shown = result if level == "full" else _detail_bound(result, level)
    if isinstance(shown, dict):
        shown = _annotate_pf(shown)
    if getattr(args, "offline", False) and isinstance(shown, dict):
        shown = {**shown, "offline": True}
    # §110 — strict: any unresolved/refused in the payload exits 2.
    if getattr(args, "strict", False) and exit_code == 0 and _has_unresolved(result):
        exit_code = 2
    text = json.dumps(shown, indent=2, sort_keys=True, default=str)
    if getattr(args, "output", None):
        Path(args.output).write_text(text + "\n")
    _write_receipt(result, text, args, exit_code)
    print(text)
    return exit_code


def _write_receipt(result: Any, text: str, args: argparse.Namespace,
                   exit_code: int) -> None:
    """§152/§156 — every operation emits an auditable receipt under
    .platformforge/receipts/. Never breaks the command on failure."""
    try:
        repo = getattr(args, "repo", "") or ""
        if not repo:
            return
        import hashlib

        from platformforge import __version__
        from platformforge.core.receipts import Receipt, ReceiptWriter
        cmd = getattr(args, "command", "")
        sub = getattr(args, f"{cmd}_cmd", "") if cmd else ""
        facts = result.get("facts", []) if isinstance(result, dict) else []
        findings = result.get("findings", []) \
            if isinstance(result, dict) else []
        rec = Receipt(
            operation=f"cli.{cmd}.{sub}" if sub else f"cli.{cmd}",
            inputs=[str(v) for a, v in sorted(vars(args).items())
                    if a in ("path", "spec", "intent", "plan",
                             "policies", "desired", "observed",
                             "planned", "facts", "output") and v],
            hashes={"output": "sha256:" + hashlib.sha256(
                text.encode()).hexdigest()},
            versions={"platformforge": __version__},
            facts=[f.get("fact_id", "") for f in facts
                   if isinstance(f, dict)][:200],
            findings=[f.get("finding_id", "") for f in findings
                      if isinstance(f, dict)][:200],
            cost={"output_bytes": len(text)},
            started_at=_RUN_STARTED or None, ended_at=time.time(),
            extra={"exit_code": exit_code,
                   "refusal": (result or {}).get("refusal")
                   if isinstance(result, dict) else None})
        ReceiptWriter(repo).emit(rec)
    except OSError:
        pass  # receipts must never break the verb they observe


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", default=True, help="structured output (default)")
    p.add_argument("--output", metavar="FILE", help="write result to FILE")
    p.add_argument(
        "--detail-level", choices=DETAIL_LEVELS, default="normal", help="summary|normal|full payload bounding"
    )
    p.add_argument("--offline", action="store_true", help="forbid any network-capable adapter")
    p.add_argument("--strict", action="store_true", help="unresolved/refusals -> exit code 2")
    p.add_argument("--repo", default=".", help="workspace/repo root")


def cmd_init(args: argparse.Namespace) -> int:
    from platformforge.core.workspace import init_workspace

    pf = init_workspace(args.repo, name=args.name)
    return _emit({"initialized": str(pf)}, args)


def cmd_doctor(args: argparse.Namespace) -> int:
    """§141 — Forge-Doctor-ready health surface.

    `--deep` validates the contracts a Forge Doctor could check: install,
    config, capability manifest, knowledge freshness, host parity, graph
    integrity, index health and the artifact store — all read-only."""
    import platform

    checks: dict[str, Any] = {
        "python": platform.python_version(),
        "platformforge": __version__,
        "pyyaml": _mod_version("yaml"),
        "jsonschema": _mod_version("jsonschema"),
        "python-hcl2": _mod_version("hcl2"),
        "mcp_adapter": _mod_version("mcp", optional=True),
        "boto3": _mod_version("boto3", optional=True),
    }
    ok = all(v != "missing" for k, v in checks.items() if k in ("pyyaml", "jsonschema", "python-hcl2"))
    detail: dict[str, Any] = {}
    if getattr(args, "deep", False):
        detail = _doctor_deep(args)
        ok = ok and all(v.get("ok", True) for v in detail.values())
    return _emit({"ok": ok, "checks": checks, "deep": detail}, args, 0 if ok else 1)


def _doctor_deep(args: argparse.Namespace) -> dict[str, Any]:
    out: dict[str, Any] = {}
    from platformforge.core.workspace import load_workspace

    ws = load_workspace(getattr(args, "repo", "."))
    # config
    out["config"] = {
        "ok": True,
        "workspace": ws.name,
        "multi_repo": ws.is_multi_repo,
        "members": len(ws.members) or 1,
    }
    # capability manifest
    try:
        from platformforge.forge import capability_manifest

        m = capability_manifest(args.repo)
        out["capability_manifest"] = {
            "ok": bool(m.get("tools")),
            "tools": len(m.get("tools", [])),
            "rules": m.get("rule_count"),
        }
    except (OSError, ValueError, KeyError) as e:
        out["capability_manifest"] = {"ok": False, "error": str(e)}
    # knowledge freshness
    try:
        from platformforge.knowledge.registry import SourceRegistry

        reg = SourceRegistry.default()
        check = reg.check()
        stale = [c["id"] for c in check if c["status"] in ("stale", "unresolved", "conflicted")]
        out["knowledge_freshness"] = {
            "ok": True,
            "entries": len(check),
            "attention": stale,
            "contract": reg.contract_check(),
        }
    except (OSError, ValueError, KeyError) as e:
        out["knowledge_freshness"] = {"ok": False, "error": str(e)}
    # host parity (host adapter files present?)
    parity = {}
    for host, marker in (("claude", ".claude"), ("devin", ".devin"), ("agents", ".agents")):
        parity[host] = (ws.root / marker).exists()
    out["host_parity"] = {"ok": True, "adapters": parity}
    # index health (tokensave db)
    idx = ws.pf_dir / "index.db"
    out["index_health"] = {
        "ok": True,
        "present": idx.is_file(),
        "bytes": idx.stat().st_size if idx.is_file() else 0,
    }
    # artifact store
    try:
        from platformforge.core.store import ArtifactStore

        st = ArtifactStore(ws.root).stats()
        out["artifact_store"] = {"ok": True, **st}
    except (OSError, ValueError, KeyError) as e:
        out["artifact_store"] = {"ok": False, "error": str(e)}
    return out


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
    return _emit(
        {
            "workspace": ws.name,
            "root": str(ws.root),
            "multi_repo": ws.is_multi_repo,
            "members": [m.name for m in ws.members] or [ws.name],
            "store": store.stats(),
        },
        args,
    )


def _member_dirs(path: str | Path) -> list[tuple[str, Path]]:
    """§126 — a workspace.yaml root expands to its member repos."""
    from platformforge.core.workspace import load_workspace

    ws = load_workspace(path)
    if ws.is_multi_repo:
        return [(m.name, p) for m, p in zip(ws.members, ws.member_paths(), strict=True) if p.is_dir()]
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
    out: dict[str, Any] = {"facts": facts, "workspace": {n: str(p) for n, p in members}}
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
    ignore = {".git", ".venv", "node_modules", ".platformforge", "vendor", "__pycache__", "dist", "build"}
    for mname, mroot in members:
        for p in sorted(mroot.rglob("*")):
            if not p.is_file() or any(part in ignore for part in p.parts):
                continue
            rel = f"{mname}/{p.relative_to(mroot)}" if mname else str(p.relative_to(mroot))
            for kind, pats in kinds.items():
                if any(p.match(pat) or rel.endswith(pat.lstrip("*")) for pat in pats):
                    inventory[kind].append(rel)
    inventory = {k: v for k, v in inventory.items() if v}
    return _emit(
        {
            "root": str(root),
            "artifacts": inventory,
            "members": [n or str(p) for n, p in members],
            "counts": {k: len(v) for k, v in inventory.items()},
        },
        args,
    )


def cmd_judge(args: argparse.Namespace) -> int:
    """Apply rule catalog to a facts JSON document (or analyzed facts file)."""
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog

    facts_doc = json.loads(Path(args.facts).read_text())
    facts, skipped_inputs = [], []
    for f in facts_doc.get("facts", facts_doc):
        try:
            facts.append(Fact.from_dict(f))
        except (TypeError, ValueError, KeyError):
            skipped_inputs.append(f)
    versions = facts_doc.get("versions", {}) if isinstance(facts_doc, dict) else {}
    if getattr(args, "versions", ""):
        versions = {**versions, **json.loads(args.versions)}
    catalog_dirs = args.catalog or [data_path("rules", "catalog")]
    rules = load_catalog(*catalog_dirs)
    findings, skipped = RuleEngine(rules, versions).evaluate(facts)
    out = {
        "findings": [f.to_dict() for f in findings],
        "skipped": skipped,
        "counts": {
            "facts": len(facts),
            "rules": len(rules),
            "violated": sum(1 for f in findings if f.status == "violated"),
            "skipped_inputs": len(skipped_inputs),
        },
        "skipped_facts": skipped_inputs,
    }
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
        out = reg.drift_report(data_path("rules", "catalog"))
        return _emit(out, args)
    if sub == "packs":
        from platformforge.knowledge.packs import PackRegistry

        packs = PackRegistry.default()
        out = {
            "packs": [p.to_dict() for p in sorted(packs.packs.values(), key=lambda x: x.pack_id)],
            "contract": packs.contract_check(),
        }
        return _emit(out, args, 2 if (args.strict and not out["contract"]["ok"]) else 0)
    report = reg.check()
    bad = [
        r for r in report if r["status"] in ("stale", "unresolved", "conflicted", "deprecated", "superseded")
    ]
    return _emit(
        {"sources": report, "attention": bad, "counts": {"total": len(report), "attention": len(bad)}},
        args,
        2 if (args.strict and bad) else 0,
    )


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
        mode = getattr(args, "mode", "literal") or "literal"
        if mode == "regex":
            out = {"hits": idx.search_regex(args.query, args.limit)}
        elif mode == "symbol":
            out = {"hits": idx.symbol(args.query)}
        elif mode == "path":
            out = {"hits": [{"path": p} for p in
                            idx.by_path(args.query)]}
        elif mode == "kind":
            out = {"hits": [{"path": p} for p in
                            idx.by_kind(args.query)]}
        else:
            out = {"hits": idx.search(args.query, args.limit)}
        out["mode"] = mode
    elif args.tokens_cmd == "pack":
        ledger = TokenLedger(args.repo)
        prev_files = None
        if getattr(args, "prev_pack", None):
            try:
                prev = json.loads(Path(args.prev_pack).read_text())
                prev_files = {f["path"]: f.get("sha256", "")
                              for f in prev.get("relevant_files", [])
                              if isinstance(f, dict)}
            except (OSError, json.JSONDecodeError):
                prev_files = None
        pack = ContextPackBuilder(idx, ledger).build(
            task=args.task,
            budget=Budget(input_budget=args.input_budget),
            changed_files=args.changed or [],
            graph_neighborhood=getattr(args, "graph_nodes", None) or None,
            risk=getattr(args, "risk", None) or None,
            previous_pack_hash=getattr(args, "prev_pack", None) or None,
            previous_files=prev_files,
            allow_escalate=getattr(args, "allow_escalate", False),
        )
        out = pack
    elif args.tokens_cmd == "delta":
        ledger = TokenLedger(args.repo)
        out = ContextPackBuilder(idx, ledger).delta_for_change(
            changed_files=args.changed or [],
            budget=Budget(input_budget=args.input_budget),
            previous_pack_hash=getattr(args, "prev_pack", None) or None,
            risk=getattr(args, "risk", None) or None,
        )
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
    res = compact_output(args.command or "", output, exit_code=args.exit_code, store=store)
    return _emit(res.to_dict(), args)


def cmd_rtk_expand(args: argparse.Namespace) -> int:
    from platformforge.core.store import ArtifactStore
    from platformforge.rtk.compact import expand

    out = expand(
        ArtifactStore(args.repo), args.artifact, start=args.start, end=args.end, pattern=args.pattern
    )
    return _emit(out, args)


def cmd_caveman(args: argparse.Namespace) -> int:
    from platformforge.caveman import compress

    text = Path(args.file).read_text() if args.file != "-" else sys.stdin.read()
    out, receipt = compress(text, mode=args.mode, context_risk=args.context_risk)
    return _emit({"compressed": out, "receipt": receipt.to_dict()}, args)


def cmd_store(args: argparse.Namespace) -> int:
    """§151 — store stats / gc. GC is dry-run unless --execute."""
    import re

    from platformforge.core.store import ArtifactStore

    store = ArtifactStore(args.repo)
    if args.store_cmd == "stats":
        return _emit({"store": store.stats()}, args)
    # collect hashes referenced anywhere under .platformforge/ (receipts,
    # packs, ledger) — referenced artifacts are never GC candidates
    referenced: set[str] = set()
    root = Path(args.repo) / ".platformforge"
    pat = re.compile(r"artifact://sha256/([0-9a-f]{64})")
    for doc in root.rglob("*.json") if root.exists() else []:
        if "store" in doc.parts:
            continue
        referenced.update(pat.findall(doc.read_text(errors="replace")))
    out = store.gc(keep_days=args.keep_days, referenced=referenced, dry_run=not args.execute)
    return _emit(out, args)


def cmd_bench(args: argparse.Namespace) -> int:
    """§148–150 — measured benchmarks over the eval corpus fixtures."""
    from platformforge import bench

    if args.bench_cmd == "scale":
        # cycle5 §317 — controlled-size graph + analytics store bench
        from platformforge.graph.bench import run_scale_benchmarks
        sizes = tuple(int(s) for s in (args.sizes or "50,200,800")
                      .split(","))
        edges = tuple(int(s) for s in (args.edges or "100000,250000,500000")
                      .split(","))
        return _emit(run_scale_benchmarks(
            sizes, edge_targets=edges, store_sweep=args.events), args)
    fn = {"run": bench.run_benchmark, "tokens": bench.token_benchmark}[args.bench_cmd]
    return _emit(fn(repeat=args.repeat), args)


def cmd_freeze(args: argparse.Namespace) -> int:
    """Freeze governance — manifest, snapshots, drift check, exceptions."""
    import pathlib

    from platformforge import freeze as fz
    from platformforge.freeze.manifest import render_markdown

    if args.freeze_cmd == "manifest":
        out = args.out or "docs/freeze/FREEZE-MANIFEST.md"
        m = fz.build_manifest()
        if args.out == "-" or (not args.out and args.path == "-"):
            return _emit(m, args)
        pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(out).write_text(render_markdown(m))
        return _emit({"written": out, "sha": m["freeze_start_sha"],
                      "agents": m["agent_contracts"]["count"]}, args)
    if args.freeze_cmd == "snapshot":
        out = fz.write_snapshots(repo=args.path or ".",
                                 out=args.out or "docs/freeze/snapshots")
        return _emit({"written": str(out)}, args)
    if args.freeze_cmd == "check":
        r = fz.check_snapshots(
            repo=args.path or ".",
            snap_dir=args.out or "docs/freeze/snapshots")
        return _emit(r, args, 0 if r["verdict"] == "pass" else 1)
    if args.freeze_cmd == "exception":
        import json as _json
        if not args.json_file:
            return _emit({"refusal": "PF-FREEZE-EXCEPTION-INPUT",
                          "unlock": "freeze exception --spec <file>"}, args, 2)
        data = _json.loads(pathlib.Path(args.json_file).read_text())
        errs = fz.exception_errors(data)
        return _emit({"valid": not errs, "errors": errs}, args,
                     0 if not errs else 1)
    return 2


def cmd_cases(args: argparse.Namespace) -> int:
    """§52–§68 — real-world case corpus: list/validate/replay/template."""
    from platformforge.cases.casefile import discover_cases
    from platformforge.cases.replay import replay_all, validate_corpus, write_case_template

    root = args.path or ".platformforge/cases"
    if args.cases_cmd == "list":
        return _emit({"cases": [c.to_dict() for c in discover_cases(root)]},
                     args)
    if args.cases_cmd == "validate":
        r = validate_corpus(root)
        return _emit(r, args, 0 if r["verdict"] == "pass" else 1)
    if args.cases_cmd == "replay":
        r = replay_all(root, tier=args.tier or None)
        return _emit(r, args, 0 if r["verdict"] == "pass" else 1)
    if args.cases_cmd == "template":
        out = args.out or "case.yaml"
        write_case_template(out)
        return _emit({"written": out}, args)
    if args.cases_cmd == "ledger":
        from platformforge.cases.ledgers import ledger_report
        return _emit(ledger_report(), args)
    if args.cases_cmd == "ledger-check":
        from platformforge.cases.ledgers import validate_ledgers
        r = validate_ledgers()
        return _emit(r, args, 0 if r["verdict"] == "pass" else 1)
    if args.cases_cmd == "route-audit":
        from platformforge.cases.routing_audit import audit_corpus
        return _emit(audit_corpus(root), args)
    if args.cases_cmd == "route-bench":
        from platformforge.cases.routing_audit import champion_challenger
        return _emit(champion_challenger(
            root, challenger=args.out or None), args)
    if args.cases_cmd == "context-audit":
        from platformforge.cases.context_audit import audit_case, write_back
        from platformforge.cases.context_audit import audit_corpus as ctx_corpus
        if args.stamp:
            from platformforge.cases.casefile import discover_cases as dc
            for c in dc(root):
                write_back(c, audit_case(c))
        return _emit(ctx_corpus(root), args)
    return 2


def cmd_economy(args: argparse.Namespace) -> int:
    from platformforge.economy import EconomyEngine

    eng = EconomyEngine(args.repo)
    sub = getattr(args, "economy_cmd", "report") or "report"
    if sub == "strategy":
        sig = (
            json.loads(args.signal)
            if args.signal.strip().startswith("{")
            else {"task_type": args.signal or "analysis"}
        )
        return _emit(eng.strategy(sig), args)
    if sub == "compare":
        sig = (
            json.loads(args.signal)
            if args.signal.strip().startswith("{")
            else {"task_type": args.signal or "analysis"}
        )
        return _emit(eng.compare(sig), args)
    if sub == "qpt":
        # §30–32 — measured quality-per-token over a facts doc
        import json as _json

        from platformforge.economy.qpt import quality_per_token
        from platformforge.tokensave.budget import Budget

        facts_doc = _json.loads(Path(args.path).read_text())
        facts = facts_doc.get("facts", facts_doc)
        out = quality_per_token(
            facts_full=facts,
            findings_full=[],
            index=_index(args),
            task=args.task or "analysis",
            budget=Budget(input_budget=args.input_budget),
            versions=json.loads(args.versions) if getattr(args, "versions", "") else None,
        )
        return _emit(out, args, 2 if out.get("quality_gate") == "fail" else 0)
    if sub == "qpt-bench":
        # §43–46 — fixed corpus: full vs packed envelopes, same judge,
        # receipts per task with quality-before-economy verdicts
        from platformforge.economy.bench import run_qpt_bench

        out = run_qpt_bench()
        bad = [c["id"] for c in out["cases"] if c["verdict"] == "optimization_not_beneficial"]
        return _emit(out, args, 2 if (args.strict and bad) else 0)
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
    if sub in ("discover", "define", "design", "contract", "plan", "review", "learn", "build", "verify"):
        body: object = (
            json.loads(args.body)
            if args.body.strip().startswith("{")
            else (args.body or f"# {sub} for {args.feature}\n")
        )
        art = proj.write_artifact(args.feature, sub, body)
        return _emit({"wrote": art.path.name, "phase": sub, "upstream": art.upstream}, args)
    if sub == "status":
        return _emit(proj.status(args.feature), args)
    if sub == "check":
        out = proj.check(args.feature)
        return _emit(out, args, 2 if (args.strict and not out["ok"]) else 0)
    if sub == "stamp":
        return _emit(proj.stamp(args.feature, args.phase), args)
    if sub == "ship":
        verify = json.loads(args.verify) if args.verify else None
        out = proj.ship(
            args.feature,
            verify=verify,
            risk_accepted=args.risk_accepted,
            override=args.override,
            override_reason=args.override_reason,
        )
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
        p = G.save(
            builder.graph, args.repo, source=args.facts, source_type=getattr(args, "source_type", "desired")
        )
        return _emit({"wrote": str(p), **builder.graph.stats()}, args)
    if sub == "snapshots":
        return _emit({"snapshots": G.snapshots(args.repo)}, args)
    g = _load_graph_or_refuse(args.repo)
    if g is None:
        return _emit(
            {"refusal": "PF-GRAPH-NOGRAPH", "unlock": "platformforge graph build <facts.json>"}, args, 2
        )
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
    if sub.startswith("identity-"):
        # §100–101 — identity path queries over the graph
        from platformforge.security.identity import (
            compromise_blast,
            who_can_access,
            who_can_become,
            workloads_using_identity,
        )

        target = args.node or args.dst or args.src
        fn = {
            "identity-become": who_can_become,
            "identity-access": who_can_access,
            "identity-workloads": workloads_using_identity,
            "identity-blast": compromise_blast,
        }[sub]
        return _emit(fn(g, target), args)
    if sub == "diff":

        def _resolve(ref: str):
            if (Path(args.repo) / ".platformforge/graph" / f"{ref}.json").exists():
                return G.load(args.repo, ref)
            return G.load_snapshot(args.repo, ref)

        return _emit(G.diff(_resolve(args.before), _resolve(args.after)), args)
    if sub == "at":
        # §82 — graph as of timestamp T (nearest snapshot ≤ T)
        from platformforge.graph import temporal as T
        if not args.at:
            return _emit(
                {"refusal": "PF-GRAPH-NO-TS",
                 "unlock": "pass --at <ISO ts>"}, args, 2)
        snap = T.snapshot_at(args.repo, args.at)
        if snap is None:
            return _emit(
                {"refusal": "PF-GRAPH-NO-SNAPSHOT",
                 "unlock": "platformforge graph build <facts> first"},
                args, 2)
        g2 = T.graph_at(args.repo, args.at)
        return _emit({"snapshot": snap,
                      "stats": g2.stats() if g2 else None}, args)
    if sub == "timeline":
        # §82 — temporal provenance: first-seen / last-observed
        from platformforge.graph import temporal as T
        out: dict[str, Any] = {}
        if args.edge_id:
            out["edge_first_seen"] = T.edge_first_seen(
                args.repo, args.edge_id)
        if args.node:
            out["node_last_observed"] = T.node_last_observed(
                args.repo, args.node)
        if not out:
            return _emit(
                {"refusal": "PF-GRAPH-NO-TARGET",
                 "unlock": "pass --edge-id and/or --node"}, args, 2)
        return _emit(out, args)
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

        fn = {
            "cloud-aws": analyze_aws_dump,
            "cloud-azure": analyze_azure_dump,
            "cloud-gcp": analyze_gcp_dump,
        }[sub]
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
    if sub == "kyverno":
        from platformforge.security.kyverno import analyze_kyverno

        return _emit(analyze_kyverno(args.path, kyverno_version=args.kyverno_version or None), args)
    if sub == "cosign":
        from platformforge.security.cosign import analyze_cosign

        return _emit(analyze_cosign(args.path), args)
    if sub == "slsa":
        from platformforge.security.slsa import slsa_assess

        doc = json.loads(Path(args.path).read_text())
        prov = doc.get("provenance", doc)
        ev = doc.get("evidence") if isinstance(doc, dict) else None
        return _emit(slsa_assess(prov, evidence=ev), args)
    if sub == "sbom":
        from platformforge.security import analyze_sbom

        vulns = json.loads(Path(args.vulns).read_text()) if args.vulns else None
        return _emit(analyze_sbom(args.path, vuln_db=vulns), args)
    if sub == "ownership":
        from platformforge.core.ownership import analyze_ownership

        facts = _json_doc(args.facts, "facts") if getattr(args, "facts", "") else None
        return _emit(analyze_ownership(args.path, facts), args)
    if sub == "contradictions":
        from platformforge.core.ownership import detect_contradictions

        facts = [f for f in _json_doc(args.path, "facts")]
        out = detect_contradictions(facts)
        return _emit(
            {
                "facts": out,
                "contradictions": len(out),
                "boundary": "declared-vs-observed diffs are named, never resolved silently",
            },
            args,
        )
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

        return _emit(_run_over_members(getattr(importlib.import_module(mod), fn), args.path), args)
    return _emit({"error": f"unknown analyze domain {sub}"}, args, 1)


def cmd_product(args: argparse.Namespace) -> int:
    from platformforge import product as P

    sub = args.product_cmd
    if sub == "maturity":
        sig = json.loads(Path(args.signals).read_text())
        return _emit(P.maturity_report(sig.get("signals", sig), sig.get("evidence")), args)
    if sub == "scorecard":
        doc = json.loads(Path(args.findings).read_text())
        findings = doc.get("findings", doc)
        from platformforge.product.scorecards import scorecard

        return _emit(scorecard(findings), args)
    if sub == "backstage":
        g = _load_graph_or_refuse(args.repo)
        if g is None:
            return _emit(
                {"refusal": "PF-GRAPH-NOGRAPH", "unlock": "platformforge graph build <facts.json>"}, args, 2
            )
        return _emit(P.to_backstage(g), args)
    if sub == "paths":
        from platformforge.product.golden_paths import load_library

        lib = load_library()
        return _emit(
            {
                "paths": [
                    {"id": p.id, "name": p.name, "version": p.version, "use_case": p.use_case}
                    for p in lib["paths"]
                ],
                "invalid": lib["invalid"],
            },
            args,
        )
    if sub == "path":
        from platformforge.product.golden_paths import describe

        return _emit(describe(args.id), args)
    if sub == "capabilities":
        from platformforge.product.golden_paths import capabilities

        return _emit(capabilities(), args)
    if sub == "path-analyze":
        if args.facts:
            doc = json.loads(Path(args.facts).read_text())
            facts = doc.get("facts", doc)
        else:
            from platformforge.collect import collect

            facts = collect(args.repo)["facts"]
        from platformforge.product.golden_paths import analyze_paths

        return _emit(analyze_paths(facts), args)
    return _emit({"error": f"unknown product verb {sub}"}, args, 1)


def cmd_agents(args: argparse.Namespace) -> int:
    from platformforge import agents as A
    from platformforge.agents.mirrors import check, lint, sync

    sub = args.agents_cmd
    if sub == "list":
        return _emit({"agents": [a.to_dict() for a in A.AGENTS.values()]}, args)
    if sub == "lint":
        out = lint()
        return _emit(out, args, 0 if out["ok"] else 2)
    if sub == "check":
        out = check(args.repo)
        return _emit(out, args, 0 if out["ok"] else 2)
    if sub == "sync":
        return _emit({"written": sync(args.repo)}, args)
    if sub == "playbook":
        return _emit(A.playbook(args.name or "platform-orchestrator", domain=args.domain), args)
    if sub == "bench":
        return _emit(A.run_agent_bench(), args)
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
        out = lab.runner.run_all(profile=args.profile or None, allow_profile=args.allow_profile)
        return _emit(out, args, 0 if not out["failed"] else 2)
    if args.lab_cmd == "chaos":
        from platformforge.lab.chaos import run_scenario

        return _emit(run_scenario(args.path or "", allow_prod=args.allow_prod), args)
    out = lab.run(args.path or "", allow_profile=args.allow_profile)
    return _emit(out, args, 2 if "refusal" in out else 0)


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
        return _emit(
            {"refusal": "PF-GRAPH-NOGRAPH", "unlock": "platformforge graph build <facts.json>"}, args, 2
        )
    from platformforge.diagnose import diagnose

    findings = _json_doc(args.findings, "findings") if args.findings else []
    facts = _json_doc(args.facts, "facts") if args.facts else []
    return _emit(diagnose(g, args.node, findings, facts), args)


def cmd_plan(args: argparse.Namespace) -> int:
    """§7 plan — findings → ordered remediation plan."""
    from platformforge.plan import remediation_plan

    findings = _json_doc(args.path, "findings")
    facts = _json_doc(args.facts, "facts") if args.facts else []
    g = _load_graph_or_refuse(args.repo)  # optional enrichment
    return _emit(remediation_plan(findings, g, facts), args)


def cmd_correlate(args: argparse.Namespace) -> int:
    """§7 correlate — OTel/telemetry correlation (observe otel)."""
    from platformforge import observe as O

    return _emit(O.correlate_spans(args.path), args)


def _build_graph_from(path: str):
    from platformforge.graph import GraphBuilder

    doc = json.loads(Path(path).read_text())
    return GraphBuilder().from_facts(doc.get("facts", doc if isinstance(doc, list) else [])).graph


def cmd_diff(args: argparse.Namespace) -> int:
    """§7 diff — graph diff between two facts docs."""
    from platformforge.graph.diff import diff as graph_diff

    return _emit(graph_diff(_build_graph_from(args.before), _build_graph_from(args.after)), args)


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
        return _emit(
            {"refusal": "PF-GRAPH-NOGRAPH", "unlock": "platformforge graph build <facts.json>"}, args, 2
        )
    from platformforge.graph.query import blast_radius

    return _emit(blast_radius(g, args.node), args)


def cmd_context(args: argparse.Namespace) -> int:
    """§7 context — context pack for a task (tokens pack)."""
    from platformforge.tokensave.budget import Budget
    from platformforge.tokensave.ledger import TokenLedger
    from platformforge.tokensave.packs import ContextPackBuilder

    pack = ContextPackBuilder(_index(args), TokenLedger(args.repo)).build(
        task=args.task, budget=Budget(input_budget=args.input_budget), changed_files=args.changed or []
    )
    return _emit(pack, args)


def cmd_policy(args: argparse.Namespace) -> int:
    """§7 policy — the rule catalog IS the policy layer."""
    from platformforge.rules import load_catalog

    cat_dir = data_path("rules", "catalog")
    rules = load_catalog(cat_dir)
    if args.policy_cmd == "list":
        return _emit(
            {"rules": [{"rule_id": r.rule_id, "domain": r.domain, "severity": r.severity} for r in rules]},
            args,
        )
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine

    facts = [Fact.from_dict(f) for f in _json_doc(args.path, "facts")]
    findings, skipped = RuleEngine(rules).evaluate(facts)
    out = {
        "findings": [f.to_dict() for f in findings],
        "skipped": skipped,
        "violated": [f.rule_id for f in findings if f.status == "violated"],
    }
    return _emit(out, args)


def cmd_security(args: argparse.Namespace) -> int:
    """§7 security — scan bundle: secrets + iam + sbom + supply → judge."""
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog
    from platformforge.security import analyze_iam_policy, analyze_sbom, analyze_supply, scan_secrets

    root = Path(args.path or args.repo)
    facts = scan_secrets(root)["facts"]
    extras = {
        "iam": ("policy.json", analyze_iam_policy),
        "sbom": ("sbom.json", analyze_sbom),
        "supply": ("supply.json", analyze_supply),
    }
    present = []
    for name, (fname, fn) in extras.items():
        p = root / fname
        if p.exists():
            facts += fn(str(p))["facts"]
            present.append(name)
    cat_dir = data_path("rules", "catalog")
    cat = [r for r in load_catalog(cat_dir) if r.domain == "security"]
    findings, skipped = RuleEngine(cat).evaluate([Fact.from_dict(f) for f in facts])
    unresolved = [f for f in findings if f.status != "violated"]
    return _emit(
        {
            "facts": facts,
            "analyzers_run": ["secrets", *present],
            "findings": [f.to_dict() for f in findings if f.status == "violated"],
            "unresolved": [f.to_dict() for f in unresolved],
            "skipped": skipped,
        },
        args,
    )


def cmd_reliability(args: argparse.Namespace) -> int:
    """§7 reliability — SRE+K8S rules over a facts doc."""
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine, load_catalog

    cat_dir = data_path("rules", "catalog")
    rules = [r for r in load_catalog(cat_dir) if r.domain in ("sre", "k8s")]
    facts = [Fact.from_dict(f) for f in _json_doc(args.path, "facts")]
    findings, skipped = RuleEngine(rules).evaluate(facts)
    violated = [f for f in findings if f.status == "violated"]
    unresolved = [f for f in findings if f.status == "unresolved"]
    return _emit(
        {
            "findings": [f.to_dict() for f in violated],
            "unresolved": [f.to_dict() for f in unresolved],
            "skipped": skipped,
            "counts": {"violated": len(violated), "unresolved": len(unresolved)},
        },
        args,
    )


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
        d = cases or __import__("platformforge.evals.runner", fromlist=["CASES_DIR"]).CASES_DIR
        return _emit(
            {"cases": [c.parent.name for c in sorted(d.glob("*/case.yaml"))] if Path(d).is_dir() else []},
            args,
        )
    if args.evals_cmd == "coverage":
        # §122 — rule → variant coverage matrix
        from platformforge.evals.coverage import rule_coverage

        out = rule_coverage(cases) if cases else rule_coverage()
        return _emit(out, args)
    if args.evals_cmd == "precision":
        # §127 — measured FP rate over negative/boundary cases
        from platformforge.evals.coverage import precision_report

        out = precision_report(cases) if cases else precision_report()
        return _emit(out, args)
    out = run_all(cases, type_filter=args.type or None) if cases else run_all(type_filter=args.type or None)
    return _emit(out, args, 2 if out["counts"]["fail"] else 0)


def cmd_risk(args: argparse.Namespace) -> int:
    """§130–131 risk engine + criticality."""
    from platformforge.risk.engine import assess_change

    signals: dict[str, Any] = {}
    if args.signals:
        signals = json.loads(Path(args.signals).read_text() if Path(args.signals).exists() else args.signals)
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
    if sub == "review":
        # §104 — full review pipeline over the sandbox delta
        from platformforge.sandbox.review import review_change

        patch = Path(args.patch).read_text() if args.patch else None
        files = {}
        for spec in args.file or []:
            rel, _, src = spec.partition("=")
            files[rel] = Path(src).read_text() if Path(src).exists() else src
        signals = {}
        if getattr(args, "signals", ""):
            signals = json.loads(Path(args.signals).read_text())
        out = review_change(args.repo, patch=patch, files=files, signals=signals)
        return _emit(out, args, 2 if "refusal" in out else 0)
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
        return _emit(
            {
                "refusal": "platform.change.core_read_only",
                "detail": "apply/approve are host-side boundaries; core emits verified sandbox diffs only",
                "unlock": "change verify --patch <diff> first",
            },
            args,
            2,
        )
    return _emit({"error": f"unknown change verb {sub}"}, args, 1)


def cmd_explain(args: argparse.Namespace) -> int:
    """§154 — evidence chain for a finding: why, which fact, which rule,
    which source, which version, and what unlocks an unresolved state."""
    doc = json.loads(Path(args.path).read_text())
    findings = doc.get("findings", doc if isinstance(doc, list) else [])
    f = next((x for x in findings if x.get("finding_id") == args.name or x.get("rule_id") == args.name), None)
    if not f:
        return _emit({"refusal": "platform.finding.unresolved", "name": args.name}, args, 2)
    facts_doc = json.loads(Path(args.facts).read_text()) if args.facts else doc.get("facts", [])
    by_id = {x.get("fact_id"): x for x in facts_doc}
    chain = [{"fact_id": e, "fact": by_id.get(e, "unresolved")} for e in f.get("evidence", [])]
    # §154 — resolve the rule's provenance: source(s) + version gate
    rule_meta: dict[str, Any] = {"rule_id": f.get("rule_id")}
    try:
        from platformforge.rules import load_catalog

        rule = next(
            (r for r in load_catalog(REPO_ROOT / "rules" / "catalog") if r.rule_id == f.get("rule_id")), None
        )
        if rule:
            rule_meta.update(
                {
                    "sources": getattr(rule, "sources", []),
                    "versions": getattr(rule, "versions", {}),
                    "severity": getattr(rule, "severity", None),
                }
            )
    except (OSError, ValueError):
        pass
    # what unlocks an unresolved/verdict-weak state
    unlock = []
    if not f.get("evidence"):
        unlock.append("collect the facts named by the rule's applies_to and re-run judge")
    fa = f.get("attrs") or {}
    if fa.get("refusal_code") == "platform.version.unresolved":
        unlock.append(fa.get("unlock") or "declare the required product version and re-run judge")
    if f.get("status") == "skipped":
        unlock.append("rule skipped: " + f.get("reason", "?"))
    return _emit({"finding": f, "evidence_chain": chain, "rule": rule_meta, "unlock": unlock}, args)


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
            skipped.append(
                {
                    "rule_id": f["rule_id"],
                    "reason": "finding without evidence — recommendation refused by contract",
                }
            )
            continue
        # §155 — qualitative expected direction only; quantified effect
        # would require a measured benchmark (model enforces this).
        sev = f.get("severity", "medium")
        recs.append(
            Recommendation(
                title=f.get("title") or f["rule_id"],
                severity=sev,
                confidence="declared",
                evidence=f["evidence"],
                root_cause=f.get("message", ""),
                proposed_change=[f.get("remediation", "resolve rule violation")],
                basis={"declared": f["evidence"]},
                risks=[f"change touches evidence {e}" for e in f["evidence"][:3]]
                or ["no evidence — refused upstream"],
                validation=[
                    (f"re-run analyze+judge after change; finding {f.get('rule_id')} must flip to passed")
                ],
                rollback=["revert the diff; verify no new violations"],
                tradeoffs=[
                    (
                        "remediation may require downtime/coordination "
                        "depending on blast radius — assess before "
                        "apply"
                    )
                ],
                expected_effect="direction: risk reduction (unquantified — no benchmark exists)",
            ).to_dict()
        )
    return _emit(
        {
            "recommendations": recs,
            "count": len(recs),
            "refused": skipped,
            "boundary": "expected_effect is directional; quantified claims require benchmark_ref",
        },
        args,
    )


def cmd_capability(args: argparse.Namespace) -> int:
    """Capability registry projection — same source as the MCP adapter."""
    from platformforge.mcp.registry import CAPABILITIES

    sub = args.capability_cmd
    if sub == "list":
        return _emit({"capabilities": [c.contract() for c in CAPABILITIES.values()]}, args)
    if sub == "describe":
        c = CAPABILITIES.get(args.name or "")
        if not c:
            return _emit(
                {
                    "refusal": "platform.capability.unresolved",
                    "name": args.name,
                    "unlock": "platformforge capability list",
                },
                args,
                2,
            )
        return _emit({**c.contract(), "description": c.description, "handler": c.handler}, args)
    if sub == "check":
        # §139 — capability negotiation: "can you analyze X at version Y?"
        dom, ver = (args.domain or ""), (args.version or "")
        matches = [
            c
            for c in CAPABILITIES.values()
            if c.domain == dom or dom in c.description.lower() or dom in c.name
        ]
        if not matches:
            return _emit(
                {
                    "supported": False,
                    "refusal": "platform.capability.unresolved",
                    "domain": dom,
                    "unlock": "platformforge capability list",
                },
                args,
                2,
            )
        out = {
            "supported": True,
            "domain": dom,
            "version": ver,
            "capabilities": [c.contract() for c in matches],
            "version_note": None,
        }
        if ver:
            from platformforge.knowledge.registry import SourceRegistry

            reg = SourceRegistry.default()
            srcs = [s for s in reg.entries.values() if dom and dom.split("-")[0] in (s.product or s.id)]
            out["version_note"] = {
                "declared": ver,
                "known_sources": [
                    {"id": s.id, "version": s.version, "freshness": s.freshness()} for s in srcs
                ],
                "caveat": "version support is evidence-bound — unknown "
                "versions degrade to unresolved, not assumed",
            }
        return _emit(out, args)
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
        d = FG.Delegation(
            from_forge=args.src or "platform-forge",
            to_forge=args.dst or "?",
            task=args.name or "",
        )
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
        out = O.error_budget(
            contract, **{k: v for k, v in sli.items() if k in ("good_events", "bad_events", "total_events")}
        )
        # wrap as fact so `judge` can evaluate PF-SLO-* rules
        fact = {
            "fact_id": out.pop("fact_id", ""),
            "kind": "sre.error_budget",
            "source": args.path,
            "location": contract.service,
            "tier": 0,
            "attrs": out,
        }
        return _emit({"result": out, "facts": [fact]}, args)
    if sub == "otel":
        return _emit(O.correlate_spans(args.path), args)
    if sub == "incident":
        alerts = json.loads(Path(args.alerts).read_text())
        changes = json.loads(Path(args.changes).read_text())
        g = _load_graph_or_refuse(args.repo)
        return _emit(O.correlate(alerts, changes, graph=g, window_s=args.window), args)
    if sub == "slo-burn":
        contract = O.SloContract.load(args.path)
        wins = json.loads(args.windows) if args.windows else {}
        return _emit(O.multi_window_burn(contract, wins), args)
    if sub == "semconv":
        return _emit(O.analyze_semconv(args.path), args)
    if sub == "timeline":
        events = json.loads(Path(args.path).read_text())
        return _emit(O.timeline(events), args)
    if sub == "postmortem":
        inc = json.loads(Path(args.incident or args.path).read_text())
        return _emit(O.postmortem(inc, inc.get("hypotheses")), args)
    if sub == "dr":
        if args.facts:
            doc = json.loads(Path(args.facts).read_text())
            facts = doc.get("facts", doc)
        else:
            from platformforge.collect import collect

            facts = collect(args.repo)["facts"]
        return _emit(O.dr_model(facts), args)
    if sub == "prometheus":
        return _emit(O.analyze_prometheus(args.path), args)
    if sub == "grafana":
        return _emit(O.analyze_grafana(args.path), args)
    if sub == "capacity":
        items = json.loads(Path(args.path).read_text())
        out = O.capacity(items)
        facts = [
            {
                "fact_id": "",
                "kind": "sre.capacity",
                "source": args.path,
                "location": c["resource"] or "?",
                "tier": 0,
                "attrs": c,
            }
            for c in out["capacity"]
        ]
        return _emit({**out, "facts": facts}, args)
    return _emit({"error": f"unknown observe verb {sub}"}, args, 1)


def cmd_live(args: argparse.Namespace) -> int:
    """§7 live — read-only provider observation surface (Cycle 3)."""
    from platformforge.live.collectors import aws_transport, k8s_transport
    from platformforge.live.collectors.aws import AwsCollector, required_permissions
    from platformforge.live.collectors.k8s import K8sCollector, required_rbac
    from platformforge.live.cursors import CursorStore
    from platformforge.live.models import ObservationScope
    from platformforge.live.store import ChangeJournal, ObservationStore

    sub = args.live_cmd
    # §25 — offline mode refuses live transports before any subprocess
    if getattr(args, "offline", False) and sub in ("snapshot", "doctor"):
        return _emit({"refusal": "PF-LIVE-OFFLINE",
                      "unlock": f"`live {sub}` spawns provider binaries — "
                                "drop --offline or use replay fixtures"},
                     args, 2)
    if sub == "rbac":
        return _emit(required_rbac(namespaced_only=args.namespaced_only), args)
    if sub == "required-permissions":
        if args.provider == "aws":
            return _emit(required_permissions(), args)
        return _emit(required_rbac(namespaced_only=args.namespaced_only), args)
    if sub == "doctor":
        checks = {"kubernetes": k8s_transport.preflight(args.context)}
        if args.provider == "aws" or args.deep:
            checks["aws"] = aws_transport.preflight()
        store = ObservationStore(args.repo)
        checks["observation_store"] = {"ok": True, "path": str(store.root)}
        checks["cursors"] = {"cursors": len(CursorStore(args.repo).all())}
        out = {"checks": checks, "ok": all(c.get("ok", True) for c in checks.values())}
        return _emit(out, args, 0 if out["ok"] else 1)
    if sub == "status":
        store = ObservationStore(args.repo)
        out = store.status()
        out["cursors"] = CursorStore(args.repo).all()
        out["change_events"] = len(
            ChangeJournal(args.repo).read(limit=1_000_000))
        return _emit(out, args)
    if sub == "changes":
        # §38/§78 — CloudTrail-style change events (T1 evidence).
        # Read mode: no flags → emit journaled events. Collect mode:
        # --collect spawns the aws adapter (offline → PF-LIVE-OFFLINE).
        journal = ChangeJournal(args.repo)
        if args.gc:
            return _emit(journal.gc(), args)
        if args.events_file:
            evs = json.loads(Path(args.events_file).read_text())
            res = journal.append(evs)
            return _emit({"journal": res}, args)
        if not args.collect:
            return _emit({"events": journal.read(
                since=args.since or "", resource=args.resource or "")}, args)
        if getattr(args, "offline", False):
            return _emit(
                {"refusal": "PF-LIVE-OFFLINE",
                 "unlock": "`live changes --collect` spawns the aws "
                           "adapter — drop --offline"}, args, 2)
        if args.provider != "aws":
            return _emit(
                {"refusal": "PF-LIVE-UNKNOWN-PROVIDER",
                 "unlock": "change-event collection is currently "
                           "aws/cloudtrail only"}, args, 2)
        if not aws_transport.aws_available():
            return _emit(
                {"refusal": "PF-LIVE-NO-AWSCLI",
                 "unlock": "install aws CLI + configure credentials"},
                args, 2)
        collector = AwsCollector(transport=aws_transport.make_transport())
        pf = collector.preflight()
        if not pf.get("ok"):
            return _emit({"refusal": "PF-LIVE-AWS-CREDS",
                          "unlock": pf.get("hint", "configure creds")},
                         args, 2)
        events: list = []
        for region in (args.region or [""]):
            events.extend(collector.lookup_events(
                region=region, account=collector.account,
                start_time=args.since or "", end_time=args.until or ""))
        res = journal.append(events)
        return _emit({"collected": len(events), "journal": res,
                      "regions": args.region or ["default"]}, args)
    if sub == "snapshot":
        scope = ObservationScope(namespaces=args.namespace or [], resource_types=args.resource_type or [])
        if args.selector:
            scope.selectors["labels"] = args.selector
        budget = _live_budget(args)
        if args.provider == "kubernetes":
            if not k8s_transport.kubectl_available():
                return _emit(
                    {
                        "refusal": "PF-LIVE-NO-KUBECTL",
                        "unlock": "install kubectl + configure a kubeconfig context",
                    },
                    args,
                    2,
                )
            collector = K8sCollector(
                transport=k8s_transport.make_transport(args.context), context=args.context
            )
            env = collector.collect(scope, budget)
        elif args.provider == "aws":
            if not aws_transport.aws_available():
                return _emit(
                    {
                        "refusal": "PF-LIVE-NO-AWSCLI",
                        "unlock": "install aws CLI + configure credentials (aws sso login)",
                    },
                    args,
                    2,
                )
            collector = AwsCollector(transport=aws_transport.make_transport())
            pf = collector.preflight()
            if not pf.get("ok"):
                return _emit(
                    {
                        "refusal": "PF-LIVE-AWS-CREDS",
                        "unlock": pf.get("hint", "configure credentials"),
                        "detail": pf.get("error", ""),
                    },
                    args,
                    2,
                )
            scope.regions = args.region or ["us-east-1"]
            scope.services = args.service or []
            env = collector.collect(scope, budget)
        else:
            return _emit(
                {
                    "refusal": "PF-LIVE-UNKNOWN-PROVIDER",
                    "unlock": "platformforge live snapshot --provider kubernetes|aws",
                },
                args,
                2,
            )
        if args.no_store:
            return _emit({"envelope": env.to_dict()}, args)
        res = ObservationStore(args.repo).put(env)
        if "refusal" in res:
            return _emit(res, args, 2)
        return _emit(
            {
                **res,
                "provider": env.provider,
                "coverage": env.coverage.get("status"),
                "fresh_until": env.fresh_until,
                "scope": env.scope,
            },
            args,
        )
    if sub == "reconcile":
        from platformforge.live.reconcile import norm_facts, norm_observed, reconcile

        desired = []
        if args.desired:
            doc = json.loads(Path(args.desired).read_text())
            desired = doc.get("facts", doc)
        else:
            from platformforge.collect import collect

            desired = collect(args.repo).get("facts", [])
        obs_env = None
        if args.observed:
            p = Path(args.observed)
            if p.exists():
                from platformforge.live.envelope import loads

                obs_env = loads(p.read_text())
            else:
                obs_env = ObservationStore(args.repo).get(args.observed)
        elif not args.no_observed:
            latest = ObservationStore(args.repo).latest()
            if latest:
                obs_env = ObservationStore(args.repo).get(latest["observation_id"])
        if obs_env is None and not args.no_observed:
            return _emit(
                {
                    "refusal": "PF-LIVE-NO-OBSERVATION",
                    "unlock": "platformforge live snapshot "
                    "--provider kubernetes|aws, or pass "
                    "--observed <envelope.json|obs-id>",
                },
                args,
                2,
            )
        planned = []
        if args.planned:
            doc = json.loads(Path(args.planned).read_text())
            planned = doc.get("facts", doc)
        out = reconcile(
            desired=norm_facts(desired, "desired"),
            planned=norm_facts(planned, "planned"),
            observed=norm_observed(obs_env) if obs_env else None,
        )
        return _emit(out, args, 2 if args.strict and (out["totals"]["drift_events"] - out["accepted"]) else 0)
    if sub == "topology":
        from platformforge.live.topology import (
            apply_runtime_edges,
            classify_behavior,
            edges_from_endpointslices,
            edges_from_hubble,
            edges_from_otel,
        )

        edges: list[dict] = []
        if args.otel:
            doc = json.loads(Path(args.otel).read_text())
            edges += edges_from_otel(doc if isinstance(doc, list) else [doc])
        if args.hubble:
            p = Path(args.hubble)
            flows = []
            for f in sorted(p.rglob("*.json*")) if p.is_dir() else [p]:
                doc = json.loads(f.read_text())
                flows += doc if isinstance(doc, list) else [doc]
            edges += edges_from_hubble(flows)
        if args.slices:
            edges += edges_from_endpointslices(json.loads(Path(args.slices).read_text()))
        declared = set()
        g = _load_graph_or_refuse(args.repo)
        if g is not None:
            declared = set(g.edges)
        out = {
            "edges": classify_behavior(edges, declared),
            "runtime_undeclared": sum(
                1 for e in classify_behavior(edges, declared) if e["behavior"] == "observed-undeclared"
            ),
        }
        if g is not None and args.apply_to_graph:
            n = apply_runtime_edges(g, edges)
            from platformforge.graph import persist as gp

            gp.save(g, args.repo, source_type="runtime")
            out["applied_to_graph"] = n
        return _emit(out, args)
    if sub == "clusters":
        from platformforge.live.federation import Cluster, ClusterRegistry

        reg = ClusterRegistry(args.repo)
        if args.register:
            spec = json.loads(args.register)
            c = Cluster(spec.pop("cluster_id"), **spec)
            return _emit({"registered": reg.register(c)}, args)
        return _emit({"clusters": reg.list()}, args)
    if sub == "drift":
        from platformforge.graph.events import EventLedger
        from platformforge.live.drift import dedup_events, diff_observations

        store = ObservationStore(args.repo)

        def _env(ref: str):
            p = Path(ref)
            if p.exists():
                from platformforge.live.envelope import loads

                return loads(p.read_text())
            return store.get(ref)

        before_ref, after_ref = args.before, args.after
        if not (before_ref and after_ref):
            rows = store.list(limit=2)
            if len(rows) < 2:
                return _emit(
                    {
                        "refusal": "PF-LIVE-NEED-2-OBS",
                        "unlock": "collect ≥2 observations or pass --before/--after",
                    },
                    args,
                    2,
                )
            after_ref, before_ref = (rows[0]["observation_id"], rows[1]["observation_id"])
        b, a = _env(before_ref), _env(after_ref)
        if b is None or a is None:
            return _emit(
                {"refusal": "PF-LIVE-NO-OBSERVATION", "unlock": "valid observation ids or files"}, args, 2
            )
        out = diff_observations(b, a)
        ledger = EventLedger(args.repo)
        prior = ledger.events(kind="drift")
        kept, suppressed = dedup_events(out["drift"], [e.get("event", e) for e in prior])
        for e in kept:
            ledger.append({"kind": "drift", "event": e, "observation_id": a.observation_id})
        out["journaled"] = len(kept)
        out["suppressed_dupes"] = suppressed
        return _emit(out, args, 2 if args.strict and out["drift"] else 0)
    if sub == "incident":
        if not args.incident:
            return _emit(
                {"refusal": "PF-LIVE-NO-INCIDENT", "unlock": "pass --incident <incident.json>"}, args, 2
            )
        from platformforge.live.incident import build_timeline, postmortem_v3, score_candidates

        inc = json.loads(Path(args.incident).read_text())
        cands = json.loads(Path(args.changes).read_text()) if args.changes else []
        events = json.loads(Path(args.events).read_text()) if args.events else []
        graph = _load_graph_or_refuse(args.repo)
        tl = build_timeline(events + [inc])
        ranked = score_candidates(inc, cands, window_s=float(args.window), graph=graph)
        out = {
            **ranked,
            "postmortem": postmortem_v3(inc, tl, ranked)["postmortem"],
            "timeline_counts": tl["counts"],
        }
        return _emit(
            out,
            args,
            2
            if args.strict and not any(h["status"] in ("confirmed", "supported") for h in ranked["ranked"])
            else 0,
        )
    if sub == "plan":
        from platformforge.live.remediate import remediate

        if args.drift_events:
            events = json.loads(Path(args.drift_events).read_text())
        else:
            from platformforge.live.drift import diff_observations

            store = ObservationStore(args.repo)
            rows = store.list(limit=2)
            if len(rows) < 2:
                return _emit(
                    {
                        "refusal": "PF-LIVE-NO-DRIFT-INPUT",
                        "unlock": "pass --drift-events <file> or collect ≥2 observations",
                    },
                    args,
                    2,
                )
            events = diff_observations(
                store.get(rows[1]["observation_id"]), store.get(rows[0]["observation_id"])
            )["drift"]
        out = remediate(events)
        return _emit(out, args, 2 if args.strict and out["counts"]["mutating"] else 0)
    if sub == "capability":
        from platformforge.live.capability import availability

        return _emit(availability(args.repo), args)
    return _emit({"error": f"unknown live verb {sub}"}, args, 1)


def cmd_ops(args: argparse.Namespace) -> int:
    """cycle4 — governed operations surface. Dry-run is the default;
    real mutation requires --execute AND a valid hash-bound approval."""
    from platformforge.live.models import now_iso
    from platformforge.ops import engine
    from platformforge.ops.actions import spec_for
    from platformforge.ops.approval import Approval
    from platformforge.ops.config import load_config, validate_config
    from platformforge.ops.models import ChangeIntent, Reason
    from platformforge.ops.operation import LockTable
    from platformforge.ops.policy import Policy
    from platformforge.ops.registry import ops_capabilities, validate_delegate_request
    from platformforge.ops.store import OperationStore

    sub = args.ops_cmd

    if sub == "capabilities":
        return _emit(ops_capabilities(), args)

    if sub == "config":
        r = load_config(root=args.repo)
        if "refusal" in r:
            return _emit(r, args, 2)
        r["violations"] = validate_config(r["config"])
        return _emit(r, args, 2 if r["violations"] else 0)

    if sub == "delegate":
        req = json.loads(Path(args.request).read_text()) if args.request else {}
        out = validate_delegate_request(req)
        return _emit(out, args, 2 if "refusal" in out else 0)

    if sub == "intent":
        doc = json.loads(Path(args.intent).read_text())
        intent = (
            ChangeIntent.from_dict(doc)
            if hasattr(ChangeIntent, "from_dict")
            else ChangeIntent(
                intent_id=doc.get("intent_id", ""),
                owner=doc.get("owner", ""),
                requested_by=doc.get("requested_by", ""),
                reason=Reason(**doc.get("reason", {"type": "manual"})),
                target_resources=doc.get("target_resources", []),
                desired_change=doc.get("desired_change", {}),
            )
        )
        out = engine.propose(intent, resources=doc.get("resources", []), sot_context=doc.get("sot_context"))
        return _emit(out, args, 2 if not out.get("ok") else 0)

    if sub == "plan":
        doc = _load_plan_doc(args.plan)
        plan = engine.plan(doc["intent"], steps=doc["steps"], expected_delta=doc["expected_delta"])
        v = plan.validate()
        out = {"plan_id": plan.plan_id, "hash": plan.hash(), "steps": len(plan.steps), "violations": v}
        return _emit(out, args, 2 if v else 0)

    if sub == "simulate":
        from platformforge.ops.simulate import simulate

        doc = _load_plan_doc(args.plan)
        plan = engine.plan(doc["intent"], steps=doc["steps"], expected_delta=doc["expected_delta"])
        r = simulate(plan, level=args.level)
        return _emit(r.to_dict(), args, 2 if r.outcome == "fail" else 0)

    if sub == "risk":
        doc = _load_plan_doc(args.plan)
        plan = engine.plan(doc["intent"], steps=doc["steps"], expected_delta=doc["expected_delta"])
        return _emit(engine.assess_risk(plan, {"environment": args.environment}), args)

    if sub == "policy-eval":
        doc = _load_plan_doc(args.plan)
        plan = engine.plan(doc["intent"], steps=doc["steps"], expected_delta=doc["expected_delta"])
        pols = [Policy(**p) for p in _load_yaml_list(args.policies)]
        d = engine.decide(plan, pols, {"environment": args.environment})
        return _emit(d.to_dict(), args, 2 if d.decision == "deny" else 0)

    if sub == "runbook":
        from platformforge.ops.runbook import BUILTIN_RUNBOOKS

        name = args.name_pos or args.name or "list"
        if name == "list":
            return _emit(
                {
                    "runbooks": [
                        {
                            "id": rb.runbook_id,
                            "title": rb.title,
                            "risk": rb.risk.get("class", "?"),
                            "approval_required": rb.approval_required,
                            "hash": rb.hash(),
                        }
                        for rb in BUILTIN_RUNBOOKS.values()
                    ]
                },
                args,
            )
        rb = BUILTIN_RUNBOOKS.get(name)
        if rb is None:
            return _emit(
                {"refusal": "PF-OPS-RUNBOOK-UNKNOWN", "unlock": f"known: {sorted(BUILTIN_RUNBOOKS)}"}, args, 2
            )
        if args.bind:
            bound = rb.bind(json.loads(Path(args.bind).read_text()))
            return _emit(
                {**bound, "steps": [s.__dict__ for s in bound.get("steps", [])]}
                if bound.get("ok")
                else bound,
                args,
                0 if bound.get("ok") else 2,
            )
        return _emit(rb.to_dict(), args)

    if sub == "run":
        if getattr(args, "offline", False) and args.execute:
            return _emit({"refusal": "PF-OPS-OFFLINE",
                          "unlock": "--execute spawns host transports; "
                                    "drop --offline or run dry-run"},
                         args, 2)
        spec = _load_yaml_or_json(args.spec)
        return _ops_run(args, spec)

    if sub == "approve":
        # Mint a signed, hash-bound Approval artifact — feeds the
        # `approvals:` list of an `ops run` spec. Never executes.
        ap = Approval(
            approval_id=args.approval_id or f"ap-{args.subject_hash[-12:]}",
            subject_hash=args.subject_hash,
            subject_kind=args.subject_kind,
            scope=[s for s in (args.scope or "").split(",") if s],
            actor=args.actor,
            actor_kind=args.actor_kind,
            role=args.role,
            type=args.approval_type,
            expires_at=args.expires_at,
            parameter_bounds=json.loads(Path(args.bounds).read_text()) if args.bounds else {},
            reason=args.reason,
        )
        ap.sign()
        return _emit(ap.to_dict(), args, 0 if args.subject_hash else 2)

    if sub == "status":
        st = OperationStore(Path(args.repo) / ".platformforge/operations")
        op = st.load_operation(args.operation_id)
        if op is None:
            return _emit(
                {
                    "refusal": "PF-OPS-UNKNOWN-OPERATION",
                    "unlock": f"known: {st.list_operations()}",
                },
                args,
                2,
            )
        return _emit({**op.to_dict(), "ledger": st.verify(args.operation_id)}, args)

    if sub == "history":
        st = OperationStore(Path(args.repo) / ".platformforge/operations")
        rows = []
        ids = [args.operation_id] if args.operation_id else st.list_operations()
        for oid in ids:
            for e in st.load_ledger(oid).entries:
                if args.resource and args.resource not in json.dumps(e.data):
                    continue
                rows.append(e.to_dict())
        rows.sort(key=lambda r: (r["at"], r["seq"]))
        return _emit({"entries": rows, "count": len(rows)}, args)

    if sub == "rollback":
        st = OperationStore(Path(args.repo) / ".platformforge/operations")
        op = st.load_operation(args.operation_id)
        envd = st.load_envelope(args.operation_id)
        if op is None or envd is None:
            return _emit(
                {
                    "refusal": "PF-OPS-UNKNOWN-OPERATION",
                    "unlock": "rollback needs a stored op+envelope; "
                    "run `ops run` first",
                },
                args,
                2,
            )
        from platformforge.ops.envelope import ExecutionEnvelope
        from platformforge.ops.executors.base import host_transport

        if getattr(args, "offline", False) and args.execute:
            return _emit(
                {
                    "refusal": "PF-OPS-OFFLINE",
                    "unlock": "--execute spawns host transports",
                },
                args,
                2,
            )
        env = ExecutionEnvelope.from_dict(envd)
        transports = {}
        if args.execute:
            t = host_transport()
            transports = {s.executor: t for s in (spec_for(a["action"]) for a in env.actions) if s}
        ledger = st.load_ledger(args.operation_id)
        mats = st.load_materials(args.operation_id)
        out = engine.execute_rollback(
            op, env, transports=transports, ledger=ledger,
            locks=LockTable(),
            materials=mats,
            trigger={"type": "manual",
                     "requested_by": getattr(args, "actor", "") or "cli",
                     "at": now_iso()},
            post_rollback_state=json.loads(args.post_rollback)
            if getattr(args, "post_rollback", None) else None,
            dry_run=not args.execute,
        )
        st.save(op, ledger)
        return _emit(out, args, 0 if out.get("ok") else 2)

    if sub == "autorem-eval":
        from platformforge.ops.autorem import evaluate_eligibility
        from platformforge.ops.risk import classify_reversibility

        doc = _load_plan_doc(args.plan)
        plan = engine.plan(
            doc["intent"], steps=doc["steps"], expected_delta=doc["expected_delta"]
        )
        risk = engine.assess_risk(plan, {"environment": args.environment})
        worst = risk["risk_class"]
        actions = {s.action for s in plan.steps}
        rev = {classify_reversibility(s.action, s.params, {}) for s in plan.steps}
        out = evaluate_eligibility(
            action=min(actions) if actions else "",
            risk_class=worst,
            capability_autonomy="A5",
            environment=args.environment,
            evidence_tier=args.evidence_tier,
            observation=None,
            max_observation_age_s=900,
            source_of_truth={"resolved": bool(doc["intent"].target_resources)},
            reversibility="fully-reversible" if rev == {"fully-reversible"} else "conditionally-reversible",
            simulation_outcome=None,
            policy_decision=None,
            unresolved_identities=0,
            conflicting_operations=0,
            verification_available=bool(doc["expected_delta"]),
            rollback_ready=True,
        )
        return _emit(out.to_dict(), args, 0 if out.eligible else 2)

    if sub == "analytics":
        from platformforge.ops.analytics import operation_analytics

        st = OperationStore(Path(args.repo) / ".platformforge/operations")
        return _emit(operation_analytics(st), args)

    if sub == "graph":
        # Phase R wiring — rebuild the operational subgraph from
        # stored ledgers/envelopes (derived, never duplicated state).
        st = OperationStore(Path(args.repo) / ".platformforge/operations")
        ids = ([args.operation_id] if args.operation_id
               else st.list_operations())
        nodes: dict = {}
        edges: list = []
        missing: list = []
        for oid in ids:
            proj = st.projection(oid)
            if proj is None:
                missing.append(oid)
                continue
            for n in proj["nodes"]:
                nodes[n["node_id"]] = n
            edges.extend(proj["edges"])
        return _emit({"nodes": sorted(nodes.values(),
                                      key=lambda n: n["node_id"]),
                      "edges": edges,
                      "operations": [i for i in ids if i not in missing],
                      "missing": missing,
                      "counts": {"nodes": len(nodes), "edges": len(edges)}},
                     args, 2 if missing and not nodes else 0)

    if sub in ("store-list", "store-verify"):
        st = OperationStore(Path(args.repo) / ".platformforge/operations")
        if sub == "store-list":
            return _emit({"operations": st.list_operations(), "audit_digest": st.audit_digest()}, args)
        out = st.verify(args.operation_id)
        return _emit(out, args, 0 if out["chain_valid"] else 2)
    return _emit({"error": f"unknown ops verb {sub}"}, args, 1)


def _ops_run(args, spec: dict) -> int:
    """platformforge ops run --spec ops.yaml [--execute]

    spec = {intent, steps, policies, approvals, observation, verify,
            environment, break_glass} — same shape as lab ops.yaml.
    Without --execute every step is dry-run; transports are the host's.
    """
    from platformforge.live.models import now_iso
    from platformforge.ops import engine
    from platformforge.ops.actions import spec_for
    from platformforge.ops.approval import Approval, BreakGlass
    from platformforge.ops.executors.base import host_transport
    from platformforge.ops.models import ChangeIntent, ExpectedDelta, PlanStep, Reason
    from platformforge.ops.operation import LockTable, Operation, OperationLedger
    from platformforge.ops.policy import Policy
    from platformforge.ops.rollback import derive_rollback
    from platformforge.ops.simulate import simulate
    from platformforge.ops.store import OperationStore
    from platformforge.ops.verify import verify as do_verify

    i = spec.get("intent", {})
    intent = ChangeIntent(
        intent_id=i.get("intent_id", "cli-intent"),
        owner=i.get("owner", ""),
        requested_by=i.get("requested_by", ""),
        reason=Reason(**i.get("reason", {"type": "manual"})),
        target_resources=list(i.get("target_resources", [])),
        desired_change=dict(i.get("desired_change", {})),
    )
    if not spec.get("steps"):
        prop = engine.propose(intent, resources=i.get("resources", []), sot_context=i.get("sot_context"))
        if not prop["ok"]:
            return _emit(prop, args, 2)

    steps = [
        PlanStep(step_id=s["step_id"], action=s["action"], params=dict(s.get("params", {})))
        for s in spec.get("steps", [])
    ]
    ed = spec.get("expected_delta") or {}
    plan = engine.plan(
        intent,
        steps=steps,
        expected_delta=ExpectedDelta(
            adds=ed.get("adds", {}), removes=ed.get("removes", {}), changes=ed.get("changes", {})
        ),
    )
    sim = simulate(plan, level=spec.get("simulation_level", "S1"))
    # rollback declaration precedes risk — the status feeds the risk
    # ceiling and policy inputs (cycle 4.1 §F)
    rb = derive_rollback(
        [{"step_id": s.step_id, "action": s.action, "params": s.params}
         for s in steps],
        {
            "environment": spec.get("environment"),
            "automatic_allowed": spec.get("auto_rollback", False),
        },
    )
    risk = engine.assess_risk(
        plan, {"environment": spec.get("environment", "unknown")},
        rollback_status=rb.status)

    # §GOVERN — cost/security gates evaluate declared change context
    # before policy/approval. fail blocks everywhere; unknown blocks
    # production (unknown ≠ clean).
    from platformforge.ops import gates as G
    gspec = spec.get("gates") or {}
    environment = spec.get("environment", "unknown")
    gate_out: dict = {"verdict": "skipped", "gates": []}
    cost_gate: dict = {}
    if gspec:
        sec = G.security_gates(
            diff=gspec.get("diff") or ed,
            ctx=gspec.get("context") or {},
            vuln_scan=gspec.get("vuln_scan"))
        gate_out = sec
        if gspec.get("cost"):
            cd = G.CostDelta(**{
                k: v for k, v in gspec["cost"].items()
                if k in G.CostDelta.__dataclass_fields__})
            cost_gate = cd.gate(
                budget_increase_max=gspec.get("budget_increase_max"),
                increase_pct_max=gspec.get("increase_pct_max"))
            gate_out["cost"] = cost_gate
            gate_out["cost_delta"] = cd.to_dict()
            rank = {"fail": 3, "unknown": 2, "skipped": 1, "pass": 0}
            if rank.get(cost_gate["status"], 2) > rank.get(
                    gate_out["verdict"], 0):
                gate_out["verdict"] = cost_gate["status"]
        blocking = ("fail",) if environment not in (
            "prod", "production") else ("fail", "unknown")
        if gate_out["verdict"] in blocking:
            return _emit(
                {"ok": False, "stage": "govern",
                 "refusal": {"refusal": "PF-OPS-GATE-FAIL",
                             "unlock": "resolve failing gate or "
                                       "supply missing evidence",
                             "verdict": gate_out["verdict"]},
                 "gates": gate_out,
                 "simulation": sim.to_dict(), "risk": risk}, args, 2)
    policies = [Policy(**p) for p in spec.get("policies", [])]
    decisions = (
        [
            engine.decide(
                plan,
                policies,
                {"environment": spec.get("environment", "unknown"), "risk_class": risk["risk_class"]},
            )
        ]
        if policies
        else []
    )
    if not decisions:
        from platformforge.ops.policy import PolicyDecision

        decisions = [
            PolicyDecision(
                policy_id="cli-default",
                decision="allow",
                reason="no policies in spec — governance passthrough",
            )
        ]
    env = engine.mint_envelope(
        plan,
        execution_id=spec.get("execution_id", "cli-ex"),
        decisions=decisions or None,
        approvals=[],
        risk=risk,
        rollback=rb,
    )
    if isinstance(env, dict):
        return _emit(
            {"ok": False, "stage": "mint", "refusal": env, "simulation": sim.to_dict(), "risk": risk}, args, 2
        )
    env_hash = env.freeze()

    approvals = []
    for a in spec.get("approvals", []):
        approvals.append(
            Approval(
                approval_id=a.get("approval_id", "ap"),
                subject_hash=env_hash if a.get("binds", "envelope") == "envelope" else a.get("binds", ""),
                scope=list(a.get("scope", env.scope)),
                actor=a.get("actor", ""),
                role=a.get("role", ""),
                actor_kind=a.get("actor_kind", "human"),
                expires_at=a.get("expires_at", ""),
            )
        )
    bg = None
    if spec.get("break_glass"):
        b = spec["break_glass"]
        bg = BreakGlass(
            break_glass_id=b.get("ticket_id", ""),
            actor=b.get("actor", ""),
            invocation_reason=b.get("reason", ""),
            scope=list(b.get("scope", env.scope)),
            expires_at=b.get("expires_at", ""),
        )

    def _stub(rc=0, out="", err=""):
        return lambda argv, cwd=None, timeout_s=None: (rc, out, err)

    transports = {}
    # declared stubs (replayable, like lab fixtures)
    for name, st in (spec.get("transports") or {}).items():
        transports[name] = _stub(st.get("rc", 0), st.get("stdout", ""), st.get("stderr", ""))
    if args.execute:
        t = host_transport()
        for s in env.actions:
            sp = spec_for(s["action"])
            if sp:
                transports[sp.executor] = t
    else:
        # dry-run: executors need a transport handle, but it must never
        # reach the host — return a marker receipt instead
        for s in env.actions:
            sp = spec_for(s["action"])
            if sp and sp.executor not in transports:
                transports[sp.executor] = _stub(0, "dry-run — host transport not invoked", "")

    op = Operation(
        operation_id=spec.get("operation_id", "cli-op"), intent_id=intent.intent_id, resources=list(env.scope)
    )
    ledger = OperationLedger()
    result = engine.execute(
        op,
        env,
        approvals=approvals,
        transports=transports,
        ledger=ledger,
        locks=LockTable(),
        dry_run=not args.execute,
        break_glass=bg,
        preconditions={
            "observation": spec.get("observation"),
            "pre_state": spec.get("pre_state"),
            "sot": spec.get("sot"),
            "current_plan_hash": env.change_plan_hash,
            "policy_decision": (decisions[0].decision if decisions else "allow"),
            "freeze_active": spec.get("freeze_active", False),
            "environment": spec.get("environment", ""),
            "maintenance_window": spec.get("maintenance_window"),
            "expected_resource_state": spec.get("expected_resource_state"),
            "current_resource_state": spec.get("current_resource_state"),
            "owner": spec.get("owner", ""),
            "current_owner": spec.get("current_owner", ""),
            "automatic_rollback": spec.get("auto_rollback", False),
        },
    )

    if result.get("ok") and spec.get("verify"):
        v = spec["verify"]
        vr = do_verify(
            expected_delta=ed,
            observations=v.get("observations", {}),
            slo_contract=v.get("slo"),
            metrics=v.get("metrics"),
            mutating=any(
                (spec_for(a["action"]) or None) is not None
                and spec_for(a["action"]).mutating
                for a in env.actions),
        )
        result["verify"] = vr.to_dict()
        result["final"] = engine.finalize_verify(op, ledger, {"convergence": vr.convergence})
        result["state"] = op.state
        # §119–127 — execute the MATERIAL-BUILT rollback when the plan
        # allows it (lab/non-prod only); otherwise the op stays
        # rollback-planned for a human `ops rollback` call.
        if op.state == "rollback-planned":
            rbp = result.get("rollback_plan") or env.rollback
            if (rbp or {}).get("status") == "executable" and \
                    (rbp or {}).get("automatic"):
                result["rollback"] = engine.execute_rollback(
                    op,
                    env,
                    transports=transports,
                    ledger=ledger,
                    completed_results=result.get("results"),
                    materials=result.get("materials"),
                    rollback_plan=rbp,
                    trigger={"type": "verification-failed",
                             "observed_delta": ed,
                             "at": now_iso()},
                    post_rollback_state=(spec.get("post_rollback") or {}),
                    dry_run=not args.execute,
                )
                result["state"] = op.state

    st = OperationStore(Path(args.repo) / ".platformforge/operations")
    # §30 — persist the material-built rollback plan + immutable
    # materials so `ops rollback` replays against captured pre-state
    if result.get("rollback_plan"):
        env.rollback = result["rollback_plan"]
    st.save(op, ledger, envelope=env, materials=result.get("materials"))
    result["graph"] = st.projection(op.operation_id)
    result["receipts"] = {
        "ledger_tip": ledger.tip,
        "ledger_valid": ledger.verify_chain(),
        "envelope": env.to_dict(),
        "simulation": sim.to_dict(),
        "risk": risk,
    }
    result["gates"] = gate_out
    result["dry_run"] = not args.execute
    return _emit(result, args, 0 if result.get("ok") else 2)


def _load_plan_doc(path: str) -> dict:
    doc = _load_yaml_or_json(path)
    from platformforge.ops.models import ChangeIntent, ExpectedDelta, PlanStep, Reason

    i = doc.get("intent", {})
    intent = ChangeIntent(
        intent_id=i.get("intent_id", ""),
        owner=i.get("owner", ""),
        requested_by=i.get("requested_by", ""),
        reason=Reason(**i.get("reason", {"type": "manual"})),
        target_resources=list(i.get("target_resources", [])),
        desired_change=dict(i.get("desired_change", {})),
    )
    steps = [
        PlanStep(step_id=s["step_id"], action=s["action"], params=dict(s.get("params", {})))
        for s in doc.get("steps", [])
    ]
    ed = doc.get("expected_delta") or {}
    return {
        "intent": intent,
        "steps": steps,
        "expected_delta": ExpectedDelta(
            adds=ed.get("adds", {}), removes=ed.get("removes", {}), changes=ed.get("changes", {})
        ),
    }


def _load_yaml_or_json(path: str):
    text = Path(path).read_text()
    if path.endswith((".yaml", ".yml")):
        import yaml

        return yaml.safe_load(text)
    return json.loads(text)


def _load_yaml_list(path: str) -> list:
    import yaml

    doc = yaml.safe_load(Path(path).read_text())
    return doc if isinstance(doc, list) else doc.get("policies", [])


def _live_budget(args: argparse.Namespace):
    from platformforge.live.budget import ObservationBudget

    return ObservationBudget(
        max_objects=args.max_objects, max_api_calls=args.max_api_calls, max_bytes=args.max_bytes
    )


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
    if sub == "focus-validate":
        # §92 — never call output FOCUS-compliant without schema check
        from platformforge.finops.focus import validate_focus

        rows = json.loads(Path(args.path).read_text())
        rows = rows if isinstance(rows, list) else rows.get("rows", [])
        out = validate_focus(rows)
        return _emit(out, args, 2 if (args.strict and not out["focus_compliant"]) else 0)
    if sub == "unit":
        # §94 unit economics — denominators must be caller-measured
        from platformforge.finops.unit import unit_economics

        doc = F.cost_facts(args.path)
        denoms = json.loads(Path(args.denominators).read_text()) if args.denominators else {}
        out = unit_economics(doc["facts"], denoms)
        return _emit(out, args, 2 if (args.strict and out["unresolved"]) else 0)
    if sub == "ingest":
        # §91 — provider billing export → normalized rows + format verdict
        from platformforge.finops.ingest import ingest_billing

        return _emit(ingest_billing(args.path), args)
    if sub == "report":
        # §90 — composite; each dimension independently evidence-bound
        from platformforge.finops.insights import finops_report

        doc = F.cost_facts(args.path)
        extra = json.loads(Path(args.denominators).read_text()) if args.denominators else {}
        return _emit(
            finops_report(
                doc["facts"],
                utilization=extra.get("utilization"),
                requested_vs_used=extra.get("requested_vs_used"),
                committed=extra.get("committed"),
                split=extra.get("split"),
            ),
            args,
        )
    if sub == "graph":
        g = _load_graph_or_refuse(args.repo)
        if g is None:
            return _emit(
                {"refusal": "PF-GRAPH-NOGRAPH", "unlock": "platformforge graph build <facts.json>"}, args, 2
            )
        doc = F.cost_facts(args.path)
        return _emit(F.graph_cost(g, doc["facts"]), args)
    return _emit({"error": f"unknown finops verb {sub}"}, args, 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="platformforge", description="Agentic Platform Engineering intelligence")
    p.add_argument("--version", action="version", version=f"platformforge {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def verb(name: str, fn, help_: str, extra=None) -> None:
        sp = sub.add_parser(name, help=help_)
        _add_common(sp)
        if extra:
            extra(sp)
        sp.set_defaults(func=fn)

    verb("init", cmd_init, "scaffold .platformforge/", lambda sp: sp.add_argument("--name", default=""))
    verb(
        "doctor",
        cmd_doctor,
        "environment health-check",
        lambda sp: sp.add_argument(
            "--deep",
            action="store_true",
            help="§141 contract checks (config, manifest, knowledge, parity, index, store)",
        ),
    )
    verb("status", cmd_status, "workspace + store status")
    verb("inspect", cmd_inspect, "inventory analyzable artifacts")
    verb(
        "judge",
        cmd_judge,
        "apply rule catalog to facts",
        lambda sp: (
            sp.add_argument("facts"),
            sp.add_argument("--catalog", nargs="*"),
            sp.add_argument(
                "--versions", default="", help='JSON product versions, e.g. \'{"kubernetes": "1.29"}\''
            ),
        ),
    )
    verb(
        "knowledge",
        cmd_knowledge,
        "knowledge freshness/drift check",
        lambda sp: sp.add_argument(
            "knowledge_cmd", nargs="?", default="check", choices=["check", "contract", "drift", "packs"]
        ),
    )

    sp = sub.add_parser("tokens", help="tokensave: index/search/pack/delta/stats/ledger")
    _add_common(sp)
    sp.add_argument("tokens_cmd", choices=["index", "search", "pack", "delta", "stats", "ledger"])
    sp.add_argument("--task", default="")
    sp.add_argument("--query", default="")
    sp.add_argument("--mode", default="literal",
                    choices=["literal", "regex", "symbol", "path", "kind"])
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--changed", nargs="*")
    sp.add_argument("--input-budget", type=int, default=None)
    sp.add_argument("--risk", default=None, choices=["low", "medium", "high", "critical"])
    sp.add_argument("--graph-nodes", nargs="*", help="seed nodes for graph-aware ranking")
    sp.add_argument("--prev-pack", default=None, help="previous pack hash — delta-aware dedup")
    sp.add_argument("--allow-escalate", action="store_true",
                    help="pack: escalate beyond budget instead of refusing")
    sp.set_defaults(func=cmd_tokens)

    sp = sub.add_parser("rtk", help="compact command output (rtk)")
    _add_common(sp)
    sp.add_argument("rtk_cmd", choices=["compact", "expand"], nargs="?", default="compact")
    sp.add_argument("file", nargs="?", default="-", help="output file to compact ('-' = stdin)")
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
    sp.add_argument("--mode", choices=["off", "lite", "full", "auto"], default="lite")
    sp.add_argument("--context-risk", default="normal")
    sp.set_defaults(func=cmd_caveman)

    sp = sub.add_parser("economy", help="economy engine report/strategy/qpt")
    _add_common(sp)
    sp.add_argument(
        "economy_cmd",
        nargs="?",
        default="report",
        choices=["report", "strategy", "compare", "qpt", "qpt-bench"],
    )
    sp.add_argument("--signal", default="", help="JSON TaskSignal (strategy/compare)")
    sp.add_argument("--path", default="", help="facts doc for qpt")
    sp.add_argument("--task", default="analysis")
    sp.add_argument("--input-budget", type=int, default=None)
    sp.add_argument(
        "--versions", default="", help='JSON product versions for qpt, e.g. \'{"kubernetes": "1.29"}\''
    )
    sp.set_defaults(func=cmd_economy)

    sp = sub.add_parser("route", help="adaptive routing decision")
    _add_common(sp)
    sp.add_argument("signal", help="JSON TaskSignal")
    sp.set_defaults(func=cmd_route)

    sp = sub.add_parser("sdd", help="native SDD lifecycle")
    _add_common(sp)
    sp.add_argument(
        "sdd_cmd",
        choices=[
            "init",
            "discover",
            "define",
            "design",
            "contract",
            "plan",
            "build",
            "review",
            "verify",
            "ship",
            "learn",
            "status",
            "check",
            "stamp",
        ],
    )
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
    sp.add_argument(
        "graph_cmd",
        choices=[
            "build",
            "stats",
            "deps",
            "dependents",
            "blast",
            "paths",
            "gaps",
            "cycles",
            "diff",
            "snapshots",
            "identity-become",
            "identity-access",
            "identity-workloads",
            "identity-blast",
            "at",
            "timeline",
        ],
    )
    sp.add_argument("facts", nargs="?", default="")
    sp.add_argument("--node", default="")
    sp.add_argument("--src", default="")
    sp.add_argument("--dst", default="")
    sp.add_argument("--before", default="")
    sp.add_argument("--after", default="")
    sp.add_argument("--at", default="", help="at: ISO timestamp")
    sp.add_argument("--edge-id", default="", help="timeline: edge id")
    sp.add_argument(
        "--source-type",
        default="desired",
        choices=["desired", "planned", "observed", "runtime"],
        help="§6 snapshot type for `graph build`",
    )
    sp.set_defaults(func=cmd_graph)

    sp = sub.add_parser("analyze", help="domain analyzers → facts")
    _add_common(sp)
    sp.add_argument(
        "analyze_cmd",
        choices=[
            "iac",
            "plan",
            "state",
            "drift",
            "k8s",
            "gitops",
            "gha",
            "iam",
            "sbom",
            "secrets",
            "supply",
            "catalog",
            "crossplane",
            "cloud-aws",
            "cloud-azure",
            "cloud-gcp",
            "helm",
            "kustomize",
            "hubble",
            "kyverno",
            "cosign",
            "slsa",
            "ownership",
            "contradictions",
        ],
    )
    sp.add_argument("--facts", default="", help="facts doc for ownership/contradiction joins")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--config", default="")
    sp.add_argument("--state", default="")
    sp.add_argument("--vulns", default="", help="offline vuln list JSON")
    sp.add_argument("--kyverno-version", default="", help="declared kyverno version for deprecation checks")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("observe", help="SRE/observability verbs")
    _add_common(sp)
    sp.add_argument(
        "observe_cmd",
        choices=[
            "slo",
            "slo-burn",
            "otel",
            "semconv",
            "incident",
            "timeline",
            "postmortem",
            "capacity",
            "dr",
            "prometheus",
            "grafana",
        ],
    )
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--sli", default="", help="JSON {good,bad,total}_events")
    sp.add_argument("--windows", default="", help="JSON {window: {good,bad}} for slo-burn")
    sp.add_argument("--alerts", default="")
    sp.add_argument("--changes", default="")
    sp.add_argument("--incident", default="", help="incident JSON for postmortem")
    sp.add_argument("--facts", default="", help="facts JSON for dr")
    sp.add_argument("--window", type=int, default=3600)
    sp.set_defaults(func=cmd_observe)

    sp = sub.add_parser("live", help="live platform observation (cycle3)")
    _add_common(sp)
    sp.add_argument(
        "live_cmd",
        choices=[
            "snapshot",
            "status",
            "doctor",
            "reconcile",
            "rbac",
            "required-permissions",
            "topology",
            "clusters",
            "drift",
            "incident",
            "plan",
            "capability",
            "changes",
        ],
    )
    sp.add_argument("--provider", default="kubernetes", choices=["kubernetes", "aws"])
    sp.add_argument("--region", action="append", help="aws: restrict regions (repeatable)")
    sp.add_argument("--service", action="append", help="aws: restrict services (repeatable)")
    sp.add_argument("--deep", action="store_true", help="doctor: probe every provider adapter")
    sp.add_argument("--context", default="", help="kube context")
    sp.add_argument("--namespace", action="append", help="restrict to namespace (repeatable)")
    sp.add_argument("--resource-type", action="append", help="restrict resource types (repeatable)")
    sp.add_argument("--selector", default="", help="k8s label selector")
    sp.add_argument("--namespaced-only", action="store_true", help="rbac: emit Role instead of ClusterRole")
    sp.add_argument("--no-store", action="store_true", help="snapshot: emit envelope without persisting")
    sp.add_argument("--desired", default="", help="reconcile: facts.json path (default: repo scan)")
    sp.add_argument("--planned", default="", help="reconcile: planned facts.json path")
    sp.add_argument("--observed", default="", help="reconcile: observation_id or envelope.json")
    sp.add_argument("--no-observed", action="store_true", help="reconcile: desired↔planned only")
    sp.add_argument("--otel", default="", help="topology: OTLP spans json")
    sp.add_argument("--hubble", default="", help="topology: hubble flows")
    sp.add_argument("--slices", default="", help="topology: endpointslices json")
    sp.add_argument(
        "--apply-to-graph", action="store_true", help="topology: persist runtime edges into graph"
    )
    sp.add_argument("--register", default="", help="clusters: register cluster JSON spec")
    sp.add_argument("--before", default="", help="drift: obs id/file")
    sp.add_argument("--after", default="", help="drift: obs id/file")
    sp.add_argument("--incident", default="", help="incident: incident JSON {timestamp,resources}")
    sp.add_argument("--changes", default="", help="incident: candidate changes JSON list")
    sp.add_argument("--events-file", default="",
                    help="changes: append ChangeEvents from JSON file (offline-safe)")
    sp.add_argument("--collect", action="store_true",
                    help="changes: collect via provider adapter (host-side)")
    sp.add_argument("--gc", action="store_true",
                    help="changes: garbage-collect the change journal")
    sp.add_argument("--since", default="", help="changes: events after ISO ts")
    sp.add_argument("--until", default="", help="changes: events before ISO ts")
    sp.add_argument("--resource", default="", help="changes: filter by resource id")
    sp.add_argument("--events", default="", help="incident: timeline events JSON list")
    sp.add_argument("--window", type=int, default=3600, help="incident: correlation window seconds")
    sp.add_argument(
        "--drift-events",
        default="",
        help="plan: drift events JSON (default: diff latest two stored observations)",
    )
    sp.add_argument("--max-objects", type=int, default=0)
    sp.add_argument("--max-api-calls", type=int, default=0)
    sp.add_argument("--max-bytes", type=int, default=0)
    sp.set_defaults(func=cmd_live)

    sp = sub.add_parser("ops", help="governed operations (cycle4)")
    _add_common(sp)
    sp.add_argument(
        "ops_cmd",
        choices=[
            "capabilities",
            "config",
            "delegate",
            "intent",
            "plan",
            "simulate",
            "risk",
            "policy-eval",
            "runbook",
            "run",
            "approve",
            "status",
            "history",
            "rollback",
            "autorem-eval",
            "analytics",
            "graph",
            "store-list",
            "store-verify",
        ],
    )
    sp.add_argument("--intent", default="", help="intent JSON file")
    sp.add_argument("--plan", default="", help="plan JSON/YAML file")
    sp.add_argument("--spec", default="", help="ops run spec YAML/JSON")
    sp.add_argument("--policies", default="", help="policies YAML list")
    sp.add_argument("--environment", default="unknown")
    sp.add_argument("--level", default="S1", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    sp.add_argument(
        "--execute",
        action="store_true",
        help="real mutation — requires hash-bound approval + host transports; default is dry-run",
    )
    sp.add_argument("--request", default="", help="delegate request JSON")
    sp.add_argument("--name", default="", help="runbook id (positional name overrides)")
    sp.add_argument("--bind", default="", help="runbook bind params JSON")
    sp.add_argument("name_pos", nargs="?", default="", help="runbook id or 'list'")
    sp.add_argument("--operation-id", default="")
    sp.add_argument("--post-rollback", default="",
                    help="rollback: post-rollback observation JSON "
                         "{step_id: {dim: value}} for verification")
    sp.add_argument("--resource", default="", help="history filter")
    sp.add_argument("--evidence-tier", default="", help="autorem-eval")
    # ops approve — mint a hash-bound approval artifact (never executes)
    sp.add_argument("--approval-id", default="")
    sp.add_argument("--subject-hash", default="",
                    help="envelope/plan hash being approved")
    sp.add_argument("--subject-kind", default="execution-envelope")
    sp.add_argument("--actor", default="", help="human identity")
    sp.add_argument("--actor-kind", default="human",
                    choices=["human", "agent", "host", "system"])
    sp.add_argument("--role", default="")
    sp.add_argument("--approval-type", default="single-human",
                    choices=["automatic-policy", "single-human",
                             "resource-owner", "platform-owner",
                             "security-review", "dual-human"])
    sp.add_argument("--expires-at", default="")
    sp.add_argument("--bounds", default="", help="parameter bounds JSON")
    sp.add_argument("--scope", default="", help="csv resource scope")
    sp.add_argument("--reason", default="")
    sp.set_defaults(func=cmd_ops)

    sp = sub.add_parser("finops", help="FinOps cost analysis")
    _add_common(sp)
    sp.add_argument(
        "finops_cmd",
        choices=["costs", "allocate", "focus", "focus-validate", "unit", "graph", "ingest", "report"],
    )
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--by", default="cost_center")
    sp.add_argument("--denominators", default="", help="JSON {unit: measured_count} for `finops unit`")
    sp.set_defaults(func=cmd_finops)

    # --- cycle 5 namespaces (read-only, fleet-dir inputs) -----------
    from platformforge.cli.fleetcmd import (
        cmd_ai,
        cmd_analytics,
        cmd_federation,
        cmd_fleet,
        cmd_optimize,
    )

    sp = sub.add_parser("fleet", help="fleet intelligence (dir input)")
    _add_common(sp)
    sp.add_argument(
        "fleet_cmd",
        choices=["list", "status", "coverage", "graph", "risks", "costs",
                 "capacity", "incidents", "operations", "drift",
                 "golden-path", "policies", "recommendations", "report"])
    sp.add_argument("path", nargs="?", default="",
                    help="fleet dir (lab/fleets/acme shape)")
    sp.add_argument("--question", default="",
                    help="risks: run a single fleet question")
    sp.add_argument("--limit", type=int, default=0)
    sp.add_argument("--window", default="", help="drift window (24h/7d/30d/90d)")
    sp.set_defaults(func=lambda a: _emit(cmd_fleet(a), a))

    sp = sub.add_parser("analytics", help="analytics summary/metric/maturity")
    _add_common(sp)
    sp.add_argument("analytics_cmd",
                    choices=["summary", "metric", "maturity"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--id", default="", help="metric id")
    sp.set_defaults(func=lambda a: _emit(cmd_analytics(a), a))

    sp = sub.add_parser("optimize",
                        help="optimization scan → ChangeIntent only")
    _add_common(sp)
    sp.add_argument("optimize_cmd",
                    choices=["scan", "list", "explain", "plan", "portfolio"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--id", default="", help="recommendation id")
    sp.add_argument("--out", default="",
                    help="plan: write the ChangeIntent doc to this file")
    sp.add_argument("--limit", type=int, default=0)
    sp.set_defaults(func=lambda a: _emit(cmd_optimize(a), a))

    sp = sub.add_parser("ai", help="AI platform awareness (bounded)")
    _add_common(sp)
    sp.add_argument("ai_cmd", choices=["workloads", "gpu", "economics"])
    sp.add_argument("path", nargs="?", default="",
                    help="yaml input (resources / capacity doc)")
    sp.add_argument("--cost", type=float, default=None)
    sp.add_argument("--denominators", default="",
                    help='JSON {tokens,inferences,gpu_hours}')
    sp.set_defaults(func=lambda a: _emit(cmd_ai(a), a))

    sp = sub.add_parser("federation",
                        help="intelligence exchange — no credentials")
    _add_common(sp)
    sp.add_argument("federation_cmd",
                    choices=["manifest", "export", "query"])
    sp.add_argument("path", nargs="?", default="",
                    help="payload yaml (export)")
    sp.add_argument("question", nargs="?", default="",
                    help="fleet question (query)")
    sp.add_argument("--nodes", nargs="*", default=[],
                    help="fleet dirs (query)")
    sp.add_argument("--classification", default="")
    sp.add_argument("--manifest", default="")
    sp.add_argument("--node-id", default="")
    sp.add_argument("--capabilities", default="")
    sp.add_argument("--freshness", default="")
    sp.add_argument("--limit", type=int, default=0)
    sp.set_defaults(func=lambda a: _emit(cmd_federation(a), a))

    sp = sub.add_parser("product", help="platform product verbs")
    _add_common(sp)
    sp.add_argument(
        "product_cmd",
        choices=["maturity", "scorecard", "backstage", "paths", "path", "capabilities", "path-analyze"],
    )
    sp.add_argument("--signals", default="", help="JSON signals doc")
    sp.add_argument("--findings", default="", help="findings JSON doc")
    sp.add_argument("--facts", default="", help="facts JSON for analysis")
    sp.add_argument("--id", default="", help="golden path id")
    sp.set_defaults(func=cmd_product)

    sp = sub.add_parser("agents", help="agent roster, mirrors, referee")
    _add_common(sp)
    sp.add_argument("agents_cmd", choices=["list", "lint", "sync", "check", "playbook", "referee", "bench"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--name", default="")
    sp.add_argument("--domain", default="")
    sp.set_defaults(func=cmd_agents)

    sp = sub.add_parser("mcp", help="MCP server + host parity")
    _add_common(sp)
    sp.add_argument("mcp_cmd", choices=["tools", "call", "serve", "integrate", "detach"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--name", default="")
    sp.add_argument("--input", default="")
    sp.add_argument("--host", default="generic", choices=["claude", "codex", "devin", "copilot", "generic"])
    sp.set_defaults(func=cmd_mcp)

    verb(
        "collect",
        cmd_collect,
        "ingest artifact dumps → facts",
        lambda sp: sp.add_argument("path", nargs="?", default=""),
    )
    verb(
        "diagnose",
        cmd_diagnose,
        "node diagnosis: facts+findings+blast",
        lambda sp: (
            sp.add_argument("node"),
            sp.add_argument("--findings", default=""),
            sp.add_argument("--facts", default=""),
        ),
    )
    verb(
        "plan",
        cmd_plan,
        "findings → ordered remediation plan",
        lambda sp: (sp.add_argument("path"), sp.add_argument("--facts", default="")),
    )
    verb("correlate", cmd_correlate, "OTel correlation (observe otel)", lambda sp: sp.add_argument("path"))
    verb(
        "diff",
        cmd_diff,
        "graph diff between two facts docs",
        lambda sp: (sp.add_argument("--before", required=True), sp.add_argument("--after", required=True)),
    )
    verb(
        "drift",
        cmd_drift,
        "IaC drift: --config dir vs --state file",
        lambda sp: (sp.add_argument("--config", required=True), sp.add_argument("--state", required=True)),
    )
    verb(
        "impact",
        cmd_impact,
        "blast radius for a graph node",
        lambda sp: sp.add_argument("--node", required=True),
    )
    verb(
        "context",
        cmd_context,
        "context pack for a task",
        lambda sp: (
            sp.add_argument("--task", default=""),
            sp.add_argument("--input-budget", type=int, default=None),
            sp.add_argument("--changed", nargs="*"),
        ),
    )
    verb(
        "policy",
        cmd_policy,
        "policy-as-code catalog check",
        lambda sp: (
            sp.add_argument("policy_cmd", choices=["check", "list"]),
            sp.add_argument("path", nargs="?", default=""),
        ),
    )
    verb(
        "security",
        cmd_security,
        "security bundle (secrets+iam+sbom+supply)",
        lambda sp: sp.add_argument("path", nargs="?", default=""),
    )
    verb(
        "reliability",
        cmd_reliability,
        "SRE+K8S rules over facts",
        lambda sp: sp.add_argument("path", nargs="?", default=""),
    )
    verb(
        "integrate",
        cmd_integrate,
        "host integration (mcp parity)",
        lambda sp: (
            sp.add_argument(
                "--host", required=True, choices=["claude", "codex", "devin", "copilot", "generic"]
            ),
            sp.add_argument("--detach", action="store_true"),
        ),
    )
    verb(
        "evals",
        cmd_evals,
        "eval framework (§94–95)",
        lambda sp: (
            sp.add_argument(
                "evals_cmd", choices=["run", "list", "coverage", "precision"], nargs="?", default="run"
            ),
            sp.add_argument("--type", default=""),
            sp.add_argument("--cases", default=""),
        ),
    )

    sp = sub.add_parser("lab", help="Forge Lab scenarios")
    _add_common(sp)
    sp.add_argument("lab_cmd", choices=["list", "run", "run-all", "chaos"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--allow-prod", action="store_true", help="chaos: allow env:production targets")
    sp.add_argument(
        "--profile",
        default="",
        choices=["static", "container", "kubernetes", "cloud"],
        help="§118 lab profile filter",
    )
    sp.add_argument("--allow-profile", action="store_true", help="§119 — opt into non-static lab profiles")
    sp.set_defaults(func=cmd_lab)

    sp = sub.add_parser("forge", help="Forge interop")
    _add_common(sp)
    sp.add_argument("forge_cmd", choices=["manifest", "delegate", "verify", "discover", "collect"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--name", default="")
    sp.add_argument("--src", default="")
    sp.add_argument("--dst", default="")
    sp.set_defaults(func=cmd_forge)

    sp = sub.add_parser("capability", help="capability registry")
    _add_common(sp)
    sp.add_argument("capability_cmd", choices=["list", "describe", "manifest", "check"])
    sp.add_argument("--name", default="")
    sp.add_argument("--domain", default="", help="§139 — domain to negotiate, e.g. k8s")
    sp.add_argument("--version", default="", help="§139 — product version to check support for")
    sp.set_defaults(func=cmd_capability)

    sp = sub.add_parser("risk", help="§130 change-risk assessment")
    _add_common(sp)
    sp.add_argument("--node", default="", help="graph node id to assess")
    sp.add_argument("--signals", default="", help="JSON signals doc")
    sp.set_defaults(func=cmd_risk)

    sp = sub.add_parser("change", help="§85–86 change lifecycle (sandboxed)")
    _add_common(sp)
    sp.add_argument("change_cmd", choices=["propose", "sandbox", "verify", "review", "approve", "apply"])
    sp.add_argument("--patch", default="", help="unified diff file")
    sp.add_argument("--file", action="append", help="rel/path=src-file (or literal content)")
    sp.add_argument("--signals", default="", help="JSON risk signals doc (review only)")
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

    sp = sub.add_parser("store", help="§151 artifact store stats/gc")
    _add_common(sp)
    sp.add_argument("store_cmd", choices=["stats", "gc"])
    sp.add_argument("--keep-days", type=float, default=30.0)
    sp.add_argument("--execute", action="store_true", help="actually delete (default: dry-run)")
    sp.set_defaults(func=cmd_store)

    sp = sub.add_parser("bench", help="§148–150 measured benchmarks")
    _add_common(sp)
    sp.add_argument("bench_cmd", choices=["run", "tokens", "scale"], nargs="?", default="run")
    sp.add_argument("--repeat", type=int, default=3)
    sp.add_argument("--sizes", help="comma list for scale bench (default 50,200,800)")
    sp.add_argument("--edges", help="comma list for edge sweep "
                    "(default 100000,250000,500000)")
    sp.add_argument("--events", action="store_true",
                    help="also run the analytics store event sweep "
                         "(10k/100k/1M)")
    sp.set_defaults(func=cmd_bench)

    sp = sub.add_parser("freeze", help="architecture freeze governance")
    _add_common(sp)
    sp.add_argument(
        "freeze_cmd",
        choices=["manifest", "snapshot", "check", "exception"],
    )
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--out", default="")
    sp.add_argument("--spec", dest="json_file", default="",
                    help="FeatureException JSON for `freeze exception`")
    sp.set_defaults(func=cmd_freeze)

    sp = sub.add_parser("cases", help="real-world case corpus + replay")
    _add_common(sp)
    sp.add_argument("cases_cmd",
                    choices=["list", "validate", "replay", "template",
                             "ledger", "ledger-check", "route-audit",
                             "route-bench", "context-audit"])
    sp.add_argument("path", nargs="?", default="")
    sp.add_argument("--tier", default="", choices=["golden", "holdout"])
    sp.add_argument("--out", default="",
                    help="challenger routing.yaml for route-bench")
    sp.add_argument("--stamp", action="store_true",
                    help="context-audit: write measured context_cost "
                         "back into case.yaml")
    sp.set_defaults(func=cmd_cases)
    return p


def main(argv: list[str] | None = None) -> int:
    global _RUN_STARTED
    _RUN_STARTED = time.time()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
