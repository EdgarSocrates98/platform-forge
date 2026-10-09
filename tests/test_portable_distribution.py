from platformforge.distribution import (
    apply_install,
    build_bundle,
    doctor,
    install_bundle,
    uninstall,
    verify_bundle,
)


def test_install_dry_run_then_install_and_uninstall(tmp_path):
    dry = apply_install(tmp_path, hosts=["codex", "claude"], dry_run=True)
    assert dry["plan"]["safe"]
    out = apply_install(tmp_path, hosts=["codex", "claude"])
    assert out["status"] == "committed"
    assert (tmp_path / ".platformforge/install-receipt.json").is_file()
    assert any((tmp_path / ".codex/agents").glob("*.toml"))
    assert any((tmp_path / ".claude/agents").glob("*.md"))
    assert any((tmp_path / ".claude/skills").glob("*/SKILL.md"))
    assert any((tmp_path / ".agents/skills").glob("*/SKILL.md"))
    assert doctor(tmp_path)["state"] == "healthy"
    rm = uninstall(tmp_path)
    assert rm["status"] == "uninstalled"


def test_user_modified_managed_file_is_preserved(tmp_path):
    apply_install(tmp_path, hosts=["agents"])
    p = next((tmp_path / ".agents/agents").glob("*.md"))
    p.write_text("user changed\n")
    out = uninstall(tmp_path)
    assert str(p.relative_to(tmp_path)) in out["preserved_modified"]
    assert p.is_file()


def test_bundle_integrity(tmp_path):
    bundle = tmp_path / "bundle"
    build_bundle(bundle, hosts=["codex"], offline=True)
    assert verify_bundle(bundle)["valid"]
    p = next((bundle / "assets").rglob("*.toml"))
    p.write_text(p.read_text() + "\ntamper\n")
    out = verify_bundle(bundle)
    assert not out["valid"]
    assert out["refusal"] == "PF-DIST-HASH-MISMATCH"


def test_bundle_installs_offline(tmp_path):
    bundle = tmp_path / "bundle"
    target = tmp_path / "target"
    target.mkdir()
    build_bundle(bundle, hosts=["codex", "claude"], offline=True)
    out = install_bundle(bundle, target)
    assert out["status"] == "committed"
    assert out["offline"] is True
    assert any((target / ".codex/agents").glob("*.toml"))
    assert any((target / ".claude/skills").glob("*/SKILL.md"))
    assert doctor(target)["state"] == "healthy"
