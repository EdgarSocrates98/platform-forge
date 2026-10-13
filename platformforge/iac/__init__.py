"""IaC analysis: Terraform/OpenTofu HCL, plan/state JSON, drift."""

from platformforge.iac.drift import drift
from platformforge.iac.plan import analyze_plan, analyze_state
from platformforge.iac.terraform import analyze_hcl

__all__ = ["analyze_hcl", "analyze_plan", "analyze_state", "drift"]
