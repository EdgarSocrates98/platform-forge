---
id: cyc9-07
title: scenarios-platform-engineering
status: inbox
created: 2026-10-15
owner: platform-forge
scope: repo
cycle: 9
wave: 3
priority: p1
risk: medium
agent: codex
source: prompt_evo_cycles.md §9.3 Platform Engineering
verification:
  - uv run pytest -q
  - uv run ruff check .
  - uv run platformforge lab run-all
---

# Cenários Forge Lab — Platform Engineering

## Outcome

Biblioteca versionada de cenários do domínio de plataforma com fixtures locais e ground truth: revisão Terraform, Kubernetes, CI/CD, segurança, FinOps, riscos de implantação, blast radius.

## Grill gate

- Problema observado: capacidades do especialista sem cenários mensuráveis.
- Usuário afetado: Benchmark Engineer e usuário avaliando o especialista.
- Falha concreta: claims de qualidade sem dataset verificável.
- Decisão: cenários do §9.3 Platform como fixtures (módulos Terraform, manifests k8s, pipelines) + classificações esperadas, limitados às capacidades suportadas.
- Fora de escopo: aplicar mudanças em infra real; centralizar motor no the-forge.
- Critério de parada: ao menos um cenário por categoria suportada, executável localmente e integrável ao harness federado.

## Acceptance

- Cenários versionados por categoria: Terraform, Kubernetes, CI/CD, segurança, FinOps, riscos de implantação, blast radius.
- Cada cenário: fixture + entrada + resultado esperado + classificação (ground truth).
- Execução local; saída compatível com contrato de métricas (cyc9-02).
- Categorias não suportadas → `not_available`, não simuladas.

## Constraints

- Independência: roda sem the-forge/CLI/Portal.
- Fixtures nunca executam apply/deploy real.

## Pending

- ⚠ Capacidades efetivamente implementadas (baseline cyc0-01); gates do repo a confirmar.
