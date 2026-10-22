"""`platformforge evals` §7.2 surface + the §7.1 classification persisted
in the forge/context/v1 manifest (lf-0038, install-2.0 ciclo 5).

Proves, in order:

1. the four §7.1 categories exist and every declared suite carries one;
2. the manifest persists the classification (`eval_suites[].kind` +
   `capabilities.evals.detail`) in the closed (id, kind, command) shape;
3. §7.3 — sealed expected answers never leave: describe/list/manifest
   carry metadata + sha256 only, never `expect:`/`expected_known_truth`
   payloads; every suite marks the environment its proof stands for
   (deterministic/simulated != real);
4. deterministic runners execute and unresolved stays unresolved.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from platformforge import discovery_ops
from platformforge.evals import surface, taxonomy
from platformforge.install.service import _context_manifest

ROOT = Path(__file__).resolve().parents[1]
CLI = "platformforge"

_ITEM_ID_RE = re.compile(r"^[a-z0-9-_]{1,128}$")


# ---------------------------------------------------------------------------
# §7.1 — the classification exists and is complete
# ---------------------------------------------------------------------------


def test_all_suites_carry_a_declared_kind():
    kinds = set(taxonomy.KINDS)
    for suite in taxonomy.catalog():
        assert suite["kind"] in kinds, suite["id"]
        assert suite["environment"] in ("deterministic", "simulated", "host")
        assert _ITEM_ID_RE.match(suite["id"]), f"id fora do ITEM_ID_RE: {suite['id']}"


def test_the_four_categories_are_all_populated():
    counts = taxonomy.kind_counts()
    assert set(counts) == {
        "developer",
        "runtime-decision",
        "output-verification",
        "host-conformance",
    }
    assert all(v > 0 for v in counts.values()), counts


def test_listing_is_the_classified_inventory():
    payload = taxonomy.listing()
    assert payload["counts"] == taxonomy.kind_counts()
    assert {s["id"] for s in payload["suites"]} == set(taxonomy.suite_ids())
    for suite in payload["suites"]:
        assert "answer" not in suite
        assert "expected" not in suite


# ---------------------------------------------------------------------------
# manifesto forge/context/v1 — classificacao persistida, schema fechado
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def manifest():
    return _context_manifest(
        scope="project", profile="recommended", hosts=["claude"], components=None
    )


def test_manifest_eval_suites_are_classified(manifest):
    from platformforge import _forgecontext as fctx

    assert fctx.validate_manifest(manifest) == []
    suites = manifest["eval_suites"]
    assert {s["id"] for s in suites} == set(taxonomy.suite_ids())
    kinds = {s["kind"] for s in suites}
    assert kinds == set(taxonomy.KINDS), kinds
    for s in suites:
        assert s["kind"] in fctx.EVAL_KINDS
        assert set(s) == {"id", "kind", "command"}
        assert s["command"][:3] == [CLI, "evals", "describe"]


def test_manifest_evals_capability_detail(manifest):
    detail = manifest["capabilities"]["evals"]["detail"]
    for kind in taxonomy.KINDS:
        assert kind in detail


def test_manifest_declares_the_7_2_ops_as_commands(manifest):
    ids = {c["id"] for c in manifest["discovery"]["commands"]}
    for esperado in (
        "evals-list",
        "evals-describe",
        "evals-run",
        "evals-result",
        "verification-plan",
        "verification-run",
    ):
        assert esperado in ids
    assert not any(
        op.startswith(("evals.", "verification.")) for op in manifest["discovery"]["ops"]
    )


def test_eval_commands_source_is_discovery_ops():
    comandos = discovery_ops.eval_commands()
    assert [c["id"] for c in comandos] == [
        "evals-list",
        "evals-describe",
        "evals-run",
        "evals-result",
        "verification-plan",
        "verification-run",
    ]
    for c in comandos:
        assert c["argv"][0] == CLI
        assert _ITEM_ID_RE.match(c["id"])
    assert set(discovery_ops.eval_ops_expanded()) == {
        "evals.list",
        "evals.describe",
        "evals.run",
        "evals.result",
        "verification.plan",
        "verification.run",
    }


def test_capabilities_verb_reports_the_classification():
    from platformforge import discovery

    caps = discovery.capabilities()
    assert caps["eval_suites"] == taxonomy.suite_ids()
    assert caps["evals"]["counts"] == taxonomy.kind_counts()
    assert set(caps["evals"]["ops"]) == set(discovery_ops.eval_ops_expanded())


# ---------------------------------------------------------------------------
# §7.3 — gabarito selado, deterministico != real
# ---------------------------------------------------------------------------


def _fatias_de_resposta() -> list[str]:
    """40-char mid slices of known answer files — if any shows up in a
    surface payload, a sealed answer leaked."""
    alvos = [
        *sorted((ROOT / ".platformforge" / "cases" / "holdout").glob("*/case.yaml")),
        *sorted((ROOT / "evals" / "cases").glob("*/case.yaml"))[:6],
    ]
    fatias: list[str] = []
    for arquivo in alvos:
        texto = arquivo.read_text(encoding="utf-8")
        meio = len(texto) // 2
        fatias.append(texto[meio : meio + 40])
    assert len(fatias) >= 6
    return fatias


def test_describe_never_echoes_sealed_answers():
    for suite_id in taxonomy.suite_ids():
        payload = json.dumps(taxonomy.describe(suite_id), ensure_ascii=False)
        for fatia in _fatias_de_resposta():
            assert fatia not in payload, f"describe({suite_id}) vazou gabarito"


def test_listing_and_manifest_do_not_leak_answers(manifest):
    for payload in (
        json.dumps(taxonomy.listing(), ensure_ascii=False),
        json.dumps(manifest["eval_suites"], ensure_ascii=False),
        json.dumps(manifest["capabilities"]["evals"], ensure_ascii=False),
    ):
        for fatia in _fatias_de_resposta():
            assert fatia not in payload


def test_sealed_suites_mark_the_answers_as_not_emitted():
    seladas = [s for s in taxonomy.catalog() if s["sealed"]]
    assert seladas, "nenhuma suite selada — a postura §7.3 estaria vazia"
    for s in seladas:
        desc = taxonomy.describe(s["id"])
        assert desc["expected_answers"].startswith("sealed")
        assert desc["integrity"]["suite_sha256"] != "unresolved"


def test_unknown_suite_is_a_named_refusal():
    with pytest.raises(taxonomy.TaxonomyError, match=taxonomy.E_SUITE):
        taxonomy.describe("suite-inexistente")


def test_every_suite_marks_the_environment_it_proves():
    for s in taxonomy.catalog():
        desc = taxonomy.describe(s["id"])
        if s["environment"] == "host":
            assert "real environment" in desc["proof"]
        else:
            assert "not real-environment proof" in desc["proof"]


# ---------------------------------------------------------------------------
# runners deterministicos — evidencia real, unresolved nunca vira pass
# ---------------------------------------------------------------------------


def test_evals_run_agent_runtime_marks_deterministic():
    payload = surface.run("agent-runtime")
    assert payload["status"] == "pass"
    assert payload["environment"] == "deterministic"
    assert payload["real_environment_proof"] is False
    assert payload["counts"]["pass"] >= 10
    # o resultado nunca ecoa o expect: dos cases
    for fatia in _fatias_de_resposta()[:6]:
        assert fatia not in json.dumps(payload, ensure_ascii=False)


def test_evals_run_holdout_replay():
    payload = surface.run("holdout")
    assert payload["status"] == "pass"
    assert payload["corpus_hash"]
    assert payload["environment"] == "deterministic"


def test_evals_result_returns_corpus_scorecard():
    payload = surface.result("holdout")
    assert payload["status"] == "ok"
    assert payload["scorecard"]["corpus_hash"]


def test_evals_result_rejects_non_corpus_suites():
    with pytest.raises(taxonomy.TaxonomyError, match=taxonomy.E_UNAVAILABLE):
        surface.result("golden-verdicts", "qualquer")


# ---------------------------------------------------------------------------
# CLI de verdade — os verbos existem e respondem
# ---------------------------------------------------------------------------


def _cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "platformforge.cli.main", *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_cli_evals_list_classified():
    proc = _cli("evals", "list", "--classified")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["counts"] == taxonomy.kind_counts()


def test_cli_evals_describe_holdout_is_metadata_only():
    proc = _cli("evals", "describe", "--suite", "holdout")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["sealed"] is True
    for fatia in _fatias_de_resposta()[:3]:
        assert fatia not in proc.stdout


def test_cli_evals_run_suite():
    proc = _cli("evals", "run", "--suite", "golden-verdicts")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["environment"] == "deterministic"
    assert payload["status"] == "pass"


def test_cli_verification_ops_exist():
    """§7.4: verification.plan/run sao `change propose`/`change verify` —
    o fluxo plan->run->evidence e invocavel, com falhas explicitas."""
    plan = _cli("change", "propose", "--help")
    assert plan.returncode == 0
    verify = _cli("change", "verify", "--help")
    assert verify.returncode == 0
