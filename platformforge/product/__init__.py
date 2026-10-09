"""Platform product: catalog, golden paths, maturity model, scorecards,
Backstage adapter (projection — never the canonical source), Crossplane."""

from platformforge.product.backstage import to_backstage
from platformforge.product.catalog import analyze_catalog
from platformforge.product.crossplane import analyze_crossplane
from platformforge.product.maturity import maturity, maturity_report

__all__ = ["analyze_catalog", "analyze_crossplane", "maturity",
           "maturity_report", "to_backstage"]
