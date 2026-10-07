# CYCLE 2 — FINAL ARCHITECTURAL REVIEW (§190)

## Shape that held up

```
collect (dump-only) → facts (T0–T7) → judge (sourced, version-gated rules)
                    → graphfy (provenance edges) → compose verbs
                    → explain/recommend/plan (evidence-bound) → receipts
        TokenSave/Caveman/RTK  =  economy layer (bounded, redacted)
        Lab + evals            =  verification corpus
        MCP                    =  bounded, redacted projection of CLI
```

The one-spine bet (ADR-0002) paid off: every new Wave-E/F/H surface —
delivery edges, identity paths, cross-repo joins, ownership conflicts —
fell out of the same `Fact→Edge` model instead of a parallel taxonomy.

## Decisions that were right

- **Provenance on edges, state on nodes** (ADR-0004) — drift and
  contradiction surfaces became trivial once provenance was first-class.
- **Analyzer-level joins** — HPA→requests, IAM→role chaining join in the
  analyzer, not in rules; rules stay declarative predicates.
- **`version_satisfies → True|False|None`** (ADR-0007) — `None` maps to
  `unresolved` notes instead of a forced verdict; kept honest.
- **Boundary redaction, defense-in-depth** (ADR-0005) — the caveman/MCP
  gaps found in Wave K were caught by the property tests, patched at the
  layer, not by trusting each tool.
- **`inferred` provenance** — cross-repo name joins are challengeable
  because they carry `provenance: inferred` + `via`.

## Known structural debts (named, not hidden)

- `cli/main.py` (~1.5k lines) is a god-dispatcher — works, but the next
  refactor should split per-domain command modules behind `main()`.
- `_load_facts`/`_load_graph_or_refuse` are duplicated across `cmd_*`
  — worth a shared loader once verb count stabilizes.
- Version-gated coverage is thin (2 rules) — the mechanism is right,
  the gate needs more rules to prove breadth.
- Precision corpus is small (6 rules measured) — honest, bounded.
- `Fact.attrs` carries both extraction and graph cross-refs
  (`attrs.graph.nodes`) — a fact↔edge separation would clean it.
- MCP bounds live on each tool rather than a single negotiated budget —
  works, but a session-level budget token would be cleaner.

## Verdict

Architecture is sound for the stated mission — offline-first,
evidence-backed, read-only — and held without bending through 13 waves.
The debts above are real but local; none compromise the epistemic core.
