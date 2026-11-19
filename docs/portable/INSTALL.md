# Install

```bash
platformforge install . --profile agentic --host codex --dry-run
platformforge install . --profile agentic --host codex --host claude
platformforge portable doctor .
```

Default behavior is workspace-local and conflict-preserving. Existing files not owned by a previous install receipt are never overwritten.

Reinstalls are incremental: byte-identical assets are classified `identical` in the plan and never re-written. Every `forge/InstallReceipt/v1` and `forge/InstallationHealth/v1` document carries a derived `lifecycle` block (`forge/InstallLifecycle/v1`) — `status: completed` means the writer finished; the honest position is `planned → applied → verified → ready`.
