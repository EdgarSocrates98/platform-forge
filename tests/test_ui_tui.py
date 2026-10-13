"""TUI/menu contract tests — vendored ui.* surface."""

import pytest


def test_menu_well_formed():
    """Every _MENU item is a (label, argv|None) pair — no bare strings."""
    from platformforge.ui import home
    for item in home._MENU:
        assert isinstance(item, tuple) and len(item) == 2, item
        label, argv = item
        assert isinstance(label, str) and label
        assert argv is None or argv == "__wizard__" or isinstance(argv, list)


def test_menu_argv_parses_against_real_parser():
    """Every menu argv must parse — a bare `["agents"]` used to fail argparse."""
    from platformforge.cli.main import build_parser
    from platformforge.ui import home
    parser = build_parser()
    for label, argv in home._MENU:
        if argv is None or argv == "__wizard__":
            continue
        try:
            ns = parser.parse_args(list(argv))
        except SystemExit as exc:  # argparse exits 2 on required-arg failure
            raise AssertionError(f"menu {label!r} argv {argv} fails parse") from exc
        assert callable(getattr(ns, "func", None)), (label, argv)


def test_tui_entries_real():
    from platformforge.ui import tui
    entries = tui.entries()
    assert len(entries) >= 3
    assert any("wizard" in e.label for e in entries)


def test_tui_renders_non_tty_ctx():
    from platformforge.ui import tui
    from platformforge.ui.app import ForgeApp
    from platformforge.ui.kit import UIContext
    from platformforge.ui.screen import Buffer
    ctx = UIContext(interactive=False, color=False, unicode=False,
                    width=80, height=24, ansi=False)
    app = ForgeApp(ctx, forge_id="x", title="cc", entries=tui.entries())
    buf = Buffer(ctx, 80, 24)
    app.render(buf)
    assert "menu" in chr(10).join(buf.render())


def test_home_requires_tty():
    from platformforge.ui import home
    from platformforge.ui.kit import NonInteractive, UIContext
    ctx = UIContext(interactive=False, color=False, unicode=False, width=80)
    with pytest.raises(NonInteractive):
        home.run_home(ctx=ctx)
