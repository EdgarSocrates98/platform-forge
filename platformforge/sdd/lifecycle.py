"""SDD lifecycle: DISCOVER → DEFINE → DESIGN → CONTRACT → PLAN → BUILD →
REVIEW → VERIFY → SHIP → LEARN. Every phase is a versioned artifact with an
upstream content hash; a changed phase marks everything downstream stale.

Ship gates refuse on: failed verification, missing evidence, stale upstream,
unresolved critical findings, failed security gate, absent risk acceptance.
Overrides always emit a receipt — never silent.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from platformforge.core.hashing import sha256_file

PHASES = ["discover", "define", "design", "contract", "plan", "build",
          "review", "verify", "ship", "learn"]
ARTIFACT_EXT = {"build": ".json", "verify": ".json", "ship": ".md",
                "learn": ".md"}
DEFAULT_EXT = ".md"
GATE_FAILURES = (
    "required_test_failed", "evidence_missing", "upstream_hash_stale",
    "critical_finding_unresolved", "security_gate_failed",
    "risk_acceptance_absent",
)
SDD_ROOT = ".platformforge/sdd"

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def artifact_name(phase: str) -> str:
    return phase + ARTIFACT_EXT.get(phase, DEFAULT_EXT)


@dataclass
class SddArtifact:
    feature: str
    phase: str
    path: Path
    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    exists: bool = False

    @property
    def status(self) -> str:
        return self.meta.get("status", "missing")

    @property
    def upstream(self) -> dict[str, Any]:
        return self.meta.get("upstream", {})


def _front(meta: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body


def _parse(text: str) -> tuple[dict[str, Any], str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


class SDDProject:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.base = self.root / SDD_ROOT

    # ── artifact io ───────────────────────────────────────────
    def _feature_dir(self, feature: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", feature):
            raise ValueError(f"invalid feature name: {feature!r}")
        return self.base / feature

    def artifact(self, feature: str, phase: str) -> SddArtifact:
        p = self._feature_dir(feature) / artifact_name(phase)
        if not p.exists():
            return SddArtifact(feature, phase, p, exists=False)
        if p.suffix == ".json":
            meta = {"sdd": 1, "phase": phase}
            doc = yaml.safe_load(p.read_text())
            if isinstance(doc, dict):
                meta = {**meta, **doc.pop("meta", doc)}
                return SddArtifact(feature, phase, p, meta=meta,
                                   body="", exists=True)
            return SddArtifact(feature, phase, p, meta=meta, exists=True)
        meta, body = _parse(p.read_text())
        return SddArtifact(feature, phase, p, meta=meta, body=body, exists=True)

    def write_artifact(self, feature: str, phase: str,
                       body: str | dict[str, Any],
                       meta_extra: dict[str, Any] | None = None) -> SddArtifact:
        d = self._feature_dir(feature)
        d.mkdir(parents=True, exist_ok=True)
        idx = PHASES.index(phase)
        upstream = {}
        if idx > 0:
            prev = self.artifact(feature, PHASES[idx - 1])
            if prev.exists:
                upstream = {"path": prev.path.name,
                            "sha256": sha256_file(prev.path)}
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        meta = {"sdd": 1, "feature": feature, "phase": phase,
                "status": "ready", "created_at": now, "updated_at": now,
                "upstream": upstream, "evidence": [], "risks": [],
                "owners": [], **(meta_extra or {})}
        p = d / artifact_name(phase)
        existing = self.artifact(feature, phase)
        if existing.exists and existing.meta.get("created_at"):
            meta["created_at"] = existing.meta["created_at"]
        if p.suffix == ".json":
            doc = {"meta": meta}
            if isinstance(body, dict):
                doc.update(body)
            p.write_text(yaml.safe_dump(doc, sort_keys=False))
        else:
            text = body if isinstance(body, str) else yaml.safe_dump(body)
            p.write_text(_front(meta, text))
        return self.artifact(feature, phase)

    # ── status & cascade ──────────────────────────────────────
    def status(self, feature: str) -> dict[str, Any]:
        stale = self._stale_phases(feature)
        phases = []
        for ph in PHASES:
            a = self.artifact(feature, ph)
            st = "missing"
            if a.exists:
                st = "stale" if ph in stale else a.status
            phases.append({"phase": ph, "status": st,
                           "file": artifact_name(ph)})
        return {"feature": feature, "phases": phases, "stale": sorted(stale)}

    def _stale_phases(self, feature: str) -> set[str]:
        """Once a phase's upstream hash mismatches, everything downstream is
        stale — the cascade never pretends nothing changed."""
        stale: set[str] = set()
        propagate = False
        for i, ph in enumerate(PHASES):
            a = self.artifact(feature, ph)
            if not a.exists:
                continue
            if propagate:
                stale.add(ph)
                continue
            if i == 0:
                continue
            up = a.upstream
            prev = self.artifact(feature, PHASES[i - 1])
            if (prev.exists and up.get("sha256")
                    and up["sha256"] != sha256_file(prev.path)):
                stale.add(ph)
                propagate = True
        return stale

    # ── gates ─────────────────────────────────────────────────
    def check(self, feature: str) -> dict[str, Any]:
        """Multidimensional validation — see sdd/gates.check()."""
        from .gates import check as _check
        out = _check(self, feature)
        out["phases"] = out.get("phases") or self.status(feature)["phases"]
        return out

    def stamp(self, feature: str, phase: str | None = None) -> dict[str, Any]:
        """Re-seal upstream hash(es) after intentional change.

        Hash stamping is *integrity binding*, not approval: it never
        promotes `ship`/`learn` and never demotes `accepted`. Status
        transitions are a separate decision (`write_artifact`/`set_status`).
        """
        stamped = []
        targets = [phase] if phase else PHASES[1:]
        for ph in targets:
            a = self.artifact(feature, ph)
            if not a.exists or ph == PHASES[0]:
                continue
            prev = self.artifact(feature, PHASES[PHASES.index(ph) - 1])
            if prev.exists:
                a.meta["upstream"] = {"path": prev.path.name,
                                      "sha256": sha256_file(prev.path)}
                if a.meta.get("status") not in ("accepted", "done"):
                    a.meta["status"] = "ready"
                a.meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                     time.gmtime())
                if a.path.suffix == ".json":
                    doc = yaml.safe_load(a.path.read_text()) or {}
                    doc["meta"] = a.meta
                    a.path.write_text(yaml.safe_dump(doc, sort_keys=False))
                else:
                    a.path.write_text(_front(a.meta, a.body))
                stamped.append(ph)
        return {"stamped": stamped, "status": self.status(feature)}

    # ── ship gate ─────────────────────────────────────────────
    def ship_gate(self, feature: str, verify: dict[str, Any] | None = None,
                  findings: list[dict[str, Any]] | None = None,
                  risk_accepted: bool = False) -> dict[str, Any]:
        """Evidence-backed ship evaluation — see sdd/gates.ship_gate()."""
        from .gates import ship_gate as _gate
        return _gate(self, feature, verify, findings, risk_accepted)

    def ship(self, feature: str, verify: dict[str, Any] | None = None,
             findings: list[dict[str, Any]] | None = None,
             risk_accepted: bool = False, override: bool = False,
             override_reason: str = "", actor: str = "") -> dict[str, Any]:
        gate = self.ship_gate(feature, verify, findings, risk_accepted)
        if not gate["allowed"] and not override:
            return {**gate, "shipped": False}
        meta_extra: dict[str, Any] = {}
        if not gate["allowed"] and override:
            from .gates import UNDISPENSABLE, override_receipt
            hard = [f for f in gate["failures"]
                    if f.split(":")[0] in UNDISPENSABLE]
            if hard:
                return {**gate, "shipped": False,
                        "override_denied": hard,
                        "reason": "undispensable failures cannot be overridden"}
            if not override_reason or not override_reason.strip():
                return {**gate, "shipped": False,
                        "override_denied": ["override_reason_empty"]}
            meta_extra["override_receipt"] = override_receipt(
                feature=feature, gate="ship",
                failures=gate["failures"], reason=override_reason,
                actor=actor or "cli")
        self.write_artifact(feature, "ship", "Shipped.\n", meta_extra)
        return {**gate, "shipped": True,
                "override": bool(meta_extra)}
