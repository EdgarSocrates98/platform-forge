"""Host mirrors — render the canonical roster to host surfaces
(§92–96): agents/, .agents/agents/, .claude/agents/, .codex/agents/,
.devin/agents/. The roster is the source of truth; mirrors are OUTPUT.
Never edit a mirror by hand — `agents check` fails on drift.
"""

from __future__ import annotations

from pathlib import Path

from platformforge.agents.roster import AGENTS, AgentSpec

GEN_BANNER = ("# GENERATED from platformforge/agents/roster.py "
              "— do not edit; run `platformforge agents sync`\n")

# every host gets the canonical mirror set (§92)
TARGETS: dict[str, str] = {
    "agents": "md",
    ".agents/agents": "md",
    ".claude/agents": "md",
    ".codex/agents": "toml",
    ".devin/agents": "md",
}

# §106 — host adapter: tier → concrete host tools/model. The roster
# stays provider-free; only mirrors carry host vocabulary. No access
# tier maps to Edit/Write: platform state is persisted through the
# `platformforge` CLI (runs/artifacts), never by editing the tree.
HOST_TOOLS: dict[str, str] = {
    "read-only": "Read, Grep, Glob, Bash",
    "state-writer": "Read, Grep, Glob, Bash",
    "workspace-writer": "Read, Grep, Glob, Bash, Edit, Write",
    "governed-writer": "Read, Grep, Glob, Bash",
}
HOST_MODEL: dict[str, str] = {
    "deterministic": "haiku",
    "fast": "haiku",
    "standard": "sonnet",
    "deep": "opus",
    "critical-review": "opus",
}

# domain → host skill carrying the verb reference for that domain
DOMAIN_SKILL: dict[str, str] = {
    "graph": "platformforge-graph",
    "change": "platformforge-change", "ops": "platformforge-change",
    "plans": "platformforge-change", "release": "platformforge-change",
    "simulate": "platformforge-change", "drift": "platformforge-change",
    "sre": "platformforge-sre", "slo": "platformforge-sre",
    "incident": "platformforge-sre", "capacity": "platformforge-sre",
    "otel": "platformforge-sre", "reliability": "platformforge-sre",
    "runtime": "platformforge-sre",
    "finops": "platformforge-finops",
    "security": "platformforge-security", "privacy": "platformforge-security",
    "fleet": "platformforge-fleet", "federation": "platformforge-fleet",
    "optimization": "platformforge-fleet", "ai": "platformforge-fleet",
    "gpu": "platformforge-fleet",
    "policy": "platformforge-governance",
    "governance": "platformforge-governance",
    "product": "platformforge-governance", "dx": "platformforge-governance",
    "golden-paths": "platformforge-governance",
    "economy": "platformforge-economy",
    "evidence": "platformforge-agents", "closure": "platformforge-agents",
    "proof": "platformforge-agents", "conflicts": "platformforge-agents",
    "tasks": "platformforge-agents", "compose": "platformforge-agents",
}


def skills_for(spec: AgentSpec) -> list[str]:
    out: list[str] = []
    for d in spec.domains:
        s = DOMAIN_SKILL.get(d, "platformforge-core")
        if s not in out:
            out.append(s)
    return out


def _description(spec: AgentSpec) -> str:
    text = f"{spec.mission}. Use when: {spec.when_to_enter}."
    if spec.when_not_to_enter:
        text += f" Do NOT use when: {spec.when_not_to_enter}."
    return text


def _yaml_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _body(spec: AgentSpec) -> str:
    def bullets(items):
        return "\n".join(f"- {i}" for i in items) or "- (none)"
    verbs = ", ".join(f"`platformforge {v}`" for v in spec.allowed_verbs)
    return f"""# {spec.name}

You are `{spec.name}`, a Platform Forge {spec.role}. Mission: {spec.mission}.

Role: {spec.role} · Access: {spec.access} · Write: {spec.write_scope}
Model tier: {spec.model_tier} · Budget: {spec.max_context_budget}B ctx /
{spec.max_tool_calls} tool calls / fanout ≤{spec.max_parallelism}
Domains: {', '.join(spec.domains)}

## Enter when
{spec.when_to_enter}

## Do NOT enter when
{spec.when_not_to_enter}

If the request matches "Do NOT enter when", stop and return a named
refusal with the agent or skill that should take it — do not stretch.

## Inputs
{bullets(spec.inputs)}

## How to work
- Do the work through the `platformforge` CLI (fall back to
  `.venv/bin/platformforge` when it is not on PATH). Verbs you may run:
  {verbs or 'none — read-only inspection of supplied artifacts'}.
- Verb reference and reading rules live in skill(s):
  {', '.join(skills_for(spec))} — load them before running verbs.
- Cite `fact_id` / `rule_id` / evidence ids for every claim; what you
  cannot back with evidence goes to `unresolved`, never into prose.
- Stay inside your budget; when it runs out, report `partial`.

Capabilities: {', '.join(spec.allowed_capabilities) or '(none declared)'}
Required evidence: {', '.join(spec.required_evidence) or '(none)'}

## Output
{', '.join(spec.outputs)}

## Boundaries
Delegates to: {', '.join(spec.delegates_to) or 'nobody'}
Never delegates to: {', '.join(spec.cannot_delegate_to) or '(none)'}
Reviewed by: {', '.join(spec.reviewers) or '(none)'}
Verifier: {spec.verifier or '(none)'}
Escalation: {spec.escalation or 'human operator'}

## Done when
{spec.done_when}

## Never
{spec.never}; edit repository files; run `change approve|apply` or any
`ops`/`live` mutation — those stay host-side behind a human gate.
"""


