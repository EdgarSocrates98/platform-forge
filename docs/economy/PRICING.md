# Provider Pricing

`platformforge/economy/pricing.py`. ADR-0059.

## Declared, never hardcoded

```yaml
provider: aws
model: some-model
effective_at: "2025-06-01"
currency: USD
input_per_million: 3.0
output_per_million: 15.0
source: https://provider.example/pricing-page
```

`load_pricing(path)` reads a catalog; `rate_for` picks the newest row
whose `effective_at <= at`.

## Missing data is a refusal

`cost(catalog, provider, model, input_tokens, output_tokens)`:

- no rate → `state=unresolved` + `PF-ECONOMY-PRICING-MISSING`
  (+ `unlock: add a pricing row`)
- no tokens → `PF-ECONOMY-USAGE-UNOBSERVED`
- priced → `state=priced`, `cost_usd`, rate bound in the answer

Tool monetary cost is optional and only reported when reliable —
estimates never become dollars.
