"""Adaptive routing — computed dispatch, never "call all agents"."""

from platformforge.routing.router import (
                                          DOMAIN_SPECIALIST,
                                          TASK_COORDINATOR,
                                          TaskSignal,
                                          load_routes,
                                          route,
                                          validate_routing,
)

__all__ = ["DOMAIN_SPECIALIST", "TASK_COORDINATOR", "TaskSignal",
           "load_routes", "route", "validate_routing"]
