---
name: Bug report
about: Something produces a wrong, missing, or unverifiable answer
title: "[bug] "
labels: bug
---

**Command run**

```bash
platformforge <verb> ...
```

**Expected vs observed** (keep the `PF-*` code / `unresolved` naming if
one was emitted — a wrong verdict and a missing refusal are different bugs)

**Evidence**

- `platformforge doctor` output
- input artifacts or a minimal fixture that reproduces it
- `fact_id`/`rule_id` involved, if known

**Environment**: python version, install method (`pip install -e .` / uv).
