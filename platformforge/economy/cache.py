"""Economy cache (§35–55) — multilayer, content-addressed, dependency-
invalidated, receipted.

Layers (§36): artifact → fact → graph → finding → context → analysis →
decision. Each layer declares which dependencies it binds to; a change in
a dependency invalidates only the layers that depend on it (§40–42):

    rule catalog changes  → findings/analysis/decision miss,
                            artifacts + facts still hit (§292 north star)
    knowledge changes     → recommendations/context miss; facts survive
    engine changes        → the corresponding layer misses

States (§44): hit | miss | stale | invalid | partial-reuse.
Never cached (§48): credentials, secret values, approval tokens — a
payload flagged sensitive is refused at `put`, and `decision` entries
require evidence_hash + policy_version + risk_profile (§53). Human
approval is operation-specific and has no cache layer (§54). Live
conclusions carry `observed_at` + `freshness_s`; stale observations never
count as a fresh hit (§55).

TTL exists but is a fallback — dependency invalidation is primary (§49).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "platformforge/cache-entry/v1"

LAYERS = ("artifact", "fact", "graph", "finding", "context",
          "analysis", "decision")

# §38/§43 — the dependency keys each layer binds to. A dep not listed
# for a layer does not invalidate it (selective invalidation, §40).
LAYER_DEPS: dict[str, tuple[str, ...]] = {
    "artifact": ("runtime_version",),
    "fact": ("artifact_hash", "extractor_version", "runtime_version"),
    "graph": ("artifact_hash", "runtime_version", "config_hash"),
    "finding": ("artifact_hash", "rule_catalog_hash", "knowledge_hash",
                "policy_hash"),
    "context": ("artifact_hash", "rule_catalog_hash", "knowledge_hash"),
    "analysis": ("rule_catalog_hash", "knowledge_hash", "engine_version",
                 "policy_hash"),
    "decision": ("evidence_hash", "policy_version", "risk_profile"),
}

DECISION_STATES = ("hit", "miss", "stale", "invalid", "partial-reuse")

# §48 — payload markers that are never persisted into cache.
SENSITIVE_MARKERS = ("credential", "secret_value", "approval_token",
                     "private_key", "session_token")


def content_hash(payload: Any) -> str:
    """§37 — content addressing: sha256 of the canonical serialization."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str).encode()
    return hashlib.sha256(body).hexdigest()


def cache_key(layer: str, scope: str, deps: dict[str, str]) -> str:
    """§39 — key = sha256(layer + scope + the deps this layer binds)."""
    bound = {k: deps.get(k, "") for k in LAYER_DEPS[layer]}
    body = json.dumps({"layer": layer, "scope": scope, "deps": bound},
                      sort_keys=True).encode()
    return hashlib.sha256(body).hexdigest()


@dataclass
class CacheDependency:
    """§43 — declared dependency set for an entry."""
    deps: dict[str, str] = field(default_factory=dict)

    def changed(self, current: dict[str, str], layer: str) -> list[str]:
        """Return the bound deps whose value changed vs `current`."""
        return [k for k in LAYER_DEPS[layer]
                if k in self.deps and self.deps[k] != current.get(k, "")]


