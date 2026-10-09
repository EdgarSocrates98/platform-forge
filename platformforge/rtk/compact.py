"""RTK compaction — turn raw command output into a bounded structure.

The agent consumes the compact result; raw output is preserved out-of-context
in the artifact store and can be expanded by id/section/line range.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from platformforge.core.store import ArtifactStore, ref
from platformforge.rtk.parsers import PARSERS, fallback

MAX_INTERESTING = 200
MAX_LINES_INLINE = 400


@dataclass
class CompactResult:
    command: str
    exit_code: int = 0
    summary: dict[str, Any] = field(default_factory=dict)
    errors: list[Any] = field(default_factory=list)
    warnings: list[Any] = field(default_factory=list)
    changed: list[Any] = field(default_factory=list)
    interesting: list[Any] = field(default_factory=list)
    omitted: int = 0
    raw_artifact: str = ""
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_command(command: str) -> str:
    """Map an argv string to a parser key — longest prefix wins."""
    toks = shlex.split(command) if isinstance(command, str) else list(command)
    if not toks:
        return ""
    base = Path(toks[0]).name
    candidates = [" ".join([base] + toks[1:i]) for i in
                  range(min(3, len(toks)), 0, -1)]
    for cand in candidates:
        if cand in PARSERS:
            return cand
    if base in PARSERS:
        return base
    return ""


def compact_output(command: str, output: str, exit_code: int = 0,
                   store: ArtifactStore | None = None,
                   max_inline_lines: int = MAX_LINES_INLINE) -> CompactResult:
    lines = output.splitlines()
    raw_ref = ""
    if store is not None:
        from platformforge.core.redaction import redact_text
        sha = store.put_text(redact_text(output),
                             meta={"command": command})
        raw_ref = ref(sha)

    key = detect_command(command)
    parser = PARSERS.get(key, fallback)
    parts = parser(lines)

    omitted = max(0, len(lines) - max_inline_lines)
    res = CompactResult(
        command=command, exit_code=exit_code,
        summary=parts.get("summary", {}),
        errors=parts.get("errors", [])[:MAX_INTERESTING],
        warnings=parts.get("warnings", [])[:MAX_INTERESTING],
        changed=parts.get("changed", [])[:MAX_INTERESTING],
        interesting=parts.get("interesting", [])[:MAX_INTERESTING],
        omitted=omitted, raw_artifact=raw_ref,
        truncated=len(lines) > max_inline_lines,
    )
    if res.truncated and not res.raw_artifact:
        res.summary["truncated_note"] = (
            "output truncated; rerun with a store to keep raw artifact")
    return res


def tool_economy_receipt(command: str, res: CompactResult,
                         raw_bytes: int | None = None,
                         expanded_bytes: int = 0) -> dict[str, Any]:
    """§110 — measured tool economy: what the raw was, what the model
    consumed, what expand-on-demand pulled."""
    return {"schema": "platformforge/tool-economy-receipt/v1",
            "command": command,
            "raw_bytes": raw_bytes,
            "compact_bytes": len(compact_json(res).encode()),
            "expanded_bytes": expanded_bytes,
            "raw_artifact": res.raw_artifact or None,
            "truncated": res.truncated,
            "note": "compact is the default surface; raw preserved as "
                    "artifact; expand on demand (§107–109)"}


def expand(store: ArtifactStore, raw_artifact: str,
           start: int | None = None, end: int | None = None,
           pattern: str | None = None) -> dict[str, Any]:
    """Lazy expansion of the preserved raw output."""
    sha = raw_artifact.removeprefix("artifact://sha256/")
    text = store.get_text(sha)
    if text is None:
        return {"error": "artifact not found", "artifact": raw_artifact}
    from platformforge.core.redaction import redact_text
    lines = redact_text(text).splitlines()  # defense in depth on read-back
    if pattern:
        import re
        rx = re.compile(pattern)
        hits = [i for i, l in enumerate(lines) if rx.search(l)]
        win = sorted({j for i in hits for j in
                      range(max(0, i - 2), min(len(lines), i + 3))})
        return {"lines": [f"{j + 1}: {lines[j]}" for j in win],
                "total": len(lines)}
    s, e = start or 0, end if end is not None else len(lines)
    return {"lines": [f"{i + 1}: {l}" for i, l in
                      enumerate(lines[s:e], start=s)], "total": len(lines)}


def compact_json(res: CompactResult) -> str:
    return json.dumps(res.to_dict(), indent=2, default=str)
