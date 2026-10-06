"""Executable rule catalog — conditions evaluate over facts, never decorative YAML."""

from platformforge.rules.engine import Rule, RuleEngine, load_catalog

__all__ = ["Rule", "RuleEngine", "load_catalog"]
