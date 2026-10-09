# Offline bundles

```bash
platformforge portable build dist/platformforge-portable --host codex
platformforge portable verify dist/platformforge-portable
```

The bundle contains generated host assets, a versioned distribution manifest and `MANIFEST.sha256`. Building and verifying the bundle require no network access. Provider-backed runtime capabilities remain separately governed.
