"""Phase 13 gate: capability registry, bounded tools, host parity, stdio."""

import io
import json

from platformforge.mcp import CAPABILITIES, call_tool
from platformforge.mcp.parity import detach, integrate
from platformforge.mcp.registry import tool_descriptors
from platformforge.mcp.server import handle


def test_registry_is_bounded():
    for c in CAPABILITIES.values():
        assert c.max_bytes > 0 and c.max_results > 0
        assert c.detail_levels
    tools = tool_descriptors()
    assert all(t["annotations"]["readOnlyHint"] for t in tools)


def test_call_tool_dispatch(tmp_path):
    (tmp_path / "m.tf").write_text('resource "aws_s3_bucket" "b" {\n'
                                 '  bucket = "x"\n  acl = "public-read"\n}\n')
    out = call_tool("platformforge_analyze",
                    {"domain": "iac", "path": str(tmp_path)}, repo=str(tmp_path))
    assert out["bounded"] is False
    assert any(f["kind"] == "iac.resource" for f in out["result"]["facts"])


def test_call_tool_bounds_oversize(tmp_path):
    out = call_tool("platformforge_analyze",
                    {"domain": "secrets", "path": str(tmp_path)},
                    repo=str(tmp_path))
    cap = CAPABILITIES["platformforge_analyze"]
    # shrink bound artificially to force the ref path
    import platformforge.mcp.tools as T
    small = T._bound({"facts": ["x" * 100] * 1000},
                     type("C", (), {"max_bytes": 10})(), str(tmp_path))
    assert small["bounded"] and "artifact://" in small["artifact_ref"]


def test_unknown_tool_refusal(tmp_path):
    out = call_tool("nope", {}, repo=str(tmp_path))
    assert out["error"] == "platform.tool.unresolved"


def test_stdio_handle(tmp_path):
    r = json.loads(handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                          str(tmp_path)))
    assert r["result"]["serverInfo"]["name"] == "platformforge"
    r2 = json.loads(handle({"jsonrpc": "2.0", "id": 2,
                            "method": "tools/list"}, str(tmp_path)))
    assert len(r2["result"]["tools"]) == len(CAPABILITIES)
    r3 = json.loads(handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                            "params": {"name": "platformforge_economy",
                                       "arguments": {}}}, str(tmp_path)))
    assert "content" in r3["result"]


def test_host_parity(tmp_path):
    for host in ("claude", "devin", "copilot", "codex"):
        out = integrate(host, tmp_path)
        assert "wrote" in out
    assert detach("claude", tmp_path)["detached"] is True
    assert detach("claude", tmp_path)["detached"] is False
