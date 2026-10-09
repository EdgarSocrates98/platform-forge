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
                 "tests/test_executors.py", "tests/test_agent_routing.py",
                 "tests/test_agent_mirrors.py"])


def gate_agent_mirrors() -> dict:
    r = _run(["platformforge", "agents", "check"])
    r["what"] = "host mirrors equal generated output — no drift, " \
        "no stray files"
    return r


def gate_agent_economy() -> dict:
    r = _run(["pytest", "-q", "tests/test_agent_economy.py"])
    r["what"] = "context packs measured+bounded, delta context, run " \
        "ledger honesty (observed requires transcript_ref)"
    return r


def gate_agent_debate() -> dict:
    r = _run(["pytest", "-q", "tests/test_agent_debate.py"])
    r["what"] = "debate bounded (≤4 participants, ≤3 rounds), " \
        "evidence-required, referee receipt, verifier still required"
    return r


def gate_agent_independence() -> dict:
    r = _run(["pytest", "-q", "tests/test_agent_adversarial.py"])
    r["what"] = "A1–A12 adversarial probes — no fabricated evidence, " \
        "no skipped verifier, no self-verification, no swarm, " \
        "no budget reset, no permission gain via mirrors"
    return r


def gate_agent_evals() -> dict:
    r = _run(["platformforge", "evals", "run"])
    r["what"] = "eval suite incl. the 10 agent cases (§175) — all pass"
    return r


# --- freeze gates (prompt_evo_freezing §7, §196) ------------------------

def gate_freeze_contracts() -> dict:
    r = _run(["platformforge", "freeze", "check"])
    r["what"] = ("no breaking drift vs docs/freeze/snapshots — "
                 "schemas/CLI/MCP/capabilities/agents")
    return r


def gate_freeze_docs() -> dict:
    expr = (
        "from pathlib import Path\n"
        "req = ['FREEZE-MANIFEST.md', 'REAL-WORLD-ISSUES.md',\n"
        "       'ARCHITECTURE-FREEZE-REVIEW.md', 'FINAL-REPORT.md',\n"
        "       'FINAL-MATRIX.md']\n"
        "missing = [f for f in req\n"
        "           if not Path('docs/freeze', f).exists()]\n"
        "import sys\n"
        "if missing:\n"
        "    print('missing:', missing); sys.exit(1)\n"
    )
    r = _py(expr)
    r["what"] = "docs/freeze required artifacts exist"
    return r


def gate_freeze_replay() -> dict:
    r = _run(["platformforge", "cases", "replay"])
    r2 = _run(["platformforge", "cases", "ledger-check"])
    r["what"] = ("deterministic replay of .platformforge/cases — "
                 "golden + holdout corpora, canonical-hash stable; "
                 "FP/FN ledger entries well-formed with resolvable "
                 "regression pointers")
    if r["rc"] == 0 and r2["rc"] != 0:
        r["rc"] = r2["rc"]
        r["tail"] += r2["tail"]
    return r


def gate_freeze_exceptions() -> dict:
    expr = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from platformforge.freeze.exceptions import exception_errors\n"
        "bad = []\n"
        "for f in Path('docs/freeze/exceptions').glob('*.json'):\n"
        "    errs = exception_errors(json.loads(f.read_text()))\n"
        "    if errs: bad.append((f.name, errs))\n"
        "if bad: print(bad); sys.exit(1)\n"
    )
    r = _py(expr)
    r["what"] = "every FeatureException doc validates (§6)"
    return r


# --- economy control plane gates (prompt_evo_economy §T) -----------------

def gate_economy_contracts() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_contracts.py",
              "tests/test_economy_v2.py"])
    r["what"] = ("EconomyPlan pipeline + explainability; BudgetEnvelope "
                 "dims/hard-soft/phases/roles/protected; unified ledger "
                 "basis separation")
    return r


def gate_economy_cache() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_cache.py"])
    r["what"] = ("multilayer cache: content addressing, dep-graph "
                 "selective invalidation, TTL/GC, decision cache, "
                 "receipts, no secret caching")
    return r


