# Install

```bash
platformforge install . --profile agentic --host codex --dry-run
platformforge install . --profile agentic --host codex --host claude
platformforge portable doctor .
```

Default behavior is workspace-local and conflict-preserving. Existing files not owned by a previous install receipt are never overwritten.
