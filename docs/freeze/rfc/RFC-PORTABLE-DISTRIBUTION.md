# RFC — Portable Distribution Unfreeze (FE-003)

## Decision

Temporarily unfreeze only the delivery layer needed to make Platform Forge consumable from arbitrary workspaces.

## Allowed changes

- additive `platformforge.distribution` and `platformforge.workspace` modules;
- install/upgrade/uninstall/portable/workspace CLI surfaces;
- additive distribution/workspace/install-receipt v1 schemas;
- generated Codex/Claude/Devin/generic host assets and canonical skills;
- offline bundle integrity, doctor, tests and documentation.

## Frozen invariants

No change is authorized to Fact/Finding semantics, Graphfy identity, Economy routing authority, agent roster authority, controlled operations, approval/rollback policy or provider access.

## Exit criteria

1. install is plan-first and refuses user-file conflicts;
2. uninstall removes only owned+unchanged assets;
3. bundle tampering fails closed;
4. offline bundle install requires no network;
5. Codex and Claude receive loadable agents and skills derived from canonical sources;
6. workspace state is local by default;
7. CLI/schema snapshots are rebaselined under FE-003;
8. portability validation gates are part of `scripts/validate.py`.

After these criteria are met, FE-003 is considered delivered and the architecture returns to freeze/dogfooding.
