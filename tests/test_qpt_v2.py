"""Cycle 2.1 §34–50 — QPT methodology: envelopes, receipts, gates."""

import json
import tempfile
from pathlib import Path

from platformforge.economy.envelope import ContextEnvelope
from platformforge.economy.qpt import quality_per_token
from platformforge.tokensave.budget import Budget
from platformforge.tokensave.index import SearchIndex


def _idx(root: Path) -> SearchIndex:
    idx = SearchIndex(root / "i.db")
    idx.index_workspace(root / "ws")
    return idx


def _workspace(root: Path) -> None:
    ws = root / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "deploy.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: web}\n"
        "spec: {replicas: 1}\n")
    (ws / "notes.md").write_text("# ops notes\nrunbook for web deploy\n" * 30)


def _facts() -> list[dict]:
    return [{"fact_id": "PF-K8S-9001aa", "kind": "k8s.workload", "tier": 3,
             "source": "deploy.yaml", "location": "deploy.yaml",
             "attrs": {"pod_spec": {"latest_tag": True}}}]


def test_envelope_serialize_is_canonical():
    a = ContextEnvelope(facts=[{"b": 1}], metadata={"x": 2})
    b = ContextEnvelope(facts=[{"b": 1}], metadata={"x": 2})
    assert a.serialize() == b.serialize()
    assert a.estimated_tokens > 0 and a.byte_size == len(a.serialize())
    det = ContextEnvelope(kind="deterministic", facts=[{"k": 1}])
    lf = det.ledger_fields()
    assert lf["deterministic_fact_count"] == 1 \
        and "model_context_bytes" not in lf
    mod = ContextEnvelope(kind="model", facts=[{"k": 1}])
    assert "model_context_bytes" in mod.ledger_fields()


def test_qpt_measured_equals_evaluated():
    """The token count reported IS the bytes the judge consumed."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _workspace(root)
        seen: list[dict] = []

        def spy(env: ContextEnvelope):
            seen.append(env.to_dict())
            return [{"rule_id": "R1", "status": "violated",
                     "fact": f["fact_id"]} for f in env.facts]

        rep = quality_per_token(facts_full=_facts(), findings_full=[],
                                index=_idx(root), task="deploy review",
                                budget=Budget(input_budget=50_000),
                                judge=spy)
        assert len(seen) == 2                      # full + packed judged
        # baseline bytes == serialized envelope the judge saw
        assert rep["baseline"]["model_context_bytes"] == \
            len(json.dumps(seen[0], sort_keys=True,
                           separators=(",", ":"), default=str).encode())
        assert rep["deterministic"]["deterministic_fact_count"] == 1
        assert "model_context_bytes" not in rep["deterministic"]
        for key in ("baseline", "optimized", "quality", "economy",
                    "verdict"):
            assert key in rep
        assert rep["verdict"] in ("beneficial", "no_reduction",
                                  "optimization_not_beneficial")


def test_qpt_optimization_not_beneficial_when_files_dropped():
    """A judge that needs file bodies loses them when the pack excludes the
    file → quality floor fails → verdict must not claim savings."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _workspace(root)
        # task with terms that match NOTHING in the workspace → pack drops
        # every file → a files-based judge loses all evidence
        def file_judge(env: ContextEnvelope):
            out = []
            for f in env.files:
                if "Deployment" in f["content"]:
                    out.append({"rule_id": "R1", "status": "violated",
                                "fact": f["path"]})
            return out
        rep = quality_per_token(facts_full=[], findings_full=[],
                                index=_idx(root), task="zzz qqq unrelated",
                                budget=Budget(input_budget=50_000),
                                judge=file_judge)
        assert rep["quality"]["finding_recall"] == 0.0
        assert rep["verdict"] == "optimization_not_beneficial"
        assert rep["quality_gate"] == "fail"


def test_qpt_unresolved_must_not_go_silent():
    """Rules unresolved at baseline must stay unresolved|violated packed."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _workspace(root)

        def judge(env: ContextEnvelope):
            if len(env.facts) > 1:
                return [{"rule_id": "R1", "status": "unresolved",
                         "fact": "f1"}]
            return []
        rep = quality_per_token(facts_full=_facts() + _facts(),
                                findings_full=[], index=_idx(root),
                                task="deploy", judge=judge,
                                budget=Budget(input_budget=50_000))
        # pack carries all facts → both sides unresolved → recall 1.0
        assert rep["quality"]["unresolved_recall"] == 1.0


def test_qpt_bench_corpus_runs():
    """§43–46 — the fixed corpus runs and emits receipts per task."""
    from platformforge.economy.bench import run_qpt_bench
    rep = run_qpt_bench()
    assert rep["aggregate"]["tasks"] == 6
    for case in rep["cases"]:
        r = case["receipt"]
        for key in ("baseline", "optimized", "quality", "economy",
                    "verdict"):
            assert key in r, f"{case['id']} missing {key}"
        assert r["verdict"] in ("beneficial", "no_reduction",
                                "optimization_not_beneficial")
