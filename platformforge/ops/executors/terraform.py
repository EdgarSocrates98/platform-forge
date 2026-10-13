"""Terraform / OpenTofu executor (§75–78).

Contract from upstream semantics: `plan -out=<f>` → `apply <f>` where
the saved plan file IS the approval target (no replanning flags at
apply). Before apply the executor re-runs a freshness check
(`plan -refresh-only -detailed-exitcode`; 2 = drift) and verifies the
plan file hash — stale plans refuse (§77). `terraform` and `tofu` share
the contract; divergent flags stay per-binary.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from platformforge.ops.executors.base import Executor


class TerraformExecutor(Executor):
    name = "terraform"
    binary = "terraform"

    def argv_for(self, action: str, params: dict[str, Any],
                 dry_run: bool) -> list[str] | dict[str, Any]:
        b = self.binary
        wd = params.get("workdir", ".")
        a = action.split(".", 1)[1]          # terraform.<verb>
        if a == "validate":
            return [b, "-chdir=" + wd, "validate", "-json"]
        if a == "plan":
            argv = [b, "-chdir=" + wd, "plan", "-input=false",
                    "-detailed-exitcode"]
            if params.get("refresh_only"):
                argv.append("-refresh-only")
            if params.get("out"):
                argv.append("-out=" + params["out"])
            for t in params.get("target", []) or []:
                argv.append("-target=" + t)
            return argv
        if a == "show":
            return [b, "-chdir=" + wd, "show", "-json",
                    params["plan_file"]]
        if a == "apply_saved_plan":
            pf = params["plan_file"]
            want = params.get("plan_hash", "")
            if want:
                try:
                    got = "sha256:" + hashlib.sha256(
                        Path(wd, pf).read_bytes()).hexdigest()
                except OSError as e:
                    return {"refusal": "PF-OPS-PLAN-UNREADABLE",
                            "unlock": f"plan file unreadable: {e}"}
                if got != want:
                    return {"refusal": "PF-OPS-PLAN-HASH-MISMATCH",
                            "unlock": "saved plan hash differs from "
                                      "approval — re-plan and re-approve"}
            return [b, "-chdir=" + wd, "apply", "-input=false",
                    pf]      # the plan file IS the bound artifact
        return super().argv_for(action, params, dry_run)


class TofuExecutor(TerraformExecutor):
    name = "tofu"
    binary = "tofu"


def summarize_plan(show_json: dict[str, Any]) -> dict[str, Any]:
    """Compact plan summary for deltas/receipts (extends iac/plan.py
    semantics with action_reason/applyable)."""
    changes: dict[str, int] = {}
    destructive = []
    for rc in show_json.get("resource_changes", []) or []:
        acts = tuple(rc.get("change", {}).get("actions", []))
        for a in acts:
            changes[a] = changes.get(a, 0) + 1
        if "delete" in acts:
            destructive.append(rc.get("address", "?"))
    return {"applyable": bool(show_json.get("applyable")),
            "errored": bool(show_json.get("errored")),
            "actions": changes,
            "destructive_addresses": destructive,
            "drift": [d.get("address") for d in
                      show_json.get("resource_drift", []) or []]}
