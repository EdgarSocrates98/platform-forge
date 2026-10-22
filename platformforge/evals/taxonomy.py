"""§7.1 taxonomy of the eval corpus — the classified inventory that the
``forge/context/v1`` manifest persists (``eval_suites[].kind`` +
``capabilities.evals.detail``) and that ``platformforge evals`` serves.

The corpus is one ``evals/cases/`` library of typed cases plus two
independent corpora — ``evals/qpt-bench/`` and the case tiers under
``.platformforge/cases/`` (``golden`` development corpus, ``holdout``
never tuned against) — plus the Forge Lab scenario suite. The taxonomy
groups by category, not by directory: the 94 cases of ``evals/cases/``
split by ``type`` into the §7.1 categories.

* ``sealed`` — §7.3: expected answers (``expect:`` blocks,
  ``expected_known_truth``) never reach the executing agent's surface;
  describe/list emit metadata + integrity hash only.
* ``environment`` — ``deterministic`` (offline recompute/replay — proves
  the engine, never a live environment) or ``simulated`` (Forge Lab
  synthetic scenarios). ``live`` cases replay *recorded* envelopes —
  they are host-conformance evidence about replay, not live host proof.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from platformforge.resources import data_path

_REPO = data_path()

KINDS: tuple[str, ...] = (
    "developer",
    "runtime-decision",
    "output-verification",
    "host-conformance",
)

E_SUITE = "EVALS-SUITE-UNKNOWN"
E_HOST = "EVALS-REQUIRES-HOST"
E_UNAVAILABLE = "EVALS-RUNNER-UNAVAILABLE"

# evals/cases types grouped into the §7.1 categories (the corpus itself is
# split by `type`, so each suite carries the types its run filters to).
_GOLDEN_TYPES = ("golden", "regression")
_AGENT_TYPES = ("agent",)
_LIVE_TYPES = ("live",)
_INTERNAL_TYPES = (
    "unit",
    "integration",
    "contract",
    "property",
    "metamorphic",
    "recall",
    "precision",
    "token_economy",
    "graph_correctness",
    "routing",
    "security",
    "knowledge",
    "version",
)

SUITES: tuple[dict[str, Any], ...] = (
    {
        "id": "golden-verdicts",
        "kind": "output-verification",
        "location": "evals/cases",
        "environment": "deterministic",
        "sealed": True,
        "types": _GOLDEN_TYPES,
        "run": {"kind": "native", "name": "case-types"},
        "runner_label": "platformforge evals run --type golden|regression",
        "description": (
            "golden/regression cases: fixture in, expected rule set out — "
            "the judge's output contract; expected sets sealed in case.yaml"
        ),
    },
    {
        "id": "agent-runtime",
        "kind": "runtime-decision",
        "location": "evals/cases",
        "environment": "deterministic",
        "sealed": True,
        "types": _AGENT_TYPES,
        "run": {"kind": "native", "name": "case-types"},
        "runner_label": "platformforge evals run --type agent",
        "description": (
            "agent cases: routing, fanout, mandatory/unexpected agents — "
            "operational decisions of the runtime, replayed offline"
        ),
    },
    {
        "id": "live-replay",
        "kind": "host-conformance",
        "location": "evals/cases",
        "environment": "deterministic",
        "sealed": True,
        "types": _LIVE_TYPES,
        "run": {"kind": "native", "name": "case-types"},
        "runner_label": "platformforge evals run --type live",
        "description": (
            "live-surface cases over recorded envelopes (collect/reconcile/"
            "drift/incident/remediate) — host-conformance evidence about "
            "replay, never live-host proof"
        ),
    },
    {
        "id": "internal-quality",
        "kind": "developer",
        "location": "evals/cases",
        "environment": "deterministic",
        "sealed": True,
        "types": _INTERNAL_TYPES,
        "run": {"kind": "native", "name": "case-types"},
        "runner_label": "platformforge evals run --type <internal types>",
        "description": (
            "unit/integration/contract/property/metamorphic/recall/"
            "precision/token_economy/graph_correctness/routing/security/"
            "knowledge/version — internal engine quality"
        ),
    },
    {
        "id": "qpt-bench",
        "kind": "output-verification",
        "location": "evals/qpt-bench",
        "environment": "deterministic",
        "sealed": True,
        "run": {"kind": "native", "name": "evals-cases-dir"},
        "runner_label": "platformforge evals run --cases evals/qpt-bench",
        "description": (
            "six bounded-budget benchmark suites (incident, k8s, terraform, "
            "iam, gha-security, change-review) — output quality under a "
            "context budget"
        ),
    },
    {
        "id": "holdout",
        "kind": "output-verification",
        "location": ".platformforge/cases/holdout",
        "environment": "deterministic",
        "sealed": True,
        "run": {"kind": "native", "name": "corpus-replay"},
        "runner_label": "platformforge cases replay --tier holdout",
        "description": (
            "retained tier — never tuned against; expected_known_truth "
            "sealed, replay compares verdicts server-side and reports "
            "match/mismatch only"
        ),
    },
    {
        "id": "golden-corpus",
        "kind": "developer",
        "location": ".platformforge/cases/golden",
        "environment": "deterministic",
        "sealed": True,
        "run": {"kind": "native", "name": "corpus-replay"},
        "runner_label": "platformforge cases replay --tier golden",
        "description": (
            "development corpus of real-world cases — the tuning set the "
            "holdout guards against overfitting"
        ),
    },
    {
        "id": "lab-scenarios",
        "kind": "output-verification",
        "location": "lab/scenarios",
        "environment": "simulated",
        "sealed": False,
        "run": {"kind": "native", "name": "lab-run-all"},
        "runner_label": "platformforge lab run-all (static profile)",
        "description": (
            "Forge Lab scenario suite — green proves the simulated "
            "environment's contracts, never a live cluster"
        ),
    },
)


class TaxonomyError(ValueError):
    """Named refusal: message already carries the ``EVALS-*`` code."""


def catalog() -> list[dict[str, Any]]:
    return [dict(s) for s in SUITES]


def suite_ids() -> list[str]:
    return [s["id"] for s in SUITES]


def get(suite_id: str) -> dict[str, Any]:
    for s in SUITES:
        if s["id"] == suite_id:
            return dict(s)
    raise TaxonomyError(
        f"{E_SUITE}: suite {suite_id!r} desconhecida; declaradas: {', '.join(suite_ids())}"
    )


def kind_counts() -> dict[str, int]:
    counts = {k: 0 for k in KINDS}
    for s in SUITES:
        counts[s["kind"]] += 1
    return counts


def capability_detail() -> str:
    """The one-line ``capabilities.evals.detail`` persisted in the manifest —
    the §7.1 classification summary plus the §7.3 posture."""
    counts = kind_counts()
    parts = ", ".join(f"{k}={counts[k]}" for k in KINDS)
    return (
        f"categories: {parts}; sealed expected answers never reach agent "
        "surfaces (evals describe emits hashes, never answers); "
        "deterministic/simulated proofs are not real-environment proof; "
        "unresolved verdicts are never promoted to pass"
    )


def _repo_path(location: str) -> Path | None:
    p = _REPO / location
    return p if p.exists() else None


def suite_sha256(suite: dict[str, Any]) -> str | None:
    """sha256 over every file under the suite location — the tamper-evident
    baseline/answer hash (§7.3). ``os.walk`` over dirs this repo owns and
    versions. ``None`` when the location is absent — reported as
    ``unresolved``, never silently omitted."""
    base = _repo_path(suite["location"])
    if base is None:
        return None
    h = hashlib.sha256()
    if base.is_file():
        h.update(base.name.encode("utf-8"))
        h.update(b"\0")
        h.update(base.read_bytes())
        return h.hexdigest()
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            p = Path(root) / name
            if not p.is_file():
                continue
            h.update(p.relative_to(base).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
    return h.hexdigest()


def describe(suite_id: str) -> dict[str, Any]:
    """evals.describe — metadata only. §7.3: sealed suites expose the answer
    location CLASS and the integrity hash, never answer content."""
    s = get(suite_id)
    digest = suite_sha256(s)
    return {
        "id": s["id"],
        "kind": s["kind"],
        "location": s["location"],
        "environment": s["environment"],
        "sealed": s["sealed"],
        "expected_answers": (
            "sealed — never emitted to executing agents" if s["sealed"] else "not sealed"
        ),
        "integrity": {
            "algorithm": "sha256",
            "suite_sha256": digest if digest is not None else "unresolved",
        },
        "runner": s["runner_label"],
        "runnable_by_cli": s["run"] is not None,
        "description": s["description"],
        "proof": (
            "host-required (real environment)"
            if s["environment"] == "host"
            else f"{s['environment']} — not real-environment proof"
        ),
    }


def listing() -> dict[str, Any]:
    """evals.list — the classified inventory with per-kind counts."""
    return {
        "schema": "platformforge/evals-list/v1",
        "categories": list(KINDS),
        "counts": kind_counts(),
        "suites": [
            {
                "id": s["id"],
                "kind": s["kind"],
                "environment": s["environment"],
                "sealed": s["sealed"],
                "runnable_by_cli": s["run"] is not None,
            }
            for s in SUITES
        ],
    }


def manifest_suites(cli: str) -> list[dict[str, Any]]:
    """The ``eval_suites`` of forge/context/v1 — the §7.1 classification in
    the closed (id, kind, command) shape. ``command`` is the read-only
    describe verb: a consumer can always inspect what a suite is."""
    return [
        {
            "id": s["id"],
            "kind": s["kind"],
            "command": [cli, "evals", "describe", "--suite", s["id"]],
        }
        for s in SUITES
    ]


__all__ = [
    "E_HOST",
    "E_SUITE",
    "E_UNAVAILABLE",
    "KINDS",
    "SUITES",
    "TaxonomyError",
    "capability_detail",
    "catalog",
    "describe",
    "get",
    "kind_counts",
    "listing",
    "manifest_suites",
    "suite_ids",
    "suite_sha256",
]
