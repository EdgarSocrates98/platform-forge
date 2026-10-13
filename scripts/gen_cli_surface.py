"""Generate docs/CLI-SURFACE.md — the complete, machine-generated
command-surface reference.

CLI-REFERENCE.md is the curated, human-readable guide; this file is the
exhaustive index: every verb, every subcommand, every flag — emitted
deterministically from build_parser() so it can never drift. The
docs-drift test regenerates it in-memory and compares bytes.

Usage: python scripts/gen_cli_surface.py [--check] [--write]
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

OUT = Path("docs/CLI-SURFACE.md")
GLOBAL_OPTS = {"detail_level", "output", "json", "offline", "strict",
               "help"}


def _subs(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for a in parser._actions:
        if isinstance(a, argparse._SubParsersAction):
            return dict(a.choices)
    return {}


def _fmt_default(a: argparse.Action) -> str:
    d = getattr(a, "default", None)
    if d in (None, argparse.SUPPRESS) or isinstance(d, bool):
        return ""
    return f" (default {d!r})"


def _action_line(a: argparse.Action) -> str:
    names = ", ".join(a.option_strings) if a.option_strings \
        else f"<{a.dest}>"
    bits = names
    if a.choices and a.dest not in GLOBAL_OPTS:
        bits += " {" + "|".join(str(c) for c in a.choices) + "}"
    elif isinstance(a, (argparse._StoreTrueAction,
                        argparse._StoreFalseAction)):
        pass
    elif a.option_strings:
        bits += " <v>"
    h = (a.help or "").strip()
    if h:
        bits += f" — {h}"
    return bits + _fmt_default(a)


def _render_parser(out: io.StringIO, parser: argparse.ArgumentParser,
                   prefix: str, depth: int) -> None:
    subs = _subs(parser)
    # positional-with-choices args (e.g. `cases <cmd>`) count as subcommands
    pos = [a for a in parser._actions
           if a.choices and not a.option_strings
           and a.dest not in GLOBAL_OPTS and a.dest != "help"]
    flags = [a for a in parser._actions
             if a.option_strings and a.dest not in GLOBAL_OPTS]
    plain_pos = [a for a in parser._actions
                 if not a.option_strings and not a.choices
                 and a.dest not in GLOBAL_OPTS and a.dest != "help"
                 and not isinstance(a, argparse._SubParsersAction)]
    if flags or plain_pos:
        arg_s = " ".join(_action_line(a) for a in plain_pos)
        fl_s = " · ".join(f"`{_action_line(a)}`" for a in flags)
        out.write(f"{'  ' * depth}- `{prefix}`"
                  + (f" {arg_s}" if arg_s else "")
                  + (f"  \n{'  ' * (depth + 1)}{fl_s}" if fl_s else "")
                  + "\n")
    for name in pos:
        out.writelines(f"{'  ' * depth}- `{prefix} {ch}`\n"
                       for ch in sorted(str(c) for c in name.choices))
    for name, sp in sorted(subs.items()):
        if _subs(sp) or any(a.option_strings for a in sp._actions
                            if a.dest not in GLOBAL_OPTS):
            _render_parser(out, sp, f"{prefix} {name}", depth + 1)
        else:
            out.write(f"{'  ' * depth}- `{prefix} {name}`\n")


def generate() -> str:
    from platformforge.cli.main import build_parser
    p = build_parser()
    out = io.StringIO()
    out.write("""# CLI SURFACE — generated reference

Machine-generated from `build_parser()` — every verb, subcommand and
flag, exhaustively. Regenerate with
`python scripts/gen_cli_surface.py --write`; the docs-drift test fails
if this file is stale. For the curated guide with examples see
[../CLI-REFERENCE.md](../CLI-REFERENCE.md).

Global flags on every verb: `--json` · `--output <file>` ·
`--detail-level summary|normal|full` · `--offline` · `--strict`.

""")
    for verb in sorted(_subs(p)):
        out.write(f"## `{verb}`\n\n")
        _render_parser(out, _subs(p)[verb], verb, 0)
        out.write("\n")
    return out.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    text = generate()
    if args.check:
        cur = OUT.read_text() if OUT.exists() else ""
        if cur != text:
            print(f"STALE: {OUT} differs from generated surface")
            return 1
        print("ok — CLI-SURFACE.md is current")
        return 0
    if args.write:
        OUT.write_text(text, encoding="utf-8")
        print(f"written {OUT} ({len(text.splitlines())} lines)")
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
