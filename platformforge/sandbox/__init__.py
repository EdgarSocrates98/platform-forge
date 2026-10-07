"""Sandbox — §86. Copy tree → apply diff → analyze before/after → compare.
Never mutates the original tree."""

from platformforge.sandbox.env import Sandbox, compare_runs, sandbox_analyze
from platformforge.sandbox.review import review_change

__all__ = ["Sandbox", "compare_runs", "review_change", "sandbox_analyze"]
