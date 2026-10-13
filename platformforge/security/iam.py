"""IAM policy → identity graph facts. Statements decompose into
can_access / assumes edges; wildcards and admin grants are flags for rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.models.base import stable_id


def _stmts(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = doc.get("Statement") or []
    return [s for s in out if isinstance(s, dict)]


def _policy_kind(doc: dict[str, Any], stmts: list[dict[str, Any]]) -> str:
    """§100 — classify the policy shape: trust / identity / resource /
    SCP / permission boundary / session. Detection is structural, never
    guessed from filename."""
    for s in stmts:
        acts = s.get("Action") or []
        acts = [acts] if isinstance(acts, str) else acts
        if "sts:AssumeRole" in acts or "sts:AssumeRoleWithSAML" in acts \
                or "sts:AssumeRoleWithWebIdentity" in acts:
            return "trust"
    if doc.get("PolicyType") == "SCP" or \
            any("aws:SourceOrgID" in str(s.get("Condition", {}))
                or s.get("Sid", "").startswith("SCP") for s in stmts):
        return "scp"
    if doc.get("PolicyType") == "PermissionsBoundary" or \
            doc.get("PermissionsBoundary"):
        return "permission_boundary"
    if any("Principal" in s for s in stmts):
        return "resource"
    return "identity"


def analyze_iam_policy(path: str | Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text())
    name = doc.get("PolicyName") or doc.get("Id") or Path(path).stem
    stmts = _stmts(doc)
    ptype = _policy_kind(doc, stmts)
    edges, principals, resources = [], [], []
    wildcard_actions = wildcard_resources = public_principals = 0
    admin = False
    federated: list[str] = []   # OIDC/SAML providers seen in trust
    chain_targets: list[str] = []  # roles this policy can assume
    for s in stmts:
        effect = s.get("Effect", "Allow")
        if effect != "Allow":
            continue
        actions = s.get("Action") or []
        actions = [actions] if isinstance(actions, str) else actions
        res = s.get("Resource") or []
        res = [res] if isinstance(res, str) else res
        pr = s.get("Principal") or {}
        pr_list = []
        if isinstance(pr, dict):
            for ptype_k, v in pr.items():
                vals = v if isinstance(v, list) else [v]
                for pv in vals:
                    pr_list.append(pv)
                    if ptype_k == "Federated":
                        federated.append(pv)   # OIDC/SAML provider ARN
        elif isinstance(pr, str):
            pr_list.append(pr)
        pr_list = [p if p != "*" else "wildcard-principal" for p in pr_list]
        public_principals += pr_list.count("wildcard-principal")
        if "*" in actions or "iam:*" in actions \
                or ("iam:PassRole" in actions and "*" in res):
            admin = True
        wildcard_actions += sum(1 for a in actions if a.endswith("*"))
        wildcard_resources += sum(1 for r in res if r == "*")
        principals += pr_list
        resources += res
        for p in pr_list:
            for r in res:
                dst = r.split(":")[-1][:48] if r != "*" else "wildcard"
                edges.append({"src_kind": "iam_principal", "src": p,
                              "dst_kind": "policy", "dst": dst,
                              "kind": "can_access",
                              "attrs": {"actions": actions,
                                        "effect": effect}})
        for a in actions:
            if a == "sts:AssumeRole":
                for r in res:
                    chain_targets.append(r)
                    for p in pr_list:
                        edges.append({"src_kind": "iam_principal", "src": p,
                                      "dst_kind": "role", "dst": r,
                                      "kind": "assumes"})
    attrs = {"policy_name": name, "policy_type": ptype,
             "statement_count": len(stmts),
             "principals": sorted(set(principals)),
             "federated_providers": sorted(set(federated)),
             "assumable_roles": sorted(set(chain_targets)),
             "wildcard_actions": wildcard_actions,
             "wildcard_resources": wildcard_resources,
             "public_principals": public_principals,
             "admin_grant": admin,
             "graph": {"nodes": [{"kind": "policy", "label": name}] +
                       [{"kind": "iam_principal", "label": p}
                        for p in sorted(set(principals))] +
                       [{"kind": "role", "label": r}
                        for r in sorted(set(chain_targets))],
                      "edges": edges}}
    return {"facts": [{"fact_id": stable_id("PF-SEC", "iam", str(path)),
                       "kind": "security.iam_policy", "source": str(path),
                       "location": name, "tier": 3, "attrs": attrs}],
            "counts": {"statements": len(stmts), "edges": len(edges)}}
