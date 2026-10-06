# Graph Report - platform-forge  (2026-10-06)

## Corpus Check
- 43 files · ~11,078 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 239 nodes · 387 edges · 18 communities (14 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b36dee6c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Fact
- properties
- engine.py
- SourceRegistry
- main.py
- receipts.py
- ArtifactStore
- hashing.py
- finding.schema.json
- test_core.py
- load_workspace
- Platform Forge
- core/__init__.py
- platformforge/__init__.py
- knowledge/__init__.py
- platformforge

## God Nodes (most connected - your core abstractions)
1. `ArtifactStore` - 16 edges
2. `Fact` - 16 edges
3. `SourceRegistry` - 10 edges
4. `Finding` - 10 edges
5. `load_catalog()` - 10 edges
6. `RuleEngine` - 10 edges
7. `_emit()` - 9 edges
8. `build_parser()` - 9 edges
9. `load_workspace()` - 9 edges
10. `cmd_judge()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `test_artifact_store_roundtrip()` --calls--> `ArtifactStore`  [EXTRACTED]
  tests/test_core.py → platformforge/core/store.py
- `test_source_freshness_classification()` --uses--> `SourceRegistry`  [INFERRED]
  tests/test_core.py → platformforge/knowledge/registry.py
- `test_fact_deterministic_id_and_tier_gate()` --calls--> `Fact`  [EXTRACTED]
  tests/test_core.py → platformforge/models/base.py
- `test_fact_rejects_llm_tier()` --calls--> `Fact`  [EXTRACTED]
  tests/test_core.py → platformforge/models/base.py
- `test_finding_requires_evidence()` --calls--> `Finding`  [EXTRACTED]
  tests/test_core.py → platformforge/models/base.py

## Import Cycles
- None detected.

## Communities (18 total, 4 thin omitted)

### Community 0 - "Fact"
Cohesion: 0.07
Nodes (26): IntEnum, EvidenceTier, Fact, Finding, FreshnessStatus, Any, Canonical contracts for the epistemic pipeline. Fact: something directly…, PF-<KIND AREA>-<n>: area derived from kind (`k8s.workload` -> K8S). (+18 more)

### Community 1 - "properties"
Cohesion: 0.06
Nodes (36): additionalProperties, type, items, minItems, type, pattern, type, type (+28 more)

### Community 2 - "engine.py"
Cohesion: 0.13
Nodes (18): _eval_op(), load_catalog(), _Missing, _num(), _parse_version(), Any, Path, Executable rules over facts. A rule = applicability + conditions over fact… (+10 more)

### Community 3 - "SourceRegistry"
Cohesion: 0.16
Nodes (10): date, knowledge_age_days(), Any, Path, Source registry + knowledge freshness. Old documentation is never eternal…, current|fresh|stale|deprecated|superseded|conflicted|unresolved., Freshness report for every registered source., SourceEntry (+2 more)

### Community 4 - "main.py"
Cohesion: 0.25
Nodes (17): ArgumentParser, Namespace, _add_common(), build_parser(), cmd_doctor(), cmd_init(), cmd_inspect(), cmd_judge() (+9 more)

### Community 5 - "receipts.py"
Cohesion: 0.16
Nodes (10): _iso(), Any, Path, Evidence receipts — every important operation emits one. Receipts capture…, Persists receipts under .platformforge/receipts/ (audit trail)., Context manager stamping started_at/ended_at on a receipt., Receipt, ReceiptWriter (+2 more)

### Community 6 - "ArtifactStore"
Cohesion: 0.26
Nodes (4): ArtifactStore, Any, Path, test_artifact_store_roundtrip()

### Community 7 - "hashing.py"
Cohesion: 0.19
Nodes (11): Any, Path, Content addressing — the basis of caching, provenance and dedup. Everything…, Canonical JSON hashing — key order and whitespace normalized., sha256_bytes(), sha256_file(), sha256_obj(), sha256_text() (+3 more)

### Community 8 - "finding.schema.json"
Cohesion: 0.15
Nodes (12): additionalProperties, description, $id, required, $schema, title, type, evidence (+4 more)

### Community 9 - "test_core.py"
Cohesion: 0.27
Nodes (11): contains_secret(), k8s_secret_values(), _marker(), Any, Secrets redaction — core layer. Applied to anything entering context packs,…, Deep-redact strings in dict/list structures., Blank out Kubernetes Secret payload fields entirely — base64 values are still…, redact_obj() (+3 more)

### Community 10 - "load_workspace"
Cohesion: 0.26
Nodes (9): find_root(), init_workspace(), load_workspace(), Path, Workspace model — Platform Forge works globally-installed, inside a repo,…, Walk up to the nearest .platformforge/ or workspace.yaml, else `start`., Workspace, WorkspaceMember (+1 more)

### Community 11 - "Platform Forge"
Cohesion: 0.33
Nodes (5): Design docs, Install, License, Platform Forge, Quick start

## Knowledge Gaps
- **39 isolated node(s):** `Install`, `Quick start`, `Design docs`, `License`, `$schema` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ArtifactStore` connect `ArtifactStore` to `test_core.py`, `main.py`, `hashing.py`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `Fact` connect `Fact` to `test_core.py`, `engine.py`, `main.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `SourceRegistry` connect `SourceRegistry` to `test_core.py`, `main.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `SourceRegistry` (e.g. with `cmd_knowledge()` and `test_source_freshness_classification()`) actually correct?**
  _`SourceRegistry` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Install`, `Quick start`, `Design docs` to the rest of the system?**
  _39 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Fact` be split into smaller, more focused modules?**
  _Cohesion score 0.0728744939271255 - nodes in this community are weakly interconnected._
- **Should `properties` be split into smaller, more focused modules?**
  _Cohesion score 0.05555555555555555 - nodes in this community are weakly interconnected._