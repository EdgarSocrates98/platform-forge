"""ProviderPricing (§89–96) — declared price catalog, never hardcoded.

Prices live in a caller-supplied YAML (default `.platformforge/pricing.yaml`),
provider-neutral (§95), version-aware via `effective_at` (§94). A lookup
without a matching rate is `PF-ECONOMY-PRICING-MISSING` (§92) — the
answer is `cost unresolved`, never $0 (§293 north star).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "platformforge/provider-pricing/v1"
PRICING_MISSING = "PF-ECONOMY-PRICING-MISSING"


@dataclass(frozen=True)
class ProviderPricing:
    """§91 — one declared rate row."""
    provider: str
    model: str
    effective_at: str
    currency: str = "USD"
    input_per_million: float = 0.0
    output_per_million: float = 0.0
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _at(value: str) -> _dt.datetime:
    s = str(value).strip()
    dt = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def load_pricing(path: str | Path) -> tuple[ProviderPricing, ...]:
    """Load a declared catalog; malformed rows are refused loudly."""
    p = Path(path)
    if not p.exists():
        return ()
    doc = yaml.safe_load(p.read_text()) or {}
    rows = doc.get("pricing", doc if isinstance(doc, list) else [])
    out: list[ProviderPricing] = []
    for i, row in enumerate(rows):
        missing = [k for k in ("provider", "model", "effective_at")
                   if k not in row]
        if missing:
            raise ValueError(f"pricing row {i}: missing {missing}")
        out.append(ProviderPricing(**{k: row.get(k) for k in
                                      ProviderPricing.__dataclass_fields__}))
    return tuple(out)


def rate_for(catalog: tuple[ProviderPricing, ...] | list[ProviderPricing],
             provider: str, model: str,
             at: _dt.datetime | None = None) -> dict[str, Any]:
    """§94 — pick the newest rate whose effective_at <= `at` (default now).
    No match → PF-ECONOMY-PRICING-MISSING, not a guess."""
    at = at or _dt.datetime.now(_dt.timezone.utc)
    candidates = [r for r in catalog
                  if r.provider == provider and r.model == model
                  and _at(r.effective_at) <= at]
    if not candidates:
        return {"refusal": PRICING_MISSING,
                "reason": f"no declared rate for {provider}/{model} "
                          f"effective at {at.date()}",
                "unlock": "add a pricing row to the declared catalog"}
    rate = max(candidates, key=lambda r: _at(r.effective_at))
    return {"rate": rate.to_dict()}


def cost(catalog, provider: str, model: str,
         input_tokens: int | None, output_tokens: int | None,
         at: _dt.datetime | None = None) -> dict[str, Any]:
    """§93 — ProviderCost. Unobserved tokens or missing rate → unresolved."""
    if input_tokens is None and output_tokens is None:
        return {"state": "unresolved",
                "reason": "no observed/estimated tokens for this call",
                "code": "PF-ECONOMY-USAGE-UNOBSERVED"}
    r = rate_for(catalog, provider, model, at)
    if "refusal" in r:
        return {"state": "unresolved", **r,
                "tokens": {"input": input_tokens, "output": output_tokens}}
    rate = ProviderPricing(**r["rate"])
    usd = ((input_tokens or 0) * rate.input_per_million
           + (output_tokens or 0) * rate.output_per_million) / 1e6
    return {"state": "priced", "cost_usd": round(usd, 8),
            "currency": rate.currency, "provider": provider,
            "model": model, "effective_at": rate.effective_at,
            "source": rate.source, "pricing_basis": "declared",
            "tokens_basis": "observed" if input_tokens is not None
            and output_tokens is not None else "partial"}
