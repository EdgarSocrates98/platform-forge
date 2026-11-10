"""Read-only platform operations projection for federated Obsidian notes."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

import yaml

_SENSITIVE = ("secret", "token", "password", "credential", "access_key", "session_key")
_SENSITIVE_TEXT = re.compile(
    r"(?i)(\b(?:secret|token|password|credential|access[_-]?key|session[_-]?key)\s*[:=]\s*)([^\s,;]+)"
)


def _safe(value: Any, key: str = "") -> Any:
    if any(marker in key.lower() for marker in _SENSITIVE):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _safe(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(item, key) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_TEXT.sub(r"\1[REDACTED]", value)
    return value


def _section(title: str, values: Any) -> list[str]:
    safe = _safe(values)
    if safe in (None, "", [], {}):
        return [f"## {title}", "- None reported", ""]
    return [f"## {title}", "```yaml", yaml.safe_dump(safe, sort_keys=True, allow_unicode=True).rstrip(), "```", ""]


def build_obsidian_operations_review(
    *,
    title: str,
    summary: str,
    workspace: str,
    vault_id: str,
    incident: dict[str, Any] | None = None,
    postmortem: dict[str, Any] | None = None,
    runbooks: list[Any] | None = None,
    terraform: list[Any] | None = None,
    kubernetes: list[Any] | None = None,
    adrs: list[Any] | None = None,
    security_review: list[Any] | None = None,
    note_path: str = "platform-operations/operations-review.md",
    confidence: str = "unknown",
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_title = str(_safe(title.strip() or "Platform operations review"))
    safe_summary = str(_safe(summary.strip()))
    metadata = _safe({
        "type": "platform-operations-review",
        "source": "platform-forge",
        "classification": "internal",
        "confidence": confidence,
        "provenance": provenance or {},
    })
    lines = ["---", yaml.safe_dump(metadata, sort_keys=True, allow_unicode=True).rstrip(), "---",
             f"# {safe_title}", "", safe_summary, ""]
    lines += _section("Incident", incident)
    lines += _section("Postmortem", postmortem)
    lines += _section("Runbooks", runbooks)
    lines += _section("Terraform", terraform)
    lines += _section("Kubernetes", kubernetes)
    lines += _section("ADRs", adrs)
    lines += _section("Security review", security_review)
    content = "\n".join(lines).rstrip() + "\n"
    return {
        "schema": "theforge/ObsidianNoteDraft/v1",
        "version": "v1",
        "workspace": workspace,
        "vault_id": vault_id,
        "path": note_path,
        "source": "platform-forge",
        "classification": "internal",
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "outcome": "projected",
        "provenance": {"adapter": "platform-forge", **_safe(provenance or {})},
        "content": content,
        "warnings": [],
        "unresolved": [],
    }


def to_obsidian_note_ref(draft: dict[str, Any]) -> dict[str, Any]:
    """Project a body-bearing draft to the canonical body-free ref."""
    if draft.get("schema") != "theforge/ObsidianNoteDraft/v1" or not isinstance(
        draft.get("content"), str
    ):
        raise ValueError("expected theforge/ObsidianNoteDraft/v1 with Markdown content")
    return {key: value for key, value in draft.items() if key != "content"} | {
        "schema": "theforge/ObsidianNoteRef/v1"
    }


__all__ = ["build_obsidian_operations_review", "to_obsidian_note_ref"]
