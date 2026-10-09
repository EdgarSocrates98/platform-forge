"""Pointer-based context refs (§59, §62) — `context://sha256/<hash>` and
the typed evidence/fact/graph pointers. Agents receive refs and expand on
demand (§63–64) instead of receiving duplicated content."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

REF_SCHEMES = ("context", "evidence", "fact", "graph", "artifact",
               "knowledge", "finding")


def _hash(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str).encode()
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class ContextRef:
    """§59 — a content-addressed pointer. `uri` is the wire form."""
    scheme: str                      # REF_SCHEMES
    digest: str
    hint: str = ""                   # what the ref points at (for budgets)

    def __post_init__(self) -> None:
        if self.scheme not in REF_SCHEMES:
            raise ValueError(f"unknown ref scheme {self.scheme!r}")
        if len(self.digest) != 64:
            raise ValueError("ref digest must be sha256 (64 hex)")

    @property
    def uri(self) -> str:
        return f"{self.scheme}://sha256/{self.digest}"

    @classmethod
    def of(cls, scheme: str, payload: Any, hint: str = "") -> ContextRef:
        return cls(scheme=scheme, digest=_hash(payload), hint=hint)

    @classmethod
    def parse(cls, uri: str) -> ContextRef:
        scheme, _, rest = uri.partition("://")
        algo, _, digest = rest.partition("/")
        if algo != "sha256":
            raise ValueError(f"unsupported ref algo {algo!r}")
        return cls(scheme=scheme, digest=digest)
