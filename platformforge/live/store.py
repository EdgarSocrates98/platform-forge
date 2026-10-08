"""ObservationStore — .platformforge/observations/ layout (cycle §206):

    .platformforge/observations/
      index.db                    # sqlite index (§210–211)
      <observation_id>/
        manifest.json             # envelope sans objects
        objects.json              # redacted object list
        receipt.json              # collector receipt
        facts.json                # extracted facts (when computed)
        artifacts/<sha>           # large raw blobs via ArtifactStore refs

Content-addressed hashing dedups identical snapshots (§96); the sqlite
index makes time-range/provider/scope/resource lookups fast (§212).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from platformforge.core.redaction import redact_text
from platformforge.core.store import ArtifactStore
from platformforge.live.envelope import validate_envelope
from platformforge.live.models import ObservationEnvelope

OBS_DIR = ".platformforge/observations"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    provider TEXT, source_type TEXT, captured_at TEXT,
    coverage TEXT, freshness TEXT, scope TEXT, objects INTEGER,
    bytes INTEGER, envelope_hash TEXT, stored_at REAL);
CREATE TABLE IF NOT EXISTS resources (
    observation_id TEXT, resource_id TEXT, resource_type TEXT,
    provider TEXT, cluster TEXT, account TEXT, region TEXT,
    namespace TEXT, name TEXT, content_hash TEXT, lifecycle TEXT);
CREATE INDEX IF NOT EXISTS res_by_id ON resources(resource_id);
CREATE INDEX IF NOT EXISTS res_by_obs ON resources(observation_id);
CREATE INDEX IF NOT EXISTS obs_by_ts ON observations(captured_at);
"""


