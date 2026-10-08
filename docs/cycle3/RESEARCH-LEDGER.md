# Cycle 3 — Research Ledger

Per §177: `source, retrieved_at, version, capability, claims`. All sources
official (kubernetes.io, docs.aws.amazon.com, opentelemetry.io,
docs.cilium.io). Retrieved during CYCLE-3 discover phase.

## Kubernetes API semantics

| Capability | Claims | Source | Version status |
|---|---|---|---|
| LIST pagination | `limit`+`continue` token; `continue` presence is the only "more pages" signal (pages may return 0 items); **collection `resourceVersion` identical across all pages** — guaranteed consistent snapshot; `remainingItemCount` absent with selectors/last page | kubernetes.io/docs/reference/using-api/api-concepts | stable |
| continue expiry | ~5–15 min; expired → `410 ResourceExpired` embedding a *new* continue token on the latest snapshot — for consistency restart the list | api-concepts | stable |
| resourceVersion modes | unset=Most Recent (quorum); `RV=0`=Any (watch cache, cheap, may rewind — no freshness guarantee); `RV=v`+`resourceVersionMatch` Exact/NotOlderThan | api-concepts (RVMatch since v1.19) | stable |
| WATCH | `?watch=true`; events ADDED/MODIFIED/DELETED/BOOKMARK/ERROR; DELETED carries last state; ERROR carries Status object; server may close anytime — resume from last RV, never "now" | api-concepts | stable |
| allowWatchBookmarks | server *may* emit BOOKMARK with RV only; never guaranteed | api-concepts; feature-gate WatchBookmark | GA since 1.17 (gate removed 1.33) |
| 410 Gone | etcd history ~5 min default → re-list, re-snapshot, resume | api-concepts | stable |
| Streaming list | `watch=true&sendInitialEvents=true&allowWatchBookmarks=true&resourceVersionMatch=NotOlderThan` → synthetic ADDEDs → annotated BOOKMARK (`k8s.io/initial-events-end`) → live events. RVM is required=NotOlderThan | api-concepts; KEP-3157 | **beta**; on-by-default 1.32 & 1.34+, off 1.33 — must probe + fallback to LIST+WATCH |
| Metadata-only | `Accept: application/json;as=PartialObjectMetadata(List);g=meta.k8s.io;v=v1`; unsupported → 406 → full-object fallback | api-concepts; KEP-2334 | GA since 1.15 |
| Discovery | `/api`,`/apis`, per-GV `APIResourceList` (name=resource path, kind, namespaced, verbs[], subresources as `x/y`); aggregated `apidiscovery.k8s.io/v2` | API concepts; KEP-3352 | v2 GA since 1.30 |
| deletionTimestamp/finalizers | object with deletionTimestamp is *terminating*, still exists until finalizers clear | object-meta docs | stable |
| EndpointSlice | label `kubernetes.io/service-name` → Service (same namespace); `endpoints[].targetRef.uid` → Pod; ownerRef stronger but optional | endpoint-slices docs | GA since 1.21 |
| ownerReferences | uid authoritative; `controller:true` max one per dependent; namespaced dependent needs same-ns owner | owners-dependents docs | stable |
| Cluster identity | no official cluster id; de-facto = `kube-system` namespace UID (codified as OTel `k8s.cluster.uid`); EKS name lives in ARN/provider API | kubernetes #77487; otel semconv | — |
| TokenRequest | `POST serviceaccounts/token` **creates a credential** — excluded from collector surface | service-accounts-admin docs | stable |

## AWS APIs