def gate_economy_context() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_gateway.py",
              "-k", "TestGateway or TestLazy or TestRole or Suff"])
    r["what"] = ("ContextGateway capsule/refs/sufficiency/role "
                 "contexts; essential-evidence refusal")
    return r


def gate_economy_budget() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_contracts.py",
              "-k", "budget or limit or protected or dimension"])
    r["what"] = "BudgetEnvelope: hard never silent, protected items"
    return r


def gate_economy_resume() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_gateway.py",
              "-k", "resume or checkpoint"])
    r["what"] = ("checkpoint/resume: spend preserved, deps revalidated, "
                 "profile never downgraded")
    return r


def gate_economy_reconcile() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_gateway.py",
              "tests/test_economy_evals.py",
              "-k", "reconcil or mismatch or unobserved"])
    r["what"] = ("planned vs observed per axis; unmeasured = unresolved, "
                 "never zero; savings claims gated on measured data")
    return r


def gate_economy_routing() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_evals.py",
              "-k", "routing or profile or champion or simple_task"])
    r["what"] = ("routing profiles + risk floors; challenger promotion "
                 "requires human; receipts bind inputs/policy")
    return r


def gate_economy_agentic() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_agents_waste.py",
              "tests/test_economy_evals.py",
              "-k", ("uniqueness or debate or duplication or fanout or "
                     "waste or stagnant")])
    r["what"] = ("agent uniqueness audit, debate bounds + stagnation "
                 "stop, waste detector, RTK economy receipt")
    return r


def gate_economy_verification() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_pricing_verify.py"])
    r["what"] = ("selective verification tiers + risk floors + security "
                 "check always-in; declared pricing or unresolved")
    return r


def gate_economy_qpt() -> dict:
    r = _run(["pytest", "-q", "tests/test_qpt_v2.py",
              "tests/test_economy_fleet_qpt.py"])
    r["what"] = ("QPT v2 no regression + v3 quality-per-cost dims "
                 "(unresolved never zeroed; floors gate savings)")
    return r


def gate_economy_evals() -> dict:
    r = _run(["pytest", "-q", "tests/test_economy_evals.py"])
    r["what"] = "13 named evals + 8 properties + E1-E12 adversarial"
    return r


def gate_economy_surface() -> dict:
    expr = (
        "import subprocess, sys\n"
        "cmds = [\n"
        " ['platformforge','economy','doctor'],\n"
        " ['platformforge','economy','checkpoint','--run-id','gate',\n"
        "  '--spent','{\"tokens\":1}'],\n"
        " ['platformforge','economy','resume','--run-id','gate'],\n"
        " ['platformforge','economy','reconcile',\n"
        "  '--planned','{\"tokens\":1}','--observed','{\"tokens\":2}'],\n"
        " ['platformforge','economy','explain','--run-id','gate'],\n"
        " ['platformforge','cache','stats'],\n"
        " ['platformforge','cache','gc'],\n"
        " ['platformforge','context','capsule','--task','t',\n"
        "  '--facts','[{\"fact_id\":\"f\"}]'],\n"
        " ['platformforge','context','gc'],\n"
        " ['platformforge','routing','explain','--signal','{}'],\n"
        " ['platformforge','routing','compare',\n"
        "  '--champion','{}','--challenger','{}'],\n"
        "]\n"
        "for c in cmds:\n"
        "    r = subprocess.run(c, capture_output=True)\n"
        "    if r.returncode not in (0, 2):\n"
        "        print('FAIL', c, r.returncode, r.stderr[-300:])\n"
        "        sys.exit(1)\n"
        "print('all economy verbs respond')\n"
    )
    r = _py(expr)
    r["what"] = ("every economy/context/cache/routing CLI verb "
                 "responds (0=ok, 2=refusal — refusals are valid)")
    return r


