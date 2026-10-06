# Platform Forge

**Agentic Platform Engineering intelligence platform** — deterministic,
offline-first, evidence-first, graph-aware, provider-neutral in the core.

Platform Forge looks at repositories, Terraform, Kubernetes, GitOps, cloud
accounts, CI/CD, observability, SLOs, security, cost and ownership, and builds
one coherent, evidence-backed model of a platform.

*Versão em Português: [README.pt-BR.md](README.pt-BR.md)*

## Install

```bash
pip install -e .          # core (offline-capable)
pip install -e ".[mcp]"   # + MCP adapter
pip install -e ".[dev]"   # + tests/lint
```

## Quick start

```bash
platformforge doctor            # environment health
platformforge init              # scaffold .platformforge/ in a repo
platformforge inspect .         # inventory artifacts
platformforge analyze .         # extract facts
platformforge judge             # apply rule catalog
platformforge graph             # build the platform graph
platformforge impact            # blast radius of a change
```

## Design docs

[ARCHITECTURE.md](ARCHITECTURE.md) · [GRAPHFY.md](GRAPHFY.md) ·
[ECONOMY.md](ECONOMY.md) · [SDD.md](SDD.md) · [AGENTIC-OS.md](AGENTIC-OS.md) ·
[DOMAIN-MAP.md](DOMAIN-MAP.md) · [CAPABILITIES.md](CAPABILITIES.md) ·
[RESEARCH.md](RESEARCH.md) · [ROADMAP.md](ROADMAP.md)

## License

MIT — see [LICENSE](LICENSE), [SOURCES.md](SOURCES.md), [CREDITS.md](CREDITS.md).
