"""Envelope validation + serialization — schema contract boundary.

Every envelope crossing into the platform is validated against
contracts/observation.schema.json and redacted before persistence
(cycle §207). Redaction receipts are attached under `hashes.redaction`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from platformforge.core.redaction import redact_obj, redact_text_report
from platformforge.live.models import SCHEMA, CollectorReceipt, ObservationEnvelope

_CONTRACT_DIR = Path(__file__).resolve().parents[2] / "contracts"


def _schema(name: str) -> dict[str, Any]:
    p = _CONTRACT_DIR / name
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def validate_envelope(doc: dict[str, Any]) -> list[str]:
    """Schema + semantic validation. Returns error list (empty = ok)."""
    errors: list[str] = []
    schema = _schema("observation.schema.json")
    if schema:
        for e in jsonschema.Draft202012Validator(schema).iter_errors(doc):
            errors.append(f"schema: {e.json_path or '/'} {e.message}")
    if doc.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    cov = (doc.get("coverage") or {}).get("status", "unknown")
    from platformforge.live.models import COVERAGE_STATUSES
    if cov not in COVERAGE_STATUSES:
        errors.append(f"invalid coverage.status: {cov}")
    for i, o in enumerate(doc.get("objects", [])):
        if not isinstance(o, dict) or not o.get("resource_id"):
            errors.append(f"objects[{i}] missing resource_id")
    return errors


def redact_envelope(env: ObservationEnvelope) -> tuple[ObservationEnvelope, dict[str, int]]:
    """§207 — boundary redaction before anything is persisted/emitted.

    Returns (redacted_envelope, redaction_counts). Objects' attributes and
    receipt text are deep-redacted; counts become the redaction receipt.
    """
    counts: dict[str, int] = {}
    redacted_objects = []
    for o in env.objects:
        ro = dict(o)
        txt = json.dumps(ro.get("attributes", {}), default=str)
        _r, c = redact_text_report(txt)
        for k, v in c.items():
            counts[k] = counts.get(k, 0) + v
        ro["attributes"] = redact_obj(ro.get("attributes", {}))
        redacted_objects.append(ro)
    env.objects = redacted_objects
    if env.receipt:
        env.receipt = redact_obj(env.receipt)
    if env.errors:
        env.errors = [redact_obj(e) for e in env.errors]
    return env, counts


def envelope_hash(env: ObservationEnvelope) -> str:
    return env.signature()


def loads(text: str) -> ObservationEnvelope:
    return ObservationEnvelope.from_dict(json.loads(text))


def dumps(env: ObservationEnvelope) -> str:
    return json.dumps(env.to_dict(), indent=2, sort_keys=True, default=str)


def receipt_dict(r: CollectorReceipt) -> dict[str, Any]:
    return r.to_dict()