def gate_economy_receipt() -> dict:
    """polish §8 — the committed closure receipt is structurally valid,
    bound to HEAD or HEAD~1 (receipt-only commit on top), uses canonical
    gate names only, and every reproduce test path exists."""
    expr = (
        "import json, re, subprocess, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, 'scripts')\n"
        "import validate as V\n"
        "p = Path(V.ECONOMY_RECEIPT_PATH)\n"
        "if not p.is_file():\n"
        "    print('missing receipt:', p); sys.exit(1)\n"
        "r = json.loads(p.read_text())\n"
        "bad = []\n"
        "if r.get('schema') != V.ECONOMY_RECEIPT_SCHEMA:\n"
        "    bad.append(('schema', r.get('schema')))\n"
        "vs = r.get('validated_sha') or ''\n"
        "ok_sha = subprocess.run(['git','cat-file','-e',\n"
        "    vs + '^{commit}'], capture_output=True).returncode == 0\n"
        "if not ok_sha: bad.append(('validated_sha-not-a-commit', vs))\n"
        "head = subprocess.run(['git','rev-parse','HEAD'],\n"
        "    capture_output=True, text=True).stdout.strip()\n"
        "head1 = subprocess.run(['git','rev-parse','HEAD~1'],\n"
        "    capture_output=True, text=True).stdout.strip()\n"
        "if vs not in (head, head1):\n"
        "    bad.append(('validated_sha-stale', vs, head))\n"
        "canon = set(V._economy_gate_names())\n"
        "extra = set(r.get('gates', {})) - canon\n"
        "if extra: bad.append(('noncanonical-gates', sorted(extra)))\n"
        "pat = re.compile('tests/' + r'\\S+' + r'\\.py')\n"
        "for g, e in r.get('gates', {}).items():\n"
        "    for t in pat.findall(e.get('reproduce') or ''):\n"
        "        if not Path(t).is_file():\n"
        "            bad.append(('dead-reproduce-path', g, t))\n"
        "if r.get('verdict') not in ('validated', 'failed'):\n"
        "    bad.append(('verdict', r.get('verdict')))\n"
        "if bad: print(bad); sys.exit(1)\n"
        "print('receipt coherent:', len(r['gates']), 'gates,',\n"
        "      'sha bound')\n"
    )
    r = _py(expr)
    r["what"] = ("committed VALIDATION-RECEIPT.json: v1 schema, "
                 "validated_sha bound to HEAD/HEAD~1, canonical gate "
                 "names only, no dead reproduce paths")
    return r


def gate_economy_closure() -> dict:
    """polish §44–45 — closure artifacts exist, status vocabulary is
    honest, routing authority documented, polish tests pass."""
    expr = (
        "import sys\n"
        "from pathlib import Path\n"
        "req = {'docs/economy-parity/FINAL-REPORT.md':\n"
        "         ['validated_sha', 'remote_ci', 'known gap'],\n"
        "       'docs/economy-parity/FINAL-MATRIX.md':\n"
        "         ['validated', 'externally-unverified'],\n"
        "       'docs/economy-parity/ECONOMY-BENCHMARKS.md':\n"
        "         ['Control Plane Overhead', 'End-to-End'],\n"
        "       'docs/economy/ROUTING.md':\n"
        "         ['decide', 'advisory'],\n"
        "       'docs/economy-parity/POLISH-BASELINE.md': ['drift']}\n"
        "bad = []\n"
        "for f, needles in req.items():\n"
        "    p = Path(f)\n"
        "    if not p.is_file(): bad.append(('missing', f)); continue\n"
        "    txt = p.read_text()\n"
        "    for n in needles:\n"
        "        if n not in txt: bad.append((f, n))\n"
        "m = Path('docs/economy-parity/FINAL-MATRIX.md').read_text()\n"
        "if '\\n' + '|' in m and ' fully-production' in m:\n"
        "    bad.append(('matrix', 'overclaimed status'))\n"
        "if bad: print(bad); sys.exit(1)\n"
        "print('closure docs coherent')\n"
    )
    r1 = _py(expr)
    r2 = _run(["pytest", "-q", "tests/test_economy_closure.py"])
    r1["what"] = ("closure artifacts exist + honest statuses + routing "
                  "authority documented + polish test suite "
                  "(receipt/parity/reproduce/authority/doctor/P1-P10)")
    if r1["rc"] == 0:
        r1["rc"] = r2["rc"]
        r1["tail"] += r2["tail"]
        r1["seconds"] = round(r1["seconds"] + r2["seconds"], 2)
        r1["cmd"] += " && " + r2["cmd"]
    return r1

