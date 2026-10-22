"""The ``platformforge evals`` surface — §7.2 ops ``evals.list``,
``evals.describe``, ``evals.run``, ``evals.result`` over the classified
taxonomy of ``platformforge.evals.taxonomy``.

Security contract (§7.3), enforced here and tested in
``tests/test_evals_surface.py``:

* sealed expected answers are NEVER emitted — ``list``/``describe`` carry
  counts, locations and an integrity hash only; run reports carry
  verdicts, never the ``expect:`` payload;
* every run result marks ``environment`` — ``deterministic``/``simulated``
  are never reported as real-environment proof;
* ``unresolved`` verdicts stay visible — never promoted to pass.
"""

from __future__ import annotations

from typing import Any

from platformforge.evals import taxonomy
from platformforge.resources import data_path

_REPO = data_path()


def _envelope(suite: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Every result carries the §7.3 markers: what environment proved it and
    whether the answers stay sealed."""
    return {
        "schema": "platformforge/evals-run/v1",
        "suite": suite["id"],
        "kind": suite["kind"],
        "environment": suite["environment"],
        "real_environment_proof": suite["environment"] == "host",
        "sealed": suite["sealed"],
        **extra,
    }


def run(suite_id: str) -> dict[str, Any]:
    """evals.run — dispatch to the suite's declared runner."""
    s = taxonomy.get(suite_id)
    spec = s["run"]
    if spec is None:
        if s["environment"] == "host":
            raise taxonomy.TaxonomyError(
                f"{taxonomy.E_HOST}: suite {suite_id!r} mede um agente de "
                "host; a CLI nao a executa (executor != avaliador). "
                f"Execute no host e pontue com `{s['runner_label']}`"
            )
        raise taxonomy.TaxonomyError(
            f"{taxonomy.E_UNAVAILABLE}: suite {suite_id!r} e corpus/"
            f"baseline — sem runner proprio; verificada via {s['runner_label']}"
        )
    kind = spec["kind"]
    if kind == "native":
        return _envelope(s, **_run_native(spec["name"], s))
    raise taxonomy.TaxonomyError(
        f"{taxonomy.E_UNAVAILABLE}: runner kind {kind!r} desconhecido para {suite_id!r}"
    )


def _run_native(name: str, suite: dict[str, Any]) -> dict[str, Any]:
    if name == "case-types":
        return _run_case_types(suite)
    if name == "evals-cases-dir":
        return _run_cases_dir(suite)
    if name == "corpus-replay":
        return _run_corpus_replay(suite)
    if name == "lab-run-all":
        return _run_lab(suite)
    raise taxonomy.TaxonomyError(
        f"{taxonomy.E_UNAVAILABLE}: runner nativo {name!r} desconhecido"
    )


def _strip_expect(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run reports carry the verdict, never the expected-answer payload —
    drop any `expect*`/`expected*` key a grader might have echoed."""
    out = []
    for r in results:
        out.append(
            {k: v for k, v in r.items()
             if not k.startswith(("expect", "expected"))}
        )
    return out


def _run_case_types(suite: dict[str, Any]) -> dict[str, Any]:
    """evals/cases filtered to the suite's declared types — the same
    computation as `evals run --type <t>`, one call per declared type."""
    from platformforge.evals.runner import run_all

    merged: list[dict[str, Any]] = []
    for t in suite["types"]:
        merged += run_all(type_filter=t)["results"]
    counts = {"pass": 0, "fail": 0, "unresolved": 0}
    for r in merged:
        counts[r["verdict"] if r["verdict"] in counts else "unresolved"] += 1
    return {
        "status": "pass" if not counts["fail"] else "fail",
        "unresolved": counts["unresolved"],
        "counts": counts,
        "types": list(suite["types"]),
        "cases": _strip_expect(merged),
        "expected_answers": "sealed — compared in-process, never echoed",
    }


def _run_cases_dir(suite: dict[str, Any]) -> dict[str, Any]:
    from platformforge.evals.runner import run_all

    base = _REPO / suite["location"]
    if not base.is_dir():
        raise taxonomy.TaxonomyError(
            f"{taxonomy.E_UNAVAILABLE}: {suite['location']} ausente no checkout"
        )
    out = run_all(base)
    return {
        "status": "pass" if not out["counts"]["fail"] else "fail",
        "unresolved": out["counts"]["unresolved"],
        "counts": out["counts"],
        "cases": _strip_expect(out["results"]),
        "expected_answers": "sealed — compared in-process, never echoed",
    }


def _run_corpus_replay(suite: dict[str, Any]) -> dict[str, Any]:
    """`cases replay --tier <t>` in-process — deterministic double-run
    comparison vs expected_known_truth; reports match/mismatch + FP/FN
    ids, never the expected payload."""
    from platformforge.cases.replay import replay_all

    base = _REPO / suite["location"]
    if not base.is_dir():
        raise taxonomy.TaxonomyError(
            f"{taxonomy.E_UNAVAILABLE}: {suite['location']} ausente "
            "(o corpus vive no checkout, nao no wheel)"
        )
    tier = base.name  # holdout | golden
    out = replay_all(root=base.parent, tier=tier)
    cases = [
        {k: v for k, v in r.items() if k != "expected_known_truth"}
        for r in out["cases"]
    ]
    return {
        "status": out["verdict"],
        "by_tier": out["by_tier"],
        "corpus_hash": out["corpus_hash"],
        "failed": out["failed"],
        "cases": cases,
        "expected_answers": "sealed — compared in-process, never echoed",
    }


def _run_lab(suite: dict[str, Any]) -> dict[str, Any]:
    """`lab run-all` in-process on the static profile — simulated
    environment proof, never a live cluster."""
    from platformforge.lab import runner as lab_runner

    base = _REPO / suite["location"]
    if not base.is_dir():
        raise taxonomy.TaxonomyError(
            f"{taxonomy.E_UNAVAILABLE}: {suite['location']} ausente no checkout"
        )
    out = lab_runner.run_all(profile="static")
    status = out.get("verdict") or out.get("status") or "unresolved"
    return {
        "status": status if status in ("pass", "fail") else "unresolved",
        "lab": out,
    }


def result(suite_id: str, run_name: str | None = None) -> dict[str, Any]:
    """evals.result — the scorecard of a corpus suite.

    Platform case runs are deterministic replays: the "recorded run" is the
    corpus replay itself, anchored by ``corpus_hash`` (sha256 over
    per-case result hashes). Non-corpus suites emit their result at run
    time — a named refusal, never a fabricated scorecard."""
    s = taxonomy.get(suite_id)
    if s["run"] is None or s["run"].get("name") != "corpus-replay":
        raise taxonomy.TaxonomyError(
            f"{taxonomy.E_UNAVAILABLE}: evals.result aplica-se aos corpora "
            "`.platformforge/cases` (holdout, golden-corpus) — as demais "
            "suites emitem o resultado no proprio `evals run`"
        )
    out = _run_corpus_replay(s)
    return _envelope(
        s,
        status="ok",
        scorecard=out,
        note=(
            "replay deterministico — o scorecard e a recomputacao ancorada "
            "em corpus_hash, nao um run_id persistido"
        ),
    )


__all__ = ["result", "run"]
