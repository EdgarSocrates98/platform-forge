"""Drift: desired (HCL) vs observed (state/plan values) attribute diff.

Reports per-attribute divergence — never a single "drifted" verdict — and
marks facts unresolved when a desired value can't be compared (computed,
interpolated).
"""

from __future__ import annotations

from typing import Any


def _is_unknown_desired(v: Any) -> bool:
    return isinstance(v, str) and ("${" in v or v.startswith("unknown"))


def drift(desired_facts: list[dict[str, Any]],
          observed_facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare iac.resource bodies against iac.state_resource values."""
    observed = {f["attrs"]["address"]: f for f in observed_facts
                if f.get("kind") == "iac.state_resource"}
    out: list[dict[str, Any]] = []
    for f in desired_facts:
        if f.get("kind") != "iac.resource":
            continue
        addr = f["attrs"]["address"]
        obs = observed.get(addr)
        if not obs:
            out.append({"address": addr, "status": "missing_in_state"})
            continue
        want = f["attrs"].get("body", {}) or {}
        got = obs["attrs"].get("values", {}) or {}
        diffs, unresolved = [], []
        for k, wv in want.items():
            if k == "depends_on" or _is_unknown_desired(wv):
                unresolved.append(k)
                continue
            gv = got.get(k)
            if gv is None:
                unresolved.append(k)
            elif wv != gv:
                diffs.append({"attr": k, "desired": wv, "observed": gv})
        out.append({"address": addr,
                    "status": "drifted" if diffs else
                              ("unresolved" if unresolved else "converged"),
                    "diffs": diffs, "unresolved_attrs": sorted(unresolved)})
    return {"resources": out,
            "counts": {"compared": len(out), "drifted": sum(
                1 for o in out if o["status"] == "drifted"),
                "missing_in_state": sum(
                    1 for o in out if o["status"] == "missing_in_state"),
                "unresolved": sum(1 for o in out
                                  if o["status"] == "unresolved")}}