def gate_portable_contracts() -> dict:
    r = _run(["pytest", "-q", "tests/test_portable_distribution.py",
              "tests/test_portable_workspace.py"])
    r["what"] = "portable contracts, ownership lifecycle and workspace manifest"
    return r


def gate_portable_surface() -> dict:
    r = _py(
        "import subprocess,sys;"
        "cmds=["
        "['platformforge','install','--help'],"
        "['platformforge','uninstall','--help'],"
        "['platformforge','upgrade','--help'],"
        "['platformforge','portable','--help'],"
        "['platformforge','workspace','--help']"
        "];"
        "bad=[];"
        "[(bad.append(c) if subprocess.run(c,capture_output=True).returncode else None) for c in cmds];"
        "assert not bad,bad;print('portable CLI surface ok')"
    )
    r["what"] = "install/uninstall/upgrade/portable/workspace CLI surfaces resolve"
    return r


def gate_portable_security() -> dict:
    r = _py(
        "import tempfile;"
        "from pathlib import Path;"
        "from platformforge.distribution.service import _safe_target;"
        "root=Path(tempfile.mkdtemp());"
        "ok=False;"
        "\ntry:_safe_target(root,'../escape')"
        "\nexcept ValueError:ok=True"
        "\nassert ok;print('path containment ok')"
    )
    r["what"] = "portable path containment fails closed"
    return r


def gate_portable_offline() -> dict:
    r = _py(
        "import tempfile;"
        "from pathlib import Path;"
        "from platformforge.distribution.bundle import build_bundle,verify_bundle;"
        "p=Path(tempfile.mkdtemp())/'bundle';"
        "build_bundle(p,hosts=['codex'],offline=True);"
        "assert verify_bundle(p)['valid'];"
        "print('offline bundle verifies')"
    )
    r["what"] = "offline bundle builds and verifies without provider/network calls"
    return r



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
    "agents-routing": gate_agent_routing,
    "agents-contract": gate_agent_contract,
    "agents-mirrors": gate_agent_mirrors,
    "agents-economy": gate_agent_economy,
    "agents-debate": gate_agent_debate,
    "agents-independence": gate_agent_independence,
    "agents-evals": gate_agent_evals,
    # freeze (prompt_evo_freezing §7)
    "freeze-contracts": gate_freeze_contracts,
    "freeze-docs": gate_freeze_docs,
    "freeze-replay": gate_freeze_replay,
    "freeze-exceptions": gate_freeze_exceptions,
    # economy control plane (prompt_evo_economy §T)
    "economy-contracts": gate_economy_contracts,
    "economy-cache": gate_economy_cache,
    "economy-context": gate_economy_context,
    "economy-budget": gate_economy_budget,
    "economy-resume": gate_economy_resume,
    "economy-reconcile": gate_economy_reconcile,
    "economy-routing": gate_economy_routing,
    "economy-agentic": gate_economy_agentic,
    "economy-verification": gate_economy_verification,
    "economy-qpt": gate_economy_qpt,
    "economy-evals": gate_economy_evals,
    "economy-surface": gate_economy_surface,
    # polish (prompt_evo_polish §8, §44–45)
    "economy-receipt": gate_economy_receipt,
    "economy-closure": gate_economy_closure,
    # FE-003 portable distribution/workspace
    "portable-contracts": gate_portable_contracts,
    "portable-surface": gate_portable_surface,
    "portable-security": gate_portable_security,
    "portable-offline": gate_portable_offline,
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
    "agents-routing": "every name in routing.yaml/orchestration.yaml/"
        "roster must resolve — run platformforge.routing.validate_routing()",
    "agents-contract": "reproduce: pytest -q tests/test_agent_*.py "
        "tests/test_orchestrator.py tests/test_coordinators.py",
    "agents-mirrors": "run platformforge agents sync — mirrors are "
        "generated, never hand-edited",
    "agents-economy": "reproduce: pytest -q tests/test_agent_economy.py",
    "agents-debate": "reproduce: pytest -q tests/test_agent_debate.py",
    "agents-independence": "reproduce: pytest -q "
        "tests/test_agent_adversarial.py",
    "agents-evals": "reproduce: platformforge evals run — fix the "
        "failing case or the machinery it probes",
    "freeze-contracts": "drift vs docs/freeze/snapshots — re-snapshot "
        "(freeze snapshot) only through a reviewed FeatureException",
    "freeze-docs": "create the missing docs/freeze artifact",
    "freeze-exceptions": "every docs/freeze/exceptions/*.json must "
        "satisfy the §6 FeatureException contract",
    "freeze-replay": "platformforge cases replay — fix the case, the "
        "analyzer, or record a documented FP/FN entry",
    "economy-contracts": "pytest tests/test_economy_contracts.py "
        "tests/test_economy_v2.py",
    "economy-cache": "pytest tests/test_economy_cache.py",
    "economy-context": "pytest tests/test_economy_gateway.py",
    "economy-budget": "pytest tests/test_economy_contracts.py -k budget",
    "economy-resume": "pytest tests/test_economy_gateway.py -k resume",
    "economy-reconcile": "pytest -k reconcil",
    "economy-routing": "pytest tests/test_economy_evals.py -k routing",
    "economy-agentic": "pytest tests/test_economy_agents_waste.py",
    "economy-verification": "pytest tests/test_economy_pricing_verify.py",
    "economy-qpt": "pytest tests/test_qpt_v2.py",
    "economy-evals": "pytest tests/test_economy_evals.py",
    "economy-surface": "run each economy/cache/context/routing verb "
        "manually — exit 0 or 2 expected",
    "economy-receipt": ("regenerate via python scripts/validate.py "
                        "--economy-receipt "
                        "docs/economy-parity/VALIDATION-RECEIPT.json"),
    "economy-closure": ("fix closure docs/statuses or the failing "
                        "tests/test_economy_closure.py case"),
    "portable-contracts": "pytest -q tests/test_portable_distribution.py tests/test_portable_workspace.py",
    "portable-surface": "platformforge install --help && platformforge portable --help",
    "portable-security": "fix containment/ownership safeguards in platformforge/distribution",
    "portable-offline": "build and verify an offline portable bundle locally",
}


