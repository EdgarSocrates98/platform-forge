# SOURCES — provenance & clean-room registry

Platform Forge reuses *conventions and contracts* from sibling first-party
projects and implements external-tool-inspired behavior clean-room.

| Inspiration | What is reused | License / provenance |
|---|---|---|
| `spark-forge-aws` (same author) | evidence model shape, rule catalog layout, SDD lifecycle discipline, economy ledger concepts, agent mirror generation | MIT — first-party |
| `api-forge` (same author) | refusal-code discipline (`AF-*` → `platform.*.unresolved`), TaskSpec-style agent contracts, capability registry → host mirror parity, context-compact/`agentops` ideas | MIT — first-party |
| TokenSave / RTK / Caveman / Graphfy / AgentSpec-style contracts | *behavioral ideas only* — all code here is original implementation | clean-room |
| CNCF Platform Maturity Model v1.0 | assessment *structure* (5 aspects × 4 levels) as inspiration; own criteria, no copied text | CC-BY — cited, not copied |
| SLSA v1.2, FOCUS 1.2/1.4, OTel semconv | public specifications — referenced, version-pinned | public specs |
| python-hcl2 | HCL parsing dependency | MIT |

Every rule's `sources:` list cites `knowledge/sources.yaml` IDs. No third-party
code is vendored without a LICENSE review recorded here.
