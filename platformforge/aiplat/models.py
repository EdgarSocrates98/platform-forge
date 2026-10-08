"""Cycle 5 Phase K — AI platform awareness (§187–201).

Platform-level contracts only — this is not an AI Forge (§188, §201):
GPU/accelerator detection, capacity dims, serving SLO, unit economics
with real denominators, optimization *recommendations* — nothing is
terminated, downsized or purchased here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

GPU_DIMENSIONS = ("model", "memory", "count", "utilization",
                  "allocation", "node_pool", "availability_zone")
AI_NODE_KINDS = ("accelerator", "gpu_pool", "model", "model_endpoint",
                 "inference_service", "training_job", "vector_store")

# §199 — kubernetes AI workload signals
K8S_GPU_RESOURCES = ("nvidia.com/gpu", "amd.com/gpu",
                     "intel.com/gpu", "google.com/tpu")
ACCELERATOR_LABELS = ("accelerator", "gpu", "nvidia.com/gpu.product",
                      "node.kubernetes.io/instance-type")


@dataclass
class GPUCapacity:
    """§192 — per-dimension GPU capacity; unknown dims stay unknown."""
    pool_id: str
    model: str = ""
    count: int | None = None
    memory_gb: float | None = None
    utilization: float | None = None      # 0..100
    allocated: int | None = None
    node_pool: str = ""
    availability_zone: str = ""
    fractional: bool | None = None        # §193 — MIG/slice awareness
    evidence: list[str] = field(default_factory=list)

    @property
    def headroom(self) -> float | None:
        if self.count is None or self.allocated is None or not self.count:
            return None
        return round((self.count - self.allocated) / self.count, 3)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/gpu-capacity/v1", **asdict(self),
                "headroom": self.headroom}


@dataclass
class ServingSLO:
    """§196 — model serving SLO; missing inputs → unknown."""
    endpoint_id: str
    latency_p95_ms: float | None = None
    availability: float | None = None
    throughput_rps: float | None = None
    error_rate: float | None = None
    targets: dict[str, float] = field(default_factory=dict)

    def verdict(self) -> str:
        if self.latency_p95_ms is None and self.error_rate is None:
            return "unknown"
        bad = []
        if self.targets.get("latency_p95_ms") and \
           self.latency_p95_ms and \
           self.latency_p95_ms > self.targets["latency_p95_ms"]:
            bad.append("latency")
        if self.targets.get("error_rate") and \
           self.error_rate is not None and \
           self.error_rate > self.targets["error_rate"]:
            bad.append("errors")
        return "violating" if bad else "healthy"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "platformforge/serving-slo/v1", **asdict(self),
                "verdict": self.verdict()}


def ai_unit_economics(cost: float | None, tokens: float | None = None,
                      inferences: float | None = None,
                      gpu_hours: float | None = None) -> dict[str, Any]:
    """§195/§361 — denominators required; no cost/token metric without
    observed tokens."""
    out: dict[str, Any] = {"schema": "platformforge/ai-unit-economics/v1"}
    if cost is None:
        return {**out, "cost": "unknown",
                "reason": "no cost data", "confidence": "low"}
    out["cost"] = cost
    for name, den in (("tokens", tokens), ("inferences", inferences),
                      ("gpu_hours", gpu_hours)):
        if den:
            key = {"tokens": "cost_per_1m_tokens",
                   "inferences": "cost_per_inference",
                   "gpu_hours": "cost_per_gpu_hour"}[name]
            scale = 1_000_000 if name == "tokens" else 1
            out[key] = round(cost / den * scale, 4)
        else:
            out[f"{name}_metric"] = "unknown"   # §295 — never fabricate
    out["confidence"] = "medium" if (tokens or inferences) else "low"
    return out


def ai_capacity_risk(pools: list[GPUCapacity],
                     queue_depth: float | None = None,
                     cold_start_rate: float | None = None) -> dict[str, Any]:
    """§197 — GPU saturation / queue / cold start / memory pressure."""
    risks = []
    for p in pools:
        if p.utilization is not None and p.utilization >= 90:
            risks.append({"pool": p.pool_id, "risk": "gpu-saturation",
                          "utilization": p.utilization})
        if p.headroom is not None and p.headroom < 0.1:
            risks.append({"pool": p.pool_id, "risk": "low-headroom",
                          "headroom": p.headroom})
    if queue_depth is not None and queue_depth > 100:
        risks.append({"risk": "queue-depth", "value": queue_depth})
    if cold_start_rate is not None and cold_start_rate > 0.2:
        risks.append({"risk": "cold-start", "rate": cold_start_rate})
    return {"schema": "platformforge/ai-capacity-risk/v1",
            "risks": risks, "pools_evaluated": len(pools),
            "confidence": "medium" if risks else "low"}


def ai_optimizations(pools: list[GPUCapacity],
                     endpoints: list[dict[str, Any]],
                     costs: dict[str, float] | None = None
                     ) -> list[dict[str, Any]]:
    """§198 — candidate optimizations with evidence; never prescriptive
    without data, never executes."""
    recs = []
    for p in pools:
        if p.utilization is not None and p.utilization < 15 and \
           p.allocated:
            recs.append({"type": "idle-gpu-pool", "pool": p.pool_id,
                         "action": "evaluate rightsizing or scale-down",
                         "evidence": {"utilization": p.utilization,
                                      "allocated": p.allocated},
                         "estimated_savings":
                         (costs or {}).get(p.pool_id),
                         "confidence": "low", "executes": False})
    for e in endpoints:
        if e.get("traffic_rps") is not None and e["traffic_rps"] < 0.1:
            recs.append({"type": "idle-endpoint",
                         "endpoint": e.get("id", "unknown"),
                         "action": "evaluate scale-to-zero or spot",
                         "evidence": {"traffic_rps": e["traffic_rps"]},
                         "estimated_savings": e.get("cost_monthly"),
                         "confidence": "low", "executes": False})
    return recs


def detect_ai_workloads(k8s_resources: list[dict[str, Any]]
                        ) -> list[dict[str, Any]]:
    """§199 — detect GPU workloads from k8s resource requests/labels."""
    out = []
    for r in k8s_resources:
        res = r.get("resources", {}) or {}
        limits = res.get("limits", {}) or {}
        labels = r.get("labels", {}) or {}
        gpu_kind = next((g for g in K8S_GPU_RESOURCES if g in limits), None)
        accel = labels.get("accelerator") or labels.get(
            "nvidia.com/gpu.product")
        if gpu_kind or accel:
            out.append({"workload": r.get("id") or r.get("name", ""),
                        "gpu_resource": gpu_kind,
                        "gpu_count": limits.get(gpu_kind) if gpu_kind
                        else None,
                        "accelerator_model": accel,
                        "fractional": bool(gpu_kind and
                                           float(limits.get(gpu_kind,
                                                            1)) < 1),
                        "evidence": ["k8s.resource.limits",
                                     "k8s.labels"]})
    return out
