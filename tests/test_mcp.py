"""Phase 13 gate: capability registry, bounded tools, host parity, stdio."""

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
    call_tool("platformforge_analyze",
              {"domain": "secrets", "path": str(tmp_path)},
              repo=str(tmp_path))
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


def test_cycle5_tools_exposed_readonly():
    """Polish — the five cycle5 namespaces reach MCP as read-only tools
    that resolve the same cmd_* functions the CLI calls."""
    from platformforge.mcp.registry import CAPABILITIES, tool_descriptors
    from platformforge.mcp.tools import call_tool

    names = {d["name"] for d in tool_descriptors()}
    for t in ("platformforge_fleet", "platformforge_analytics",
              "platformforge_optimize", "platformforge_ai",
              "platformforge_federation"):
        cap = CAPABILITIES[t]
        assert cap.risk == "read" and cap.mutable is False
        assert t in names

    r = call_tool("platformforge_fleet",
                  {"op": "risks", "path": "lab/fleets/acme",
                   "question": "unowned"})
    assert r["result"]["count"] >= 1

    # optimize plan emits the intent but can never write a file via MCP
    r = call_tool("platformforge_optimize",
                  {"op": "plan", "path": "lab/fleets/acme",
                   "id": "opt-2-scan-3", "out": "/tmp/x-shall-not-exist"})
    assert "change_intent" in r["result"]
    assert "written" not in r["result"]

    # federation secrets still denied at the boundary
    r = call_tool("platformforge_federation",
                  {"op": "export", "classification": "internal",
                   "path": "evals/cases/contract-fact/fixture/facts.yaml"})
    assert "refusal" in r["result"] or r["result"].get("action")
