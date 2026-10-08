"""Graph queries: deps, dependents, paths, blast radius, gap detectors.

Discipline (GRAPHFY.md): proximity is not causality — blast radius is
reported per impact class and per hop, never as one merged number."""

from __future__ import annotations

from collections import deque
from typing import Any

from platformforge.graph.model import Edge, Graph, impact_class

DEPENDENCY_KINDS = frozenset(
    ["depends_on", "calls", "consumes", "reads", "writes", "uses_secret", "runs_on", "contained_by", "routes_to", "publishes_to", "provisioned_by"])


def _adj(g: Graph, reverse: bool = False,
         kinds: frozenset[str] | None = None) -> dict[str, list[Edge]]:
    adj: dict[str, list[Edge]] = {nid: [] for nid in g.nodes}
    for e in g.edges.values():
        if kinds is not None and e.kind not in kinds:
            continue
        (adj[e.dst] if reverse else adj[e.src]).append(e)
    return adj


def neighbors(g: Graph, nid: str, kind: str | None = None) -> list[Edge]:
    return [e for e in _adj(g)[nid] if kind is None or e.kind == kind]


def dependencies(g: Graph, nid: str, transitive: bool = True,
                 max_depth: int = 64) -> dict[str, int]:
    """BFS downstream (what nid depends on) → {node_id: depth}."""
    return _reach(g, nid, reverse=False, max_depth=max_depth) \
        if transitive else {e.dst: 1 for e in
                            _adj(g, kinds=DEPENDENCY_KINDS)[nid]}


def dependents(g: Graph, nid: str, transitive: bool = True,
               max_depth: int = 64) -> dict[str, int]:
    """BFS upstream (what depends on nid) → {node_id: depth}."""
    return _reach(g, nid, reverse=True, max_depth=max_depth) \
        if transitive else {e.src: 1 for e in
                            _adj(g, reverse=True,
                                 kinds=DEPENDENCY_KINDS)[nid]}


def _reach(g: Graph, nid: str, reverse: bool, max_depth: int,
           kinds: frozenset[str] | None = DEPENDENCY_KINDS) -> dict[str, int]:
    adj = _adj(g, reverse, kinds)
    seen: dict[str, int] = {}
    q: deque[tuple[str, int]] = deque([(nid, 0)])
    while q:
        cur, d = q.popleft()
        if d >= max_depth:
            continue
        for e in adj.get(cur, []):
            nxt = e.src if reverse else e.dst
            if nxt not in seen and nxt != nid:
                seen[nxt] = d + 1
                q.append((nxt, d + 1))
    return seen


def paths(g: Graph, src: str, dst: str, max_paths: int = 16,
          max_depth: int = 32) -> list[list[str]]:
    """All simple src→dst paths (bounded)."""
    out: list[list[str]] = []
    adj = _adj(g)
    stack = [(src, [src])]
    while stack and len(out) < max_paths:
        cur, path = stack.pop()
        if cur == dst:
            out.append(path)
            continue
        if len(path) > max_depth:
            continue
        for e in adj.get(cur, []):
            if e.dst not in path:
                stack.append((e.dst, path + [e.dst]))
    return out


def blast_radius(g: Graph, nid: str, max_depth: int = 64) -> dict[str, Any]:
    """What breaks if nid breaks: upstream dependents (things that depend on
    nid) decomposed by impact class and hop distance."""
    adj_rev = _adj(g, reverse=True, kinds=DEPENDENCY_KINDS)
    seen: dict[str, dict[str, Any]] = {}
    q: deque[tuple[str, int, Edge | None]] = deque([(nid, 0, None)])
    while q:
        cur, d, _via = q.popleft()
        if d >= max_depth:
            continue
        for e in adj_rev.get(cur, []):
            if e.src == nid or e.src in seen:
                continue
            seen[e.src] = {"depth": d + 1,
                           "impact_class": impact_class(e.kind),
                           "via_edge": e.eid, "provenance": e.provenance}
            q.append((e.src, d + 1, e))
    by_class: dict[str, list[str]] = {}
    for target, info in seen.items():
        by_class.setdefault(info["impact_class"], []).append(target)
    return {
        "origin": nid,
        "impacted_total": len(seen),
        "by_class": {k: sorted(v) for k, v in sorted(by_class.items())},
        "nodes": {k: seen[k] for k in sorted(seen)},
        "note": "graph proximity is not proven causality; classes are "
                "reported separately",
    }


def cycles(g: Graph, max_cycles: int = 100) -> list[list[str]]:
    """Detect dependency cycles via DFS (bounded)."""
    color: dict[str, int] = {}
    out: list[list[str]] = []
    adj = _adj(g, kinds=DEPENDENCY_KINDS)

    def dfs(u: str, stack: list[str]) -> None:
        color[u] = 1
        for e in adj.get(u, []):
            if len(out) >= max_cycles:
                return
            if color.get(e.dst, 0) == 1 and e.dst in stack:
                out.append(stack[stack.index(e.dst):] + [e.dst])
            elif color.get(e.dst, 0) == 0:
                dfs(e.dst, stack + [e.dst])
        color[u] = 2

    for n in sorted(g.nodes):
        if color.get(n, 0) == 0 and len(out) < max_cycles:
            dfs(n, [n])
    return out


