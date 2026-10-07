"""Context packs v2 — graph-aware, explainable, budget-deciding (§22–§28).

Pipeline (§23): task → intent terms → candidate files → changed artifacts →
graph seeds/neighborhood → rules → facts → historical findings → risk
modifiers → rank → dedup → budget → pack.

Every item carries `score` + `reasons` (§25). Items are classified
essential / high-value / optional / background (§27). If essential alone
exceeds the budget the pack returns `budget_decision: refuse` — essential
evidence is never dropped silently.
"""

from __future__ import annotations

import json
import re
from typing import Any

from platformforge.tokensave.budget import Budget
from platformforge.tokensave.estimate import estimate_tokens
from platformforge.tokensave.index import SearchIndex
from platformforge.tokensave.ledger import LedgerEntry, TokenLedger

WORD_RE = re.compile(r"[A-Za-z0-9_.\-/]{3,}")

ESSENTIAL = "essential"        # findings, facts, rules, unresolved — never dropped
HIGH_VALUE = "high-value"      # changed files, graph distance ≤ 1, risk-flagged
OPTIONAL = "optional"
BACKGROUND = "background"

# §24 — explainable scoring weights. Each contributes a named reason.
W_CHANGED = 10.0
W_TASK_TERM = 2.0
W_SYMBOL = 3.0
W_PATH_TERM = 4.0
W_GRAPH_DIST = {1: 6.0, 2: 3.0}
W_RISK = {"critical": 8.0, "high": 5.0, "medium": 2.0}
W_RULE = 4.0


