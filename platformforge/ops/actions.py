"""Cycle 4 — typed action vocabulary (§68–69, ADR-0021).

Every mutation is a *typed action* with a declared executor, params
schema, risk base, dry-run and rollback support. There is deliberately
**no `shell.run`** — anything that cannot be expressed as a typed action
refuses (`PF-OPS-UNSTRUCTURED`) instead of degrading to arbitrary shell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionSpec:
    """Contract for one typed action (§70 executor contract fields)."""
    action: str
    executor: str                    # git|terraform|tofu|argocd|kubernetes|observe
    mutating: bool = False
    risk_base: str = "R0"
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()
    dry_run: bool = True             # executor supports dry-run
    idempotent: bool = True
    rollback_action: str = ""        # typed action that reverses it
    required_permissions: tuple[str, ...] = ()
    timeout_s: int = 300
    side_effects: str = ""           # declared blast: pr-created, pods…


_ACTIONS: dict[str, ActionSpec] = {a.action: a for a in [
    # ---- Git (source-of-truth executor) --------------------------------
    ActionSpec("git.create_branch", "git", True, "R0",
               ("repo", "branch", "base"), ("remote",),
               rollback_action="git.delete_branch",
               required_permissions=("git:write",)),
    ActionSpec("git.apply_patch", "git", True, "R1",
               ("repo", "patch"), ("branch", "check_only"),
               rollback_action="git.revert_commit"),
    ActionSpec("git.commit", "git", True, "R1",
               ("repo", "message"), ("signoff",),
               rollback_action="git.revert_commit"),
    ActionSpec("git.push", "git", True, "R1", ("repo", "branch"),
               ("remote",)),
    ActionSpec("git.open_pr", "git", True, "R2",
               ("repo", "title", "head", "base", "body"),
               ("draft", "labels"), rollback_action="git.close_pr",
               required_permissions=("github:pull-request:write",),
               side_effects="pr-created"),
    ActionSpec("git.delete_branch", "git", True, "R1", ("repo", "branch")),
    ActionSpec("git.revert_commit", "git", True, "R1",
               ("repo", "commit_sha")),
    ActionSpec("git.close_pr", "git", True, "R1", ("repo", "pr")),
    # ---- Terraform / OpenTofu -------------------------------------------
    ActionSpec("terraform.validate", "terraform", False, "R0", ("workdir",)),
    ActionSpec("terraform.plan", "terraform", False, "R0",
               ("workdir",), ("out", "target", "refresh_only")),
    ActionSpec("terraform.show", "terraform", False, "R0", ("workdir", "plan_file")),
    ActionSpec("terraform.apply_saved_plan", "terraform", True, "R3",
               ("workdir", "plan_file", "plan_hash"),
               rollback_action="terraform.apply_saved_plan",
               required_permissions=("terraform:apply",),
               timeout_s=1800,
               side_effects="infrastructure-mutation"),
    ActionSpec("tofu.validate", "tofu", False, "R0", ("workdir",)),
    ActionSpec("tofu.plan", "tofu", False, "R0", ("workdir",),
               ("out", "refresh_only")),
    ActionSpec("tofu.apply_saved_plan", "tofu", True, "R3",
               ("workdir", "plan_file", "plan_hash"),
               required_permissions=("tofu:apply",), timeout_s=1800,
               side_effects="infrastructure-mutation"),
    # ---- GitOps -----------------------------------------------------------
    ActionSpec("argocd.sync", "argocd", True, "R3",
               ("app",), ("revision", "resource", "dry_run"),
               rollback_action="argocd.rollback",
               required_permissions=("argocd:sync",),
               side_effects="cluster-reconcile"),
    ActionSpec("argocd.diff", "argocd", False, "R0", ("app",), ("revision",)),
    ActionSpec("argocd.wait", "argocd", False, "R0", ("app",),
               ("health", "timeout_s")),
    ActionSpec("argocd.rollback", "argocd", True, "R3",
               ("app",), ("history_id",),
               required_permissions=("argocd:sync",)),
    # ---- Kubernetes (narrow, §82) ----------------------------------------
    ActionSpec("kubernetes.scale", "kubernetes", True, "R2",
               ("kind", "name", "replicas"),
               ("namespace", "context", "current_replicas",
                "resource_version"),
               rollback_action="kubernetes.scale",
               required_permissions=("k8s:*/scale:update",),
               side_effects="workload-capacity"),
    ActionSpec("kubernetes.rollout_restart", "kubernetes", True, "R2",
               ("kind", "name"), ("namespace", "context"),
               rollback_action="kubernetes.rollout_undo",
               required_permissions=("k8s:workloads:patch",),
               side_effects="pod-recreation"),
    ActionSpec("kubernetes.rollout_undo", "kubernetes", True, "R3",
               ("kind", "name"), ("namespace", "to_revision"),
               required_permissions=("k8s:workloads:patch",)),
    ActionSpec("kubernetes.annotate", "kubernetes", True, "R1",
               ("kind", "name", "annotations"),
               ("namespace", "resource_version"),
               rollback_action="kubernetes.annotate",
               side_effects="metadata-only"),
    ActionSpec("kubernetes.rollout_status", "kubernetes", False, "R0",
               ("kind", "name"), ("namespace", "timeout_s")),
    # ---- Observation (read-only steps) ------------------------------------
    ActionSpec("k8s.observe", "observe", False, "R0",
               ("resource_types",), ("namespace",)),
    ActionSpec("aws.observe", "observe", False, "R0", ("services",),
               ("region",)),
]}

FORBIDDEN_ACTIONS = ("shell.run", "execute_anything", "aws.call",
                     "kubectl.exec", "eval")


def spec_for(action: str) -> ActionSpec | None:
    return _ACTIONS.get(action)


def validate_action(action: str, params: dict[str, Any]
                    ) -> dict[str, Any] | None:
    """Return None when valid, else a refusal dict."""
    if action in FORBIDDEN_ACTIONS:
        return {"refusal": "PF-OPS-UNSTRUCTURED",
                "unlock": "use a typed action from the vocabulary — "
                          "arbitrary shell is refused by design (ADR-0021)"}
    spec = _ACTIONS.get(action)
    if spec is None:
        return {"refusal": "PF-OPS-UNKNOWN-ACTION",
                "unlock": f"action must be one of {sorted(_ACTIONS)}"}
    missing = [p for p in spec.required_params if p not in params]
    if missing:
        return {"refusal": "PF-OPS-ACTION-PARAMS",
                "unlock": f"{action} requires params {missing}"}
    unknown = [p for p in params
               if p not in spec.required_params + spec.optional_params]
    if unknown:
        return {"refusal": "PF-OPS-ACTION-PARAMS",
                "unlock": f"{action} does not accept params {unknown}"}
    return None


def actions_for_executor(executor: str) -> list[str]:
    return sorted(a for a, s in _ACTIONS.items() if s.executor == executor)


def catalog() -> dict[str, Any]:
    return {a: {"executor": s.executor, "mutating": s.mutating,
                "risk_base": s.risk_base, "dry_run": s.dry_run,
                "idempotent": s.idempotent,
                "rollback_action": s.rollback_action,
                "required_permissions": list(s.required_permissions),
                "timeout_s": s.timeout_s,
                "side_effects": s.side_effects}
            for a, s in sorted(_ACTIONS.items())}