class ObservationStore:
    def __init__(self, root: str | Path):
        self.root = Path(root) / OBS_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts = ArtifactStore(root)
        self.db = sqlite3.connect(str(self.root / "index.db"))
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # ── write path ───────────────────────────────────────────
    def put(self, env: ObservationEnvelope,
            facts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Validate → redact → persist. Refuses invalid envelopes."""
        doc = env.to_dict()
        errors = validate_envelope(doc)
        if errors:
            return {"refusal": "PF-LIVE-INVALID-ENVELOPE",
                    "unlock": "fix envelope against "
                              "platformforge/observation/v1",
                    "errors": errors}
        odir = self.root / env.observation_id
        odir.mkdir(parents=True, exist_ok=True)
        manifest = {k: v for k, v in doc.items() if k != "objects"}
        (odir / "manifest.json").write_text(json.dumps(
            manifest, indent=2, sort_keys=True, default=str) + "\n")
        (odir / "objects.json").write_text(json.dumps(
            env.objects, indent=2, sort_keys=True, default=str) + "\n")
        if env.receipt:
            (odir / "receipt.json").write_text(json.dumps(
                env.receipt, indent=2, sort_keys=True, default=str) + "\n")
        if facts is not None:
            (odir / "facts.json").write_text(json.dumps(
                {"facts": facts}, indent=2, sort_keys=True,
                default=str) + "\n")
        self._index(env)
        return {"observation_id": env.observation_id,
                "envelope_hash": env.signature(),
                "objects": len(env.objects), "path": str(odir)}

    def _index(self, env: ObservationEnvelope) -> None:
        cov = (env.coverage or {}).get("status", "unknown")
        self.db.execute(
            "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (env.observation_id, env.provider, env.source_type,
             env.captured_at, cov,
             env.freshness_status_at(),
             json.dumps(env.scope, sort_keys=True, default=str),
             len(env.objects), env.bytes, env.signature(), time.time()))
        self.db.execute("DELETE FROM resources WHERE observation_id=?",
                        (env.observation_id,))
        for o in env.objects:
            self.db.execute(
                "INSERT INTO resources VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (env.observation_id, o.get("resource_id", ""),
                 o.get("resource_type", ""), o.get("provider", env.provider),
                 o.get("cluster", ""), o.get("account", ""),
                 o.get("region", ""), o.get("namespace", ""),
                 o.get("name", ""), o.get("content_hash", ""),
                 o.get("lifecycle", "present")))
        self.db.commit()

    # ── read path ────────────────────────────────────────────
    def get(self, observation_id: str) -> ObservationEnvelope | None:
        odir = self.root / observation_id
        mp, op = odir / "manifest.json", odir / "objects.json"
        if not mp.exists():
            return None
        doc = json.loads(mp.read_text())
        doc["objects"] = (json.loads(op.read_text())
                          if op.exists() else [])
        return ObservationEnvelope.from_dict(doc)

    def manifest(self, observation_id: str) -> dict[str, Any] | None:
        p = self.root / observation_id / "manifest.json"
        return json.loads(p.read_text()) if p.exists() else None

    def facts(self, observation_id: str) -> list[dict[str, Any]]:
        p = self.root / observation_id / "facts.json"
        if not p.exists():
            return []
        return json.loads(p.read_text()).get("facts", [])

    def receipts(self, observation_id: str) -> dict[str, Any] | None:
        p = self.root / observation_id / "receipt.json"
        return json.loads(p.read_text()) if p.exists() else None

    def list(self, provider: str | None = None, since: str | None = None,
             until: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        q = ("SELECT observation_id, provider, source_type, captured_at, "
             "coverage, objects, envelope_hash FROM observations WHERE 1=1")
        args: list[Any] = []
        if provider:
            q += " AND provider=?"; args.append(provider)
        if since:
            q += " AND captured_at>=?"; args.append(since)
        if until:
            q += " AND captured_at<=?"; args.append(until)
        q += " ORDER BY captured_at DESC LIMIT ?"; args.append(limit)
        return [dict(zip(("observation_id", "provider", "source_type",
                          "captured_at", "coverage", "objects",
                          "envelope_hash"), r, strict=True))
                for r in self.db.execute(q, args)]

    def find_resource(self, resource_id: str | None = None,
                      cluster: str | None = None, account: str | None = None,
                      resource_type: str | None = None,
                      name: str | None = None,
                      limit: int = 100) -> list[dict[str, Any]]:
        q = ("SELECT observation_id, resource_id, resource_type, cluster, "
             "account, region, namespace, name, lifecycle, content_hash "
             "FROM resources WHERE 1=1")
        args: list[Any] = []
        for col, val in (("resource_id", resource_id), ("cluster", cluster),
                         ("account", account), ("resource_type", resource_type),
                         ("name", name)):
            if val:
                q += f" AND {col}=?"; args.append(val)
        q += " ORDER BY observation_id DESC LIMIT ?"; args.append(limit)
        cols = ("observation_id", "resource_id", "resource_type", "cluster",
                "account", "region", "namespace", "name", "lifecycle",
                "content_hash")
        return [dict(zip(cols, r, strict=True)) for r in self.db.execute(q, args)]

    def latest(self, provider: str | None = None) -> dict[str, Any] | None:
        rows = self.list(provider=provider, limit=1)
        return rows[0] if rows else None

    def status(self) -> dict[str, Any]:
        obs = self.list(limit=50)
        providers: dict[str, dict[str, Any]] = {}
        for o in obs:
            p = providers.setdefault(o["provider"], {
                "observations": 0, "last": "", "coverage": set()})
            p["observations"] += 1
            p["last"] = max(p["last"], o["captured_at"])
            p["coverage"].add(o["coverage"])
        for p in providers.values():
            p["coverage"] = sorted(p["coverage"])
        return {"observations": len(obs), "providers": providers,
                "store": str(self.root),
                "artifact_store": self.artifacts.stats()}


def redact_for_output(text: str) -> str:
    """Boundary helper: nothing leaving the store carries raw secrets."""
    return redact_text(text)
