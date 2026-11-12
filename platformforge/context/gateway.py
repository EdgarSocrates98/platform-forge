"""ContextGateway (§56–75) — the single context layer.

Pipeline (§58): task → scope → search → graph expansion → evidence
selection → dedup → budget → pack → redaction → ContextRef.

Every model/agent entry goes through `build()`; the capsule it returns is
the minimal sufficient context, not the maximal available one (§297).
Essential evidence that cannot fit the budget is a refusal
(PF-CONTEXT-ESSENTIAL) — never silently truncated (§235 eval).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from platformforge.context.capsule import CLASSIFICATIONS, SCOPES, ContextCapsule
from platformforge.context.refs import ContextRef
from platformforge.context.sufficiency import ContextSufficiencyResult, Sufficiency, assess
from platformforge.core.redaction import redact_text
from platformforge.economy.cache import CacheStore
from platformforge.economy.ledger import EconomyLedger, ToolUsageEntry

REFUSAL_ESSENTIAL = "PF-CONTEXT-ESSENTIAL"
PROTECTED_CLASSIFICATIONS = frozenset(("confidential", "restricted"))


@dataclass(frozen=True)
class AuthorizationDecision:
    """Trusted host decision consumed by the context boundary.

    Platform Forge deliberately does not mint identities.  Agent Bridge (or
    another host authority) supplies this shape after authenticating the
    principal, checking session state/revocation and resolving workspace
    scope.  A caller-provided principal or classification list is never a
    grant by itself.
    """

    allow: bool
    principal: str = ""
    workspace_id: str = ""
    session_id: str = ""
    classifications: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    reason: str = ""


class ContextAuthorizer(Protocol):
    def authorize(self, *, principal: str, workspace_id: str,
                  session_id: str, operation: str, resource: str,
                  classification: str) -> AuthorizationDecision | Mapping[str, Any]:
        """Return a decision from a trusted authentication authority."""

# §70–73 — which capsule sections each role receives.
ROLE_SECTIONS: dict[str, tuple[str, ...]] = {
    "specialist": ("summary", "task", "scope", "facts", "findings",
                   "rules", "knowledge_refs", "graph_refs",
                   "artifact_refs", "open_questions"),
    "reviewer": ("summary", "task", "scope", "findings", "rules",
                 "open_questions"),
    "verifier": ("summary", "task", "findings", "rules",
                 "open_questions"),        # §71: criteria+evidence+outputs
    "critic": ("summary", "task", "open_questions"),  # §72 assumptions
    "referee": ("summary", "task", "open_questions"),
    "planner": ("summary", "task", "scope", "open_questions",
                "knowledge_refs"),
}


@dataclass
class ContextRequest:
    task: str
    scope: str = "repository"
    classification: str = "internal"
    budget_bytes: int | None = None          # soft context budget
    essential_bytes: int | None = None       # §235 — must-fit floor
    required_sections: list[str] = field(default_factory=list)
    role: str = "specialist"
    query: str = ""
    facts: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    knowledge_refs: list[str] = field(default_factory=list)
    graph_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    deps: dict[str, str] = field(default_factory=dict)
    workspace_id: str = ""
    session_id: str = ""
    principal: str = ""
    policy_version: str = "platformforge/context-policy/v1"


class ContextGateway:
    def __init__(self, root: str | Path,
                 *, authorizer: ContextAuthorizer | None = None,
                 workspace_id: str = ""):
        self.root = Path(root)
        self.authorizer = authorizer
        self.workspace_id = workspace_id or str(self.root.resolve())
        self.cache = CacheStore(root)
        self.ledger = EconomyLedger(root)
        self._store = self.root / ".platformforge" / "context-store"
        self._store.mkdir(parents=True, exist_ok=True)

    # -- build (pipeline §58) ------------------------------------------
    def build(self, req: ContextRequest) -> dict[str, Any]:
        t0 = time.monotonic()
        schema_error = _validate_request(req)
        if schema_error:
            return {"refusal": "PF-CONTEXT-SCHEMA", "reason": schema_error}
        if not req.task.strip():
            return {"refusal": "PF-CONTEXT-SCHEMA", "reason": "task is required"}
        workspace_id = req.workspace_id or self.workspace_id
        if req.classification in PROTECTED_CLASSIFICATIONS:
            decision = self._authorize(
                principal=req.principal,
                workspace_id=workspace_id,
                session_id=req.session_id,
                operation="build",
                resource="context:build",
                classification=req.classification,
            )
            if "refusal" in decision:
                return decision
        # 1–2. task + scope are inputs; 3–4. search/graph expansion is the
        # caller's job (facts/findings arrive already extracted — the
        # gateway assembles, it does not analyze).
        # 5. evidence selection: essential sections first, dedup (§6).
        facts = _dedup(req.facts, key=lambda f: f.get("fact_id",
                                                      json.dumps(f,
                                                                 sort_keys=True,
                                                                 default=str)))
        findings = _dedup(req.findings, key=lambda f: f.get(
            "finding_id", f.get("rule_id", json.dumps(f, sort_keys=True,
                                                    default=str))))

        safe_facts, fact_redacted = _redact_with_meta(facts)
        safe_findings, finding_redacted = _redact_with_meta(findings)
        safe_rules, rules_redacted = _redact_with_meta(req.rules)
        safe_knowledge, knowledge_redacted = _redact_with_meta(req.knowledge_refs)
        safe_graph, graph_redacted = _redact_with_meta(req.graph_refs)
        safe_artifacts, artifacts_redacted = _redact_with_meta(req.artifact_refs)
        safe_questions, questions_redacted = _redact_with_meta(req.open_questions)
        redacted = any((fact_redacted, finding_redacted, rules_redacted,
                        knowledge_redacted, graph_redacted, artifacts_redacted,
                        questions_redacted))
        warnings = [
            "sensitive values were redacted before serialization"
        ] if redacted else []

        safe_task = _redact(req.task)
        capsule = ContextCapsule(
            summary=f"{safe_task} ({req.scope})",
            task=safe_task, scope=req.scope,
            classification=req.classification,
            facts=safe_facts, findings=safe_findings, rules=safe_rules,
            knowledge_refs=safe_knowledge, graph_refs=safe_graph,
            artifact_refs=safe_artifacts,
            open_questions=safe_questions,
            budget={"budget_bytes": req.budget_bytes,
                    "essential_bytes": req.essential_bytes},
            warnings=warnings,
            workspace_id=workspace_id,
            session_id=req.session_id,
            policy_version=req.policy_version)

        # 7. budget — essential evidence must fit or the capsule refuses
        size = capsule.byte_size
        if req.essential_bytes is not None and \
                req.budget_bytes is not None and \
                req.essential_bytes > req.budget_bytes:
            self.ledger.record(ToolUsageEntry(
                tool="context.build", output_bytes=size,
                duration_ms=(time.monotonic() - t0) * 1000,
                task=req.task))
            return {"refusal": REFUSAL_ESSENTIAL,
                    "reason": f"essential {req.essential_bytes}B > "
                              f"budget {req.budget_bytes}B — narrow scope "
                              "or raise budget; never truncate evidence",
                    "sufficiency": ContextSufficiencyResult(
                        Sufficiency.INSUFFICIENT,
                        ["essential-evidence"],
                        "budget smaller than essential floor").to_dict()}

        # 8. redaction — secrets never persist into the store (§224)
        try:
            capsule = self._prepare_capsule(capsule)
            self._persist(capsule)
        except (TypeError, ValueError) as exc:
            return {"refusal": "PF-CONTEXT-SCHEMA", "reason": str(exc)}

        # 9. ContextRef + sufficiency + cache receipt
        ref = capsule.ref()
        suff = assess(required=req.required_sections,
                      present=[s for s in ("facts", "findings", "rules",
                                           "knowledge_refs",
                                           "graph_refs")
                               if getattr(capsule, s)])
        self.ledger.record(ToolUsageEntry(
            tool="context.build", output_bytes=size,
            duration_ms=(time.monotonic() - t0) * 1000,
            task=req.task))
        return {"capsule": capsule.to_dict(), "ref": ref,
                "bytes": size, "sufficiency": suff.to_dict(),
                "expandable": capsule.expandable}

    # -- lazy refs (§63–64) ---------------------------------------------
    def _prepare_capsule(self, capsule: ContextCapsule) -> ContextCapsule:
        """Apply the persistence invariant to every write path.

        ``delta()`` and other internal callers may receive a capsule built by
        an adapter.  It is therefore unsafe to assume the object was already
        redacted merely because it is a ``ContextCapsule`` instance.
        """
        if not isinstance(capsule, ContextCapsule):
            raise TypeError("capsule must be a ContextCapsule")
        if capsule.classification not in CLASSIFICATIONS:
            raise ValueError("unknown classification is not persistable")
        safe = ContextCapsule(
            schema=capsule.schema,
            capsule_id=capsule.capsule_id,
            summary=_redact(capsule.summary),
            task=_redact(capsule.task),
            scope=capsule.scope,
            classification=capsule.classification,
            facts=_redact(capsule.facts),
            findings=_redact(capsule.findings),
            rules=_redact(capsule.rules),
            knowledge_refs=_redact(capsule.knowledge_refs),
            graph_refs=_redact(capsule.graph_refs),
            artifact_refs=_redact(capsule.artifact_refs),
            open_questions=_redact(capsule.open_questions),
            budget=_redact(capsule.budget),
            expandable=_redact(capsule.expandable),
            warnings=list(capsule.warnings),
            workspace_id=capsule.workspace_id or self.workspace_id,
            session_id=capsule.session_id,
            policy_version=capsule.policy_version,
        )
        return safe

    def _persist(self, capsule: ContextCapsule) -> None:
        # _persist is intentionally defensive even though it is private:
        # hash exactly the sanitized canonical bytes persisted so a ref is an
        # integrity claim, never an authorization claim.
        capsule = self._prepare_capsule(capsule)
        blob = capsule.to_dict()
        encoded = _canonical_bytes(blob)
        digest = _digest(encoded)
        if digest != capsule.content_hash():
            raise ValueError("PF-CONTEXT-INTEGRITY: capsule hash is not canonical")
        destination = self._store / f"{digest}.json"
        fd, temporary = tempfile.mkstemp(
            prefix=f".{digest}.", suffix=".tmp", dir=self._store
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            if _digest(destination.read_bytes()) != digest:
                raise OSError("persisted context bytes failed verification")
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _inspect_storage(self, ref: str) -> dict[str, Any]:
        """Trusted storage resolver; never expose this as an agent boundary."""
        try:
            digest = ContextRef.parse(ref).digest
        except (TypeError, ValueError):
            return {"refusal": "PF-CONTEXT-REF-SCHEMA",
                    "reason": "context reference must be context://sha256/<64 hex>"}
        p = self._store / f"{digest}.json"
        if not p.exists():
            return {"refusal": "PF-CONTEXT-REF-UNKNOWN",
                    "reason": f"no stored capsule for {ref}",
                    "unlock": "rebuild the context that minted the ref"}
        try:
            blob = json.loads(p.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {"refusal": "PF-CONTEXT-INTEGRITY",
                    "reason": f"stored capsule is unreadable for {ref}"}
        if _digest(_canonical_bytes(blob)) != digest:
            return {"refusal": "PF-CONTEXT-INTEGRITY",
                    "reason": f"stored capsule bytes do not match {ref}"}
        return blob

    def inspect(self, ref: str, *, principal: str = "", workspace_id: str = "",
                session_id: str = "", allowed_classifications: tuple[str, ...] | None = None,
                authorizer: ContextAuthorizer | None = None) -> dict[str, Any]:
        """Resolve a ref only after applying the protected-context policy."""
        cap = self._inspect_storage(ref)
        if "refusal" in cap:
            return cap
        decision = self._authorize_for_capsule(
            ref, cap, principal=principal, workspace_id=workspace_id,
            session_id=session_id, operation="inspect",
            allowed_classifications=allowed_classifications,
            authorizer=authorizer)
        if "refusal" in decision:
            return decision
        return cap

    def expand(self, ref: str, section: str = "", *, principal: str = "",
               workspace_id: str = "", session_id: str = "",
               allowed_classifications: tuple[str, ...] | None = None,
               authorizer: ContextAuthorizer | None = None) -> dict[str, Any]:
        """§63–64 — lazy expansion: return only the requested section
        (or the full capsule when section is empty)."""
        cap = self._inspect_storage(ref)
        if "refusal" in cap:
            return cap
        decision = self._authorize_for_capsule(
            ref, cap, principal=principal, workspace_id=workspace_id,
            session_id=session_id, operation="expand",
            allowed_classifications=allowed_classifications,
            authorizer=authorizer)
        if "refusal" in decision:
            return decision
        if section:
            if section not in cap:
                return {"refusal": "PF-CONTEXT-SECTION-UNKNOWN",
                        "reason": f"capsule has no section {section!r}",
                        "sections": sorted(k for k in cap
                                           if not k.startswith("_"))}
            return {"ref": ref, "section": section,
                    "content": cap[section]}
        return {"ref": ref, "capsule": cap}

    def delta(self, base_ref: str, capsule: ContextCapsule,
              *, principal: str = "", workspace_id: str = "",
              session_id: str = "", authorizer: ContextAuthorizer | None = None
              ) -> dict[str, Any]:
        """§74 — baseline + delta: emit only the sections that changed vs
        the stored baseline capsule. Unchanged sections ship as the ref."""
        base = self._inspect_storage(base_ref)
        if "refusal" in base:
            return base
        prepared = self._prepare_capsule(capsule)
        auth = self._authorize_for_capsule(
            base_ref, base, principal=principal,
            workspace_id=workspace_id or prepared.workspace_id,
            session_id=session_id or prepared.session_id,
            operation="delta", allowed_classifications=(prepared.classification,),
            authorizer=authorizer)
        if "refusal" in auth:
            return auth
        delta: dict[str, Any] = {}
        reused: list[str] = []
        for k, v in prepared.to_dict().items():
            if k in ("schema",):
                continue
            if base.get(k) != v:
                delta[k] = v
            else:
                reused.append(k)
        self._persist(prepared)
        return {"baseline_ref": base_ref, "delta_ref": prepared.ref(),
                "delta": delta, "reused_sections": reused,
                "delta_bytes": len(json.dumps(delta, default=str)),
                "full_bytes": prepared.byte_size}

    # -- role-specific (§70–73) -----------------------------------------
    def for_role(self, ref: str, role: str, *, principal: str = "",
                 workspace_id: str = "", session_id: str = "",
                 authorizer: ContextAuthorizer | None = None) -> dict[str, Any]:
        """Project a stored capsule to the sections a role receives.
        Verifier gets criteria+evidence+outputs — not the transcript."""
        if role not in ROLE_SECTIONS:
            return {"refusal": "PF-CONTEXT-ROLE-UNKNOWN",
                    "reason": f"role {role!r} not in "
                              f"{sorted(ROLE_SECTIONS)}"}
        cap = self._inspect_storage(ref)
        if "refusal" in cap:
            return cap
        decision = self._authorize_for_capsule(
            ref, cap, principal=principal, workspace_id=workspace_id,
            session_id=session_id, operation="project",
            allowed_classifications=None, authorizer=authorizer)
        if "refusal" in decision:
            return decision
        return {"role": role, "ref": ref,
                "context": {s: cap.get(s) for s in ROLE_SECTIONS[role]}}

    def _authorize_for_capsule(
        self, ref: str, cap: Mapping[str, Any], *, principal: str,
        workspace_id: str, session_id: str, operation: str,
        allowed_classifications: tuple[str, ...] | None,
        authorizer: ContextAuthorizer | None,
    ) -> dict[str, Any]:
        classification = str(cap.get("classification", "unknown"))
        if classification not in CLASSIFICATIONS:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "unknown classification is denied by default"}
        requested_workspace = workspace_id or str(cap.get("workspace_id") or self.workspace_id)
        requested_session = session_id or str(cap.get("session_id") or "")
        return self._authorize(
            principal=principal, workspace_id=requested_workspace,
            session_id=requested_session, operation=operation,
            resource=ref, classification=classification,
            allowed_classifications=allowed_classifications,
            authorizer=authorizer)

    def _authorize(
        self, *, principal: str, workspace_id: str, session_id: str,
        operation: str, resource: str, classification: str,
        allowed_classifications: tuple[str, ...] | None = None,
        authorizer: ContextAuthorizer | None = None,
    ) -> dict[str, Any]:
        if classification not in PROTECTED_CLASSIFICATIONS:
            return {}
        authority = authorizer or self.authorizer
        if authority is None:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "protected context requires a trusted authorization authority"}
        if not principal:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "principal is required and must be resolved by the host authority"}
        try:
            raw = authority.authorize(
                principal=principal, workspace_id=workspace_id,
                session_id=session_id, operation=operation,
                resource=resource, classification=classification)
        except Exception as exc:  # noqa: BLE001 - authority failures fail closed
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": f"authorization authority rejected request: {exc}"}
        if isinstance(raw, AuthorizationDecision):
            decision = raw
        elif isinstance(raw, Mapping):
            decision = AuthorizationDecision(
                allow=bool(raw.get("allow")),
                principal=str(raw.get("principal") or ""),
                workspace_id=str(raw.get("workspace_id") or ""),
                session_id=str(raw.get("session_id") or ""),
                classifications=tuple(str(v) for v in raw.get("classifications", ())),
                operations=tuple(str(v) for v in raw.get("operations", ())),
                reason=str(raw.get("reason") or ""))
        else:
            decision = AuthorizationDecision(allow=False, reason="invalid authority decision")
        if not decision.allow or not decision.principal or decision.principal != principal:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": decision.reason or "trusted authority denied the request"}
        if decision.workspace_id and decision.workspace_id != workspace_id:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "workspace does not match the authorized context"}
        if decision.session_id and decision.session_id != session_id:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "session does not match the authorized context"}
        if classification not in decision.classifications:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "classification is not in the trusted authority scope"}
        if decision.operations and operation not in decision.operations:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "operation is not in the trusted authority scope"}
        if allowed_classifications is not None and classification not in allowed_classifications:
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "caller classification request exceeds its authorized scope"}
        return {}


def _dedup(items: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    seen, out = set(), []
    for it in items:
        k = key(it)
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def _validate_request(req: ContextRequest) -> str:
    """Validate the request boundary before touching or persisting payloads."""
    if not isinstance(req.task, str):
        return "task must be a string"
    if req.scope not in SCOPES:
        return f"scope must be one of {SCOPES}"
    if req.classification not in CLASSIFICATIONS:
        return f"classification must be one of {CLASSIFICATIONS}"
    list_fields = (
        "facts", "findings", "rules", "knowledge_refs", "graph_refs",
        "artifact_refs", "open_questions", "required_sections",
    )
    for name in list_fields:
        if not isinstance(getattr(req, name), list):
            return f"{name} must be a list"
    if not all(isinstance(section, str) and section for section in req.required_sections):
        return "required_sections must contain non-empty strings"
    for name in ("budget_bytes", "essential_bytes"):
        value = getattr(req, name)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            return f"{name} must be a non-negative integer or null"
    return ""


_SECRET_KEYS = ("password", "secret", "token", "api_key", "private_key",
                "credential")


def _redact(obj: Any) -> Any:
    """§224 — boundary redaction before capsule persistence. Values whose
    key looks secret-shaped are replaced, never stored."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if any(s in str(k).lower()
                                        for s in _SECRET_KEYS)
                    else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def _redact_with_meta(obj: Any) -> tuple[Any, bool]:
    """Redact recursively and report degradation instead of hiding it."""
    if isinstance(obj, str):
        safe = redact_text(obj)
        return safe, safe != obj
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        changed = False
        for key, value in obj.items():
            if any(secret in str(key).lower() for secret in _SECRET_KEYS):
                out[key] = "[REDACTED]"
                changed = True
            else:
                out[key], child_changed = _redact_with_meta(value)
                changed = changed or child_changed
        return out, changed
    if isinstance(obj, list):
        values = []
        changed = False
        for value in obj:
            safe, child_changed = _redact_with_meta(value)
            values.append(safe)
            changed = changed or child_changed
        return values, changed
    if isinstance(obj, tuple):
        values, changed = _redact_with_meta(list(obj))
        return values, changed
    return obj, False


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def _digest(value: bytes) -> str:
    import hashlib
    return hashlib.sha256(value).hexdigest()
