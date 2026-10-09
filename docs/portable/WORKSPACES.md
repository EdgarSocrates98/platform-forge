# Workspaces

```bash
platformforge workspace init .
platformforge workspace add ./service-a
platformforge workspace list
platformforge workspace doctor
```

The manifest lives at `.platformforge/workspace.json`. State mode is `workspace-local` by default and multi-repo membership is explicit.
