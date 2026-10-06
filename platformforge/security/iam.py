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


def analyze_iam_policy(path: str | Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text())
    name = doc.get("PolicyName") or doc.get("Id") or Path(path).stem
    stmts = _stmts(doc)
    edges, principals, resources = [], [], []
    wildcard_actions = wildcard_resources = public_principals = 0
    admin = False
    for s in stmts:
        effect = s.get("Effect", "Allow")
        if effect != "Allow":
            continue
        actions = s.get("Action") or []
        actions = [actions] if isinstance(actions, str) else actions
        res = s.get("Resource") or []
        res = [res] if isinstance(res, str) else res
        pr = s.get("Principal") or {}
        if pr == "*":
            public_principals += 1
        pr_list = []
        if isinstance(pr, dict):
            for v in pr.values():
                pr_list += v if isinstance(v, list) else [v]
        elif isinstance(pr, str):
            pr_list.append(pr)
        pr_list = [p if p != "*" else "wildcard-principal" for p in pr_list]
        if "*" in actions or "iam:*" in actions or "iam:PassRole" in actions \
                and "*" in res:
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
                    for p in pr_list:
                        edges.append({"src_kind": "iam_principal", "src": p,
                                      "dst_kind": "role", "dst": r,
                                      "kind": "assumes"})
    attrs = {"policy_name": name, "statement_count": len(stmts),
             "principals": sorted(set(principals)),
             "wildcard_actions": wildcard_actions,
             "wildcard_resources": wildcard_resources,
             "public_principals": public_principals,
             "admin_grant": admin,
             "graph": {"nodes": [{"kind": "policy", "label": name}] +
                       [{"kind": "iam_principal", "label": p}
                        for p in sorted(set(principals))],
                      "edges": edges}}
    return {"facts": [{"fact_id": stable_id("PF-SEC", "iam", str(path)),
                       "kind": "security.iam_policy", "source": str(path),
                       "location": name, "tier": 3, "attrs": attrs}],
            "counts": {"statements": len(stmts), "edges": len(edges)}}
