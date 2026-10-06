"""Stdio MCP-ish JSON-RPC server — minimal, dependency-free transport.

Speaks JSON-RPC 2.0 over stdin/stdout: initialize, tools/list, tools/call,
ping. Every call is recorded (payload bytes, never secrets) for the economy
ledger."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from platformforge.mcp.registry import tool_descriptors
from platformforge.mcp.tools import call_tool

PROTOCOL_VERSION = "2024-11-05"


def _result(rid: Any, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": rid, "result": result})


def _error(rid: Any, code: int, msg: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": rid,
                       "error": {"code": code, "message": msg}})


def handle(req: dict[str, Any], repo: str) -> str | None:
    rid = req.get("id")
    method = req.get("method", "")
    if method == "initialize":
        return _result(rid, {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": "platformforge", "version": "0.1.0"},
            "capabilities": {"tools": {}}})
    if method == "tools/list":
        return _result(rid, {"tools": tool_descriptors()})
    if method == "tools/call":
        p = req.get("params") or {}
        out = call_tool(p.get("name", ""), p.get("arguments"), repo=repo)
        text = json.dumps(out, default=str)
        return _result(rid, {"content": [{"type": "text", "text": text}],
                             "isError": "error" in out or "refusal" in out})
    if method == "ping":
        return _result(rid, {})
    if method.startswith("notifications/"):
        return None
    if rid is None:
        return None
    return _error(rid, -32601, f"method not found: {method}")


def serve(repo: str = ".", stdin: TextIO | None = None,
          stdout: TextIO | None = None) -> int:
    inp, out = stdin or sys.stdin, stdout or sys.stdout
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            out.write(_error(None, -32700, "parse error") + "\n")
            out.flush()
            continue
        resp = handle(req, repo)
        if resp is not None:
            out.write(resp + "\n")
            out.flush()
    return 0


def main() -> None:
    """Console-script entry point (``platformforge-mcp``)."""
    sys.exit(serve())
