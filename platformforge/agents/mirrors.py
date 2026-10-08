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


def _md(spec: AgentSpec) -> str:
    def bullets(items):
        return "\n".join(f"- {i}" for i in items) or "- (none)"
    return f"""---
name: {spec.name}
description: {spec.when_to_enter}
---

# {spec.name}

Role: {spec.role} · Access: {spec.access} · Write: {spec.write_scope}
Model tier: {spec.model_tier} · Budget: {spec.max_context_budget}B ctx /
{spec.max_tool_calls} tool calls / fanout ≤{spec.max_parallelism}
Domains: {', '.join(spec.domains)}

## Mission
{spec.mission}

## Enter when
{spec.when_to_enter}

## Do NOT enter when
{spec.when_not_to_enter}

## Inputs
{bullets(spec.inputs)}

## Method
Allowed verbs: {', '.join(spec.allowed_verbs) or 'read-only inspection'}
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
{spec.never}
"""


def _toml(spec: AgentSpec) -> str:
    lines = [f'name = "{spec.name}"',
             f'description = """{spec.when_to_enter}"""',
             f'role = "{spec.role}"',
             f'access = "{spec.access}"',
             f'model_tier = "{spec.model_tier}"',
             f'domains = {list(spec.domains)!r}'.replace("'", '"'),
             f'verbs = {list(spec.allowed_verbs)!r}'.replace("'", '"'),
             f'verifier = "{spec.verifier}"',
             f'never = """{spec.never}"""']
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
            out[str(p.relative_to(root))] = GEN_BANNER + render(spec, fmt)
    return out


def sync(root: str | Path) -> dict[str, list[str]]:
    root = Path(root)
    want = expected(root)
    written: dict[str, list[str]] = {rel: [] for rel in TARGETS}
    for rel in TARGETS:
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel_path, content in want.items():
        p = root / rel_path
        p.write_text(content)
        written[str(Path(rel_path).parent)].append(rel_path)
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
        elif p.read_text() != content:
            problems.append(f"stale mirror: {rel_path}")
    stale_dirs = []
    for rel in TARGETS:
        d = root / rel
        if d.is_dir():
            for f in sorted(d.iterdir()):
                rel_f = str(f.relative_to(root))
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