def _head_sha() -> str:
    r = _run(["git", "rev-parse", "HEAD"])
    return r["tail"][-1].strip() if r["tail"] else ""


def _economy_gate_names() -> list[str]:
    """§91 — the canonical economy taxonomy is derived from GATES,
    never hand-listed. Receipt gates == validator gates by construction."""
    return sorted(n for n in GATES if n.startswith("economy-"))


ECONOMY_RECEIPT_SCHEMA = "platformforge/economy-validation-receipt/v1"
ECONOMY_RECEIPT_PATH = "docs/economy-parity/VALIDATION-RECEIPT.json"


def _economy_receipt_doc(gates: dict[str, dict], failed: list[str],
                         remote_ci: str) -> dict:
    return {
        "schema": ECONOMY_RECEIPT_SCHEMA,
        "kind": "platformforge/economy-validation-receipt/1",
        "cycle": "economy-parity",
        "spec": "prompt_evo_economy.md",
        "exception": "FE-002",
        "validated_sha": _head_sha(),
        "closure_sha": None,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "validator": "scripts/validate.py",
        "validator_version": "economy-validation-receipt/v1",
        "gates": gates,
        "quality": {"note": "QPT/QPC floors enforced inside "
                            "economy-qpt / economy-evals gates; quality "
                            "floors gate every economy claim"},
        "benchmarks": {"control_plane_overhead":
                       "docs/economy-parity/ECONOMY-BENCHMARKS.md",
                       "end_to_end": "insufficient evidence — no "
                                     "production corpus claimed"},
        "known_gaps": [
            ("real provider pricing catalog not bundled (declared-rates "
             "engine only, by design)"),
            ("money axis lacks a real model-call corpus — QPC money is "
             "unresolved without declared pricing + measured usage"),
            ("production savings unproven; microbench overhead only"),
            ("analysis cache reuse requires identical evidence/policy/"
             "risk tuple — conservative by construction"),
        ],
        "remote_ci": remote_ci,
        "verdict": "validated" if not failed else "failed",
        "failed": failed,
    }


