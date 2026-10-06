"""Context packs — the minimum context an agent needs for a task.

task → rank candidate files (terms, changed files, symbols, graph distance,
rules, ownership, risk) → pack under budget → ledger entry. Dedup by content
hash: identical content is packed once.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from platformforge.tokensave.budget import Budget, check_input_budget
from platformforge.tokensave.estimate import estimate_tokens
from platformforge.tokensave.index import SearchIndex
from platformforge.tokensave.ledger import LedgerEntry, TokenLedger

WORD_RE = re.compile(r"[A-Za-z0-9_.\-/]{3,}")


class ContextPackBuilder:
    def __init__(self, index: SearchIndex, ledger: TokenLedger | None = None):
        self.index = index
        self.ledger = ledger

    def _task_terms(self, task: str) -> list[str]:
        return [t.lower() for t in WORD_RE.findall(task)]

    def _rank_files(self, terms: list[str], changed: list[str],
                    limit: int = 50) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for path in changed:
            scores[path] = scores.get(path, 0.0) + 10.0
        for term in terms:
            for hit in self.index.search(f'"{term}"', limit=20):
                scores[hit["path"]] = scores.get(hit["path"], 0.0) + 2.0
            for hit in self.index.symbol(term):
                scores[hit["path"]] = scores.get(hit["path"], 0.0) + 3.0
            for path in self.index.by_path(f"*{term}*"):
                scores[path] = scores.get(path, 0.0) + 4.0
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]

    def build(self, task: str, budget: Budget | None = None,
              changed_files: list[str] | None = None,
              facts: list[dict] | None = None,
              findings: list[dict] | None = None,
              rules: list[str] | None = None,
              graph_neighborhood: list[dict] | None = None,
              max_file_bytes: int = 20_000) -> dict[str, Any]:
        budget = budget or Budget()
        changed = changed_files or []
        ranked = self._rank_files(self._task_terms(task), changed)
        seen_hash: set[str] = set()

        files_out, symbols_out = [], []
        used_tokens = 0
        skipped = 0
        for path, score in ranked:
            body = self.index.read(path)
            if body is None:
                continue
            sha = self.index.db.execute(
                "SELECT sha256 FROM files WHERE path=?", (path,)).fetchone()[0]
            if sha in seen_hash:
                skipped += 1
                continue  # dedup identical content
            truncated = body[:max_file_bytes]
            tokens = estimate_tokens(truncated)
            if budget.input_budget and used_tokens + tokens > budget.input_budget:
                # try head-only inclusion before skipping outright
                head = truncated[: len(truncated) // 4]
                head_tokens = estimate_tokens(head)
                if used_tokens + head_tokens <= budget.input_budget:
                    truncated, tokens = head + "\n…[truncated by budget]", head_tokens
                else:
                    skipped += 1
                    continue
            seen_hash.add(sha)
            used_tokens += tokens
            files_out.append(path)
            sym_row = self.index.db.execute(
                "SELECT symbols FROM files WHERE path=?", (path,)).fetchone()
            if sym_row and sym_row[0]:
                symbols_out.extend(sym_row[0].split()[:8])

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
            "packed_files": len(files_out),
            "packed_bytes": sum(len(self.index.read(p) or "") for p in files_out),
            "est_input_tokens": used_tokens,
            "skipped_duplicates": skipped,
        }
        verdict = check_input_budget(budget, used_tokens)
        if verdict.decision == "refuse":
            pack["refusals"] = [verdict.to_dict()]
            pack["relevant_files"] = []
        else:
            pack["refusals"] = [] if verdict.decision == "ok" else [verdict.to_dict()]

        if self.ledger:
            self.ledger.record(LedgerEntry(
                operation="context.pack",
                context_requested=estimate_tokens(task) + sum(
                    estimate_tokens(self.index.read(p) or "") for p, _ in ranked),
                context_delivered=used_tokens,
                context_skipped=skipped,
                input_tokens_est=used_tokens,
                token_basis="estimated",
            ))
        return pack

    def delta_for_change(self, changed_files: list[str],
                         budget: Budget | None = None) -> dict[str, Any]:
        """PR-style delta reading: diff → impacted files → neighborhood pack."""
        return self.build(
            task="review change", budget=budget, changed_files=changed_files)


def pack_to_text(pack: dict[str, Any], index: SearchIndex) -> str:
    """Render a pack for an agent prompt — files included by reference."""
    out = [f"# task: {pack['task']['description']}"]
    for path in pack["relevant_files"]:
        body = index.read(path) or ""
        out.append(f"\n## file: {path}\n```\n{body}\n```")
    if pack.get("facts"):
        out.append("\n## facts\n" + json.dumps(pack["facts"], default=str))
    if pack.get("findings"):
        out.append("\n## findings\n" + json.dumps(pack["findings"], default=str))
    return "\n".join(out)
