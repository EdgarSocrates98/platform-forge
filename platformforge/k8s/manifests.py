"""Kubernetes manifest analyzer — multi-doc YAML → facts + graph edges.

Workload-bearing controllers emit `k8s.workload` facts with extracted pod
spec signals (images, resources, probes, securityContext, secret refs) so
PF-K8S-* rules stay declarative. Cross-resource joins (PDB/NetworkPolicy
coverage, Service→selector match) are computed here and recorded as fact
attrs — the rule engine never does joins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platformforge.core.redaction import k8s_secret_values, redact_obj
from platformforge.models.base import stable_id

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet",
                  "Job", "CronJob", "Pod"}


def _docs(path: Path):
    for f in sorted(path.rglob("*.yaml")) + sorted(path.rglob("*.yml")) \
            if path.is_dir() else [path]:
        try:
            for i, doc in enumerate(yaml.safe_load_all(f.read_text())):
                if isinstance(doc, dict) and doc.get("kind") \
                        and doc.get("apiVersion"):
                    yield f, i, doc
        except yaml.YAMLError:
            continue


def _pod_spec(doc: dict[str, Any]) -> dict[str, Any]:
    kind = doc.get("kind")
    spec = doc.get("spec") or {}
    if kind == "Pod":
        return spec
    if kind == "CronJob":
        return (((spec.get("jobTemplate") or {}).get("spec") or {})
                .get("template") or {}).get("spec") or {}
    return ((spec.get("template") or {}).get("spec") or {})


def _labels_match(selector: dict[str, Any] | None,
                  labels: dict[str, Any]) -> bool:
    """K8s label selector (matchLabels or direct selector) ⊆ labels."""
    sel = (selector or {}).get("matchLabels", selector or {})
    if not isinstance(sel, dict) or not sel:
        return False
    return all(labels.get(k) == v for k, v in sel.items())


def _workload_attrs(doc: dict[str, Any], secret_names: set[str]) -> dict[str, Any]:
    spec = doc.get("spec") or {}
    psp = _pod_spec(doc)
    containers = list(psp.get("containers") or []) + \
        list(psp.get("initContainers") or [])
    images, used_secrets, used_cms = [], [], []
    sec_flags = {"privileged": False, "run_as_root": False,
                 "run_as_non_root_set": False, "read_only_rootfs": False,
                 "allow_priv_esc": False}
    no_limits = no_requests = no_probes = 0
    env_hardcoded_secret = []
    pod_sc = psp.get("securityContext") or {}
    for c in containers:
        img = c.get("image", "")
        images.append(img)
        res = c.get("resources") or {}
        if not res.get("limits"):
            no_limits += 1
        if not res.get("requests"):
            no_requests += 1
        if not (c.get("livenessProbe") or c.get("readinessProbe")):
            no_probes += 1
        csc = c.get("securityContext") or {}
        sec_flags["privileged"] |= bool(csc.get("privileged"))
        sec_flags["read_only_rootfs"] |= bool(csc.get("readOnlyRootFilesystem"))
        if csc.get("allowPrivilegeEscalation") is not False:
            sec_flags["allow_priv_esc"] = True
        if csc.get("runAsNonRoot") is True or pod_sc.get("runAsNonRoot") is True:
            sec_flags["run_as_non_root_set"] = True
        run_as = csc.get("runAsUser", pod_sc.get("runAsUser"))
        if run_as == 0:
            sec_flags["run_as_root"] = True
        for env in c.get("env") or []:
            name = env.get("name", "")
            vf = env.get("valueFrom") or {}
            if "secretKeyRef" in vf:
                used_secrets.append(vf["secretKeyRef"].get("name", ""))
            elif "configMapKeyRef" in vf:
                used_cms.append(vf["configMapKeyRef"].get("name", ""))
            elif env.get("value") is not None and \
                    any(t in name.lower() for t in
                        ("password", "secret", "token", "apikey", "api_key")):
                env_hardcoded_secret.append(name)
    for vol in psp.get("volumes") or []:
        if isinstance(vol, dict) and vol.get("secret"):
            used_secrets.append((vol["secret"] or {}).get("secretName", ""))
    return {
        "pod_spec": {
            "images": images,
            "container_count": len(containers),
            "no_limits": no_limits, "no_requests": no_requests,
            "no_probes": no_probes,
            "latest_tag": any((":" not in i) or i.endswith(":latest")
                              for i in images),
            **sec_flags,
            "host_network": bool(psp.get("hostNetwork")),
            "host_pid": bool(psp.get("hostPID")),
            "host_ipc": bool(psp.get("hostIPC")),
            "service_account": psp.get("serviceAccountName"),
            "automount_token": psp.get("automountServiceAccountToken", True),
            "env_hardcoded_secret": env_hardcoded_secret,
            "secrets_used": sorted({s for s in used_secrets if s}),
            "configmaps_used": sorted({c for c in used_cms if c}),
        },
        "replicas": spec.get("replicas", 1),
    }


def analyze_k8s(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    docs = list(_docs(root))
    facts: list[dict[str, Any]] = []

    # first pass: collect workloads + their labels for cross-resource joins
    wl_labels: dict[str, dict[str, str]] = {}
    for f, i, doc in docs:
        if doc["kind"] in WORKLOAD_KINDS:
            meta = doc.get("metadata") or {}
            ns = meta.get("namespace", "default")
            lbl = (((doc.get("spec") or {}).get("template") or {})
                   .get("metadata") or {}).get("labels") or {}
            wl_labels[f"{ns}/{meta.get('name')}"] = lbl

    NODE_KIND = {"Service": "k8s_service", "Ingress": "ingress",
                 "Namespace": "namespace",
                 "ServiceAccount": "service_account",
                 "Secret": "secret",
                 "NetworkPolicy": "security_policy"}

    def _coverage(kind: str, key: str) -> dict[str, int]:
        counts = {k: 0 for k in wl_labels}
        for f, i, doc in docs:
            if doc["kind"] != kind:
                continue
            meta = doc.get("metadata") or {}
            ns = meta.get("namespace", "default")
            sel = (doc.get("spec") or {}).get(key)
            for wk, lbl in wl_labels.items():
                if wk.split("/")[0] == ns and _labels_match(sel, lbl):
                    counts[wk] += 1
        return counts

    pdb_cov = _coverage("PodDisruptionBudget", "selector")
    netpol_cov = _coverage("NetworkPolicy", "podSelector")

    for f, i, doc in docs:
        kind, meta = doc["kind"], doc.get("metadata") or {}
        ns, name = meta.get("namespace", "default"), meta.get("name", "?")
        loc = f"{f}::{ns}/{name}"
        base = {"api_version": doc.get("apiVersion"), "kind": kind,
                "namespace": ns, "name": name,
                "labels": meta.get("labels") or {}}
        nk = "workload" if kind in WORKLOAD_KINDS else NODE_KIND.get(kind)
        g_nodes = [{"kind": nk, "label": f"{ns}/{name}"}] if nk else []
        g_edges = []
        wk = f"{ns}/{name}"
        attrs: dict[str, Any] = dict(base)

        if kind in WORKLOAD_KINDS:
            attrs.update(_workload_attrs(doc, set()))
            attrs["pdb_count"] = pdb_cov.get(wk, 0)
            attrs["netpol_count"] = netpol_cov.get(wk, 0)
            fact_kind = "k8s.workload"
            g_nodes = [{"kind": "workload", "label": wk,
                        "attrs": {"k8s_kind": kind, "file": str(f)}}]
            g_edges.append({"src_kind": "workload", "src": wk,
                            "dst_kind": "namespace", "dst": ns,
                            "kind": "contained_by"})
            sa = attrs["pod_spec"].get("service_account")
            if sa:
                g_edges.append({"src_kind": "workload", "src": wk,
                                "dst_kind": "service_account", "dst": f"{ns}/{sa}",
                                "kind": "assumes"})
            for s in attrs["pod_spec"]["secrets_used"]:
                g_edges.append({"src_kind": "workload", "src": wk,
                                "dst_kind": "secret", "dst": f"{ns}/{s}",
                                "kind": "uses_secret"})
        elif kind == "Service":
            fact_kind = "k8s.service"
            spec = doc.get("spec") or {}
            attrs["svc_type"] = spec.get("type", "ClusterIP")
            attrs["selector"] = spec.get("selector") or {}
            attrs["ports"] = spec.get("ports") or []
            g_nodes = [{"kind": "k8s_service", "label": wk}]
            for wkey, lbl in wl_labels.items():
                if wkey.split("/")[0] == ns and \
                        _labels_match(attrs["selector"], lbl):
                    g_edges.append({"src_kind": "k8s_service", "src": wk,
                                    "dst_kind": "workload", "dst": wkey,
                                    "kind": "routes_to"})
        elif kind == "Ingress":
            fact_kind = "k8s.ingress"
            spec = doc.get("spec") or {}
            hosts = [r.get("host") for r in spec.get("rules") or []
                     if isinstance(r, dict)]
            attrs["hosts"] = hosts
            attrs["tls"] = bool(spec.get("tls"))
            backends = []
            for r in spec.get("rules") or []:
                for p in ((r.get("http") or {}).get("paths") or []):
                    svc = (((p.get("backend") or {}).get("service") or {})
                           .get("name"))
                    if svc:
                        backends.append(svc)
            attrs["backend_services"] = backends
            g_nodes = [{"kind": "ingress", "label": wk}]
            for b in backends:
                g_edges.append({"src_kind": "ingress", "src": wk,
                                "dst_kind": "k8s_service", "dst": f"{ns}/{b}",
                                "kind": "routes_to"})
            g_edges.append({"src_kind": "ingress", "src": wk,
                            "dst_kind": "api", "dst": "external",
                            "kind": "exposes"})
        elif kind == "HorizontalPodAutoscaler":
            fact_kind = "k8s.hpa"
            spec = doc.get("spec") or {}
            tgt = spec.get("scaleTargetRef") or {}
            attrs.update({"min_replicas": spec.get("minReplicas"),
                          "max_replicas": spec.get("maxReplicas"),
                          "target": f"{tgt.get('kind')}/{tgt.get('name')}"})
            g_nodes = [{"kind": "workload", "label": wk}]
        elif kind == "PodDisruptionBudget":
            fact_kind = "k8s.pdb"
            spec = doc.get("spec") or {}
            attrs.update({"min_available": spec.get("minAvailable"),
                          "max_unavailable": spec.get("maxUnavailable")})
        elif kind == "NetworkPolicy":
            fact_kind = "k8s.network_policy"
            spec = doc.get("spec") or {}
            attrs.update({"has_ingress": bool(spec.get("ingress")),
                          "has_egress": bool(spec.get("egress")),
                          "pod_selector": spec.get("podSelector")})
        elif kind == "Secret":
            fact_kind = "k8s.secret"
            attrs["type"] = doc.get("type", "Opaque")
            attrs["keys"] = sorted((doc.get("data") or {}).keys())
            doc = {**doc, **k8s_secret_values(doc)}  # redact payload
        elif kind == "ServiceAccount":
            fact_kind = "k8s.service_account"
            attrs["automount_token"] = doc.get("automountServiceAccountToken")
        elif kind in ("Role", "ClusterRole", "RoleBinding",
                      "ClusterRoleBinding"):
            fact_kind = "k8s.rbac"
            attrs["rules"] = len(doc.get("rules") or [])
            attrs["subjects"] = doc.get("subjects") or []
        else:
            fact_kind = "k8s.generic"
        attrs["graph"] = {"nodes": g_nodes, "edges": g_edges}
        facts.append({"fact_id": stable_id("PF-K8S", fact_kind, loc),
                      "kind": fact_kind, "source": str(f), "location": loc,
                      "tier": 3, "attrs": attrs})
    return {"facts": facts, "counts": {"docs": len(docs),
                                       "facts": len(facts)}}
