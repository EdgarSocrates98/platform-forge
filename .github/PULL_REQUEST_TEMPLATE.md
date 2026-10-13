## Summary

<!-- What changes and why. Link the issue/spec if one exists. -->

## Evidence

<!-- This project is evidence-first: paste the commands you ran and
     their verdicts. -->

```bash
uv run pytest -q
uv run ruff check .
uv run python scripts/validate.py   # or: the gates your change touches
```

- [ ] Tests/lint green locally
- [ ] `tests/test_docs_drift.py` passes (docs name real verbs only)
- [ ] New behavior has a test + eval/lab case where applicable
- [ ] No secrets/credentials in the diff
- [ ] Refusals keep a `PF-*` code + `unlock`
- [ ] Docs updated (CAPABILITIES/CLI-REFERENCE/CHANGELOG) if surface changed

## Boundaries checked

- [ ] No mutation path added to the offline core
- [ ] `planned ≠ observed` preserved; absences are named, not zero
- [ ] New agent/roster changes pass `agents lint` + `agents check`