| Capability | Claims | Source | Version status |
|---|---|---|---|
| Config ListDiscoveredResources | resourceType required; returns discovered *including not-recorded*; limit ≤100, nextToken | API_ListDiscoveredResources | current |
| Config status semantics | OK / ResourceDiscovered / ResourceNotRecorded / ResourceDeleted / ResourceDeletedNotRecorded — last two are tombstone-grade evidence | API_ConfigurationItem | current |
| Config SelectResourceConfig | SQL subset; **cannot query not-recorded or deleted**; ≤100/page | API_SelectResourceConfig | current |
| Config coverage | only supported-type list recorded; GetDiscoveredResourceCounts empty if recorder off → check DescribeConfigurationRecorders first | resource-config-reference | current |
| Aggregators | multi-account/multi-region/org read-only views; ListAggregateDiscoveredResources / SelectAggregateResourceConfig | aggregate-data docs | current |
| Resource Explorer Search | QueryString + optional ViewArn (default view); ≤1000/page, **hard cap 1000 results**; tokens expire 24h; **async index — modifications may take up to 2 weeks** → never authoritative | API_Search; using-search; quotas | current |
| CloudTrail LookupEvents | management events, last 90 days, ≤50/page (NextToken + identical params), **2 req/s/account/Region**; `CloudTrailEvent` JSON string = full record | API_LookupEvents | current |
| EKS Pod Identity | ListPodIdentityAssociations (ns/SA filters, ≤100/page) → summary lacks roleArn → DescribePodIdentityAssociation for roleArn | API_(List|Describe)PodIdentityAssociation(s) | current |
| IRSA vs Pod Identity | distinct surfaces: SA annotation `eks.amazonaws.com/role-arn`+OIDC+trust vs EKS API association+`pods.eks.amazonaws.com` trust; **IRSA wins when both** (web-identity earlier in credential chain) — migration path | pod-identities docs; standardized-credentials | current |
| Pagination | NextToken/Marker/ContinuationToken variants; terminate on null token not empty page | cli-usage-pagination | current |
| Throttling | Throttling*/TooManyRequestsException/RequestLimitExceeded/SlowDown; backoff w/ full jitter, 20s cap | feature-retry-behavior | current |
| STS GetCallerIdentity | no permissions required — safe preflight for account+ARN | API_GetCallerIdentity | current |
| Secret-surface exclusions | `secretsmanager:GetSecretValue`/`BatchGetSecretValue`, `kms:Decrypt`, `ssm:GetParameter*` SecureString are *value reads* despite Get* prefix — exclude by name | API refs; AWSSecretsManagerClientReadOnlyAccess | current |

## OTel / Hubble / Prometheus

| Capability | Claims | Source | Version status |
|---|---|---|---|
| Resource identity attrs | `service.name` Required+Stable; `service.namespace`/`service.instance.id`/`k8s.cluster.name`/`k8s.namespace.name`/`k8s.pod.name`/`k8s.deployment.name` Recommended+Stable; **`cloud.*` = Development stability**; identity attrs are `k8s.pod.uid`/`k8s.cluster.uid` | semconv resource/{service,k8s,cloud} | mixed |
| Span→edge recipe | pair CLIENT|PRODUCER span with SERVER|CONSUMER whose parentSpanId matches → service.name→service.name edge; unpaired clients → virtual node via server.address/db.namespace/service.peer.name | servicegraphconnector design | — |
| Span attrs | `server.address`+`server.port` Required on HTTP client; `db.system.name` (new, Stable; `db.system` deprecated); `peer.service` deprecated → `service.peer.name` | http/db/rpc semconv | mixed |
| SpanKind | proto int kind: SERVER=2 CLIENT=3 PRODUCER=4 CONSUMER=5 | trace api spec | stable |
| OTLP JSON | traceId/spanId hex strings; enums as ints; lowerCamelCase; file exporter = one JSON/line (TracesData) | OTLP spec; file-exporter spec | stable |
| Hubble flows | eBPF datapath monitor events = real-traffic evidence; verdicts FORWARDED/DROPPED/AUDIT(m)/…; **finite ring buffer → lost_events reported**; `-o jsonpb` line format `{flow:{...},node_name,time}`; Endpoint has `source_service`/`destination_service`, `pod_name`, labels — no pod IP (in flow.IP) | docs.cilium.io hubble internals + flow proto | current |
| Prometheus mesh counters | `istio_requests_total{reporter,source_workload(_namespace),destination_workload(_namespace),destination_service…}` — counter increments only on real traffic (T0); missing series ≠ no traffic | istio metrics ref; hubble metrics | current |
| Trace sampling | default ParentBased(AlwaysOn); `traceidratio` deprecated→ProbabilitySampler; tail-sampling biases toward errors → **edge presence is sound, edge absence is never proof** | otel sdk/config specs; tailsamplingprocessor | current |
| EndpointSlice | proves routing membership only (T1), not traffic | endpoint-slices docs | stable |

## Design consequences folded into CYCLE-3 design/contract

- `sendInitialEvents` gated on server version ≥1.34-on / capability probe
  with mandatory LIST+WATCH fallback (spec §40–41).
- Pod Identity needs `Describe` per association (summary lacks roleArn).
- Resource Explorer results tagged non-authoritative (index lag ≤2wk).
- Selector-less ListDiscoveredResources exposes not-recorded types →
  coverage `recorded|not-recorded|unsupported` (cycle §57).
- OTel ingest accepts both flattened JSONL and real OTLP `resourceSpans`
  (repo gap noted in `observe/otel.py` — fixed in Phase G).
- Hubble AUDIT ≠ drop; lost_events → coverage note, not silence.
