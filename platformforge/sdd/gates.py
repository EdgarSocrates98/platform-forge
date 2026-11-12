"""SDD multidimensional gates — honest check(), evidence-backed ship_gate(),
and governed overrides. All refusals carry deterministic codes; nothing
trusting caller-supplied booleans alone."""

from __future__ import annotations

import time
from typing import Any

import yaml

from platformforge.core.hashing import sha256_file

SCHEMA_VERSION = "sdd-gates/1"

#: Gates that can never be overridden — risk-acceptance and stale-hash are
#: structural, not discretionary.
UNDISPENSABLE = frozenset({"upstream_hash_stale", "risk_acceptance_absent"})

_PHASES_REQ_SHIP = ("discover", "define", "design", "contract", "plan",
                    "build", "review", "verify")
#: phases whose artifact must contain a machine-checkable evidence body
_EVIDENCED = ("build", "verify")


def _refuse(code: str, phase: str, field: str, reason: str,
            unlock: str, evidence: str = "") -> dict[str, Any]:
    return {"code": code, "phase": phase, "field": field,
            "reason": reason, "unlock": unlock, "evidence": evidence}


def check(project: Any, feature: str) -> dict[str, Any]:
    """Multidimensional validation → ok/refused[]/unresolved[]/warnings[].

    Replaces the old 'no-stale ⇒ ok' false-positive: existence, frontmatter,
    identity, order, upstream integrity, status taxonomy, evidence, and
    ship-phase consistency are all evaluated.
    """
    st = project.status(feature)
    refused: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    warnings: list[str] = []
    evidence: list[str] = []

    statuses = {p["phase"]: p["status"] for p in st["phases"]}
    for i, ph in enumerate(project_phase_order()):
        a = project.artifact(feature, ph)
        if not a.exists:
            continue
        evidence.append(f"{ph}:{a.path.name}")
        m = a.meta
        if m.get("sdd") != 1:
            refused.append(_refuse("schema_version", ph, "sdd",
                                   f"meta.sdd={m.get('sdd')!r}",
                                   "rewrite artifact with sdd: 1"))
        if m.get("feature") != feature:
            refused.append(_refuse("identity_mismatch", ph, "feature",
                                   f"meta.feature={m.get('feature')!r} != {feature!r}",
                                   "fix frontmatter feature"))
        if m.get("phase") != ph:
            refused.append(_refuse("identity_mismatch", ph, "phase",
                                   f"meta.phase={m.get('phase')!r} != {ph!r}",
                                   "fix frontmatter phase"))
        if m.get("status") not in ("draft", "ready", "accepted",
                                   "stale", "done"):
            refused.append(_refuse("status_invalid", ph, "status",
                                   f"status={m.get('status')!r}",
                                   "use draft|ready|accepted|done"))
        up = m.get("upstream") or {}
        if i > 0 and statuses.get(phase_before(ph)) not in (None, "missing") \
                and not up.get("sha256"):
            unresolved.append(_refuse("upstream_unsealed", ph, "upstream",
                                      "predecessor exists but upstream.sha256 absent",
                                      "run sdd stamp after intentional change"))
        if ph in _EVIDENCED and a.exists:
            try:
                doc = yaml.safe_load(a.path.read_text()) or {}
            except yaml.YAMLError:
                refused.append(_refuse("artifact_unreadable", ph, "body",
                                       "artifact is not parseable YAML",
                                       "rewrite the artifact"))
                continue
            if not isinstance(doc, dict) or "meta" not in doc:
                refused.append(_refuse("schema_version", ph, "meta",
                                       "evidenced artifact missing meta block",
                                       "wrap fields under meta:"))
    if st["stale"]:
        refused.append(_refuse("upstream_hash_stale", "any", "upstream",
                               f"stale phases: {st['stale']}",
                               "re-stamp after intentional upstream change"))
    return {"ok": not refused, "feature": feature,
            "schema_version": SCHEMA_VERSION,
            "refused": refused, "unresolved": unresolved,
            "warnings": warnings, "evidence": evidence,
            "stale": st["stale"], "phases": st["phases"]}


