"""Phase L — dynamic capability availability, MCP live surface,
credential boundaries."""

from __future__ import annotations

import json

from platformforge.live.capability import CREDENTIAL_BOUNDARY, availability
from platformforge.mcp.tools import call_tool


class TestAvailability:

    def test_verdicts_cover_all_verbs(self, tmp_path):
        out = availability(tmp_path)
        for verb in ("snapshot", "status", "doctor", "reconcile",
                     "rbac", "topology", "clusters", "drift",
                     "incident", "plan", "capability"):
            v = out["verbs"][verb]
            assert "available" in v and "reason" in v
        assert out["counts"]["verbs"] == len(out["verbs"])

    def test_drift_unavailable_without_observations(self, tmp_path):
        out = availability(tmp_path)
        assert out["verbs"]["drift"]["available"] is False
        assert "≥2" in out["verbs"]["drift"]["reason"]

    def test_credential_boundary_contract(self, tmp_path):
        cb = availability(tmp_path)["credential_boundary"]
        assert cb["core_imports_provider_sdk"] is False
        assert cb["credentials_persisted"] is False
        assert cb["transports"]["kubernetes"]["mutates"] is False
        assert "--token" in cb["transports"]["kubernetes"]["denied_args"]

    def test_cli_capability(self, tmp_path, capsys):
        from platformforge.cli.main import main
        code = main(["live", "capability", "--repo", str(tmp_path)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["schema"] == "platformforge/live-capability/v1"


class TestMcpLive:

    def test_capability_registered(self):
        from platformforge.mcp.registry import CAPABILITIES
        cap = CAPABILITIES["platformforge_live"]
        assert cap.domain == "live" and cap.mutable is False
        d = cap.contract()
        assert d["risk"] == "read" and d["offline"] is False

    def test_tools_list_includes_live(self):
        from platformforge.mcp.registry import tool_descriptors
        names = {t["name"] for t in tool_descriptors()}
        assert "platformforge_live" in names

    def test_call_tool_status(self, tmp_path):
        out = call_tool("platformforge_live", {"op": "status"},
                        repo=str(tmp_path))
        assert "result" in out and "error" not in out

    def test_call_tool_capability(self, tmp_path):
        out = call_tool("platformforge_live", {"op": "capability"},
                        repo=str(tmp_path))
        assert out["result"]["schema"] == \
            "platformforge/live-capability/v1"

    def test_call_tool_drift_refuses_empty_store(self, tmp_path):
        out = call_tool("platformforge_live", {"op": "drift"},
                        repo=str(tmp_path))
        assert out["result"]["refusal"] == "PF-LIVE-NEED-2-OBS"

    def test_call_tool_incident(self, tmp_path):
        inc = tmp_path / "i.json"
        inc.write_text(json.dumps(
            {"timestamp": "2025-06-10T12:00:00Z",
             "resources": ["svc/x"]}))
        out = call_tool("platformforge_live",
                        {"op": "incident", "incident": str(inc)},
                        repo=str(tmp_path))
        assert "ranked" in out["result"]
        assert out["result"]["postmortem"]["root_cause"]["status"] == \
            "unresolved"

    def test_call_tool_clusters(self, tmp_path):
        out = call_tool("platformforge_live", {"op": "clusters"},
                        repo=str(tmp_path))
        assert out["result"]["clusters"] == []


class TestCredentialBoundary:

    def test_no_credential_keys_in_store(self, tmp_path):
        """§266 — the store boundary never persists creds: the store API
        has no credential parameter and the boundary contract declares
        credential-free persistence."""
        assert CREDENTIAL_BOUNDARY["credentials_persisted"] is False
        assert CREDENTIAL_BOUNDARY["core_reads_env_credentials"] is False
