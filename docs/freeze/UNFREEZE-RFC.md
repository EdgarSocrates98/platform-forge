# UNFREEZE RFC — template (§209)

> An unfreeze request is a FeatureException with `decision:
> deferred` and this document attached as evidence. The freeze is
> the default state; the burden of proof is on the unfreeze.

## 1. Trigger

Which §208 condition is met?

- [ ] real-world blocker (link the case in `.platformforge/cases/`)
- [ ] major ecosystem evolution (cite the dated external source)
- [ ] new required platform paradigm (explain why no current pillar covers it)

## 2. Evidence

- `real_world_blocker`: the exact capability gap, with a reproducible case.
- Why existing capability is insufficient (which verb was tried, what it returned).
- Alternatives considered and why each fails.

## 3. Blast radius

- schemas touched (new family? migration of a frozen one?)
- agents touched (roster delta, budget delta)
- control planes touched
- estimated review surface (files, gates)

## 4. Rollback

How the change is reverted if the post-freeze evidence contradicts it.

## 5. Decision

`approved` | `rejected` | `deferred` — decided by, date, case id.
