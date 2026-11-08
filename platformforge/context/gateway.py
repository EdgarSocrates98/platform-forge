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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from platformforge.context.capsule import CLASSIFICATIONS, ContextCapsule
from platformforge.context.refs import ContextRef
from platformforge.context.sufficiency import ContextSufficiencyResult, Sufficiency, assess
from platformforge.economy.cache import CacheStore
from platformforge.economy.ledger import EconomyLedger, ToolUsageEntry

REFUSAL_ESSENTIAL = "PF-CONTEXT-ESSENTIAL"

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


class ContextGateway:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.cache = CacheStore(root)
        self.ledger = EconomyLedger(root)
        self._store = self.root / ".platformforge" / "context-store"
        self._store.mkdir(parents=True, exist_ok=True)

    # -- build (pipeline §58) ------------------------------------------
    def build(self, req: ContextRequest) -> dict[str, Any]:
        t0 = time.monotonic()
        if not req.task.strip():
            return {"refusal": "PF-CONTEXT-SCHEMA", "reason": "task is required"}
        if req.classification not in CLASSIFICATIONS:
            return {
                "refusal": "PF-CONTEXT-SCHEMA",
                "reason": f"classification must be one of {CLASSIFICATIONS}",
            }
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
            warnings=warnings)

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
        self._persist(capsule)

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
    def _persist(self, capsule: ContextCapsule) -> None:
        # The capsule is already redacted. Hash exactly the canonical bytes
        # persisted so a ref is an integrity claim, never an authorization
        # claim. Replace is atomic on the same filesystem.
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
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def inspect(self, ref: str) -> dict[str, Any]:
        """Resolve a `context://sha256/<hash>` ref to its stored capsule."""
        digest = ContextRef.parse(ref).digest
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

    def expand(self, ref: str, section: str = "", *, principal: str = "",
               allowed_classifications: tuple[str, ...] = ("public", "internal")) -> dict[str, Any]:
        """§63–64 — lazy expansion: return only the requested section
        (or the full capsule when section is empty)."""
        cap = self.inspect(ref)
        if "refusal" in cap:
            return cap
        if cap.get("classification") in ("confidential", "restricted") and (
                not principal or cap.get("classification") not in allowed_classifications):
            return {"refusal": "PF-CONTEXT-AUTHORIZATION",
                    "reason": "protected context requires an authorized principal and classification scope"}
        if section:
            if section not in cap:
                return {"refusal": "PF-CONTEXT-SECTION-UNKNOWN",
                        "reason": f"capsule has no section {section!r}",
                        "sections": sorted(k for k in cap
                                           if not k.startswith("_"))}
            return {"ref": ref, "section": section,
                    "content": cap[section]}
        return {"ref": ref, "capsule": cap}

    def delta(self, base_ref: str, capsule: ContextCapsule
              ) -> dict[str, Any]:
        """§74 — baseline + delta: emit only the sections that changed vs
        the stored baseline capsule. Unchanged sections ship as the ref."""
        base = self.inspect(base_ref)
        if "refusal" in base:
            return base
        delta: dict[str, Any] = {}
        reused: list[str] = []
        for k, v in capsule.to_dict().items():
            if k in ("schema",):
                continue
            if base.get(k) != v:
                delta[k] = v
            else:
                reused.append(k)
        self._persist(capsule)
        return {"baseline_ref": base_ref, "delta_ref": capsule.ref(),
                "delta": delta, "reused_sections": reused,
                "delta_bytes": len(json.dumps(delta, default=str)),
                "full_bytes": capsule.byte_size}

    # -- role-specific (§70–73) -----------------------------------------
    def for_role(self, ref: str, role: str) -> dict[str, Any]:
        """Project a stored capsule to the sections a role receives.
        Verifier gets criteria+evidence+outputs — not the transcript."""
        if role not in ROLE_SECTIONS:
            return {"refusal": "PF-CONTEXT-ROLE-UNKNOWN",
                    "reason": f"role {role!r} not in "
                              f"{sorted(ROLE_SECTIONS)}"}
        cap = self.inspect(ref)
        if "refusal" in cap:
            return cap
        return {"role": role, "ref": ref,
                "context": {s: cap.get(s) for s in ROLE_SECTIONS[role]}}


def _dedup(items: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    seen, out = set(), []
    for it in items:
        k = key(it)
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


_SECRET_KEYS = ("password", "secret", "token", "api_key", "private_key",
                "credential")


def _redact(obj: Any) -> Any:
    """§224 — boundary redaction before capsule persistence. Values whose
    key looks secret-shaped are replaced, never stored."""
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if any(s in str(k).lower()
                                        for s in _SECRET_KEYS)
                    else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def _redact_with_meta(obj: Any) -> tuple[Any, bool]:
    """Redact recursively and report degradation instead of hiding it."""
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
