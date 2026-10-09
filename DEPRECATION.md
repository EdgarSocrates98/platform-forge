# Deprecation & versioning policy

## Principles

- **Contracts version, behavior migrates.** Every persisted artifact
  (`observation`, `graph`, `operation`, `config`, `envelope`) carries a
  `schema`/`schema_version`. New versions add forward migrations; old
  versions still *read*.
- **Nothing is deleted silently.** A deprecated verb/field keeps working
  for at least one minor release and emits a `deprecated` warning in the
  output payload.
- **Unknown ≠ removed.** An unrecognized schema version refuses with
  `PF-OPS-CONFIG-VERSION` (or the domain's equivalent) and an upgrade
  instruction — never a guess.

## Current deprecations

| Item | Since | Replacement | Removal |
|---|---|---|---|
| capability-manifest/v2 | cycle 4 | v3 (adds `operations`, `cross_forge`) | v2 readers unaffected; emitters produce v3 only |

## Breaking-change process

1. Bump `schema_version`; write `_migrate_N_to_N+1` (see
   `platformforge/ops/config.py`, `platformforge/ops/store.py`).
2. Old stores migrate on open; failed migrations refuse, never corrupt.
3. CLI flags: old flag keeps working for one release with a warning;
   removal is a minor-version event documented in CHANGELOG.
4. Action vocabulary is append-only. Removing a typed action is a
   breaking change requiring a manifest version bump.

## API/CLI stability

- `platformforge.*` Python API: pre-1.0, minor-version breakage allowed
  but each break must ship a migration note.
- JSON outputs (`-o json`): field *removals* are breaking; additions are
  safe.
- Exit codes and `PF-*` refusal codes are a stable contract — codes are
  never reused for different meanings.
