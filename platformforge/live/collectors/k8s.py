"""Kubernetes live collector — read-only, metadata-first (cycle §22–§31).

Design:
- transport is injected: `transport(args) -> (rc, stdout, stderr)`. The
  kubectl subprocess boundary lives in `k8s_transport.py`; tests inject
  fakes — the collector core never touches the network.
- metadata-first: full objects are fetched over the wire (kubectl has
  no PartialObjectMetadata path), but the persisted envelope only keeps
  the projected attribute subset — token economy at our side (§144).
- pagination: `--chunk-size` + `--continue`, every page ledgered.
- watch: resourceVersion cursors; 410 Gone/Expired → resnapshot, never
  silent gap (§27–28); watch failures are evidence, not errors hidden.
- coverage: per-resource-type; Forbidden → permission-limited +
  denied_scopes, never a global failure (§8, §17).
- read-only: only get/list/watch verbs; `required_rbac` emits a minimal
  ClusterRole — never cluster-admin (§31).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from platformforge.live.budget import ObservationBudget, ProviderCallLedger
from platformforge.live.models import (
    CollectorReceipt,
    Coverage,
    ObservationEnvelope,
    ObservationScope,
    ObservedObject,
    iso,
    now_iso,
    parse_ts,
)

_SENSITIVE_ANNOTATION = re.compile(
    r"(password|token|secret|private[-_.]?key|credential)", re.IGNORECASE)

Transport = Callable[[list[str]], tuple[int, str, str]]

COLLECTOR_VERSION = "k8s-collector/0.3.0"

# §24 — default inventory set; extendable via scope.resource_types.
# secrets: metadata-only (data stripped at projection), still useful
# for drift/inventory without payload exposure.
DEFAULT_RESOURCES = (
    "deployments.apps", "statefulsets.apps", "daemonsets.apps",
    "replicasets.apps", "pods", "services", "ingresses.networking.k8s.io",
    "configmaps", "secrets", "serviceaccounts", "namespaces",
    "persistentvolumeclaims", "jobs.batch", "cronjobs.batch",
    "endpointslices.discovery.k8s.io", "networkpolicies.networking.k8s.io",
    "roles.rbac.authorization.k8s.io", "rolebindings.rbac.authorization.k8s.io",
    "clusterroles.rbac.authorization.k8s.io",
    "clusterrolebindings.rbac.authorization.k8s.io")

SENSITIVE_KINDS = {"Secret"}
SECRET_DATA_KEYS = ("data", "stringData", "binaryData")

WATCH_ACTION_RESNAPSHOT = "resnapshot"
WATCH_ACTION_APPLY = "apply"


def kind_of(api_version: str, kind: str) -> str:
    """Normalized resource_type: `k8s:<group>/<Kind>` or `k8s:<Kind>`."""
    group = api_version.split("/")[0] if "/" in api_version else ""
    return f"k8s:{group}/{kind}" if group else f"k8s:{kind}"


def canonical_id(cluster: str, namespace: str, kind: str, name: str,
                 uid: str = "") -> str:
    """§43 — strong identity prefers UID; namespaced, deterministic."""
    base = f"k8s://{cluster or 'unknown'}/{namespace or '-'}/{kind}/{name}"
    return f"{base}#{uid}" if uid else base


def project_object(obj: dict[str, Any], *, cluster: str = "",
                   observed_at: str = "") -> ObservedObject:
    """Project a raw k8s object to an ObservedObject. Secret payloads are
    blanked before they ever reach the envelope (§31, §207)."""
    meta = obj.get("metadata", {}) or {}
    api, kind = obj.get("apiVersion", ""), obj.get("kind", "")
    ns, name = meta.get("namespace", ""), meta.get("name", "")
    uid = meta.get("uid", "")
    attrs: dict[str, Any] = {
        "apiVersion": api, "kind": kind,
        "resource_version": meta.get("resourceVersion", ""),
        "generation": meta.get("generation"),
        "labels": meta.get("labels", {}),
        "annotations": {
            k: v for k, v in (meta.get("annotations") or {}).items()
            if not _SENSITIVE_ANNOTATION.match(k)},
        "owner_refs": [
            {"kind": r.get("kind"), "name": r.get("name"),
             "uid": r.get("uid")}
            for r in meta.get("ownerReferences", [])],
        "creation_timestamp": meta.get("creationTimestamp", ""),
        "deletion_timestamp": meta.get("deletionTimestamp", "")}
    spec = obj.get("spec")
    if isinstance(spec, dict):
        attrs["spec_keys"] = sorted(spec.keys())
        # shallow signal fields for topology/reconciliation
        for k in ("replicas", "type", "clusterIP", "ports", "selector",
                  "serviceAccountName", "serviceAccount"):
            if k in spec:
                attrs[f"spec.{k}"] = spec[k]
    if kind in SENSITIVE_KINDS:
        for dk in SECRET_DATA_KEYS:
            if dk in obj:
                attrs["secret_payload_blank"] = True
        attrs["secret_type"] = obj.get("type", "")
    status = obj.get("status")
    if isinstance(status, dict):
        attrs["status.phase"] = status.get("phase", "")
        attrs["status.conditions"] = [
            {"type": c.get("type"), "status": c.get("status")}
            for c in status.get("conditions", [])][:8]
    lifecycle = "present"
    if meta.get("deletionTimestamp"):
        lifecycle = "deleting"
    return ObservedObject(
        resource_id=canonical_id(cluster, ns, kind, name, uid),
        resource_type=kind_of(api, kind),
        attributes={k: v for k, v in attrs.items() if v not in ("", {}, [], None)},
        provider="kubernetes", cluster=cluster, namespace=ns, name=name,
        uid=uid, lifecycle=lifecycle,
        observed_at=observed_at)


@dataclass
class K8sCollector:
    """Pure collector core — `transport` is the only side effect."""
    transport: Transport | None = None
    context: str = ""
    chunk_size: int = 500

    def _run(self, args: list[str]) -> tuple[int, str, str]:
        if self.transport is None:
            raise RuntimeError("no transport — host-side kubectl adapter "
                               "required (see k8s_transport.py)")
        return self.transport(args)

    def _base_args(self) -> list[str]:
        return ["--context", self.context] if self.context else []

    # ── discovery ─────────────────────────────────────────────
    def discover(self) -> dict[str, Any]:
        """api-resources --verbs=list; unsupported types are evidence."""
        rc, out, err = self._run(
            self._base_args() + ["api-resources", "--verbs=list",
                                 "--no-headers", "-o",
                                 "wide"])
        if rc != 0:
            return {"ok": False, "error": err.strip() or "discovery failed",
                    "resources": []}
        names = []
        for line in out.splitlines():
            parts = line.split()
            if parts:
                names.append(parts[0].split(",")[0])
        return {"ok": True, "resources": sorted(set(names))}

    def can_i(self, verbs: tuple[str, ...] = ("get", "list", "watch")) -> \
            dict[str, Any]:
        """Credential preflight — which read verbs are granted."""
        granted, denied = [], []
        for v in verbs:
            rc, out, _ = self._run(
                self._base_args() + ["auth", "can-i", v, "*", "--all-namespaces"])
            (granted if rc == 0 and out.strip().startswith("yes") else denied).append(v)
        return {"granted": sorted(granted), "denied": sorted(denied),
                "cluster_admin_required": False}

    # ── collection ────────────────────────────────────────────
    def collect(self, scope: ObservationScope | None = None,
                budget: ObservationBudget | None = None) -> ObservationEnvelope:
        scope = scope or ObservationScope(provider="kubernetes")
        scope.provider = "kubernetes"
        if self.context:
            scope.clusters = sorted(set(scope.clusters) | {self.context})
        budget = budget or ObservationBudget()
        ledger = ProviderCallLedger(collector=COLLECTOR_VERSION,
                                    started_at=now_iso())
        started = time.monotonic()
        captured_at = now_iso()
        envelope = ObservationEnvelope.new(
            collector="kubernetes", version=COLLECTOR_VERSION,
            provider="kubernetes", source_type="observed",
            scope=scope, captured_at=captured_at)

        resources = (scope.resource_types or list(DEFAULT_RESOURCES))
        denied_scopes: list[dict[str, Any]] = []
        per_type: dict[str, str] = {}
        reasons: list[str] = []
        total_pages = 0

        for res in resources:
            violation = budget.check(ledger)
            if violation:
                per_type[res] = "truncated"
                reasons.append(f"budget {violation} hit — remaining types "
                               "declared truncated, not skipped")
                break
            namespaced = res != "namespaces" and not res.startswith("cluster")
            args = self._base_args() + ["get", res, "-o", "json",
                                        "--chunk-size", str(self.chunk_size)]
            if scope.namespaces:
                args += ["-n", ",".join(scope.namespaces)]
            elif namespaced:
                args += ["--all-namespaces"]
            if scope.selectors.get("labels"):
                args += ["-l", scope.selectors["labels"]]
            ledger.pages_since_reset = 0
            rc, out, err = self._run(args)
            ledger.record_call("k8s.get", pages=1,
                               nbytes=len(out.encode()))
            total_pages += 1
            if rc != 0:
                msg = err.strip()
                if "Forbidden" in msg or "forbidden" in msg:
                    per_type[res] = "permission-limited"
                    denied_scopes.append({"resource_type": res,
                                          "reason": msg})
                    continue
                if "the server doesn't have a resource type" in msg or \
                        "NotFound" in msg:
                    per_type[res] = "unsupported"
                    continue
                per_type[res] = "unknown"
                ledger.errors.append(f"{res}: {msg}")
                reasons.append(f"{res}: {msg}")
                continue
            try:
                doc = json.loads(out)
            except json.JSONDecodeError:
                per_type[res] = "unknown"
                ledger.errors.append(f"{res}: undecodable response")
                continue
            items = doc.get("items", []) if isinstance(doc, dict) else []
            cont = doc.get("metadata", {}).get("continue", "")
            rv = doc.get("metadata", {}).get("resourceVersion", "")
            for obj in items:
                o = project_object(obj, cluster=self.context,
                                   observed_at=captured_at)
                envelope.objects.append(o.to_dict())
            ledger.record_call("k8s.get", pages=0, objects=len(items))
            ledger.pages_since_reset = 0
            # continuation pages (kubectl returns remaining via --continue)
            while cont:
                ledger.pages_since_reset += 1
                violation = budget.check(ledger)
                if violation:
                    per_type[res] = "truncated"
                    reasons.append(f"{res}: budget {violation} — partial list")
                    cont = ""
                    break
                rc, out, err = self._run(
                    self._base_args() + ["get", res, "-o", "json",
                                         "--chunk-size", str(self.chunk_size),
                                         "--continue", cont] +
                    (["-n", ",".join(scope.namespaces)]
                     if scope.namespaces else
                     (["--all-namespaces"] if namespaced else [])))
                ledger.record_call("k8s.get", pages=1,
                                   nbytes=len(out.encode()))
                total_pages += 1
                if rc != 0:
                    per_type[res] = "partial"
                    ledger.errors.append(f"{res} continuation: {err.strip()}")
                    break
                doc = json.loads(out)
                items = doc.get("items", [])
                cont = doc.get("metadata", {}).get("continue", "")
                for obj in items:
                    envelope.objects.append(project_object(
                        obj, cluster=self.context,
                        observed_at=captured_at).to_dict())
                ledger.record_call("k8s.get", pages=0, objects=len(items))
            else:
                per_type.setdefault(res, "complete")
            per_type.setdefault(res, "complete")
            if rv:
                envelope.pagination[res] = {"resource_version": rv}

        done = now_iso()
        envelope.completed_at = done
        cap = parse_ts(captured_at)
        if cap:
            envelope.fresh_until = iso(cap + timedelta(seconds=300))
        status = "complete"
        if any(v in ("permission-limited", "partial", "truncated")
               for v in per_type.values()):
            status = "partial" if any(v == "complete" for v in per_type.values()) \
                else "permission-limited"
        elif not per_type:
            status = "unknown"
        envelope.coverage = Coverage(
            status=status, per_resource_type=per_type,
            reasons=sorted(set(reasons))).to_dict()
        envelope.permissions = {
            "denied_scopes": denied_scopes,
            "cluster_admin_required": False}
        envelope.errors = ledger.errors
        envelope.bytes = ledger.bytes
        receipt = CollectorReceipt(
            collector="kubernetes", collector_version=COLLECTOR_VERSION,
            provider="kubernetes", started_at=ledger.started_at,
            completed_at=done, scope=scope.to_dict(),
            api_calls=ledger.api_calls, pages=ledger.pages,
            objects=ledger.objects, bytes=ledger.bytes,
            errors=ledger.errors,
            permission_denied=denied_scopes,
            metadata_only=True,
            coverage=envelope.coverage,
            freshness={"captured_at": captured_at,
                       "fresh_until": envelope.fresh_until},
            duration_s=round(time.monotonic() - started, 3))
        envelope.receipt = receipt.to_dict()
        return envelope

    # ── watch (§27–28) ────────────────────────────────────────
    def watch(self, res: str, *, resource_version: str = "",
              timeout_s: int = 60,
              handler: Callable[[dict[str, Any]], None] | None = None,
              ) -> dict[str, Any]:
        """Single watch pass. Returns cursor + events + whether a
        resnapshot is required. Never long-polls forever — the host
        loops; this returns bounded evidence."""
        args = self._base_args() + ["get", res, "--watch",
                                    "-o", "json",
                                    "--timeout-seconds", str(timeout_s)]
        if resource_version:
            args += ["--resource-version", resource_version]
        rc, out, err = self._run(args)
        events, cursor, resnapshot = [], resource_version, False
        for line in out.splitlines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            o = ev.get("object", {})
            rv = o.get("metadata", {}).get("resourceVersion", "")
            if rv:
                cursor = rv
            if ev.get("type") == "ERROR":
                code = (o.get("code"), o.get("reason", ""))
                if 410 in code or "Expired" in str(code):
                    resnapshot = True
            events.append({"type": ev.get("type"),
                           "kind": o.get("kind", ""),
                           "name": o.get("metadata", {}).get("name", ""),
                           "namespace": o.get("metadata", {}).get("namespace", ""),
                           "uid": o.get("metadata", {}).get("uid", ""),
                           "resource_version": rv})
            if handler:
                handler(events[-1])
        if rc != 0 and ("410" in err or "Expired" in err or "Gone" in err):
            resnapshot = True
        return {"resource": res, "events": events, "cursor": cursor,
                "resnapshot": resnapshot,
                "error": err.strip() if rc != 0 else ""}


def required_rbac(*, namespaced_only: bool = False,
                  extra_types: list[str] | None = None) -> dict[str, Any]:
    """§31 — minimal read-only RBAC manifest. get/list/watch only; the
    generator structurally cannot emit cluster-admin."""
    rules = [{"apiGroups": ["*"], "resources": ["*"],
              "verbs": ["get", "list", "watch"]}]
    if extra_types:
        rules.append({"apiGroups": ["*"], "resources": extra_types,
                      "verbs": ["get", "list", "watch"]})
    kind = "Role" if namespaced_only else "ClusterRole"
    manifest = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": kind,
        "metadata": {"name": "platformforge-live-reader",
                     "labels": {"app.kubernetes.io/part-of":
                                "platformforge"}},
        "rules": rules}
    return {"kind": kind, "verbs": ["get", "list", "watch"],
            "cluster_admin": False, "manifest": manifest,
            "yaml_hint": "apply with: kubectl apply -f rbac.yaml"}