def phase_before(phase: str) -> str:
    from .lifecycle import PHASES
    return PHASES[project_phase_order().index(phase) - 1]


def project_phase_order() -> list[str]:
    from .lifecycle import PHASES
    return PHASES


def _read_verify(project: Any, feature: str) -> dict[str, Any]:
    """Read the persisted verify.json — never caller dicts alone."""
    a = project.artifact(feature, "verify")
    if not a.exists:
        return {}
    try:
        doc = yaml.safe_load(a.path.read_text())
    except yaml.YAMLError:
        return {"_corrupt": True}
    return doc if isinstance(doc, dict) else {}


def _evidence_tampered(project: Any, feature: str,
                       phase: str) -> str | None:
    """Re-hash the artifact and compare against the *successor's*
    recorded upstream hash — detects post-hoc modification."""
    order = project_phase_order()
    idx = order.index(phase)
    if idx + 1 >= len(order):
        return None
    nxt = project.artifact(feature, order[idx + 1])
    art = project.artifact(feature, phase)
    if not nxt.exists or not art.exists:
        return None
    rec = (nxt.meta.get("upstream") or {}).get("sha256")
    if rec and rec != sha256_file(art.path):
        return f"{phase}->hash-mismatch"
    return None


def ship_gate(project: Any, feature: str,
              verify: dict[str, Any] | None = None,
              findings: list[dict[str, Any]] | None = None,
              risk_accepted: bool = False) -> dict[str, Any]:
    """Evidence-backed ship evaluation. Caller dicts may *add* failures,
    never remove them — the persisted artifacts are the floor."""
    failures: list[str] = []
    evidence: list[str] = []
    status = project.status(feature)
    if status["stale"]:
        failures.append("upstream_hash_stale")

    missing = [p["phase"] for p in status["phases"]
               if p["phase"] in _PHASES_REQ_SHIP and p["status"] == "missing"]
    if missing:
        failures.append(f"evidence_missing:{','.join(missing)}")

    # persisted verify.json is authoritative; caller dict can only worsen
    vdoc = _read_verify(project, feature)
    caller = verify or {}
    if vdoc.get("_corrupt"):
        failures.append("verify_artifact_corrupt")
    if caller.get("required_failed") or caller.get("tests") == "failed" \
            or vdoc.get("tests") == "failed" or vdoc.get("required_failed"):
        failures.append("required_test_failed")
    if caller.get("security") == "failed" or vdoc.get("security") == "failed":
        failures.append("security_gate_failed")
    critical = [f for f in (findings or [])
                if f.get("severity") == "critical"
                and f.get("status") == "violated"]
    if critical:
        failures.append("critical_finding_unresolved")

    for ph in ("build", "verify"):
        t = _evidence_tampered(project, feature, ph)
        if t:
            failures.append(f"evidence_tampered:{t}")
            evidence.append(t)

    high_risk = caller.get("risk") in ("high", "critical") \
        or vdoc.get("risk") in ("high", "critical")
    if high_risk and not risk_accepted:
        failures.append("risk_acceptance_absent")
    return {"feature": feature, "allowed": not failures,
            "failures": failures, "evidence": evidence,
            "rule": "overrides emit a receipt via ship(override=True)"}


def validate_override(*, feature: str, gate: str, failures: list[str],
                      reason: str, actor: str) -> tuple[bool, str]:
    """Override contract → (allowed, deny_reason)."""
    if not reason or not reason.strip():
        return False, "override_reason_empty"
    if not actor or not actor.strip() or actor.strip() == "unknown":
        return False, "override_actor_missing"
    if gate not in failures:
        return False, f"override_gate_absent:{gate}"
    if gate in UNDISPENSABLE:
        return False, f"override_undispensable:{gate}"
    return True, ""


def override_receipt(*, feature: str, gate: str, failures: list[str],
                     reason: str, actor: str) -> dict[str, Any]:
    return {"id": f"ovr-{int(time.time())}", "feature": feature,
            "gate": gate, "overridden_failures": failures,
            "reason": reason, "actor": actor,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "schema": SCHEMA_VERSION}
