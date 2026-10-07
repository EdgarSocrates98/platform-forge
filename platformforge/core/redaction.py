"""Secrets redaction — core layer. Applied to anything entering context
packs, receipts, findings messages, or LLM-bound payloads. Never prints a
secret value; replaces with a stable redaction marker."""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Ordered (label, pattern). First match wins per span.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_key", re.compile(r"(?i)aws_secret_access_key['\"\s:=]+[A-Za-z0-9/+=]{40}")),
    ("github_token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{22,}\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b")),
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}")),
    # Delimiter required (:= or quote) — prose like "password policy" must
    # not redact (§88 false-positive guard).
    ("password_kv", re.compile(r"(?i)\b(pass(word)?|passwd|pwd)\s*[:='\"]\s*['\"]?[^\s'\"]{6,}")),
    ("conn_string", re.compile(r"\b(?:postgres|mysql|mongodb|redis|amqp|mssql|sqlserver)://[^\s'\"]+")),
    ("generic_secret_kv", re.compile(r"(?i)\b(api[_-]?key|secret|token)['\"\s:=]+[A-Za-z0-9_\-\.]{16,}")),
]

SECRET_VALUE_KEYS = ("stringData", "data")  # k8s Secret keys whose values are secrets


def _marker(label: str, matched: str) -> str:
    return f"[REDACTED:{label}:{hashlib.sha256(matched.encode()).hexdigest()[:8]}]"


def redact_text(text: str) -> str:
    for label, pat in PATTERNS:
        text = pat.sub(lambda m, label=label: _marker(label, m.group(0)), text)
    return text


def redact_text_report(text: str) -> tuple[str, dict[str, int]]:
    """Redact and return per-label counts for a redaction receipt (§18)."""
    counts: dict[str, int] = {}
    for label, pat in PATTERNS:
        def _sub(m: re.Match[str], label: str = label) -> str:
            counts[label] = counts.get(label, 0) + 1
            return _marker(label, m.group(0))
        text = pat.sub(_sub, text)
    return text, counts


def redaction_receipt(source: str, counts: dict[str, int]) -> dict[str, Any]:
    """§18 — a receipt names what was redacted (labels + counts + hash of
    the pattern set), never the values. """
    return {
        "kind": "pf-redaction-receipt/1",
        "source": str(source),
        "redactions": dict(sorted(counts.items())),
        "total": sum(counts.values()),
        "patterns_sha256": hashlib.sha256(
            "".join(p.pattern for _, p in PATTERNS).encode()).hexdigest()[:16],
    }


def redact_obj(obj: Any) -> Any:
    """Deep-redact strings in dict/list structures."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


def k8s_secret_values(obj: dict[str, Any]) -> dict[str, Any]:
    """Blank out Kubernetes Secret payload fields entirely — base64 values are
    still secrets."""
    out = dict(obj)
    for key in SECRET_VALUE_KEYS:
        if key in out and isinstance(out[key], dict):
            out[key] = {k: "[REDACTED:k8s-secret]" for k in out[key]}
    return out


def contains_secret(text: str) -> bool:
    return any(pat.search(text) for _, pat in PATTERNS)
