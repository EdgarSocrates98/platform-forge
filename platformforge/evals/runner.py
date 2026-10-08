"""Eval runner — evals/cases/*.yaml, offline, deterministic.

Each case maps a type to a real check:

- golden/unit/integration/regression → analyze a fixture, judge, compare
  `expect.rules_fired`/`rules_not_fired`
- recall/precision → expected rule set vs observed set, `threshold`
- contract → validate a doc against contracts/*.schema.json
- token_economy → context pack respects `--input-budget`
- routing → `route(TaskSignal)` mode matches `expect.mode`
- graph_correctness → build graph from fixture facts, assert dependents
  or blast membership
- security → scan_secrets output must not contain `must_not_contain`
- property/metamorphic → transform invariants (rtk compact→expand round-trip)

Unknown type → verdict `unresolved` (declared, never silently passed).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

EVAL_TYPES = ("unit", "integration", "golden", "contract", "property",
              "metamorphic", "regression", "recall", "precision",
              "token_economy", "graph_correctness", "routing", "security",
              "knowledge", "version", "live")
VARIANTS = ("positive", "negative", "boundary", "unresolved", "version")

from platformforge.resources import data_path

_REPO = data_path()
CASES_DIR = _REPO / "evals" / "cases"


def _catalog():
    from platformforge.rules import load_catalog
    return load_catalog(_REPO / "rules" / "catalog")


_ANALYZER_KW = {"kyverno": "kyverno_version"}


def _facts_for(case: dict, case_dir: Path) -> list[dict]:
    dom = case.get("domain", "k8s")
    fx = case_dir / case.get("fixture", "fixture")
    from platformforge.lab.runner import _analyzer
    out = _analyzer(dom, fx)
    # analyzers needing a declared version get it from the case
    if _ANALYZER_KW.get(dom) and (case.get("versions") or {}).get("kyverno"):
        kw = _ANALYZER_KW[dom]
        fn = _resolve_for(dom)
        out = fn(fx, **{kw: case["versions"]["kyverno"]})
    return out["facts"]


def _resolve_for(dom: str):
    from platformforge.lab.runner import _ANALYZERS, _resolve
    return _resolve(_ANALYZERS[dom])


def _fired_ids(facts: list[dict],
               versions: dict | None = None) -> set[str]:
    from platformforge.models import Fact
    from platformforge.rules import RuleEngine
    fs = [f if isinstance(f, Fact) else Fact.from_dict(f) for f in facts]
    findings, _skipped = RuleEngine(_catalog(),
                                    versions=versions).evaluate(fs)
    return {f.rule_id for f in findings if f.status == "violated"}


def _grade_analyze(case: dict, case_dir: Path) -> dict[str, Any]:
    fired = _fired_ids(_facts_for(case, case_dir), case.get("versions"))
    exp = case.get("expect", {})
    missing = sorted(set(exp.get("rules_fired", [])) - fired)
    extra = sorted(fired & set(exp.get("rules_not_fired", [])))
    ok = not missing and not extra
    return {"verdict": "pass" if ok else "fail", "fired": sorted(fired),
            "missing": missing, "unexpected": extra}


def _grade(case: dict, case_dir: Path) -> dict[str, Any]:
    t = case.get("type", "golden")
    exp = case.get("expect", {})
    if t in ("golden", "unit", "integration", "regression"):
        return _grade_analyze(case, case_dir)
    if t in ("recall", "precision"):
        fired = _fired_ids(_facts_for(case, case_dir), case.get("versions"))
        want = set(exp.get("rules_fired", []))
        tp = len(fired & want)
        val = (tp / len(want)) if t == "recall" and want else \
              (tp / len(fired)) if fired else 0.0
        thr = exp.get("threshold", 1.0)
        return {"verdict": "pass" if val >= thr else "fail",
                t: val, "fired": sorted(fired), "expected": sorted(want)}
    if t == "contract":
        import jsonschema
        schema = json.loads((_REPO / "contracts" / exp["schema"])
                            .read_text())
        doc = yaml.safe_load((case_dir / case["fixture"]).read_text())
        errs = [e.message for e in
                jsonschema.Draft7Validator(schema).iter_errors(doc)]
        return {"verdict": "pass" if not errs else "fail", "errors": errs}
    if t == "graph_correctness":
        facts = _facts_for(case, case_dir)
        from platformforge.graph import GraphBuilder
        g = GraphBuilder().from_facts(facts).graph
        node = exp["node"]
        if "dependents_of" in exp:
            from platformforge.graph.query import dependents
            got = sorted(dependents(g, node))
            return {"verdict": "pass" if got == sorted(exp["dependents_of"])
                    else "fail", "got": got}
        if "blast_of" in exp:
            from platformforge.graph.query import blast_radius
            got = sorted(blast_radius(g, node)["nodes"])
            return {"verdict": "pass" if got == sorted(exp["blast_of"])
                    else "fail", "got": got}
        return {"verdict": "unresolved",
                "reason": "no graph assertion in expect"}
    if t == "routing":
        from platformforge.routing import TaskSignal, route
        got = route(TaskSignal.from_dict(case["signal"]))
        ok = got.get("mode") == exp.get("mode")
        return {"verdict": "pass" if ok else "fail", "mode": got.get("mode"),
                "agents": got.get("agents")}
    if t == "token_economy":
        from platformforge.tokensave.budget import Budget
        from platformforge.tokensave.index import SearchIndex
        from platformforge.tokensave.packs import ContextPackBuilder
        with tempfile.TemporaryDirectory() as td:
            idx = SearchIndex(Path(td) / "i.db")
            idx.index_workspace(case_dir / case.get("fixture", "fixture"))
            pack = ContextPackBuilder(idx, None).build(
                task=case.get("query", ""),
                budget=Budget(input_budget=exp["budget"]))
        over = pack["est_input_tokens"] > exp["budget"]
        refused = bool(pack.get("refusals"))
        return {"verdict": "pass" if not over or refused else "fail",
                "est_input_tokens": pack["est_input_tokens"],
                "refusals": pack.get("refusals")}
    if t == "security":
        from platformforge.security import scan_secrets
        out = scan_secrets(case_dir / case.get("fixture", "fixture"))
        blob = json.dumps(out, default=str)
        leaked = [v for v in exp.get("must_not_contain", []) if v in blob]
        return {"verdict": "pass" if not leaked else "fail",
                "leaked": leaked}
    if t == "knowledge":
        # every expected source id must exist in the registry
        from platformforge.knowledge.registry import SourceRegistry
        reg = SourceRegistry.default()
        missing = [s for s in exp.get("sources", [])
                   if s not in reg.entries]
        return {"verdict": "pass" if not missing else "fail",
                "missing_sources": missing}
    if t == "version":
        # Tri-state contract (cycle 2.1): compatible → passed/violated;
        # incompatible → version-mismatch skip; unknown → unresolved
        # finding with refusal metadata — never a strong verdict.
        from platformforge.models import Fact
        from platformforge.rules import RuleEngine
        fs = [Fact.from_dict(f)
              for f in _facts_for(case, case_dir)]
        engine = RuleEngine(_catalog(),
                            versions=case.get("versions"))
        findings, skipped = engine.evaluate(fs)
        got_skipped = {s.get("rule_id") for s in skipped}
        skip_reasons = {s.get("rule_id"): s.get("reason") for s in skipped}
        by_status: dict[str, set[str]] = {}
        for f in findings:
            by_status.setdefault(f.status, set()).add(f.rule_id)
        want_skipped = {
            (next(iter(w)) if isinstance(w, dict) else w)
            for w in exp.get("rules_skipped", [])}
        missing_skip = sorted(want_skipped - got_skipped)
        # `rules_skipped` entries may be bare ids or {id: reason} maps —
        # a wrong skip reason must not satisfy the expectation.
        bad_reason = {}
        for want in exp.get("rules_skipped", []):
            if isinstance(want, dict):
                rid, reason = next(iter(want.items()))
                if rid in skip_reasons and skip_reasons[rid] != reason:
                    bad_reason[rid] = {"want": reason,
                                       "got": skip_reasons[rid]}
        checks: dict[str, tuple[set[str], str]] = {
            "rules_fired": (set(exp.get("rules_fired", [])), "violated"),
            "rules_not_fired": (set(exp.get("rules_not_fired", [])),
                                "violated"),
            "unresolved": (set(exp.get("unresolved", [])), "unresolved"),
            "passed": (set(exp.get("passed", [])), "passed"),
        }
        missing: dict[str, list[str]] = {}
        fired = by_status.get("violated", set())
        strong = fired | by_status.get("passed", set())
        for key, (want, status) in checks.items():
            if not want:
                continue
            if key == "rules_not_fired":
                # "not fired" = no strong verdict at all — `passed` also
                # counts as firing (a silent pass is still an overclaim).
                bad = sorted(want & strong)
                if bad:
                    missing["rules_not_fired"] = bad
                continue
            got = by_status.get(status, set())
            miss = sorted(want - got)
            if miss:
                missing[key] = miss
        # hard invariant: a rule expected unresolved must never emit a
        # strong verdict (overclaim), and vice-versa
        overclaim = sorted(set(exp.get("unresolved", [])) & strong)
        ok = not (missing_skip or missing or overclaim or bad_reason)
        return {"verdict": "pass" if ok else "fail",
                "skipped": sorted(got_skipped),
                "skip_reasons": skip_reasons,
                "bad_skip_reasons": bad_reason,
                "by_status": {k: sorted(v) for k, v in by_status.items()},
                "overclaim": overclaim,
                "missing": missing,
                "missing_skips": missing_skip}
    if t == "live":
        return _grade_live(case, case_dir)
    if t in ("property", "metamorphic"):
        if exp.get("check") == "rtk_round_trip":
            from platformforge.core.store import ArtifactStore
            from platformforge.rtk import compact_output
            from platformforge.rtk.compact import expand
            text = (case_dir / case["fixture"]).read_text()
            with tempfile.TemporaryDirectory() as td:
                store = ArtifactStore(td)
                res = compact_output("cat", text, store=store)
                full = expand(store, res.raw_artifact)
            ok = "\n".join(l.split(": ", 1)[1] for l in full["lines"]) == \
                text.rstrip("\n")
            return {"verdict": "pass" if ok else "fail"}
        return {"verdict": "unresolved",
                "reason": f"unknown property check {exp.get('check')!r}"}
    return {"verdict": "unresolved", "reason": f"unimplemented type {t}"}


def _env_from(path: Path):
    from platformforge.live.envelope import loads
    return loads(path.read_text())


def _grade_live(case: dict, case_dir: Path) -> dict[str, Any]:
    """cycle3 §258 — live-surface evals over recorded fixtures.

    expect.check ∈ collect-k8s | collect-aws | drift | reconcile |
    incident | plan | multicluster | secret-free."""
    exp = case.get("expect", {})
    fx = case_dir / case.get("fixture", "fixture")
    check = exp.get("check", "")
    if check in ("collect-k8s", "collect-aws"):
        from platformforge.live.fixtures import collect_fixture
        from platformforge.live.models import ObservationScope
        provider = "kubernetes" if check == "collect-k8s" else "aws"
        scope = ObservationScope(
            provider=provider,
            resource_types=exp.get("resource_types", []),
            namespaces=exp.get("namespaces", []),
            regions=exp.get("regions", []),
            services=exp.get("services", []))
        try:
            env = collect_fixture(provider, fx, scope=scope).to_dict()
            out = {"envelope": env}
        except Exception as e:  # noqa: BLE001 — fixture error = eval fail
            return {"verdict": "fail", "error": str(e)}
        env = out["envelope"]
        cov = env.get("coverage", {}).get("status")
        n = len(env.get("objects", []))
        failures = []
        if "objects_min" in exp and n < exp["objects_min"]:
            failures.append(f"objects {n} < {exp['objects_min']}")
        if "coverage" in exp and cov != exp["coverage"]:
            failures.append(f"coverage {cov} != {exp['coverage']}")
        for rt in exp.get("denied_types", []):
            if env["coverage"].get("per_resource_type", {}).get(rt) \
                    != "permission-limited":
                failures.append(f"{rt} not marked permission-limited")
        for rt in exp.get("unsupported_types", []):
            if env["coverage"].get("per_resource_type", {}).get(rt) \
                    != "unsupported":
                failures.append(f"{rt} not marked unsupported")
        return {"verdict": "pass" if not failures else "fail",
                "failures": failures, "objects": n, "coverage": cov}
    if check == "drift":
        from platformforge.live.drift import diff_observations
        out = diff_observations(_env_from(fx / "before.json"),
                                _env_from(fx / "after.json"))
        got = {e["drift_class"] for e in out["drift"]}
        want = set(exp.get("drift_classes", []))
        absent = set(exp.get("absent_classes", []))
        ok = want <= got and not (got & absent)
        return {"verdict": "pass" if ok else "fail",
                "drift_classes": sorted(got),
                "missing": sorted(want - got),
                "unexpected": sorted(got & absent)}
    if check == "reconcile":
        from platformforge.live.reconcile import norm_facts, norm_observed, reconcile
        desired = json.loads((fx / "desired.json").read_text())
        desired = desired.get("facts", desired)
        obs = _env_from(fx / "observed.json") \
            if (fx / "observed.json").exists() else None
        out = reconcile(desired=norm_facts(desired, "desired"),
                        planned=[], observed=norm_observed(obs))
        got = {e["drift_class"] for e in out["drift"]}
        want = set(exp.get("drift_classes", []))
        ok = want <= got
        return {"verdict": "pass" if ok else "fail",
                "drift_classes": sorted(got),
                "missing": sorted(want - got)}
    if check == "incident":
        from platformforge.live.incident import score_candidates
        inc = json.loads((fx / "incident.json").read_text())
        cands = json.loads((fx / "changes.json").read_text())
        ranked = score_candidates(inc, cands)["ranked"]
        top = ranked[0]["status"] if ranked else "none"
        ok = top == exp.get("top_status", top)
        return {"verdict": "pass" if ok else "fail",
                "top_status": top, "ranked": len(ranked)}
    if check == "plan":
        from platformforge.live.remediate import remediate
        events = json.loads((fx / "drift.json").read_text())
        out = remediate(events)
        c = out["counts"]
        failures = []
        for k, v in exp.get("counts", {}).items():
            if c.get(k) != v:
                failures.append(f"counts.{k} {c.get(k)} != {v}")
        env = out["envelope"]
        if env["auto_apply"] or env["status"] != "awaiting-approval":
            failures.append("envelope must be awaiting-approval")
        return {"verdict": "pass" if not failures else "fail",
                "failures": failures, "counts": c}
    if check == "multicluster":
        from platformforge.live.federation import Cluster, ClusterRegistry
        specs = json.loads((fx / "clusters.json").read_text())
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            reg = ClusterRegistry(td)
            for s in specs:
                s = dict(s)
                reg.register(Cluster(s.pop("cluster_id"), **s))
            clusters = reg.list()
        want = set(exp.get("clusters", []))
        got = {c["cluster_id"] for c in clusters}
        return {"verdict": "pass" if got == want else "fail",
                "clusters": sorted(got), "missing": sorted(want - got)}
    if check == "temporal":
        # §258 — temporal graph eval: fixture graph.json (v2) +
        # expect.now/max_age_s → expire_stale_edges verdict
        from platformforge.graph.model import Graph
        from platformforge.graph.temporal import expire_stale_edges
        g = Graph.from_dict(json.loads((fx / "graph.json").read_text()))
        expired = expire_stale_edges(
            g, now=exp.get("now", "2100-01-01T00:00:00Z"),
            max_age_s=float(exp.get("max_age_s", 3600)))
        want = sorted(exp.get("expired_edges", []))
        failures = []
        if expired != want:
            failures.append(f"expired {expired} != {want}")
        # expired edges are marked, never deleted (§92)
        for eid in expired:
            if eid not in g.edges:
                failures.append(f"{eid} deleted instead of marked")
            elif not g.edges[eid].temporal.get("expired"):
                failures.append(f"{eid} not marked expired")
        return {"verdict": "pass" if not failures else "fail",
                "failures": failures, "expired": expired}
    if check == "secret-free":
        # §266 — serialized envelope must not contain banned strings
        blob = (fx / "envelope.json").read_text()
        leaked = [s for s in exp.get("must_not_contain", [])
                  if s in blob]
        return {"verdict": "pass" if not leaked else "fail",
                "leaked": leaked}
    if check == "ops-scenario":
        # cycle4 — governed pipeline eval over a lab ops.yaml fixture
        from platformforge.lab.opslab import run_ops_scenario
        try:
            r = run_ops_scenario(fx)
        except Exception as e:  # noqa: BLE001 — fixture error = eval fail
            return {"verdict": "fail", "error": str(e)}
        return {"verdict": "pass" if r["passed"] else "fail",
                "failures": r.get("failures", []),
                "checks": r.get("checks", [])}
    if check == "ops-invariant":
        # cycle4.1 — correctness probes (tamper/refusal/builder)
        import tempfile

        from platformforge.evals.ops_invariants import PROBES
        probe = PROBES.get(str(exp.get("probe", "")))
        if probe is None:
            return {"verdict": "unresolved",
                    "reason": f"unknown probe {exp.get('probe')!r}"}
        with tempfile.TemporaryDirectory() as td:
            try:
                r = probe(td)
            except Exception as e:  # noqa: BLE001
                return {"verdict": "fail", "error": str(e)}
        return {"verdict": "pass" if r.get("ok") else "fail",
                "detail": r.get("detail")}
    return {"verdict": "unresolved",
            "reason": f"unknown live check {check!r}"}


def run_case(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    case = yaml.safe_load(p.read_text())
    res = _grade(case, p.parent)
    return {"id": case.get("id", p.stem), "type": case.get("type", "golden"),
            "variant": case.get("variant"), "case_of": case.get("case_of"),
            **res}


def run_all(cases_dir: str | Path = CASES_DIR,
            type_filter: str | None = None) -> dict[str, Any]:
    d = Path(cases_dir)
    # one dir per case: <cases>/<id>/case.yaml + fixture/ (fixture yaml
    # files never collide with the case file name)
    results = []
    for c in sorted(d.glob("*/case.yaml")) if d.is_dir() else []:
        r = run_case(c)
        if type_filter and r["type"] != type_filter:
            continue
        results.append(r)
    counts = {"pass": 0, "fail": 0, "unresolved": 0}
    for r in results:
        counts[r["verdict"] if r["verdict"] in counts else "unresolved"] += 1
    return {"evals": len(results), "results": results, "counts": counts}
