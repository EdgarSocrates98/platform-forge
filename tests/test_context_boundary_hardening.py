"""Cycle 2.8 negative tests for the protected Context Gateway boundary."""

from __future__ import annotations

from dataclasses import dataclass

from platformforge.context import AuthorizationDecision, ContextCapsule, ContextGateway, ContextRequest


@dataclass
class Authority:
    state: str = "active"
    allowed_classifications: tuple[str, ...] = ("confidential",)
    allowed_operations: tuple[str, ...] = ("build", "inspect", "expand", "project", "delta")

    def authorize(self, **kwargs):
        if self.state != "active":
            return AuthorizationDecision(False, reason=f"session {self.state}")
        return AuthorizationDecision(
            allow=True,
            principal=kwargs["principal"],
            workspace_id="workspace-a",
            session_id="session-a",
            classifications=self.allowed_classifications,
            operations=self.allowed_operations,
        )


def _request(**overrides):
    values = {
        "task": "review protected evidence",
        "classification": "confidential",
        "principal": "agent-a",
        "workspace_id": "workspace-a",
        "session_id": "session-a",
        "facts": [{"fact_id": "f-1", "password": "synthetic-password"}],
    }
    values.update(overrides)
    return ContextRequest(**values)


def _secure(tmp_path, authority=None):
    return ContextGateway(
        tmp_path,
        authorizer=authority or Authority(),
        workspace_id="workspace-a",
    )


def test_inspect_does_not_treat_hash_as_permission(tmp_path):
    gateway = _secure(tmp_path)
    built = gateway.build(_request())
    assert "ref" in built
    assert gateway.inspect(built["ref"])["refusal"] == "PF-CONTEXT-AUTHORIZATION"
    assert gateway.inspect(
        built["ref"], principal="agent-a", workspace_id="workspace-a",
        session_id="session-a")["classification"] == "confidential"


def test_workspace_session_revocation_and_operation_fail_closed(tmp_path):
    authority = Authority()
    gateway = _secure(tmp_path, authority)
    built = gateway.build(_request())
    ref = built["ref"]

    assert gateway.expand(
        ref, principal="agent-a", workspace_id="workspace-b", session_id="session-a",
    )["refusal"] == "PF-CONTEXT-AUTHORIZATION"
    assert gateway.expand(
        ref, principal="agent-a", workspace_id="workspace-a", session_id="session-b",
    )["refusal"] == "PF-CONTEXT-AUTHORIZATION"

    authority.state = "expired"
    assert gateway.expand(
        ref, principal="agent-a", workspace_id="workspace-a", session_id="session-a",
    )["refusal"] == "PF-CONTEXT-AUTHORIZATION"

    authority.state = "active"
    authority.allowed_operations = ("build", "inspect")
    assert gateway.expand(
        ref, "facts", principal="agent-a", workspace_id="workspace-a", session_id="session-a",
    )["refusal"] == "PF-CONTEXT-AUTHORIZATION"


def test_client_cannot_invent_classification_scope(tmp_path):
    authority = Authority(allowed_classifications=("internal",))
    gateway = _secure(tmp_path, authority)
    built = gateway.build(_request())
    assert built["refusal"] == "PF-CONTEXT-AUTHORIZATION"


def test_delta_redacts_untrusted_capsule_before_hash_and_persist(tmp_path):
    gateway = ContextGateway(tmp_path)
    base = gateway.build(ContextRequest(task="baseline", facts=[{"fact_id": "base"}]))
    candidate = ContextCapsule(
        task="candidate",
        summary="candidate",
        facts=[{"fact_id": "new", "token": "synthetic-token"}],
    )
    result = gateway.delta(base["ref"], candidate)
    stored = gateway.inspect(result["delta_ref"])
    assert stored["facts"][0]["token"] == "[REDACTED]"
    assert "synthetic-token" not in result["delta_ref"]


def test_unknown_classification_is_not_public(tmp_path):
    gateway = ContextGateway(tmp_path)
    result = gateway.build(ContextRequest(task="bad", classification="unknown"))
    assert result["refusal"] == "PF-CONTEXT-SCHEMA"
