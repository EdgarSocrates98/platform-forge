"""Cycle 5 Phase J — federation contracts (§167–177).

Federation = intelligence exchange, never distributed execution
(§168, §172). Each node keeps its own execution authority; remote
nodes can never grant it (§301). Credentials never cross the boundary
(§175, §302).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from platformforge.fleet.models import classify
from platformforge.live.models import canonical_hash

MANIFEST_SCHEMA = "platformforge/node-manifest/v1"
SUMMARY_SCHEMA = "platformforge/federation-summary/v1"
EXPORT_ACTIONS = ("allow", "redact", "aggregate", "deny")


@dataclass
class NodeManifest:
    """§170 — what a Forge node is and what it may share."""
    node_id: str
    capabilities: list[str] = field(default_factory=list)
    fleet_scope: dict[str, Any] = field(default_factory=dict)
    data_freshness: str = "unknown"
    authority: str = "local"          # only ever "local" (§172)
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"schema": MANIFEST_SCHEMA, **asdict(self)}


@dataclass
class FederationPolicy:
    """§177/§309 — what may leave this node, per classification.
    Default for unmapped classifications: `deny` (fail closed)."""
    rules: dict[str, str] = field(default_factory=lambda: {
        "public": "allow", "internal": "aggregate",
        "sensitive": "redact", "restricted": "deny"})

    def action_for(self, classification: str) -> str:
        return self.rules.get(classification, "deny")


SECRET_KEYS = ("password", "secret", "token", "credential", "api_key",
               "private_key", "access_key", "session")


def _contains_secret(obj: Any, depth: int = 0) -> bool:
    if depth > 8:
        return True
    if isinstance(obj, dict):
        return any(
            any(s in str(k).lower() for s in SECRET_KEYS)
            or _contains_secret(v, depth + 1)
            for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return any(_contains_secret(v, depth + 1) for v in obj)
    return False


def export_summary(node: NodeManifest, payload: dict[str, Any],
                   classification: str,
                   policy: FederationPolicy | None = None,
                   ) -> dict[str, Any]:
    """§174–177 — build a shareable summary under the export policy.
    Refuses anything containing credential-shaped fields regardless of
    classification (§175/§302)."""
    cls = classify(classification)
    pol = policy or FederationPolicy()
    action = pol.action_for(cls)
    if _contains_secret(payload):
        return {"schema": SUMMARY_SCHEMA, "node_id": node.node_id,
                "action": "deny",
                "reason": "PF-FED-SECRET-BOUNDARY",
                "note": "credentials never leave the node"}
    if action == "deny":
        return {"schema": SUMMARY_SCHEMA, "node_id": node.node_id,
                "action": "deny", "classification": cls}
    out: dict[str, Any] = {"schema": SUMMARY_SCHEMA,
                           "node_id": node.node_id, "action": action,
                           "classification": cls,
                           "authority": "local",
                           "freshness": node.data_freshness}
    if action == "aggregate":
        out["payload"] = _aggregate(payload)
    elif action == "redact":
        out["payload"] = _redact(payload)
    else:
        out["payload"] = payload
    out["hash"] = "sha256:" + canonical_hash(out["payload"])
    return out


def _aggregate(payload: dict[str, Any]) -> dict[str, Any]:
    """Counts + ratios only — individual records stay home (§310)."""
    out: dict[str, Any] = {"aggregated": True}
    for k, v in payload.items():
        if isinstance(v, list):
            out[f"{k}.count"] = len(v)
        elif isinstance(v, dict):
            out[k] = _aggregate(v)
        elif isinstance(v, (int, float)):
            out[k] = v
        else:
            out[f"{k}.present"] = bool(v)
    return out


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    import json

    from platformforge.live.store import redact_for_output
    return json.loads(redact_for_output(json.dumps(payload)))


def federated_query(nodes: list[NodeManifest],
                    query_fn, question: str) -> dict[str, Any]:
    """§171 — fan out a question to node summaries; each node answers
    *from its own data* — authority and credentials stay local."""
    answers = []
    for n in nodes:
        r = query_fn(n, question)
        answers.append({"node_id": n.node_id,
                        "freshness": n.data_freshness, **r})
    covered = sum(1 for a in answers if a.get("answered"))
    return {"question": question, "nodes": len(nodes),
            "answered": covered,
            "coverage": round(covered / len(nodes), 3) if nodes else 0.0,
            "answers": answers,
            "note": "intelligence federation — no execution authority "
                    "crossed the boundary"}
