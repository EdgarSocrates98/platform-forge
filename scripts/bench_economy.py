"""Economy control-plane overhead benchmark (prompt_evo_economy §T).

Measures the economy layer's own cost — lookup/build/route/ledger —
so the plane cannot cost more than it saves. Writes real numbers to
docs/economy-parity/BENCHMARKS.md. No extrapolation, no claims.
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _time(fn, n=100):
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1e6)
    return {"n": n, "median_us": round(statistics.median(samples), 1),
            "p95_us": round(sorted(samples)[int(n * 0.95)], 1),
            "max_us": round(max(samples), 1)}


def main() -> int:
    from platformforge.context.gateway import ContextGateway, ContextRequest
    from platformforge.economy.budget import BudgetEnvelope, Limit
    from platformforge.economy.cache import CacheStore
    from platformforge.economy.ledger import EconomyLedger, ToolUsageEntry
    from platformforge.routing import TaskSignal, route
    from platformforge.routing.decision import RoutingRequest

    tmp = Path(tempfile.mkdtemp(prefix="econ-bench-"))
    out = {"env": {"python": sys.version.split()[0]},
           "measured": {}, "note": "microbenchmarks on synthetic payloads "
           "— overhead of the economy layer itself, not savings"}

    store = CacheStore(tmp / "cache")
    deps = {"artifact_hash": "a", "rule_catalog_hash": "v1"}
    for i in range(200):
        store.put("fact", f"k{i}", {"v": i}, deps)
    out["measured"]["cache_put"] = _time(
        lambda: store.put("fact", "kx", {"v": 1}, deps))
    out["measured"]["cache_get_hit"] = _time(
        lambda: store.get("fact", "k1", deps))
    out["measured"]["cache_get_miss"] = _time(
        lambda: store.get("fact", "kx", deps))
    out["measured"]["cache_stats"] = _time(lambda: store.stats(), n=20)
    out["measured"]["cache_entries"] = 200

    gw = ContextGateway(tmp / "gw")
    facts = [{"fact_id": f"f{i}", "value": "x" * 40} for i in range(50)]
    out["measured"]["context_build"] = _time(
        lambda: gw.build(ContextRequest(
            task="bench", facts=facts, budget_bytes=100_000)), n=50)
    ref = gw.build(ContextRequest(task="bench", facts=facts))["ref"]
    out["measured"]["context_inspect"] = _time(
        lambda: gw.inspect(ref), n=50)
    out["measured"]["context_expand"] = _time(
        lambda: gw.expand(ref, "facts"), n=50)

    sig = TaskSignal(task_type="analysis", domains=["k8s"],
                     complexity="medium", risk="medium")
    out["measured"]["router_route"] = _time(lambda: route(sig), n=200)
    out["measured"]["routing_profile_floor"] = _time(
        lambda: RoutingRequest(risk="high").effective_profile(), n=500)

    led = EconomyLedger(tmp / "led")
    ent = ToolUsageEntry(tool="t", calls=1, output_bytes=128)
    out["measured"]["ledger_record"] = _time(lambda: led.record(ent))
    out["measured"]["ledger_entries"] = 100

    env = BudgetEnvelope(limits={"input_tokens": Limit(soft=100, hard=500)})
    out["measured"]["budget_check"] = _time(
        lambda: env.check("input_tokens", 250), n=500)

    # --- mode comparison: context bytes per strategy --------------------
    bytes_row = {}
    for mode, budget in (("full", None), ("tokensave", 20_000),
                         ("cache-only", None), ("deep", 200_000)):
        req = ContextRequest(task="bench", facts=facts,
                             budget_bytes=budget)
        r = gw.build(req)
        bytes_row[mode] = r.get("bytes")
    out["measured"]["context_bytes_by_mode"] = bytes_row

    p = ROOT / "docs" / "economy-parity" / "BENCHMARKS.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
    print(json.dumps(out["measured"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