def condensation(g: Graph,
                 kinds: frozenset[str] | None = DEPENDENCY_KINDS):
    """SCC condensation of the dependency graph (iterative Tarjan).

    Returns (node→scc int, members per scc, condensed reverse adjacency
    scc→[parent sccs]). Nodes inside one SCC reach each other, so every
    blast cone decomposes as: own SCC members + members of ancestor SCCs.
    """
    adj_fwd: dict[str, list[str]] = {n: [] for n in g.nodes}
    for e in g.edges.values():
        if kinds is None or e.kind in kinds:
            adj_fwd[e.src].append(e.dst)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    scc_of: dict[str, int] = {}
    members: list[list[str]] = []
    t = 0
    for root in g.nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            u, pi = work[-1]
            if pi == 0:
                index[u] = low[u] = t; t += 1
                stack.append(u); on_stack.add(u)
            recurse = False
            nbrs = adj_fwd.get(u, [])
            for i in range(pi, len(nbrs)):
                v = nbrs[i]
                if v not in index:
                    work[-1] = (u, i + 1)
                    work.append((v, 0))
                    recurse = True
                    break
                if v in on_stack:
                    low[u] = min(low[u], index[v])
            if recurse:
                continue
            work.pop()
            if work:
                p = work[-1][0]
                low[p] = min(low[p], low[u])
            if low[u] == index[u]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    scc_of[w] = len(members)
                    comp.append(w)
                    if w == u:
                        break
                members.append(comp)
    rev: dict[int, list[int]] = {i: [] for i in range(len(members))}
    seen_pair: set[tuple[int, int]] = set()
    for e in g.edges.values():
        if kinds is not None and e.kind not in kinds:
            continue
        a, b = scc_of.get(e.dst), scc_of.get(e.src)
        if a is not None and b is not None and a != b \
                and (a, b) not in seen_pair:
            seen_pair.add((a, b))
            rev[a].append(b)
    return scc_of, members, rev


def _articulation_points(g: Graph) -> list[str]:
    """Undirected cut vertices (iterative Tarjan) — nodes whose removal
    increases the component count of the dependency graph."""
    adj: dict[str, set[str]] = {n: set() for n in g.nodes}
    for e in g.edges.values():
        if e.kind in DEPENDENCY_KINDS:
            adj[e.src].add(e.dst)
            adj[e.dst].add(e.src)
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str] = {}
    aps: set[str] = set()
    t = 0
    for root in g.nodes:
        if root in disc:
            continue
        stack = [(root, iter(sorted(adj[root])))]
        disc[root] = low[root] = t; t += 1
        parent[root] = ""
        children = 0
        while stack:
            u, it = stack[-1]
            advanced = False
            for v in it:
                if v not in disc:
                    parent[v] = u
                    children += 1 if u == root else 0
                    disc[v] = low[v] = t; t += 1
                    stack.append((v, iter(sorted(adj[v]))))
                    advanced = True
                    break
                if v != parent.get(u):
                    low[u] = min(low[u], disc[v])
            if not advanced:
                stack.pop()
                if stack:
                    p = stack[-1][0]
                    low[p] = min(low[p], low[u])
                    if p != root and low[u] >= disc[p]:
                        aps.add(p)
        if children > 1:
            aps.add(root)
    return sorted(aps)


def gaps(g: Graph) -> dict[str, Any]:
    """Structural gaps: orphans, missing ownership/observability/protection,
    unallocated cost, external exposure, single points of failure,
    unreachable resources."""
    fwd = _adj(g)
    inbound = _adj(g, reverse=True)
    orphans = [n for n in g.nodes if not fwd[n] and not inbound[n]]
    owned = {e.dst for e in g.edges.values() if e.kind == "owns"}
    observed = {e.src for e in g.edges.values() if e.kind == "observed_by"} | \
        {e.dst for e in g.edges.values() if e.kind == "observed_by"}
    secured = {e.src for e in g.edges.values() if e.kind == "secured_by"}
    billed = {e.src for e in g.edges.values() if e.kind == "billed_to"}
    exposed = {e.src for e in g.edges.values() if e.kind == "exposes"} | \
        {nid for nid, n in g.nodes.items() if n.attrs.get("public")}
    workloads = {nid for nid, n in g.nodes.items()
                 if n.kind in ("workload", "service", "component")}
    resources = {nid for nid, n in g.nodes.items()
                 if n.kind in ("database", "bucket", "queue", "volume",
                               "cluster", "load_balancer")}
    # unreachable: a workload/resource nothing depends on, calls, or
    # exposes — present in the platform but dead-ended from consumers.
    unreachable = sorted(
        n for n in workloads | resources
        if n not in orphans and not inbound[n] and n not in exposed)
    return {
        "orphans": sorted(orphans),
        "ownership_gaps": sorted(n for n in workloads | resources
                                 if n not in owned),
        "unmonitored": sorted(n for n in workloads if n not in observed),
        "unprotected": sorted(n for n in workloads | resources
                              if n not in secured),
        "unallocated_cost": sorted(n for n in workloads | resources
                                   if n not in billed),
        "external_exposure": sorted(exposed),
        "single_points_of_failure": _articulation_points(g),
        "unreachable": unreachable,
    }
