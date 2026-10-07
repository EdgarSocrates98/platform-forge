"""Artifact-type detection + dispatch for `collect`.

Signals are intentionally cheap and deterministic: filename patterns first,
then document shape. Every file under the collected path is accounted for —
`detected` or `undetected` — so nothing is silently dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

_IGNORE = {".git", ".platformforge", ".venv", "node_modules", "__pycache__"}


def _looks_k8s(doc: dict) -> bool:
    return isinstance(doc.get("apiVersion"), str) and "kind" in doc


def _shape_domain(path: Path, doc: Any) -> str | None:
    """Document-shape heuristics, ordered most-specific first."""
    if isinstance(doc, dict):
        if _looks_k8s(doc):
            if doc.get("kind") in ("Application", "AppProject") \
                    and "argoproj.io" in str(doc.get("apiVersion")):
                return "gitops"
            return "k8s"
        if doc.get("format_version") or "terraform_version" in doc:
            return "plan" if "planned_values" in doc else "state"
        # AWS CLI dumps: top-level keys like Vpcs/Subnets/Roles/Accounts
        if set(doc) & {"Vpcs", "Subnets", "InternetGateways", "NatGateways",
                       "RouteTables", "SecurityGroups", "LoadBalancers",
                       "HostedZones", "Roles", "Policies", "Users",
                       "PolicyVersion", "Organization", "Accounts",
                       "OrganizationalUnits", "Reservations", "Functions",
                       "Clusters", "Buckets", "DBInstances", "QueueUrls",
                       "Queues", "Topics", "TableNames"}:
            return "cloud-aws"
        if "Statement" in doc:
            return "iam"
        if doc.get("bomFormat") == "CycloneDX" \
                or doc.get("spdxVersion"):
            return "sbom"
        if "predicateType" in doc or "provenance" in doc:
            return "supply"
        if any(k in doc for k in ("BillingAccountId", "ResourceId",
                                  "ServiceName")) and "Charge" in str(doc)[:2000]:
            return "finops"
    if isinstance(doc, dict) and isinstance(doc.get("items"), list) \
            and all(_looks_k8s(i) for i in doc["items"]
                    if isinstance(i, dict)):
        return "k8s"
    return None


def detect_file(path: Path) -> str | None:
    """Best-effort domain for a single artifact file."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".tf":
        return "iac"
    if name in ("policy.json", "trust.json") or name.endswith(".policy.json"):
        return "iam"
    if name in ("sbom.json", "sbom.cdx.json") or "sbom" in name:
        return "sbom"
    if name in ("billing.json", "costs.json", "focus.csv", "billing.csv") \
            or "billing" in name:
        return "finops"
    if name in ("supply.json", "provenance.json", "attestation.json") \
            or "in-toto" in name:
        return "supply"
    if name in ("slo.yaml", "slo.yml"):
        return "slo"
    if name in ("otel.yaml", "otel.yml") or "otel" in name:
        return "otel"
    if suffix not in (".json", ".yaml", ".yml"):
        return None
    try:
        doc = json.loads(path.read_text()) if suffix == ".json" \
            else yaml.safe_load(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError,
            yaml.YAMLError):
        return None
    if isinstance(doc, list):
        doc = next((d for d in doc if isinstance(d, dict)), None)
        if doc is None:
            return None
    return _shape_domain(path, doc)


def collect(path: str | Path) -> dict[str, Any]:
    """Walk path, detect artifact types, run matching analyzers, merge facts.

    Returns {facts, detected: {domain: [files]}, undetected: [files]}.
    Read-only: this never touches a provider.
    """
    root = Path(path)
    files = ([root] if root.is_file() else
             sorted(p for p in root.rglob("*")
                    if p.is_file() and not _IGNORE.intersection(p.parts)))
    detected: dict[str, list[str]] = {}
    undetected: list[str] = []
    buckets: dict[str, list[Path]] = {}
    for f in files:
        dom = detect_file(f)
        if dom is None:
            undetected.append(str(f))
        else:
            detected.setdefault(dom, []).append(str(f))
            buckets.setdefault(dom, []).append(f)

    facts: list[dict[str, Any]] = []
    from platformforge import iac, security
    from platformforge.finops import cost_facts
    for dom, paths in buckets.items():
        try:
            if dom == "iac":
                facts += iac.analyze_hcl(paths[0].parent)["facts"]
            elif dom in ("plan", "state"):
                fn = (iac.analyze_plan if dom == "plan" else
                      iac.analyze_state)
                for p in paths:
                    facts += fn(str(p))["facts"]
            elif dom == "iam":
                for p in paths:
                    facts += security.analyze_iam_policy(str(p))["facts"]
            elif dom == "sbom":
                facts += security.analyze_sbom(str(paths[0]))["facts"]
            elif dom == "supply":
                facts += security.analyze_supply(str(paths[0]))["facts"]
            elif dom == "finops":
                facts += cost_facts(str(paths[0]))["facts"]
            elif dom == "cloud-aws":
                from platformforge.cloud import analyze_aws_dump
                for p in paths:
                    facts += analyze_aws_dump(str(p))["facts"]
            elif dom in ("k8s", "gitops"):
                # dir-level domains: run once over the common parent
                parent = paths[0].parent
                mod = ("platformforge.k8s:analyze_k8s" if dom == "k8s"
                       else "platformforge.cicd:analyze_gitops")
                m, fn = mod.split(":")
                import importlib
                facts += getattr(importlib.import_module(m), fn)(parent)["facts"]
        except Exception as exc:  # noqa: BLE001 — analyzer failure degrades to undetected, not a crash
            undetected.append(f"{dom}:{exc!r}")
    # secrets is a baseline dir-scan over everything collected — dumps are
    # exactly where leaked credentials surface
    from platformforge.security import scan_secrets
    facts += scan_secrets(root)["facts"]
    return {"facts": facts, "detected": detected, "undetected": undetected}
