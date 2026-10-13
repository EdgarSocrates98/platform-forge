# AI-PLATFORM — platform-level awareness, not an AI Forge

`platformforge/aiplat/` sees AI workloads as platform resources:
GPU/accelerator inventory, pools, model serving, inference
endpoints, training jobs, vector stores. It answers platform
questions (capacity, cost, utilization, SLO headroom) — it does not
manage models, prompts, or inference quality.

## Detection

`detect_ai_workloads(k8s_resources)` finds GPU requests/limits
(`nvidia.com/gpu`, MIG slices, accelerator labels) and serving
workloads — deterministic from declared resources.

## GPU capacity

`GPUCapacity` / `ai_capacity_risk(pools)` — allocation vs count,
utilization %, saturation per pool. MIG/fractional-GPU partitions
are first-class members, not opaque shares.

## Unit economics — denominators required

`ai_unit_economics(cost, tokens=?, inferences=?, gpu_hours=?)`
emits a metric **only** when its denominator is observed:

| Denominator present | Metric emitted |
|---|---|
| `tokens` | `cost_per_1m_tokens` |
| `inferences` | `cost_per_inference` |
| `gpu_hours` | `cost_per_gpu_hour` |
| none | `cost_monthly` only — `*_metric: "unknown"` |

A missing denominator produces no rate metric (adversarial E11) —
an endpoint with cost but zero observed traffic reports
`tokens_metric: unknown`, not a fabricated rate.

## Findings

`ai_findings`-class signals: `ai.underutilized-serving` (cost ≫
traffic), `ai.gpu-pool-saturation`, stranded accelerators — all
platform-scope, evidence-cited.

## Boundary

No model registry, no eval harness, no serving control plane. Graph
vocab adds `accelerator`, `gpu_pool`, `model`, `model_endpoint`,
`inference_service`, `training_job`, `vector_store` — awareness only.