def _md(spec: AgentSpec) -> str:
    # frontmatter must open on line 1 or hosts ignore the agent; the
    # banner therefore lives inside it as a YAML comment.
    return f"""---
{GEN_BANNER.rstrip()}
name: {spec.name}
description: {_yaml_str(_description(spec))}
tools: {HOST_TOOLS.get(spec.access, HOST_TOOLS["read-only"])}
model: {HOST_MODEL.get(spec.model_tier, "inherit")}
---

{_body(spec)}"""


def _toml_str(text: str) -> str:
    return '"""' + text.replace("\\", "\\\\").replace('"""', '\\"""') + '"""'


def _toml(spec: AgentSpec) -> str:
    lines = [GEN_BANNER.rstrip(),
             f'name = "{spec.name}"',
             f'description = {_toml_str(_description(spec))}',
             f'developer_instructions = {_toml_str(_body(spec))}',
             f'role = "{spec.role}"',
             f'access = "{spec.access}"',
             f'model_tier = "{spec.model_tier}"',
             f'domains = {list(spec.domains)!r}'.replace("'", '"'),
             f'verbs = {list(spec.allowed_verbs)!r}'.replace("'", '"'),
             f'verifier = "{spec.verifier}"',
             f'never = {_toml_str(spec.never)}']
    return "\n".join(lines) + "\n"


def render(spec: AgentSpec, fmt: str) -> str:
    return _toml(spec) if fmt == "toml" else _md(spec)


def expected(root: str | Path) -> dict[str, str]:
    """Mirror path → expected content. The drift gate compares this."""
    root = Path(root)
    out: dict[str, str] = {}
    for rel, fmt in TARGETS.items():
        ext = ".toml" if fmt == "toml" else ".md"
        for spec in AGENTS.values():
            p = root / rel / f"{spec.name}{ext}"
            out[p.relative_to(root).as_posix()] = render(spec, fmt)
    return out


def sync(root: str | Path) -> dict[str, list[str]]:
    root = Path(root)
    want = expected(root)
    written: dict[str, list[str]] = {rel: [] for rel in TARGETS}
    for rel in TARGETS:
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel_path, content in want.items():
        p = root / rel_path
        p.write_text(content, encoding="utf-8")
        written[Path(rel_path).parent.as_posix()].append(rel_path)
    return {k: sorted(v) for k, v in written.items()}


def check(root: str | Path) -> dict[str, object]:
    """Mirror drift gate — on-disk must equal generated; extra files in
    mirror dirs that aren't generated are drift too."""
    root = Path(root)
    want = expected(root)
    problems = []
    for rel_path, content in want.items():
        p = root / rel_path
        if not p.is_file():
            problems.append(f"missing mirror: {rel_path}")
        elif p.read_text(encoding="utf-8") != content:
            problems.append(f"stale mirror: {rel_path}")
    stale_dirs = []
    for rel in TARGETS:
        d = root / rel
        if d.is_dir():
            for f in sorted(d.iterdir()):
                rel_f = f.relative_to(root).as_posix()
                if f.is_file() and rel_f not in want \
                        and f.suffix in (".md", ".toml"):
                    stale_dirs.append(rel_f)
    problems += [f"stray mirror file (not generated): {s}"
                 for s in stale_dirs]
    return {"ok": not problems, "problems": problems,
            "mirrors": len(want)}


def lint() -> dict[str, object]:
    problems = []
    for a in AGENTS.values():
        problems.extend(f"{a.name}: {e}" for e in a.contract_errors())
    return {"agents": len(AGENTS), "problems": problems,
            "ok": not problems}
