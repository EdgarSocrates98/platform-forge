"""Content addressing — the basis of caching, provenance and dedup.

Everything persistent is keyed by sha256 of canonical content, never by
filename or path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj: Any) -> str:
    """Canonical JSON hashing — key order and whitespace normalized."""
    return sha256_text(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    )


def short(content_hash: str, n: int = 12) -> str:
    return content_hash[:n]
