from platformforge.workspace import add_repo, doctor, ensure_workspace, remove_repo


def test_workspace_multi_repo_lifecycle(tmp_path):
    a = tmp_path / "app"; a.mkdir()
    ws = ensure_workspace(tmp_path, hosts=["codex"])
    assert ws.state_mode == "workspace-local"
    ws = add_repo(tmp_path, a)
    assert ws.repos[0].name == "app"
    assert doctor(tmp_path)["state"] == "healthy"
    ws = remove_repo(tmp_path, "app")
    assert ws.repos == []