def economy_receipt(out_path: str, *, remote_ci: str) -> int:
    """§12, §62–65 — generate the economy closure receipt.

    Schema `platformforge/economy-validation-receipt/v1`:
    - `validated_sha` binds the FUNCTIONAL commit the gates ran against.
    - `closure_sha` stays null in the committed file: the receipt-only
      closure commit cannot contain its own hash (§65 — no paradox).
      The `economy-receipt` gate accepts validated_sha == HEAD or
      HEAD~1 (receipt-only commit on top).
    - `gates` keys are exactly the canonical `economy-*` names — no
      aliases, no parallel taxonomy (§10–11). `reproduce` is the actual
      command the gate ran, not a handwritten string (§15).
    - `remote_ci` is caller-supplied observation, never claimed here.

    Two passes: a skeleton receipt (gate names present, results pending)
    is written first so the self-referential gates (economy-receipt,
    economy-closure) validate the real artifact, then the file is
    overwritten with final results.
    """
    names = _economy_gate_names()
    gates: dict[str, dict] = {}
    failed = []
    # pass 1 — skeleton so self-referential gates read this artifact
    Path(out_path).write_text(json.dumps(_economy_receipt_doc(
        {n: {"ok": None, "reproduce": "pending", "seconds": None}
         for n in names}, [], remote_ci), indent=2, sort_keys=True)
        + "\n")
    for name in names:
        res = GATES[name]()
        ok = res.get("rc", 1) == 0
        entry = {"ok": ok, "reproduce": res.get("cmd", "n/a"),
                 "seconds": res.get("seconds")}
        if not ok:
            entry["why"] = res.get("tail", [])[-3:]
            entry["unlock"] = UNLOCK.get(name, "see the gate output")
            failed.append(name)
        gates[name] = entry
        print(f"{'PASS' if ok else 'FAIL'} {name}", file=sys.stderr)
    # pass 2 — write-then-verify fixpoint for the self-referential
    # gates: economy-receipt and economy-closure must evaluate a file
    # that already carries final results — their pass-1 verdict read the
    # skeleton and is a stale artifact, not a real failure. Mark them
    # tentatively ok with their real reproduce commands, rewrite, then
    # re-run just those two against the final file. A still-failing
    # result is a real failure and is recorded honestly.
    self_ref = ("economy-receipt", "economy-closure")
    for name in self_ref:
        prev = gates.get(name, {})
        gates[name] = {"ok": True,
                       "reproduce": prev.get("reproduce") or "n/a",
                       "seconds": prev.get("seconds")}
    failed = [n for n in failed if n not in self_ref]
    Path(out_path).write_text(json.dumps(
        _economy_receipt_doc(gates, failed, remote_ci),
        indent=2, sort_keys=True) + "\n")
    for name in self_ref:
        res = GATES[name]()
        ok = res.get("rc", 1) == 0
        entry = {"ok": ok, "reproduce": res.get("cmd", "n/a"),
                 "seconds": res.get("seconds")}
        if not ok:
            entry["why"] = res.get("tail", [])[-3:]
            entry["unlock"] = UNLOCK.get(name, "see the gate output")
            failed.append(name)
        gates[name] = entry
        print(f"{'PASS' if ok else 'FAIL'} {name} (fixpoint)",
              file=sys.stderr)
    # pass 3 — final results overwrite the tentative file
    Path(out_path).write_text(json.dumps(
        _economy_receipt_doc(gates, failed, remote_ci),
        indent=2, sort_keys=True) + "\n")
    return 0 if not failed else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", choices=sorted(GATES))
    ap.add_argument("--receipt", help="write machine-readable receipt JSON")
    ap.add_argument("--economy-receipt", metavar="PATH",
                    help="run canonical economy-* gates and write the "
                         "v1 closure receipt (validated_sha = HEAD)")
    ap.add_argument("--remote-ci", default="not independently verified",
                    help="observed remote CI status string recorded "
                         "verbatim in the economy receipt")
    args = ap.parse_args()

    if args.economy_receipt:
        return economy_receipt(args.economy_receipt,
                               remote_ci=args.remote_ci)

    names = [args.gate] if args.gate else list(GATES)
    receipt = {"kind": "platformforge/validation-receipt/1",
               "sha": [_head_sha()] if not args.gate else None,
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
