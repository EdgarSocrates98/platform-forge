# Portable Distribution & Workspace Integration

Portable distribution is an additive delivery layer over the frozen Platform Forge core.

```
canonical agents / capabilities
        |
        v
DistributionManifest
        |
        v
InstallPlan -> staged writes -> integrity check -> commit
        |
        v
workspace-local .platformforge + selected host mirrors
```

Principles:

- plan-first, no overwrite of user-modified files;
- workspace-local by default; no global host configuration;
- Codex, Claude, Devin and generic `.agents` mirrors are generated from the canonical roster;
- bundle verification is checksum-based and fails closed;
- offline bundles perform no downloads;
- install receipts are the ownership source for upgrade/uninstall;
- the portable layer does not alter evidence, Graphfy, economy or operations semantics.