class ContextPackBuilder:
    def __init__(self, index: SearchIndex, ledger: TokenLedger | None = None):
        self.index = index
        self.ledger = ledger

    def _task_terms(self, task: str) -> list[str]:
        return [t.lower() for t in WORD_RE.findall(task)]

    def _rank_files(self, terms: list[str], changed: list[str],
                    graph_nodes: list[str] | None,
                    rule_ids: list[str] | None,
                    risk: str | None,
                    limit: int = 50) -> list[dict[str, Any]]:
        """Ranked candidates with explainable reasons (§24–§25)."""
        scores: dict[str, float] = {}
        reasons: dict[str, list[str]] = {}

        def bump(path: str, w: float, reason: str) -> None:
            scores[path] = scores.get(path, 0.0) + w
            reasons.setdefault(path, [])
            if reason not in reasons[path]:
                reasons[path].append(reason)

        for path in changed:
            bump(path, W_CHANGED, "changed-file")
        for term in terms:
            for hit in self.index.search(f'"{term}"', limit=20):
                bump(hit["path"], W_TASK_TERM, f"task-term:{term}")
            for hit in self.index.symbol(term):
                bump(hit["path"], W_SYMBOL, f"symbol:{term}")
            for path in self.index.by_path(f"*{term}*"):
                bump(path, W_PATH_TERM, f"path:{term}")
        for node in graph_nodes or []:
            # graph seeds/neighbors: node label terms hit path ranking
            depth = 1 if ":" not in node else int(node.split(":", 1)[1])
            w = W_GRAPH_DIST.get(depth, 1.0)
            label = node.split("/")[-1].split(":")[0]
            for hit in self.index.search(f'"{label}"', limit=10):
                bump(hit["path"], w, f"graph-distance:{depth}")
            for path in self.index.by_path(f"*{label}*"):
                bump(path, w, f"graph-distance:{depth}")
        for rid in rule_ids or []:
            for hit in self.index.search(f'"{rid}"', limit=5):
                bump(hit["path"], W_RULE, f"rule:{rid}")
        if risk:
            for term in ("iam", "policy", "secret", "sg", "security"):
                for hit in self.index.by_path(f"*{term}*"):
                    bump(hit, W_RISK.get(risk, 0.0), f"risk:{risk}")
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{"path": p, "score": round(s, 2), "reasons": reasons[p]}
                for p, s in ranked[:limit]]

    def build(self, task: str, budget: Budget | None = None,
              changed_files: list[str] | None = None,
              facts: list[dict] | None = None,
              findings: list[dict] | None = None,
              rules: list[str] | None = None,
              graph_neighborhood: list[dict] | None = None,
              risk: str | None = None,
              previous_pack_hash: str | None = None,
              max_file_bytes: int = 20_000,
              retain_content: bool = False) -> dict[str, Any]:
        budget = budget or Budget()
        changed = changed_files or []
        node_terms = [
            f"{n.get('node', '')}:{n.get('depth', '')}" if isinstance(n, dict)
            else str(n) for n in (graph_neighborhood or [])]
        ranked = self._rank_files(self._task_terms(task), changed,
                                  node_terms, rules, risk)
        seen_hash: set[str] = set()

        files_out: list[dict[str, Any]] = []
        symbols_out: list[str] = []
        used_tokens = 0
        skipped = 0
        reused = 0
        for cand in ranked:
            path, score, c_reasons = cand["path"], cand["score"], cand["reasons"]
            body = self.index.read(path)
            if body is None:
                continue
            sha = self.index.db.execute(
                "SELECT sha256 FROM files WHERE path=?", (path,)).fetchone()[0]
            if sha in seen_hash:
                skipped += 1
                continue  # dedup identical content
            cls = HIGH_VALUE if ("changed-file" in c_reasons
                                 or "graph-distance:1" in c_reasons) \
                else OPTIONAL
            truncated = body[:max_file_bytes]
            tokens = estimate_tokens(truncated)
            if budget.input_budget and used_tokens + tokens > budget.input_budget:
                head = truncated[: len(truncated) // 4]
                head_tokens = estimate_tokens(head)
                if used_tokens + head_tokens <= budget.input_budget:
                    truncated, tokens = head + "\n…[truncated by budget]", head_tokens
                elif cls == HIGH_VALUE and previous_pack_hash is None:
                    # high-value overflowing: degrade to optional head anyway
                    skipped += 1
                    continue
                else:
                    skipped += 1
                    continue
            seen_hash.add(sha)
            used_tokens += tokens
            entry = {"path": path, "score": score,
                     "reasons": c_reasons, "class": cls,
                     "tokens": tokens,
                     "delivered_bytes": len(truncated.encode()),
                     "delivered_chars": len(truncated)}
            if retain_content:
                # exact delivered payload — QPT measures what ships
                entry["content"] = truncated
            files_out.append(entry)
            sym_row = self.index.db.execute(
                "SELECT symbols FROM files WHERE path=?", (path,)).fetchone()
            if sym_row and sym_row[0]:
                symbols_out.extend(sym_row[0].split()[:8])

        # §27–28 — essential evidence is facts/findings/rules/unresolved.
        essential = {"facts": facts or [], "findings": findings or [],
                     "rules": rules or []}
        essential_tokens = estimate_tokens(json.dumps(essential, default=str))
        over_essential = bool(budget.input_budget
                              and essential_tokens > budget.input_budget)
        if over_essential:
            decision = "refuse"
            decision_reason = ("essential evidence exceeds input budget "
                               "— refusing rather than dropping evidence")
        elif used_tokens > 0 and budget.input_budget \
                and used_tokens + essential_tokens > budget.input_budget:
            decision = "reduced_scope"
            decision_reason = "optional items dropped to fit budget"
        elif skipped:
            decision = "reduced_scope"
            decision_reason = "duplicates/overflow skipped"
        else:
            decision, decision_reason = "ok", "within budget"

        pack = {
            "task": {"description": task, "changed_files": changed},
            "relevant_files": files_out,
            "relevant_symbols": sorted(set(symbols_out))[:100],
            "facts": facts or [],
            "findings": findings or [],
            "graph_neighborhood": graph_neighborhood or [],
            "rules": rules or [],
            "sources": [],
            "budget": budget.to_dict(),
            "budget_decision": decision,
            "budget_reason": decision_reason,
            "packed_files": len(files_out),
            "packed_bytes": sum(f["delivered_bytes"] for f in files_out),
            "est_input_tokens": used_tokens + essential_tokens,
            "essential_tokens": essential_tokens,
            "skipped_duplicates": skipped,
            "delta_aware": previous_pack_hash is not None,
            "reused_from_previous": reused,
        }
        if decision == "refuse":
            pack["refusals"] = [{
                "code": "PF-BUDGET-ESSENTIAL",
                "reason": decision_reason,
                "unlock": "raise --input-budget or narrow the task scope"}]
            pack["relevant_files"] = []
        else:
            pack["refusals"] = []

        if self.ledger:
            self.ledger.record(LedgerEntry(
                operation="context.pack",
                context_requested=estimate_tokens(task) + sum(
                    estimate_tokens(self.index.read(c["path"]) or "")
                    for c in ranked),
                context_candidate=sum(
                    estimate_tokens(self.index.read(c["path"]) or "")
                    for c in ranked),
                context_selected=used_tokens,
                context_delivered=used_tokens + essential_tokens,
                context_skipped=skipped,
                essential_tokens=essential_tokens,
                optional_tokens=used_tokens,
                input_tokens_est=used_tokens + essential_tokens,
                token_basis="estimated",
                extra={"budget_decision": decision},
            ))
        return pack

    def delta_for_change(self, changed_files: list[str],
                         budget: Budget | None = None,
                         graph_neighborhood: list[dict] | None = None,
                         previous_pack_hash: str | None = None,
                         risk: str | None = None) -> dict[str, Any]:
        """§26 — PR-style delta: diff → files → graph neighbors → rules →
        pack. previous_pack_hash marks the delta (content-addressed dedup
        already skips identical bodies)."""
        return self.build(
            task="review change", budget=budget, changed_files=changed_files,
            graph_neighborhood=graph_neighborhood,
            previous_pack_hash=previous_pack_hash, risk=risk)


def pack_to_text(pack: dict[str, Any], index: SearchIndex) -> str:
    """Render a pack for an agent prompt — file bodies bounded by what the
    pack actually delivered (`delivered_bytes`), plus the essential
    facts/findings/rules the pack carries. Never re-reads beyond the
    pack's own truncation."""
    out = [f"# task: {pack['task']['description']}"]
    for f in pack["relevant_files"]:
        path = f["path"] if isinstance(f, dict) else f
        reasons = ""
        content = None
        if isinstance(f, dict):
            reasons = f"  # {', '.join(f.get('reasons', []))}"
            content = f.get("content")
        out.append(f"\n## {path}{reasons}")
        if content is None:
            body = index.read(path) or ""
            delivered = f.get("delivered_chars") if isinstance(f, dict) \
                else None
            content = body[:delivered] if delivered else body[:4000]
        out.append(content)
    essential = {"facts": pack.get("facts") or [],
                 "findings": pack.get("findings") or [],
                 "rules": pack.get("rules") or []}
    if any(essential.values()):
        out.append("\n## essential-evidence")
        out.append(json.dumps(essential, default=str)[:8000])
    return "\n".join(out)
