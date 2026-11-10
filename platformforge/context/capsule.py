"""ContextCapsule (§60–61) — the bounded payload handed to a model/agent.

Sections hold refs, not duplicated bytes (§62): facts/findings/rules are
`fact://`/`finding://` pointers into the store; expandable detail lives
behind `context://` refs resolved by `context expand` (§63–64)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA = "platformforge/context-capsule/v1"

SCOPES = ("repository", "resource", "cluster", "fleet", "incident",
          "operation", "service")            # §68
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")

# §111 — compression/projection may never strip these from a capsule.
ESSENTIAL_FIELDS = ("facts", "findings", "open_questions")


@dataclass
class ContextCapsule:
    schema: str = SCHEMA
    capsule_id: str = ""
    summary: str = ""
    task: str = ""
    scope: str = "repository"
    classification: str = "internal"
    facts: list[Any] = field(default_factory=list)
    findings: list[Any] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    knowledge_refs: list[str] = field(default_factory=list)
    graph_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    expandable: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # Authorization binding is metadata, never an access grant.  A caller
    # must still present a trusted authority decision before protected
    # content is resolved.
    workspace_id: str = ""
    session_id: str = ""
    policy_version: str = "platformforge/context-policy/v1"
    # section name → context:// uri with full detail (§62)

    def __post_init__(self) -> None:
        if self.scope not in SCOPES:
            raise ValueError(f"scope {self.scope!r} not in {SCOPES}")
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(
                f"classification {self.classification!r} not in {CLASSIFICATIONS}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def serialize(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False,
                          default=str).encode("utf-8")

    @property
    def byte_size(self) -> int:
        return len(self.serialize())

    def content_hash(self) -> str:
        import hashlib
        return hashlib.sha256(self.serialize()).hexdigest()

    def ref(self) -> str:
        return f"context://sha256/{self.content_hash()}"
