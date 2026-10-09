import json
from pathlib import Path
from platformforge.distribution import apply_install, uninstall, doctor, build_bundle, verify_bundle

def test_install_dry_run_then_install_and_uninstall(tmp_path):
    dry = apply_install(tmp_path, hosts=["codex","claude"], dry_run=True)
    assert dry["plan"]["safe"]
    out = apply_install(tmp_path, hosts=["codex","claude"])
    assert out["status"] == "committed"
    assert (tmp_path / ".platformforge/install-receipt.json").is_file()
    assert any((tmp_path / ".codex/agents").glob("*.toml"))
    assert any((tmp_path / ".claude/agents").glob("*.md"))
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
    b = tmp_path / "bundle"
    build_bundle(b, hosts=["codex"], offline=True)
    assert verify_bundle(b)["valid"]
    p = next((b / "assets").rglob("*.toml"))
    p.write_text(p.read_text() + "\ntamper\n")
    out = verify_bundle(b)
    assert not out["valid"] and out["refusal"] == "PF-DIST-HASH-MISMATCH"
