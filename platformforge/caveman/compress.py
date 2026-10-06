"""Output compression with protected spans + receipts.

Modes: off | lite | full | auto.
  off   — passthrough
  lite  — drop filler, keep sentences & structure
  full  — aggressive: terse fragments, bullets over prose
  auto  — decide by context risk (info→full, architecture→lite,
          incident/destructive→prose with explicit warnings)
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from platformforge.tokensave.estimate import estimate_tokens

PROTECTED_PATTERNS = [
    r"\b(error|warning|exception|denied|failed|fatal|panic)[:\s][^\n]*",
    r"PF-[A-Z0-9-]+-\d+",                                 # fact/rule ids
    r"artifact://sha256/[0-9a-f]{64}",
    r"arn:aws:[\w\-:]+/[^\s]*",                           # ARNs
    r"https?://[^\s)\]]+",
    r"[\w./\-]+/[\w./\-]+",                               # paths
    r"\bv?\d+\.\d+(?:\.\d+)?\b",                          # versions
    r"\b\d+(?:\.\d+)?\s*(?:ms|s|MB|GB|TB|%|Mi|Gi|m)?\b",
    r"`[^`]+`",                                           # inline code/commands
    r"\b(allow|deny|delete|create|update|iam:[\w*]+|s3:[\w*]+)\b",
    r"AKIA[0-9A-Z]{16}|REDACTED:[\w]+:[0-9a-f]{8}",
]

FILLER = re.compile(
    r"(?i)\b(certainly|basically|actually|essentially|in conclusion|"
    r"it is important to note that|please note that|as you can see|"
    r"as mentioned (earlier|above)|in order to|due to the fact that|"
    r"it should be noted|the fact that)\b[,]?")
WORDY = [
    (re.compile(r"(?i)\bis able to\b"), "can"),
    (re.compile(r"(?i)\bin the event that\b"), "if"),
    (re.compile(r"(?i)\ba large number of\b"), "many"),
    (re.compile(r"(?i)\bat this point in time\b"), "now"),
    (re.compile(r"(?i)\bhas the ability to\b"), "can"),
    (re.compile(r"(?i)\bprior to\b"), "before"),
    (re.compile(r"(?i)\bin close proximity to\b"), "near"),
    (re.compile(r"(?i)\bdo not hesitate to\b"), ""),
]
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
RISKY = re.compile(r"(?i)\b(destroy|delete|drop|production|incident|sev[0-9]|"
                   r"irreversible|destructive|security breach|outage)\b")
DECISION = re.compile(r"(?i)\b(architecture|design decision|tradeoff|trade-off|"
                      r"alternatives? considered|rationale)\b")


@dataclass
class CompressionReceipt:
    mode: str
    before_chars: int
    after_chars: int
    before_tokens_est: int
    after_tokens_est: int
    compression_ratio: float
    protected_spans: int
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_COMBINED = re.compile(
    "|".join(f"(?:{p})" for p in PROTECTED_PATTERNS), re.IGNORECASE)


def _protect(text: str) -> tuple[str, list[str]]:
    """Replace protected spans with placeholders → compress prose only.
    Single alternation pass: a placeholder can never match a later pattern."""
    spans: list[str] = []

    def stash(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    return _COMBINED.sub(stash, text), spans


def _restore(text: str, spans: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def _lite(text: str) -> str:
    text = FILLER.sub("", text)
    for rx, rep in WORDY:
        text = rx.sub(rep, text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _full(text: str) -> str:
    text = _lite(text)
    out = []
    for sent in SENT_SPLIT.split(text):
        s = sent.strip()
        if not s:
            continue
        # drop connective-only sentences, keep payload sentences
        if len(s) < 4:
            continue
        if re.match(r"(?i)^(however|moreover|furthermore|additionally|also|"
                    r"in addition|note that|it is worth)\b[,]?\s*", s):
            s = re.sub(r"(?i)^(however|moreover|furthermore|additionally|also|"
                       r"in addition|note that|it is worth)\b[,]?\s*", "", s)
        out.append(s)
    return "\n".join(out)


def choose_mode(text: str, context_risk: str = "normal") -> str:
    if context_risk in ("security-incident", "destructive"):
        return "off"    # prose + explicit warnings — no compression on risk
    if RISKY.search(text):
        return "lite"   # keep signal fully readable
    if DECISION.search(text):
        return "lite"
    return "full"


def compress(text: str, mode: str = "lite",
             context_risk: str = "normal") -> tuple[str, CompressionReceipt]:
    if mode not in ("off", "lite", "full", "auto"):
        raise ValueError(f"unknown mode {mode!r}")
    actual = choose_mode(text, context_risk) if mode == "auto" else mode
    before_chars = len(text)
    before_tokens = estimate_tokens(text)

    protected, spans = _protect(text)
    if actual == "off":
        out = text
    elif actual == "lite":
        out = _lite(protected)
    else:
        out = _full(protected)
    out = _restore(out, spans)

    rc = CompressionReceipt(
        mode=actual, before_chars=before_chars, after_chars=len(out),
        before_tokens_est=before_tokens, after_tokens_est=estimate_tokens(out),
        compression_ratio=(1 - len(out) / before_chars) if before_chars else 0.0,
        protected_spans=len(spans),
    )
    return out, rc
