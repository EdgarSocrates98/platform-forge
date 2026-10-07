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

from platformforge.core.redaction import k8s_secret_values
from platformforge.models.base import stable_id

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet",
                  "Job", "CronJob", "Pod", "Rollout"}

# apiVersion → k8s version that stopped serving it (k8s.io deprecation
# guide). Used by version-gated rules PF-K8S-030/031 — a fact carries the
# removal version; the cluster version decides applicability.
API_REMOVED = {
    "apps/v1beta1": "1.16",
    "apps/v1beta2": "1.16",
    "extensions/v1beta1": "1.22",
    "networking.k8s.io/v1beta1": "1.22",
    "admissionregistration.k8s.io/v1beta1": "1.22",
    "apiextensions.k8s.io/v1beta1": "1.22",
    "rbac.authorization.k8s.io/v1beta1": "1.22",
    "scheduling.k8s.io/v1beta1": "1.22",
    "storage.k8s.io/v1beta1": "1.22",
    "discovery.k8s.io/v1beta1": "1.21",
    "authentication.k8s.io/v1beta1": "1.24",
    "node.k8s.io/v1beta1": "1.24",
    "policy/v1beta1": "1.25",
    "batch/v1beta1": "1.25",
    "autoscaling/v2beta1": "1.25",
    "autoscaling/v2beta2": "1.26",
    "events.k8s.io/v1beta1": "1.25",
    "flowcontrol.apiserver.k8s.io/v1beta1": "1.26",
    "flowcontrol.apiserver.k8s.io/v1beta2": "1.29",
}


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
            # §62 scheduling/placement signals
            "has_affinity": bool(psp.get("affinity")),
            "has_pod_anti_affinity": bool(
                (psp.get("affinity") or {}).get("podAntiAffinity")),
            "topology_spread": bool(
                psp.get("topologySpreadConstraints")),
            "tolerations": len(psp.get("tolerations") or []),
            "priority_class": psp.get("priorityClassName"),
            "pvc_refs": sorted({(v.get("persistentVolumeClaim") or {})
                                .get("claimName", "")
                                for v in psp.get("volumes") or []
                                if isinstance(v, dict)
                                and v.get("persistentVolumeClaim")}),
        },
        "replicas": spec.get("replicas", 1),
    }


