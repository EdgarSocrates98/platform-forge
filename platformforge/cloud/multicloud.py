"""Azure + GCP dump analyzers (§175–§176) — provider-observed facts via the
§49 common model. Shape-detected, offline, never calls a provider API.

Accepted:
  azure:  dumps with `value[]` items carrying `type` like
          Microsoft.Network/virtualNetworks, Microsoft.Compute/*,
          Microsoft.Storage/storageAccounts, Microsoft.Web/sites,
          Microsoft.Sql/servers, Microsoft.KeyVault/vaults, or a bare
          `subscriptions`/`tenants` list
  gcp:    dumps with `items[]`/`projects[]` carrying `kind` like
          compute#network, compute#instance, container#cluster,
          storage#bucket, sqladmin#instance, or `folders`/`organizations`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformforge.cloud.common import resource_fact

_AZURE_TYPE_MAP = {
    "microsoft.network/virtualnetworks": "vpc",
    "microsoft.network/subnets": "subnet",
    "microsoft.network/loadbalancers": "load_balancer",
    "microsoft.network/publicipaddresses": "load_balancer",
    "microsoft.compute/virtualmachines": "instance",
    "microsoft.storage/storageaccounts": "bucket",
    "microsoft.sql/servers": "database",
    "microsoft.web/sites": "function",
    "microsoft.keyvault/vaults": "secret",
    "microsoft.container_service/managedclusters": "cluster",
    "microsoft.documentdb/databaseaccounts": "database",
}
_GCP_KIND_MAP = {
    "compute#network": "vpc", "compute#subnetwork": "subnet",
    "compute#instance": "instance", "compute#forwardingrule": "load_balancer",
    "compute#backend": "load_balancer",
    "container#cluster": "cluster", "storage#bucket": "bucket",
    "sqladmin#instance": "database", "iam#serviceAccount": "principal",
    "cloudresourcemanager#project": "project",
    "cloudresourcemanager#folder": "organization",
    "cloudresourcemanager#organization": "organization",
    "cloudfunctions#function": "function",
}


def _az_type(rtype: str) -> str:
    return _AZURE_TYPE_MAP.get(str(rtype).lower(), "component")


def analyze_azure_dump(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
    facts: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            unresolved.append(f.name)
            continue
        items = doc.get("value") or doc.get("items") or (
            [doc] if isinstance(doc, dict) and "type" in doc else [])
        matched = False
        if isinstance(items, list):
            for it in items:
                if not isinstance(it, dict):
                    continue
                rtype = it.get("type", "")
                if not str(rtype).lower().startswith("microsoft."):
                    continue  # not an Azure resource item
                rid = (it.get("id") or it.get("name") or "").rsplit("/", 1)[-1]
                if not rid:
                    continue
                matched = True
                sub = it.get("id", "").split("/resourceGroups/")[0].rsplit("/", 1)[-1] \
                    if "/subscriptions/" in it.get("id", "") else ""
                facts.append(resource_fact(
                    "azure", _az_type(rtype), rid, source=str(f),
                    account=sub, region=it.get("location", ""),
                    attrs={"azure_type": rtype, "resource_group":
                           it.get("id", "").split("/resourceGroups/")[-1]
                           .split("/")[0] if "resourceGroups" in
                           it.get("id", "") else "",
                           "sku": (it.get("sku") or {}).get("name")}))
        for s in doc.get("subscriptions", doc.get("Subscriptions", [])):
            matched = True
            facts.append(resource_fact(
                "azure", "account",
                s.get("subscriptionId") or s.get("id", "?"), source=str(f),
                attrs={"name": s.get("displayName") or s.get("name")}))
        if not matched:
            unresolved.append(f.name)
    return {"facts": facts, "unresolved": unresolved,
            "counts": {"facts": len(facts), "unrecognized": len(unresolved)},
            "provenance": "provider-observed-dump"}


def analyze_gcp_dump(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
    facts: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            unresolved.append(f.name)
            continue
        items = doc.get("items") or doc.get("projects") \
            or ([doc] if "kind" in doc else [])
        matched = False
        for it in items if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            kind = it.get("kind", "")
            rtype = _GCP_KIND_MAP.get(kind)
            if rtype is None and "/" in str(kind):
                rtype = "component"
            rid = it.get("name") or it.get("id") or it.get("selfLink", "?")
            rid = str(rid).rsplit("/", 1)[-1]
            if rtype is None:
                continue
            matched = True
            project = it.get("project") or doc.get("projectId", "")
            facts.append(resource_fact(
                "gcp", rtype, rid, source=str(f),
                account=project, region=it.get("region", "").rsplit("/", 1)[-1],
                attrs={"gcp_kind": kind}))
        for pr in doc.get("projects", []):
            if isinstance(pr, dict):
                matched = True
                facts.append(resource_fact(
                    "gcp", "project", pr.get("projectId", "?"), source=str(f),
                    attrs={"name": pr.get("name"),
                           "lifecycle": pr.get("lifecycleState")}))
        if not matched:
            unresolved.append(f.name)
    return {"facts": facts, "unresolved": unresolved,
            "counts": {"facts": len(facts), "unrecognized": len(unresolved)},
            "provenance": "provider-observed-dump"}
