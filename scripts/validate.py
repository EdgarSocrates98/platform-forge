#!/usr/bin/env python3
"""Cycle 2.1 §143–147 — single validation source.

CI orchestrates this script; it does not re-implement gates. Locally:

    python scripts/validate.py              # all gates → receipt JSON
    python scripts/validate.py --gate lint  # one gate
    python scripts/validate.py --receipt out.json

Every failure is explainable (§147): the gate reports what failed, why,
how to reproduce (`reproduce` field), and how to unlock.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path = REPO) -> dict:
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       check=False)
    return {"cmd": " ".join(cmd), "rc": p.returncode,
            "seconds": round(time.time() - t0, 2),
            "tail": (p.stdout + p.stderr).strip().splitlines()[-5:]}


def _py(expr: str) -> dict:
    return _run([sys.executable, "-c", expr])


def gate_lint() -> dict:
    return _run(["ruff", "check", "."])


def gate_tests() -> dict:
    return _run(["pytest", "-q"])


def gate_provenance() -> dict:
    r = _py("from platformforge.rules.engine import catalog_provenance_report;"
            "from platformforge.resources import data_path;"
            "r = catalog_provenance_report(data_path('rules','catalog'));"
            "assert r['coverage'] == 1.0, r; print(r)")
    r["what"] = "every rule cites >=1 source"
    return r


def gate_linkage() -> dict:
    r = _py("from platformforge.knowledge.registry import SourceRegistry;"
            "from platformforge.resources import data_path;"
            "r = SourceRegistry.default().link_rules(data_path('rules','catalog'));"
            "assert not r['unlinked'], r['unlinked'];"
            "assert not r['bad_refs'], r['bad_refs'];"
            "print(r['coverage'], 'exact-id linked')")
    r["what"] = "rule sources resolve by canonical id — no fuzzy matching"
    return r


def gate_knowledge() -> dict:
    r = _py("from platformforge.knowledge.registry import (SourceRegistry, "
            "SOURCE_AUTHORITIES);"
            "reg = SourceRegistry.default();"
            "c = reg.contract_check(); assert c['ok'], c;"
            "bad = [e.id for e in reg.entries.values() "
            "     if e.source_authority not in SOURCE_AUTHORITIES];"
            "assert not bad, f'unknown authority: {bad}';"
            "print(len(reg.entries), 'sources valid')")
    r["what"] = "source registry contract + closed authority vocabulary"
    return r


def gate_packs() -> dict:
    r = _py("from platformforge.knowledge.packs import PackRegistry;"
            "c = PackRegistry.default().contract_check();"
            "assert c['ok'], c;"
            "print(c['packs'], 'packs,', c['consumed'], 'consumed')")
    r["what"] = "knowledge packs resolve sources+rules+analyzers; "
    "none unconsumed"
    return r


def gate_lab() -> dict:
    return _run(["platformforge", "lab", "run-all"])


def gate_evals() -> dict:
    # Assert on verdict counts — a case regressing to `unresolved` or
    # `fail` fails the gate. (Can't use --strict: expected-unresolved
    # rules legitimately appear in passing cases' by_status.)
    r = _py("import json, subprocess;"
            "out = subprocess.run(['platformforge','evals','run'],"
            " capture_output=True, text=True).stdout;"
            "d = json.loads(out[out.find('{'):]);"
            "c = d['counts'];"
            "assert c.get('fail', 0) == 0 and c.get('unresolved', 0) == 0, c;"
            "print(c)")
    r["what"] = "every eval case passes; none unresolved or failed"
    return r


def gate_coverage() -> dict:
    # assert, don't just print — uncovered rules fail the gate
    r = _py("import json, subprocess;"
            "out = subprocess.run(['platformforge','evals','coverage'],"
            " capture_output=True, text=True).stdout;"
            "d = json.loads(out[out.find('{'):]);"
            "unc = d['counts'].get('uncovered', []);"
            "assert not unc, f'uncovered rules: {unc}';"
            "print(d['counts']['rules'], 'rules, 0 uncovered')")
    r["what"] = "every rule is named by an eval case or lab scenario"
    return r


def gate_mcp_parity() -> dict:
    r = _py("from platformforge.mcp.registry import tool_descriptors;"
            "t = tool_descriptors(); assert len(t) >= 20, len(t);"
            "print(len(t), 'mcp tools')")
    r["what"] = "MCP tool surface registered"
    return r


def gate_docs() -> dict:
    return _run(["pytest", "-q", "tests/test_docs_drift.py"])


def gate_security() -> dict:
    r = _run(["pytest", "-q", "tests/test_redaction.py",
              "tests/test_offline.py"])
    r["what"] = "redaction coverage + offline enforcement"
    return r


def gate_package() -> dict:
    """Build + validate the wheel — never skipped: a missing wheel is a
    failure, not a pass (the gate exists to prove installable truth)."""
    if not list(REPO.glob("dist/*.whl")):
        b = _run(["uv", "build", "--out-dir", "dist"])
        if b["rc"] != 0:
            return {"rc": b["rc"], "tail": b["tail"],
                    "what": "wheel build (uv build)"}
    if not list(REPO.glob("dist/*.whl")):
        return {"rc": 1, "tail": ["uv build produced no wheel"],
                "what": "wheel build produced an artifact"}
    r = _py("import zipfile, glob;"
            "w = zipfile.ZipFile(glob.glob('dist/*.whl')[0]);"
            "names = w.namelist();"
            "need = ('platformforge/data/rules/catalog/',"
            "        'platformforge/data/knowledge/sources.yaml',"
            "        'platformforge/data/contracts/fact.schema.json',"
            "        'platformforge/data/lab/scenarios/',"
            "        'platformforge/data/evals/cases/');"
            "miss = [n for n in need "
            "        if not any(x.startswith(n) for x in names)];"
            "assert not miss, miss;"
            "print(sum(1 for x in names if '/data/' in x), 'data files')")
    r["what"] = "wheel ships rules/knowledge/contracts/lab/evals data"
    return r


def gate_self() -> dict:
    """§43 dogfooding — the platform validates its own repo: inspect
    finds analyzable artifacts, agents lint is clean, the capability
    manifest builds, collect accounts for every file."""
    r = _py(
        "import json, subprocess\n"
        "def run(*a):\n"
        "    p = subprocess.run(['platformforge', *a], capture_output=True,\n"
        "                       text=True)\n"
        "    return json.loads(p.stdout[p.stdout.find('{'):]), p.returncode\n"
        "inv, rc1 = run('inspect', '--repo', '.')\n"
        "assert rc1 == 0 and inv.get('artifacts'), 'inspect found nothing'\n"
        "lint, rc2 = run('agents', 'lint')\n"
        "assert rc2 == 0 and lint.get('ok', True), 'agents lint failed'\n"
        "man, rc3 = run('capability', 'manifest')\n"
        "assert rc3 == 0 and (man.get('capabilities_v2') or "
        "man.get('capabilities')), 'manifest empty'\n"
        "print('self-gate: inspect+agents+manifest ok')")
    r["what"] = "platformforge inspects/lints/manifests itself (§43)"
    return r


# --- Cycle 4.1 — governed operations gates (§H) -----------------------

def gate_ops_contracts() -> dict:
    """Typed-action contract: every mutating action declares a rollback
    strategy + required pre-state or an explicit non-executable
    strategy; builders exist for executable strategies; forbidden
    action names stay refused."""
    r = _py(
        "from platformforge.ops.actions import (catalog, spec_for,\n"
        "    validate_action, FORBIDDEN_ACTIONS)\n"
        "from platformforge.ops.rollback_builders import BUILDERS\n"
        "cat = catalog()\n"
        "bad = []\n"
        "for name, s in cat.items():\n"
        "    if not s['mutating']:\n"
        "        continue\n"
        "    if not s['rollback_strategy']:\n"
        "        bad.append(f'{name}:no-strategy')\n"
        "    if s['rollback_strategy'] in ('direct-inverse',\n"
        "            'previous-revision', 'source-revert',\n"
        "            'compensating-operation') and not s['rollback_builder']:\n"
        "        bad.append(f'{name}:no-builder')\n"
        "    if s['rollback_builder'] and \\\n"
        "            s['rollback_builder'] not in BUILDERS:\n"
        "        bad.append(f'{name}:builder-missing')\n"
        "assert not bad, bad\n"
        "for f in FORBIDDEN_ACTIONS:\n"
        "    assert validate_action(f, {}) is not None, f\n"
        "print(len(cat), 'actions, contracts ok')")
    r["what"] = "mutating actions declare strategy+prestate+builder; forbidden refused"
    return r


def gate_ops_approval() -> dict:
    return _run(["pytest", "-q", "tests/test_ops_approval.py",
                 "tests/test_ops_models.py"])


def gate_ops_execution() -> dict:
    return _run(["pytest", "-q", "tests/test_ops_executors.py",
                 "tests/test_ops_operation.py",
                 "tests/test_ops_pipeline.py", "tests/test_cli_ops.py"])


def gate_ops_rollback() -> dict:
    r = _run(["pytest", "-q", "tests/test_ops_rollback.py",
              "tests/test_ops_gapwave.py"])
    r["what"] = "material-bound rollback plans + engine"
    if r["rc"] == 0:
        inv = _py(
            "from platformforge.ops.rollback import terraform_plan_reuse_check\n"
            "assert terraform_plan_reuse_check('sha256:x','sha256:x')\\\n"
            "    ['refusal'] == 'PF-OPS-PLAN-REUSE'\n"
            "print('forward-plan reuse refused')")
        if inv["rc"] != 0:
            return inv
    return r


def gate_ops_verification() -> dict:
    return _run(["pytest", "-q", "tests/test_ops_verify.py"])


def gate_ops_policy() -> dict:
    return _run(["pytest", "-q", "tests/test_ops_policy.py",
                 "tests/test_ops_autorem.py", "tests/test_ops_property.py"])


def gate_ops_evals() -> dict:
    r = _py(
        "from platformforge.evals.runner import run_all\n"
        "out = run_all()\n"
        "ops = [r for r in out['results'] if r['id'].startswith('ops-')]\n"
        "assert len(ops) >= 8, len(ops)\n"
        "bad = [r['id'] for r in ops if r['verdict'] != 'pass']\n"
        "assert not bad, bad\n"
        "print(len(ops), 'ops evals pass')")
    r["what"] = "ops-* eval cases all pass"
    return r


def gate_ops_lab() -> dict:
    r = _py(
        "from platformforge.lab.runner import run_all\n"
        "out = run_all()\n"
        "res = out.get('scenarios') or out.get('results') or []\n"
        "ops = [r for r in res if 'ops-' in (r.get('scenario') or\n"
        "       r.get('id') or '')]\n"
        "assert len(ops) >= 10, len(ops)\n"
        "bad = [r for r in ops if not r.get('passed', True)]\n"
        "assert not bad, [r.get('failures') for r in bad]\n"
        "print(len(ops), 'ops lab scenarios pass')")
    r["what"] = "ops-* lab scenarios all pass"
    return r


# ── cycle5 gates (§364) ─────────────────────────────────────────────


def gate_fleet_contracts() -> dict:
    r = _py(
        "from platformforge.fleet.models import (\n"
        "    Fleet, FleetSnapshot, MemberObservation, member_key)\n"
        "from platformforge.analytics.models import (\n"
        "    PlatformMetric, AnalyticsDataQuality, HistoricalPattern)\n"
        "f = Fleet.from_dict({'fleet_id':'f','members':{'clusters':"
        "[{'kind':'cluster','canonical_id':'c1'}]}})\n"
        "assert member_key('cluster','c1') == 'cluster:c1'\n"
        "s = FleetSnapshot(fleet_id='f', member_observations=[\n"
        "    MemberObservation(member_id='cluster:c1', status='observed')])\n"
        "assert s.to_dict()['fleet_id'] == 'f'\n"
        "assert PlatformMetric(metric_id='m', dimension='reliability',\n"
        "    scope={'fleet':'f'}, value=1, unit='u').to_dict()\n"
        "assert AnalyticsDataQuality().confidence_cap in "
        "('low','medium','high')\n"
        "assert HistoricalPattern(pattern_id='p', window='90d')"
        ".to_dict()\n"
        "print('fleet contracts round-trip')")
    r["what"] = "fleet + analytics contracts serialize/round-trip"
    return r


def gate_fleet_graph() -> dict:
    r = _run(["pytest", "-q", "tests/test_fleet.py"])
    r["what"] = "org layers, fleet questions, memory+sqlite backends"
    return r


def gate_analytics() -> dict:
    r = _py(
        "from platformforge.analytics.dx import dx_metrics\n"
        "from platformforge.analytics.goldenpath import golden_path_analytics\n"
        "from platformforge.analytics.finops_v4 import cost_hierarchy\n"
        "from platformforge.analytics.capacity import capacity_risk, "
        "CapacitySnapshot\n"
        "assert dx_metrics([])['scope'].startswith('team')\n"
        "assert 'paths' in golden_path_analytics([])\n"
        "assert 'unallocated' in cost_hierarchy([])\n"
        "assert capacity_risk(CapacitySnapshot(member_id='m'))['risk']\n"
        "print('analytics engines answer on empty input without crash')")
    r["what"] = "measurement/golden-path/finops/capacity on empty input"
    return r


def gate_history() -> dict:
    r = _py(
        "from platformforge.analytics.history import HistoryEngine, WINDOWS\n"
        "eng = HistoryEngine()\n"
        "assert set(WINDOWS) >= {'24h','7d','30d','90d'}\n"
        "assert eng.patterns('90d') == []\n"
        "eng.ingest_events('incident', [{'ts':'bad-ts'}], 't')\n"
        "assert eng.patterns('90d') == []  # unparseable never counted\n"
        "print('history windows + insufficient-history honest')")
    r["what"] = "windows exist; empty/invalid input → no pattern"
    return r


def gate_optimization() -> dict:
    r = _py(
        "from platformforge.optimize.engine import OptimizationEngine\n"
        "from platformforge.optimize.models import (\n"
        "    OptimizationOpportunity, OptimizationRecommendation)\n"
        "from platformforge.ops.models import ChangeIntent\n"
        "eng = OptimizationEngine()\n"
        "eng.add_opportunity(OptimizationOpportunity(\n"
        "    opportunity_id='o', type='cost', scope={}, evidence=[],\n"
        "    uncertainty='high'))\n"
        "assert eng.recommendations() == []  # suppressed\n"
        "ci = OptimizationEngine.plan(OptimizationRecommendation(\n"
        "    recommendation_id='r', type='c', scope={'s':'x'}))\n"
        "assert isinstance(ci, ChangeIntent)\n"
        "assert ci.reason.type == 'recommendation'\n"
        "print('optimization boundary: suppressed + ChangeIntent only')")
    r["what"] = "uncertain suppressed; plan() → ChangeIntent only"
    return r


def gate_federation() -> dict:
    r = _py(
        "from platformforge.federation.node import NodeManifest, export_summary\n"
        "from platformforge.ops.registry import delegation_contract, "
        "validate_delegate_request\n"
        "node = NodeManifest(node_id='n')\n"
        "assert export_summary(node, {'api_key':'AKIAIOSFODNN7EXAMPLE'},"
        " 'public')['action'] == 'deny'\n"
        "assert export_summary(node, {'x':1}, 'restricted')['action'] "
        "== 'deny'\n"
        "for bad in ('direct-execution','approval-minting',\n"
        "            'full-fleet-dump'):\n"
        "    assert bad in delegation_contract()['refuses']\n"
        "assert validate_delegate_request({'kind':'shell-command'})"
        "['refusal'].startswith('PF-OPS')\n"
        "print('federation bounded; exec refused')")
    r["what"] = "secrets/restricted denied; delegation refuses exec"
    return r


def gate_privacy() -> dict:
    r = _py(
        "from platformforge.analytics.dx import (FORBIDDEN_METRICS,\n"
        "    dx_metrics, guard_no_person_metrics)\n"
        "from platformforge.ops.config import validate_config\n"
        "m = dx_metrics([{'path':'p','status':'ok','person':'x'}])\n"
        "assert guard_no_person_metrics(m) == []\n"
        "v = validate_config({'privacy':{'dx_metrics':'per-person'},\n"
        "                   'retention':{'telemetry':'local-only'}})\n"
        "assert any(x['refusal']=='PF-OPS-CONFIG-PRIVACY' for x in v)\n"
        "print('dx team-level only; privacy pinned')")
    r["what"] = "no person metrics; privacy not configurable downward"
    return r


def gate_ai_platform() -> dict:
    r = _py(
        "from platformforge.aiplat.models import (ai_unit_economics,\n"
        "    detect_ai_workloads)\n"
        "assert 'cost_per_1m_tokens' not in ai_unit_economics(100)\n"
        "assert ai_unit_economics(100, tokens=1000000)"
        "['cost_per_1m_tokens'] == 100.0\n"
        "w = detect_ai_workloads([{'resources':{'limits':"
        "{'nvidia.com/gpu':1}}}])\n"
        "assert w\n"
        "print('ai awareness: denominators required')")
    r["what"] = "unit economics only with denominators; gpu detected"
    return r


def gate_fleet_evals() -> dict:
    r = _py(
        "from platformforge.evals.runner import run_all\n"
        "out = run_all()\n"
        "fl = [r for r in out['results']\n"
        "      if r['id'].startswith('fleet-inv-')]\n"
        "assert len(fl) >= 10, len(fl)\n"
        "bad = [r['id'] for r in fl if r['verdict'] != 'pass']\n"
        "assert not bad, bad\n"
        "print(len(fl), 'fleet invariant evals pass')")
    r["what"] = "fleet-inv-* eval cases all pass"
    return r


def gate_fleet_lab() -> dict:
    r = _py(
        "from platformforge.lab.runner import run_all\n"
        "out = run_all()\n"
        "res = out.get('scenarios') or out.get('results') or []\n"
        "fl = [r for r in res if str(r.get('scenario') or '')"
        ".startswith('fleet-')]\n"
        "assert len(fl) >= 10, len(fl)\n"
        "bad = [r['scenario'] for r in fl if not r.get('passed', True)]\n"
        "assert not bad, bad\n"
        "print(len(fl), 'fleet lab scenarios pass')")
    r["what"] = "fleet-* lab scenarios all pass"
    return r


def gate_adversarial() -> dict:
    r = _run(["pytest", "-q", "tests/test_fleet_adversarial.py"])
    r["what"] = "E1–E12 adversarial invariants fail closed"
    return r


# --- cycle5.1 (§91) ------------------------------------------------------


def gate_agent_routing() -> dict:
    r = _py("from platformforge.routing import validate_routing;"
            "r = validate_routing();"
            "assert r['ok'], r['problems'];"
            "print(r['routes'], 'routes,', r['agents'], 'agents — no drift')")
    r["what"] = "every routing.yaml + orchestration.yaml + roster ref " \
        "resolves — no missing agents"
    return r


def gate_agent_contract() -> dict:
    return _run(["pytest", "-q", "tests/test_agent_protocol.py",
                 "tests/test_agent_handoffs.py", "tests/test_agent_budget.py",
                 "tests/test_orchestrator.py", "tests/test_coordinators.py",
                 "tests/test_specialists.py", "tests/test_reviewers.py",
                 "tests/test_executors.py", "tests/test_agent_routing.py"])


GATES = {
    "lint": gate_lint, "tests": gate_tests, "provenance": gate_provenance,
    "linkage": gate_linkage, "knowledge": gate_knowledge,
    "packs": gate_packs, "lab": gate_lab, "evals": gate_evals,
    "coverage": gate_coverage, "mcp-parity": gate_mcp_parity,
    "docs": gate_docs, "security": gate_security, "package": gate_package,
    "self": gate_self,
    "ops-contracts": gate_ops_contracts,
    "ops-approval": gate_ops_approval,
    "ops-execution": gate_ops_execution,
    "ops-rollback": gate_ops_rollback,
    "ops-verification": gate_ops_verification,
    "ops-policy": gate_ops_policy,
    "ops-evals": gate_ops_evals,
    "ops-lab": gate_ops_lab,
    # cycle5 (§364)
    "fleet-contracts": gate_fleet_contracts,
    "fleet-graph": gate_fleet_graph,
    "analytics": gate_analytics,
    "history": gate_history,
    "optimization": gate_optimization,
    "federation": gate_federation,
    "privacy": gate_privacy,
    "ai-platform": gate_ai_platform,
    "fleet-evals": gate_fleet_evals,
    "fleet-lab": gate_fleet_lab,
    "adversarial": gate_adversarial,
    "agent-routing": gate_agent_routing,
    "agent-contract": gate_agent_contract,
}

UNLOCK = {
    "lint": "ruff check --fix . or fix the reported lines",
    "tests": "reproduce: pytest -q; fix the failing test or the code",
    "provenance": "add a canonical `sources:` id to the uncovered rule",
    "linkage": "use a registry `id:` (not a URL); fix `source_refs` keys",
    "knowledge": "complete required entry fields; fix source_authority",
    "packs": "resolve pack refs or remove the unconsumed pack",
    "lab": "platformforge lab run-all; fix the failing scenario/expected.yaml",
    "evals": "platformforge evals run; fix case or graded behavior",
    "coverage": "add an eval/lab case naming the uncovered rule",
    "mcp-parity": "register the missing tool in mcp/registry.py",
    "docs": "update docs to name the real verb (tests/test_docs_drift.py)",
    "security": "keep redaction before index/compress; fix the pattern or FP",
    "package": "check pyproject force-include map; rebuild wheel",
    "self": "run platformforge inspect . / agents lint / capability manifest",
    "ops-contracts": "declare rollback_strategy/pre_state/builder on the ActionSpec",
    "ops-approval": "reproduce: pytest tests/test_ops_approval.py",
    "ops-execution": "reproduce: pytest tests/test_ops_executors.py tests/test_ops_pipeline.py",
    "ops-rollback": "reproduce: pytest tests/test_ops_rollback.py; material must drive reversal",
    "ops-verification": "reproduce: pytest tests/test_ops_verify.py",
    "ops-policy": "reproduce: pytest tests/test_ops_policy.py tests/test_ops_autorem.py",
    "ops-evals": "platformforge evals run; fix the failing ops-* case",
    "ops-lab": "platformforge lab run-all; fix the failing ops-* scenario",
    "fleet-contracts": "fix the dataclass in platformforge/fleet|analytics models",
    "fleet-graph": "reproduce: pytest tests/test_fleet.py",
    "analytics": "analytics engines must answer empty input without crash",
    "history": "windows exist in analytics/history.WINDOWS; unparseable ts skipped",
    "optimization": "uncertainty high suppresses; plan() returns ChangeIntent only",
    "federation": "export_summary deny secrets/restricted; delegation refuses exec",
    "privacy": "dx_metrics must stay team-level; privacy pins not overridable",
    "ai-platform": "ai_unit_economics requires a real denominator",
    "fleet-evals": "platformforge evals run; fix the failing fleet-inv-* case",
    "fleet-lab": "platformforge lab run-all; fix the failing fleet-* scenario",
    "adversarial": "reproduce: pytest tests/test_fleet_adversarial.py",
    "agent-routing": "every name in routing.yaml/orchestration.yaml/"
        "roster must resolve — run platformforge.routing.validate_routing()",
    "agent-contract": "reproduce: pytest -q tests/test_agent_*.py "
        "tests/test_orchestrator.py tests/test_coordinators.py",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", choices=sorted(GATES))
    ap.add_argument("--receipt", help="write machine-readable receipt JSON")
    args = ap.parse_args()

    names = [args.gate] if args.gate else list(GATES)
    receipt = {"kind": "platformforge/validation-receipt/1",
               "sha": _run(["git", "rev-parse", "HEAD"])["tail"][-1:]
                      if not args.gate else None,
               "gates": {}}
    failed = []
    for name in names:
        res = GATES[name]()
        ok = res.get("rc", 1) == 0
        entry = {"ok": ok, "reproduce": res.get("cmd", "n/a"),
                 "seconds": res.get("seconds")}
        if res.get("skipped"):
            entry["skipped"] = res["skipped"]
        if not ok:
            entry["why"] = res.get("tail", [])[-3:]
            entry["unlock"] = UNLOCK.get(name, "see the gate output")
            failed.append(name)
        receipt["gates"][name] = entry
        print(f"{'PASS' if ok else 'FAIL'} {name}", file=sys.stderr)

    receipt["verdict"] = "validated" if not failed else "failed"
    receipt["failed"] = failed
    if args.receipt or not args.gate:
        out = json.dumps(receipt, indent=2, sort_keys=True)
        if args.receipt:
            Path(args.receipt).write_text(out)
        else:
            print(out)
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
