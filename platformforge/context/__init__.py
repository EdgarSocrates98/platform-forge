"""Unified Context Gateway (§56–75) — single layer through which all
model/agent context passes."""

from platformforge.context.capsule import ContextCapsule
from platformforge.context.gateway import ContextGateway, ContextRequest
from platformforge.context.refs import ContextRef
from platformforge.context.sufficiency import ContextSufficiencyResult, Sufficiency

__all__ = ["ContextCapsule", "ContextGateway", "ContextRef",
           "ContextRequest", "ContextSufficiencyResult", "Sufficiency"]
