"""Phase I — host mirrors: generated from canonical roster, drift gate."""

from __future__ import annotations

from pathlib import Path

from platformforge.agents.mirrors import TARGETS, check, expected, sync
from platformforge.agents.roster import AGENTS

ROOT = Path(__file__).resolve().parent.parent


def test_all_five_hosts_generated():
    want = expected(ROOT)
    hosts = {Path(p).parts[0] for p in want}
    assert hosts == {"agents", ".agents", ".claude", ".codex",
                     ".devin"}
    assert len(want) == len(AGENTS) * len(TARGETS)


def test_committed_mirrors_match_roster():
    out = check(ROOT)
    assert out["ok"], out["problems"][:10]


def test_check_detects_drift(tmp_path):
    sync(tmp_path)
    assert check(tmp_path)["ok"]
    # hand-edit a mirror — drift
    p = tmp_path / "agents" / "platform-orchestrator.md"
    p.write_text(p.read_text() + "\nhuman edit\n")
    out = check(tmp_path)
    assert not out["ok"]
    assert any("stale mirror" in pr for pr in out["problems"])
    # stray file — drift
    (tmp_path / "agents" / "rogue.md").write_text("x")
    out2 = check(tmp_path)
    assert any("stray" in pr for pr in out2["problems"])


def test_mirror_content_carries_contract():
    md = (ROOT / "agents" / "platform-verifier.md").read_text()
    assert "role" in md.lower() and "verifier" in md
    assert "Never" in md
    toml = (ROOT / ".codex" / "agents"
            / "platform-verifier.toml").read_text()
    assert 'name = "platform-verifier"' in toml


def test_mirror_banner_present():
    for host in TARGETS:
        ext = ".toml" if host.endswith("codex/agents") else ".md"
        p = ROOT / host / f"platform-orchestrator{ext}"
        text = p.read_text()
        if ext == ".md":
            # hosts only load agents whose frontmatter opens on line 1
            assert text.startswith("---\n# GENERATED")
        else:
            assert text.startswith("# GENERATED")
