from platformforge.context.obsidian import build_obsidian_operations_review


def test_platform_projection_carries_operations_sections_and_redacts_secrets():
    note = build_obsidian_operations_review(
        title="Checkout incident",
        summary="Evidence-backed review.",
        workspace="platform",
        vault_id="team-vault",
        incident={"id": "inc-42", "status": "resolved"},
        postmortem={"root_cause": {"status": "unresolved"}},
        runbooks=["replica-drift-restore"],
        kubernetes=[{"namespace": "checkout", "service_account_token": "do-not-write"}],
    )
    assert note["schema"] == "theforge/ObsidianNoteRef/v1"
    assert "inc-42" in note["content"]
    assert "do-not-write" not in note["content"]
    assert "[REDACTED]" in note["content"]
