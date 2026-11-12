"""Federated SDD adapter tests — Onda 5A.

The adapter converts native gate results into forge/* contracts without
touching the native engine. Canonical JSON Schemas live in the-forge;
these tests assert the emitted shape (required keys, enums, item form).
"""

from __future__ import annotations

from platformforge.sdd import federated


def test_phase_map_covers_native_phases():
    for native in ("discover", "define", "design", "contract", "plan",
                   "build", "review", "verify"):
        assert federated.map_phase(native) in (
            "explore", "define", "design", "plan", "build_report",
            "verify", "ship", "learn")


def test_gate_from_native_result():
    native = {
        "ok": False,
        "refused": [{"code": "upstream_hash_stale", "phase": "verify",
                     "field": "upstream.sha256",
                     "unlock": "rerun sdd stamp"}],
        "unresolved": [{"code": "risk_pending", "phase": "review",
                        "unlock": "record risk acceptance"}],
    }
    gate = federated.to_gate("F1", "verify", native)
    assert gate["schema"] == "forge/SDDGate/v1"
    assert gate["phase"] == "verify"
    assert gate["ok"] is False
    assert gate["refused"][0]["code"] == "upstream_hash_stale"
    assert gate["refused"][0]["feature"] == "F1"
    assert gate["refused"][0]["path"] == "verify"
    assert gate["unresolved"][0]["unlock"] == "record risk acceptance"


def test_gate_native_to_canonical_phase():
    gate = federated.to_gate("F1", "build", {"ok": True, "refused": [],
                                             "unresolved": []})
    assert gate["phase"] == "build_report"


def test_receipt_round_trip():
    r = federated.to_receipt(
        "F1", "build", "pytest run", "builder-agent",
        "2026-04-05T10:00:00Z", verdict="pass",
        outputs=["tests/out.xml"], rollback_ref="design.md#rollback")
    assert r["schema"] == "forge/SDDReceipt/v1"
    assert r["phase"] == "build_report"
    assert r["verdict"] == "pass"
    assert r["outputs"] == ["tests/out.xml"]


def test_evidence_computes_sha(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("evidence")
    ev = federated.to_evidence(f, kind="test-run", agent="t",
                               command=["pytest"])
    assert ev["schema"] == "forge/Evidence/v1"
    assert ev["sha256"].startswith("sha256:")
    assert len(ev["sha256"]) == 71


def test_federated_view_empty_dir(tmp_path):
    assert federated.federated_view(tmp_path, feature="F1") == {}
