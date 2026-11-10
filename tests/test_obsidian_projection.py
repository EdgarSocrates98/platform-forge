from platformforge.context.obsidian import build_obsidian_operations_review, to_obsidian_note_ref


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
        terraform=["credential=do-not-write-text"],
    )
    assert note["schema"] == "theforge/ObsidianNoteDraft/v1"
    ref = to_obsidian_note_ref(note)
    assert ref["schema"] == "theforge/ObsidianNoteRef/v1"
    assert "content" not in ref
    assert "inc-42" in note["content"]
    assert "do-not-write" not in note["content"]
    assert "[REDACTED]" in note["content"]


def test_platform_projection_redacts_secrets_in_title_and_summary():
    note = build_obsidian_operations_review(
        title="Token=do-not-write",
        summary="password=do-not-write-summary",
        workspace="platform",
        vault_id="team-vault",
    )
    assert "do-not-write" not in note["content"]
    assert "[REDACTED]" in note["content"]
