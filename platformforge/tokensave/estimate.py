"""Token estimation — honest heuristic.

~4 chars/token is the documented approximation for code+prose in English.
Estimates are ALWAYS labeled `estimated`, never `observed` — provider token
counts are only real when a host transcript supplies them.
"""

from __future__ import annotations

CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str | bytes) -> int:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return max(1, round(len(text) / CHARS_PER_TOKEN)) if text else 0


def estimate_obj(obj) -> int:
    import json
    return estimate_tokens(json.dumps(obj, default=str))
