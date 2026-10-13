"""Cycle 4.1 — per-action rollback builders (§33–35).

One registry, one builder per mutating action — no giant if-chain.
A builder receives (params, material, ctx) and returns a typed rollback
action dict {action, params, rationale} or None when the captured
material is insufficient (which degrades the plan honestly — never
invents parameters). Every produced action is re-checked with
`validate_action` before the plan may be marked `executable` (§35).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Builder = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]],
                   dict[str, Any] | None]


def _k8s_common(params: dict[str, Any]) -> dict[str, Any]:
    return {k: params[k] for k in
            ("kind", "name", "namespace", "context") if k in params}


def build_k8s_scale(params, material, ctx):
    """§9 — scale back to the *captured* replica count, never the
    forward param."""
    pre = material.get("pre_state", {})
    if "replicas" not in pre:
        return None
    p = {**_k8s_common(params), "replicas": pre["replicas"]}
    if pre.get("resource_version"):
        p["resource_version"] = pre["resource_version"]
    return {"action": "kubernetes.scale", "params": p,
            "rationale": "direct-inverse from captured replicas="
                         f"{pre['replicas']}"}


def build_k8s_annotate(params, material, ctx):
    """§10 — restore the captured annotation map; keys the forward
    step *added* (absent in pre-state) go to remove_annotations."""
    pre = material.get("pre_state", {})
    if "annotations" not in pre:
        return None
    prev = dict(pre["annotations"])
    forward = set(params.get("annotations") or {})
    added = sorted(k for k in forward if k not in prev)
    p = {**_k8s_common(params),
         "annotations": {k: v for k, v in prev.items() if k in forward}}
    if added:
        p["remove_annotations"] = added
    if pre.get("resource_version"):
        p["resource_version"] = pre["resource_version"]
    return {"action": "kubernetes.annotate", "params": p,
            "rationale": f"restore {len(p['annotations'])} keys, "
                         f"remove {added or 'none'}"}


def build_k8s_rollout_restart(params, material, ctx):
    pre = material.get("pre_state", {})
    if "revision" not in pre:
        return None
    return {"action": "kubernetes.rollout_undo",
            "params": {**_k8s_common(params),
                       "to_revision": pre["revision"]},
            "rationale": f"previous-revision → {pre['revision']}"}


def build_git_apply_patch(params, material, ctx):
    """§11 — revert the commit the forward step *produced*."""
    res = material.get("execution_result", {})
    sha = res.get("resulting_commit") or res.get("commit_sha")
    if not sha:
        return None
    return {"action": "git.revert_commit",
            "params": {"repo": params.get("repo", ""), "commit_sha": sha},
            "rationale": f"revert resulting_commit {sha[:12]}"}


build_git_commit = build_git_apply_patch


def build_git_open_pr(params, material, ctx):
    res = material.get("execution_result", {})
    pr = res.get("pr") or res.get("pr_number")
    if not pr:
        return None
    return {"action": "git.close_pr",
            "params": {"repo": params.get("repo", ""), "pr": pr},
            "rationale": f"close pr {pr}"}


def build_git_create_branch(params, material, ctx):
    if not params.get("branch"):
        return None
    return {"action": "git.delete_branch",
            "params": {"repo": params.get("repo", ""),
                       "branch": params["branch"]},
            "rationale": "direct-inverse delete created branch"}


def build_git_delete_branch(params, material, ctx):
    """Previous-revision: recreate the branch at its captured sha."""
    pre = material.get("pre_state", {})
    if not pre.get("branch_sha"):
        return None
    return {"action": "git.create_branch",
            "params": {"repo": params.get("repo", ""),
                       "branch": params.get("branch", ""),
                       "base": pre["branch_sha"]},
            "rationale": f"recreate branch at {pre['branch_sha'][:12]}"}


def build_argocd_sync(params, material, ctx):
    """§13–14 — prefer argo history rollback; when source-of-truth is
    Git and a revert commit is supplied, git-revert is the preferred
    path (declared, not silently chosen)."""
    pre = material.get("pre_state", {})
    sot = (material.get("source_of_truth") or {}).get("resolved", "")
    if sot in ("git", "gitops") and pre.get("git_revert_commit"):
        return {"action": "git.revert_commit",
                "params": {"repo": pre.get("repo", params.get("repo", "")),
                           "commit_sha": pre["git_revert_commit"]},
                "rationale": "source-revert via git (SoT=git)"}
    hid = pre.get("history_id")
    if hid is None:
        return None
    return {"action": "argocd.rollback",
            "params": {"app": params.get("app", ""), "history_id": hid},
            "rationale": f"previous-revision history_id={hid}"}


def build_terraform_apply(params, material, ctx):
    """§15–19 — NEVER reuse the forward saved plan. Returns a
    replan descriptor, not an action: the rollback is a *new governed
    operation* (source-revert → plan BA → approval → apply BA)."""
    pre = material.get("pre_state", {})
    out = {"replan": {
        "source_ref": pre.get("source_ref", ""),
        "workspace": pre.get("workspace", ""),
        "state_serial": pre.get("state_serial"),
        "forward_plan_hash": (params.get("plan_hash") or
                              pre.get("plan_hash", "")),
        "resource_addresses": list(pre.get("resource_addresses", [])),
    }}
    return out  # deliberate: no executable action


# Registry — action → builder. Mutating actions missing here degrade to
# unknown (the honest answer), never to a guessed inverse.
BUILDERS: dict[str, Builder] = {
    "kubernetes.scale": build_k8s_scale,
    "kubernetes.annotate": build_k8s_annotate,
    "kubernetes.rollout_restart": build_k8s_rollout_restart,
    "git.apply_patch": build_git_apply_patch,
    "git.commit": build_git_commit,
    "git.open_pr": build_git_open_pr,
    "git.create_branch": build_git_create_branch,
    "git.delete_branch": build_git_delete_branch,
    "argocd.sync": build_argocd_sync,
    "terraform.apply_saved_plan": build_terraform_apply,
    "tofu.apply_saved_plan": build_terraform_apply,
}
