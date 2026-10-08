"""Cycle 5 Phase O — graph + analytics scale benchmarks (§317).

Every number is measured on seeded synthetic service graphs — no
scale claim without a measurement. Complements platformforge/bench.py
(which times the real eval corpus) with controlled-size scaling.
"""

from __future__ import annotations

import json
import tempfile
import tracemalloc
from pathlib import Path
from time import perf_counter
from typing import Any


def _timer(fn, *a, **kw) -> tuple[Any, float]:
    t0 = perf_counter()
    out = fn(*a, **kw)
    return out, round((perf_counter() - t0) * 1000, 2)


def synthetic_graph(n_services: int = 200, fanout: int = 3):
    """Deterministic seed — same n always produces the same graph."""
    from platformforge.graph.model import Edge, Graph, Node
    g = Graph()
    for i in range(n_services):
        g.add_node(Node.make("service", f"svc-{i}",
                             attrs={"environment": "prod"}))
    for i in range(n_services):
        for j in range(1, fanout + 1):
            t = (i + j * 17) % n_services
            if t != i:
                g.add_edge(Edge(f"service/svc-{i}", f"service/svc-{t}",
                                "depends_on"))
        g.add_node(Node.make("cluster", f"c-{i % 8}"))
        g.add_edge(Edge(f"service/svc-{i}", f"cluster/c-{i % 8}",
                        "runs_on"))
    return g


def run_scale_benchmarks(sizes: tuple[int, ...] = (50, 200, 800)) \
        -> dict[str, Any]:
    """Measured timings across graph build/query/serialize/diff and
    the analytics SQLite store."""
    from platformforge.analytics.store import AnalyticsStore
    from platformforge.graph.diff import diff as graph_diff
    from platformforge.graph.query import blast_radius, dependents

    report: dict[str, Any] = {
        "schema": "platformforge/scale-benchmarks/v1",
        "method": "perf_counter ms; tracemalloc KiB; seeded synthetic "
                  "graphs (deterministic shape per n)",
        "sizes": {}}

    for n in sizes:
        g, t_build = _timer(synthetic_graph, n)
        g2, _ = _timer(synthetic_graph, n)
        merged, t_merge = _timer(_merge, g, g2)
        deps, t_deps = _timer(dependents, g, "service/svc-0")
        blast, t_blast = _timer(blast_radius, g, "service/svc-0")
        blob, t_ser = _timer(json.dumps, g.to_dict(), default=str)
        t_deser = _timer(json.loads, blob)[1]
        _d, t_diff = _timer(graph_diff, g, g2)

        tracemalloc.start()
        synthetic_graph(n)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        with tempfile.TemporaryDirectory() as td:
            st = AnalyticsStore(Path(td) / "a.db")
            t_ins = _timer(_fill_events, st, n)[1]
            _e, t_q = _timer(st.events)
            t_forget = _timer(st.forget_subject, "svc:x")[1]
            size = (Path(td) / "a.db").stat().st_size
            st.close()

        report["sizes"][str(n)] = {
            "nodes": len(g.nodes), "edges": len(g.edges),
            "build_ms": t_build, "merge_ms": t_merge,
            "dependents_ms": t_deps, "dependents_found": len(deps),
            "blast_ms": t_blast,
            "blast_nodes": len(blast.get("nodes", [])),
            "serialize_ms": t_ser, "deserialize_ms": t_deser,
            "diff_ms": t_diff,
            "peak_build_kib": round(peak / 1024, 1),
            "store_insert_ms": t_ins, "store_query_ms": t_q,
            "store_forget_ms": t_forget,
            "store_size_bytes": size,
            "merged_nodes": len(merged.nodes)}
    return report


def _merge(g1, g2):
    from platformforge.graph.model import Graph
    out = Graph()
    for g in (g1, g2):
        for n in g.nodes.values():
            out.add_node(n)
        for e in g.edges.values():
            out.add_edge(e)
    return out


def _fill_events(st, n: int) -> None:
    st.put_events([
        {"kind": "operation",
         "ts": f"2025-11-{(i % 28) + 1:02d}T00:00:00Z",
         "subject": f"svc:{i % 50}", "outcome": "converged",
         "source": "bench", "attrs": {"i": i}} for i in range(n)])


def benchmark_summary(report: dict[str, Any]) -> list[str]:
    """Numbers only — no extrapolated scale claims."""
    return [
        f"n={n} nodes={m['nodes']} edges={m['edges']} | "
        f"build {m['build_ms']}ms merge {m['merge_ms']}ms "
        f"deps {m['dependents_ms']}ms blast {m['blast_ms']}ms "
        f"diff {m['diff_ms']}ms ser {m['serialize_ms']}ms "
        f"deser {m['deserialize_ms']}ms | "
        f"peak {m['peak_build_kib']}KiB | "
        f"store ins {m['store_insert_ms']}ms q {m['store_query_ms']}ms "
        f"forget {m['store_forget_ms']}ms ({m['store_size_bytes']}B)"
        for n, m in report["sizes"].items()]
