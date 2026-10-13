"""MCP adapter — capability registry → bounded tools. CLI and MCP invoke
the same core; MCP adds only transport + output bounding."""

from platformforge.mcp.registry import CAPABILITIES, Capability
from platformforge.mcp.tools import call_tool

__all__ = ["CAPABILITIES", "Capability", "call_tool"]
