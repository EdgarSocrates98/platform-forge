"""Eval framework (§94–95) — typed cases over fixtures, graded offline.

Case types (§94): unit, integration, golden, contract, property,
metamorphic, regression, recall, precision, token_economy,
graph_correctness, routing, security.

§95 variants per finding: positive | negative | boundary | unresolved |
version — declared in `variant` and checked against the expectation kind
(positive must fire, negative must not, boundary states the edge,
unresolved expects the finding absent AND the fact unresolved, version
pairs a rule constraint with a fixture version).
"""

from platformforge.evals.runner import EVAL_TYPES, VARIANTS, run_all, run_case

__all__ = ["EVAL_TYPES", "VARIANTS", "run_all", "run_case"]
