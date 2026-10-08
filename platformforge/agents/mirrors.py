"""Host mirrors — render canonical roster to .claude/agents/*.md,
.agents/agents/*.md, .codex/agents/*.toml. Generated artifacts: the roster
is source, mirrors are output. Never edit a mirror by hand."""

from __future__ import annotations

from pathlib import Path

from platformforge.agents.roster import AGENTS, AgentSpec


def _md(spec: AgentSpec, drop_tools: bool = False) -> str:
    ex = ("\n## Executors\n" + "\n".join(f"- {e}" for e in spec.executors)
          if spec.executors else "")
    return f"""---
name: {spec.name}
description: {spec.when}
---

# {spec.name}

Role: {spec.role} · Access: {spec.access}
Domains: {', '.join(spec.domains)}

## When you enter
{spec.when}

## Never do
{spec.never}

## Inputs
{chr(10).join('- ' + i for i in spec.inputs) or '- facts'}

## Method
Allowed verbs: {', '.join(spec.verbs) or 'read-only inspection'}

## Output
{', '.join(spec.outputs)}{ex}
"""


def _toml(spec: AgentSpec) -> str:
    lines = [f'name = "{spec.name}"',
             f'description = """{spec.when}"""',
             f'role = "{spec.role}"',
             f'access = "{spec.access}"',
             f'verbs = {list(spec.verbs)!r}'.replace("'", '"')]
    return "\n".join(lines) + "\n"


def sync(root: str | Path) -> dict[str, list[str]]:
    root = Path(root)
    written: dict[str, list[str]] = {}
    targets = {
        ".claude/agents": _md,
        ".agents/agents": _md,
        ".codex/agents": lambda s: _toml(s),
    }
    for rel, render in targets.items():
        d = root / rel
        d.mkdir(parents=True, exist_ok=True)
        files = []
        for spec in AGENTS.values():
            ext = ".toml" if rel == ".codex/agents" else ".md"
            p = d / f"{spec.name}{ext}"
            content = ("# GENERATED from platformforge/agents/roster.py "
                       "— do not edit\n" + render(spec))
            p.write_text(content)
            files.append(str(p.relative_to(root)))
        written[rel] = sorted(files)
    return written


def lint() -> dict[str, object]:
    problems = []
    for a in AGENTS.values():
        problems.extend(f"{a.name}: {e}" for e in a.contract_errors())
    return {"agents": len(AGENTS), "problems": problems,
            "ok": not problems}