def analyze_k8s(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    docs = list(_docs(root))
    facts: list[dict[str, Any]] = []

    # first pass: collect workloads + their labels for cross-resource joins
    wl_labels: dict[str, dict[str, str]] = {}
    wl_attrs: dict[str, dict[str, Any]] = {}
    for f, i, doc in docs:
        if doc["kind"] in WORKLOAD_KINDS:
            meta = doc.get("metadata") or {}
            ns = meta.get("namespace", "default")
            lbl = (((doc.get("spec") or {}).get("template") or {})
                   .get("metadata") or {}).get("labels") or {}
            wl_labels[f"{ns}/{meta.get('name')}"] = lbl
            wl_attrs[f"{ns}/{meta.get('name')}"] = _workload_attrs(
                doc, set())["pod_spec"]

    NODE_KIND = {"Service": "k8s_service", "Ingress": "ingress",
                 "Namespace": "namespace",
                 "ServiceAccount": "service_account",
                 "Secret": "secret",
                 "NetworkPolicy": "security_policy",
                 "PersistentVolumeClaim": "storage",
                 "PersistentVolume": "storage",
                 "StorageClass": "storage",
                 "GatewayClass": "gateway",
                 "Gateway": "gateway",
                 "HTTPRoute": "route", "GRPCRoute": "route",
                 "TCPRoute": "route", "TLSRoute": "route",
                 "ReferenceGrant": "security_policy",
                 "CiliumNetworkPolicy": "security_policy",
                 "CiliumClusterwideNetworkPolicy": "security_policy",
                 "Rollout": "workload",
                 "VerticalPodAutoscaler": "autoscaler",
                 "ScaledObject": "autoscaler",
                 "NodePool": "autoscaler"}

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
                "labels": meta.get("labels") or {},
                "api_removed_in": API_REMOVED.get(doc.get("apiVersion")),
                "api_beta_track": "beta" in (doc.get("apiVersion") or "")}
        nk = "workload" if kind in WORKLOAD_KINDS else NODE_KIND.get(kind)
        g_nodes = [{"kind": nk, "label": f"{ns}/{name}"}] if nk else []
        g_edges = []
        wk = f"{ns}/{name}"
        attrs: dict[str, Any] = dict(base)

        if kind in WORKLOAD_KINDS:
            attrs.update(_workload_attrs(doc, set()))
            attrs["pdb_count"] = pdb_cov.get(wk, 0)
            attrs["netpol_count"] = netpol_cov.get(wk, 0)
            if kind == "Rollout":  # §70 — Argo Rollouts strategy signals
                strat = (doc.get("spec") or {}).get("strategy") or {}
                attrs["rollout"] = {
                    "canary": bool(strat.get("canary")),
                    "blue_green": bool(strat.get("blueGreen")),
                    "analysis_refs": sorted({
                        s.get("analysis", {}).get("templateName", "")
                        for s in (strat.get("canary") or {}).get("steps") or []
                        if isinstance(s, dict) and s.get("analysis")})}
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
        elif kind == "ServiceAccount":
            fact_kind = "k8s.service_account"
            attrs["automount_token"] = doc.get("automountServiceAccountToken")
        elif kind in ("Role", "ClusterRole", "RoleBinding",
                      "ClusterRoleBinding"):
            fact_kind = "k8s.rbac"
            rules = doc.get("rules") or []
            attrs["rules"] = len(rules)
            attrs["subjects"] = doc.get("subjects") or []
            # §62 — RBAC depth: wildcard verbs/resources, cluster-admin binds
            attrs["wildcard_verbs"] = any(
                "*" in (r.get("verbs") or []) for r in rules)
            attrs["wildcard_resources"] = any(
                "*" in (r.get("resources") or []) for r in rules)
            attrs["binds_cluster_admin"] = (
                (doc.get("roleRef") or {}).get("name") == "cluster-admin")
            role_ref = doc.get("roleRef") or {}
            if role_ref.get("name"):
                g_edges.append({"src_kind": "service_account",
                                "src": wk, "dst_kind": "security_policy",
                                "dst": role_ref["name"],
                                "kind": "assumes"})
        elif kind == "Namespace":
            fact_kind = "k8s.namespace"
            lbl = meta.get("labels") or {}
            attrs["pod_security"] = {
                k.split("pod-security.kubernetes.io/")[-1]: v
                for k, v in lbl.items()
                if k.startswith("pod-security.kubernetes.io/")}
        elif kind == "PersistentVolumeClaim":
            fact_kind = "k8s.pvc"
            spec = doc.get("spec") or {}
            attrs.update({"storage_class": spec.get("storageClassName"),
                          "access_modes": spec.get("accessModes") or [],
                          "size": ((spec.get("resources") or {})
                                   .get("requests") or {}).get("storage")})
        elif kind == "PersistentVolume":
            fact_kind = "k8s.pv"
            spec = doc.get("spec") or {}
            attrs.update({"storage_class": spec.get("storageClassName"),
                          "reclaim": spec.get("persistentVolumeReclaimPolicy"),
                          "capacity": (spec.get("capacity") or {})
                                      .get("storage"),
                          "csi_driver": (spec.get("csi") or {}).get("driver")})
        elif kind == "StorageClass":
            fact_kind = "k8s.storageclass"
            attrs.update({"provisioner": doc.get("provisioner"),
                          "reclaim": doc.get("reclaimPolicy"),
                          "expansion": doc.get("allowVolumeExpansion"),
                          "binding": doc.get("volumeBindingMode")})
        elif kind == "GatewayClass":
            fact_kind = "k8s.gatewayclass"
            spec = doc.get("spec") or {}
            attrs["controller"] = spec.get("controllerName")
        elif kind == "Gateway":
            fact_kind = "k8s.gateway"
            spec = doc.get("spec") or {}
            listeners = spec.get("listeners") or []
            attrs["gateway_class"] = spec.get("gatewayClassName")
            attrs["listeners"] = [{"port": li.get("port"),
                                   "protocol": li.get("protocol"),
                                   "hostname": li.get("hostname"),
                                   "tls": bool(li.get("tls"))}
                                  for li in listeners]
            attrs["has_plain_http_listener"] = any(
                li.get("protocol") in ("HTTP", "TCP") and not li.get("tls")
                for li in listeners)
            g_nodes = [{"kind": "gateway", "label": wk}]
            if spec.get("gatewayClassName"):
                g_edges.append({"src_kind": "gateway", "src": wk,
                                "dst_kind": "gateway",
                                "dst": spec["gatewayClassName"],
                                "kind": "contained_by"})
            g_edges.append({"src_kind": "gateway", "src": wk,
                            "dst_kind": "api", "dst": "external",
                            "kind": "exposes"})
        elif kind in ("HTTPRoute", "GRPCRoute", "TCPRoute", "TLSRoute"):
            fact_kind = "k8s.route"
            spec = doc.get("spec") or {}
            parents = [p.get("name") for p in spec.get("parentRefs") or []
                       if p.get("name")]
            backends = [b.get("name") for r in spec.get("rules") or []
                        for b in r.get("backendRefs") or []
                        if b.get("name")]
            attrs.update({"route_kind": kind, "parents": parents,
                          "backends": backends,
                          "hostnames": spec.get("hostnames") or []})
            g_nodes = [{"kind": "route", "label": wk}]
            for p in parents:
                g_edges.append({"src_kind": "route", "src": wk,
                                "dst_kind": "gateway", "dst": p,
                                "kind": "attached_to"})
            for b in backends:
                g_edges.append({"src_kind": "route", "src": wk,
                                "dst_kind": "k8s_service", "dst": f"{ns}/{b}",
                                "kind": "routes_to"})
        elif kind == "ReferenceGrant":
            fact_kind = "k8s.reference_grant"
            spec = doc.get("spec") or {}
            attrs.update({
                "from": [{"kind": r.get("kind"), "ns": r.get("namespace")}
                         for r in spec.get("from") or []],
                "to": [r.get("kind") for r in spec.get("to") or []]})
        elif kind in ("CiliumNetworkPolicy",
                      "CiliumClusterwideNetworkPolicy"):
            fact_kind = "k8s.cilium_policy"
            spec = doc.get("spec") or doc.get("specs") or {}
            specs = spec if isinstance(spec, list) else [spec]
            def _l7(specs: list) -> bool:
                """L7 marker: `rules` under toPorts of any ingress/egress."""
                for s in specs:
                    if not isinstance(s, dict):
                        continue
                    for d in ("ingress", "egress"):
                        for e in s.get(d) or []:
                            if isinstance(e, dict) and any(
                                    "rules" in p
                                    for p in e.get("toPorts") or []
                                    if isinstance(p, dict)):
                                return True
                return False
            attrs.update({
                "clusterwide": kind == "CiliumClusterwideNetworkPolicy",
                "has_egress": any(s.get("egress") for s in specs
                                  if isinstance(s, dict)),
                "has_ingress": any(s.get("ingress") for s in specs
                                   if isinstance(s, dict)),
                "l7_rules": _l7(specs)})
        elif kind in ("AnalysisTemplate", "AnalysisRun", "Experiment"):
            fact_kind = "k8s.analysis"
            spec = doc.get("spec") or {}
            attrs["metrics"] = [m.get("name") for m in
                                spec.get("metrics") or []]
        elif kind == "VerticalPodAutoscaler":
            fact_kind = "k8s.vpa"
            spec = doc.get("spec") or {}
            tgt = spec.get("targetRef") or {}
            upd = spec.get("updatePolicy") or {}
            attrs.update({"target": f"{tgt.get('kind')}/{tgt.get('name')}",
                          "update_mode": upd.get("updateMode", "Auto")})
            if tgt.get("name"):
                g_edges.append({"src_kind": "autoscaler", "src": wk,
                                "dst_kind": "workload",
                                "dst": f"{ns}/{tgt['name']}",
                                "kind": "scales"})
        elif kind == "ScaledObject":
            fact_kind = "k8s.keda"
            spec = doc.get("spec") or {}
            tgt = (spec.get("scaleTargetRef") or {})
            attrs.update({"target": f"{tgt.get('kind', 'Deployment')}"
                                    f"/{tgt.get('name')}",
                          "triggers": [t.get("type") for t in
                                       spec.get("triggers") or []],
                          "min_replicas": spec.get("minReplicaCount"),
                          "max_replicas": spec.get("maxReplicaCount")})
            if tgt.get("name"):
                g_edges.append({"src_kind": "autoscaler", "src": wk,
                                "dst_kind": "workload",
                                "dst": f"{ns}/{tgt['name']}",
                                "kind": "scales"})
        elif kind == "NodePool":
            fact_kind = "k8s.karpenter"
            spec = doc.get("spec") or {}
            attrs.update({"disruption": spec.get("disruption") or {},
                          "limits": spec.get("limits") or {},
                          "weight": spec.get("weight")})
            g_nodes = [{"kind": "autoscaler", "label": wk}]
        elif kind == "HorizontalPodAutoscaler":
            fact_kind = "k8s.hpa"
            spec = doc.get("spec") or {}
            tgt = spec.get("scaleTargetRef") or {}
            twl = wl_attrs.get(f"{ns}/{tgt.get('name')}") or {}
            attrs.update({"min_replicas": spec.get("minReplicas"),
                          "max_replicas": spec.get("maxReplicas"),
                          "target": f"{tgt.get('kind')}/{tgt.get('name')}",
                          "metrics": [m.get("type") for m in
                                      spec.get("metrics") or []],
                          # §68 — joined: does the target declare requests?
                          "target_has_requests":
                              twl.get("no_requests", 0) == 0
                              if twl else None,
                          "target_known": bool(twl)})
            g_nodes = [{"kind": "autoscaler", "label": wk}]
            if tgt.get("name"):
                g_edges.append({"src_kind": "autoscaler", "src": wk,
                                "dst_kind": "workload",
                                "dst": f"{ns}/{tgt['name']}",
                                "kind": "scales"})
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
        elif kind == "CustomResourceDefinition":
            fact_kind = "k8s.crd"
            spec = doc.get("spec") or {}
            attrs.update({"group": spec.get("group"),
                          "scope": spec.get("scope"),
                          "versions": [v.get("name") for v in
                                       spec.get("versions") or []]})
        else:
            fact_kind = "k8s.generic"
        attrs["graph"] = {"nodes": g_nodes, "edges": g_edges}
        facts.append({"fact_id": stable_id("PF-K8S", fact_kind, loc),
                      "kind": fact_kind, "source": str(f), "location": loc,
                      "tier": 3, "attrs": attrs})
    return {"facts": facts, "counts": {"docs": len(docs),
                                       "facts": len(facts)}}
