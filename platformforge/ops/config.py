"""Cycle 4 phase V — `.platformforge/config.yaml` schema + migrations.

Config domains: autonomy, policies, approval, operations, retention,
live, economy. Loading never crashes on unknown keys — they are
reported; bad versions migrate forward or refuse with PF-OPS-CONFIG-*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_SCHEMA_VERSION = 2
CONFIG_PATH = ".platformforge/config.yaml"

# every domain gets safe deterministic defaults — absence ≠ permissive
DEFAULTS: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "autonomy": {"max": "A4",
                 "a5_environments": ["lab"],
                 "per_capability": {}},
    "policies": {"files": [], "shadow_default": False,
                 "external_adapters": []},
    "approval": {"default_ttl_s": 86400,
                 "required_for_risk": ["R3", "R4", "R5"],
                 "break_glass": {"enabled": True,
                                 "max_ttl_s": 3600,
                                 "post_review_required": True},
                 "actor_kinds": ["human"]},
    "operations": {"default_dry_run": True,
                   "max_observation_age_s": 900,
                   "store": ".platformforge/operations",
                   "require_execute_flag": True},
    "retention": {"ledger_days": 365, "observation_days": 90,
                  "telemetry": "local-only"},
    "live": {"budgets": {"calls_per_collect": 50,
                         "window_s": 300},
             "offline_default": True},
    "economy": {"enabled": True, "currency": "USD",
                "budget_increase_max": None},
    "rbac": {"roles": {"viewer": {"autonomy": "A1"},
                       "operator": {"autonomy": "A4"},
                       "owner": {"autonomy": "A4"},
                       "oncall": {"autonomy": "A4",
                                  "break_glass": True}}},
}

_MIGRATIONS = {}


def _migrate_0_to_1(raw: dict[str, Any]) -> dict[str, Any]:
    """v0 (no schema_version) → v1: wrap bare keys into domains."""
    out = dict(raw)
    if "approval_ttl" in out:
        out.setdefault("approval", {})["default_ttl_s"] = \
            out.pop("approval_ttl")
    out["schema_version"] = 1
    return out


def _migrate_1_to_2(raw: dict[str, Any]) -> dict[str, Any]:
    """v1 → v2: rbac domain added; telemetry pinned to local-only."""
    out = dict(raw)
    out.setdefault("rbac", dict(DEFAULTS["rbac"]))
    out.setdefault("retention", {})["telemetry"] = \
        out.get("retention", {}).get("telemetry", "local-only")
    out["schema_version"] = 2
    return out


_MIGRATIONS.update({0: _migrate_0_to_1, 1: _migrate_1_to_2})


def load_config(path: str | Path | None = None,
                root: str | Path | None = None) -> dict[str, Any]:
    """Load + migrate + merge with defaults. Missing file → defaults
    (offline-first: no config is valid config)."""
    p = Path(path) if path else \
        Path(root or ".") / CONFIG_PATH
    if not p.exists():
        return {"config": dict(DEFAULTS), "source": "defaults",
                "migrated": []}
    try:
        raw = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        return {"refusal": "PF-OPS-CONFIG-PARSE",
                "unlock": f"fix YAML: {e}"}
    if not isinstance(raw, dict):
        return {"refusal": "PF-OPS-CONFIG-PARSE",
                "unlock": "config must be a mapping"}

    migrated: list[int] = []
    v = raw.get("schema_version", 0)
    if v > CONFIG_SCHEMA_VERSION:
        return {"refusal": "PF-OPS-CONFIG-VERSION",
                "unlock": f"schema_version {v} > supported "
                          f"{CONFIG_SCHEMA_VERSION} — upgrade "
                          "platformforge"}
    while v < CONFIG_SCHEMA_VERSION:
        raw = _MIGRATIONS[v](raw)
        migrated.append(v)
        v = raw.get("schema_version", v + 1)

    cfg = _deep_merge(dict(DEFAULTS), raw)
    unknown = sorted(set(raw) - set(DEFAULTS) - {"schema_version"})
    return {"config": cfg, "source": str(p), "migrated": migrated,
            "unknown_keys": unknown}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def validate_config(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Semantic validation — refuse unsafe ceilings."""
    v = []
    amax = cfg.get("autonomy", {}).get("max", "A4")
    if amax in ("A5", "A6"):
        envs = cfg.get("autonomy", {}).get("a5_environments", [])
        if amax == "A6" or "prod" in envs:
            v.append({"refusal": "PF-OPS-CONFIG-AUTONOMY",
                      "unlock": "A6 is a non-goal; A5 may never "
                                "include prod"})
    for f_ in cfg.get("policies", {}).get("files", []):
        pass   # existence checked by host, not core
    return v