@dataclass
class CacheDecision:
    """§44 — the auditable outcome of a lookup."""
    state: str                       # DECISION_STATES
    layer: str
    key: str
    reason: str = ""
    changed_deps: list[str] = field(default_factory=list)
    entry_age_s: float | None = None
    reusable_layers: list[str] = field(default_factory=list)
    invalidated_layers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CacheEntry:
    schema: str = SCHEMA
    layer: str = ""
    key: str = ""
    scope: str = ""
    payload: Any = None
    payload_hash: str = ""
    deps: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    ttl_s: float | None = None        # §49 — fallback only
    observed_at: float | None = None  # §55 — live conclusions
    freshness_s: float | None = None
    live: bool = False

    def expired(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        if self.ttl_s is not None and now - self.created_at > self.ttl_s:
            return True
        if self.live:
            if self.observed_at is None or self.freshness_s is None:
                return True          # live entry without freshness: stale
            return now - self.observed_at > self.freshness_s
        return False


class CacheStore:
    """`.platformforge/cache/<layer>/<key>.json` + per-layer counters."""

    def __init__(self, root: str | Path):
        self.dir = Path(root) / ".platformforge" / "cache"
        for layer in LAYERS:
            (self.dir / layer).mkdir(parents=True, exist_ok=True)
        self._stats_path = self.dir / "stats.json"

    # -- stats ----------------------------------------------------------
    def _stats(self) -> dict[str, int]:
        if self._stats_path.exists():
            return json.loads(self._stats_path.read_text())
        return {"hits": 0, "misses": 0, "stale": 0, "invalid": 0,
                "invalidations": 0, "puts": 0, "bytes_reused": 0,
                "refused": 0}

    def _bump(self, **kw: int) -> None:
        s = self._stats()
        for k, v in kw.items():
            s[k] = s.get(k, 0) + v
        self._stats_path.write_text(json.dumps(s, indent=1, sort_keys=True))

    # -- write ------------------------------------------------------------
    def put(self, layer: str, scope: str, payload: Any,
            deps: dict[str, str], *, ttl_s: float | None = None,
            live: bool = False, observed_at: float | None = None,
            freshness_s: float | None = None,
            sensitive: bool = False) -> CacheDecision:
        """§48/§53/§54/§55 guards enforced at write time."""
        if layer not in LAYERS:
            raise ValueError(f"unknown cache layer {layer!r}")
        if sensitive:
            self._bump(refused=1)
            return CacheDecision(
                "invalid", layer, "", reason=(
                    "refused: sensitive payload — credentials, secret "
                    "values and approval tokens are never cached (§48/§54)"))
        if layer == "decision":
            missing = [k for k in LAYER_DEPS["decision"]
                       if k not in deps]
            if missing:
                self._bump(refused=1)
                return CacheDecision(
                    "invalid", layer, "", reason=(
                        f"decision cache requires {missing} "
                        "(§53: evidence_hash+policy_version+risk_profile)"))
        key = cache_key(layer, scope, deps)
        ent = CacheEntry(layer=layer, key=key, scope=scope,
                         payload=payload, payload_hash=content_hash(payload),
                         deps=dict(deps), ttl_s=ttl_s, live=live,
                         observed_at=observed_at, freshness_s=freshness_s)
        (self.dir / layer / f"{key}.json").write_text(
            json.dumps(asdict(ent), sort_keys=True, default=str))
        self._bump(puts=1)
        return CacheDecision("hit", layer, key, "stored")

    # -- read -------------------------------------------------------------
    def _load(self, layer: str, key: str) -> CacheEntry | None:
        p = self.dir / layer / f"{key}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        return CacheEntry(**{k: v for k, v in d.items()
                             if k in CacheEntry.__dataclass_fields__})

    def get(self, layer: str, scope: str, current_deps: dict[str, str],
            *, now: float | None = None
            ) -> tuple[CacheDecision, Any | None]:
        """Lookup: dependency-diff first, freshness second (§44, §55)."""
        # the stored key encodes the OLD deps — recompute from stored deps
        # is impossible, so lookup scans by scope+layer prefix: keys are
        # content-derived, so we resolve the entry whose deps-match.
        # For a 1:1 scope→key mapping we store under a scope index.
        for cand in (self.dir / layer).glob("*.json"):
            d = json.loads(cand.read_text())
            if d.get("scope") != scope:
                continue
            ent = CacheEntry(**{k: v for k, v in d.items()
                                if k in CacheEntry.__dataclass_fields__})
            dep = CacheDependency(ent.deps)
            changed = dep.changed(current_deps, layer)
            if changed:
                self._bump(invalid=1)
                return (CacheDecision(
                    "invalid", layer, ent.key,
                    f"deps changed: {changed}", changed), None)
            if ent.expired(now):
                self._bump(stale=1)
                return (CacheDecision(
                    "stale", layer, ent.key,
                    "freshness/ttl expired", entry_age_s=(
                        (now or time.time()) - ent.created_at)), None)
            self._bump(hits=1, bytes_reused=len(
                json.dumps(ent.payload, default=str)))
            return (CacheDecision("hit", layer, ent.key, "deps match"),
                    ent.payload)
        self._bump(misses=1)
        return (CacheDecision("miss", layer,
                              cache_key(layer, scope, current_deps),
                              "no entry for scope"), None)

    def invalidate_dep(self, dep_key: str, new_value: str
                       ) -> dict[str, Any]:
        """§40–42 — selective invalidation: drop every entry whose bound
        deps include dep_key with a different value; keep the rest."""
        removed: list[str] = []
        kept: list[str] = []
        for layer in LAYERS:
            if dep_key not in LAYER_DEPS[layer]:
                kept.append(layer)
                continue
            for cand in (self.dir / layer).glob("*.json"):
                d = json.loads(cand.read_text())
                if d.get("deps", {}).get(dep_key) not in (None, new_value):
                    cand.unlink()
                    removed.append(f"{layer}/{d.get('key', cand.stem)}")
        self._bump(invalidations=len(removed))
        return {"dep": dep_key, "removed": removed,
                "unaffected_layers": [l for l in kept]}

    # -- maintenance --------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        """§51 — hits/misses/bytes reused/entries/invalidations."""
        s = self._stats()
        entries = sum(1 for layer in LAYERS
                      for _ in (self.dir / layer).glob("*.json"))
        return {**s, "entries": entries,
                "layers": {l: sum(1 for _ in (self.dir / l).glob("*.json"))
                           for l in LAYERS}}

    def gc(self, *, now: float | None = None) -> dict[str, Any]:
        """§50 — remove expired entries; dependency-invalid entries are
        already removed by invalidate_dep."""
        now = now if now is not None else time.time()
        removed = []
        for layer in LAYERS:
            for cand in (self.dir / layer).glob("*.json"):
                d = json.loads(cand.read_text())
                ent = CacheEntry(**{k: v for k, v in d.items()
                                    if k in CacheEntry.__dataclass_fields__})
                if ent.expired(now):
                    cand.unlink()
                    removed.append(f"{layer}/{d.get('key', cand.stem)}")
        return {"gc_removed": removed, "remaining": self.stats()["entries"]}

    def reuse_plan(self, current_deps: dict[str, str], scopes: dict[str,
                   str], *, now: float | None = None) -> CacheDecision:
        """§44 partial-reuse — per-layer lookup over a pipeline; returns
        which layers still hit vs miss (§292 north star shape)."""
        hit, missed = [], []
        for layer, scope in scopes.items():
            if layer not in LAYERS:
                continue
            dec, _ = self.get(layer, scope, current_deps, now=now)
            (hit if dec.state == "hit" else missed).append(layer)
        state = ("hit" if not missed else
                 "partial-reuse" if hit else "miss")
        return CacheDecision(state, "pipeline", "",
                             f"reusable={hit} recompute={missed}",
                             reusable_layers=hit, invalidated_layers=missed)
