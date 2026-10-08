"""Cycle 4 — executor boundary (§70–71, ADR-0027).

Executors are deterministic host-side adapters. The core builds typed
steps; transports run them; results come back as ExecutionReceipts.
An executor NEVER sees LLM context and NEVER receives a raw shell
string — only `action` + validated `params`.

Transport contract (same shape as collectors):
    run(argv: list[str], cwd: str|None, timeout_s: int)
        -> (rc: int, stdout: str, stderr: str)
Injected per call — tests and fixtures replay deterministic transports.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from platformforge.live.models import canonical_hash, now_iso
from platformforge.ops.actions import spec_for, validate_action

Transport = Callable[..., tuple[int, str, str]]

RECEIPT_SCHEMA = "platformforge/execution-receipt/v1"


@dataclass
class ExecutionReceipt:
    """§94–96 — what happened, hashed, reproducible."""
    step_id: str
    action: str
    executor: str
    ok: bool
    dry_run: bool = False
    rc: int = 0
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    refusal: dict[str, Any] | None = None
    error: str = ""
    argv_hash: str = ""        # hash of the argv (argv may contain paths)
    side_effects: str = ""
    receipt_hash: str = ""

    def finalize(self) -> ExecutionReceipt:
        body = {"step_id": self.step_id, "action": self.action,
                "executor": self.executor, "ok": self.ok,
                "dry_run": self.dry_run, "rc": self.rc,
                "finished_at": self.finished_at,
                "outputs": self.outputs, "error": self.error,
                "argv_hash": self.argv_hash,
                "refusal": self.refusal}
        self.receipt_hash = "sha256:" + canonical_hash(body)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"schema": RECEIPT_SCHEMA, "step_id": self.step_id,
                "action": self.action, "executor": self.executor,
                "ok": self.ok, "dry_run": self.dry_run, "rc": self.rc,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "duration_ms": self.duration_ms,
                "outputs": self.outputs,
                "argv_hash": self.argv_hash,
                "side_effects": self.side_effects,
                "refusal": self.refusal, "error": self.error,
                "receipt_hash": self.receipt_hash}


class Executor:
    """Base: dispatch typed actions to argv builders; wrap in receipts."""
    name = "abstract"

    def supports(self, action: str) -> bool:
        s = spec_for(action)
        return bool(s and s.executor == self.name)

    def argv_for(self, action: str, params: dict[str, Any],
                 dry_run: bool) -> list[str] | dict[str, Any]:
        """Return argv or a refusal dict."""
        return {"refusal": "PF-OPS-NO-EXECUTOR",
                "unlock": f"{self.name} has no argv builder for {action}"}

    def run_step(self, step_id: str, action: str,
                 params: dict[str, Any], *,
                 transport: Transport | None = None,
                 dry_run: bool = False, cwd: str | None = None,
                 timeout_s: int | None = None) -> ExecutionReceipt:
        spec = spec_for(action)
        started = now_iso()
        t0 = time.monotonic()
        r = ExecutionReceipt(step_id=step_id, action=action,
                             executor=self.name, ok=False,
                             dry_run=dry_run, started_at=started)

        def finish(ok: bool, **kw) -> ExecutionReceipt:
            r.ok = ok
            r.finished_at = now_iso()
            r.duration_ms = int((time.monotonic() - t0) * 1000)
            for k, v in kw.items():
                setattr(r, k, v)
            return r.finalize()

        if spec is None:
            return finish(False, refusal={
                "refusal": "PF-OPS-UNKNOWN-ACTION",
                "unlock": f"action {action} not in vocabulary"})
        if spec.executor != self.name:
            return finish(False, refusal={
                "refusal": "PF-OPS-WRONG-EXECUTOR",
                "unlock": f"{action} is owned by {spec.executor}, "
                          f"not {self.name}"})
        err = validate_action(action, params)
        if err:
            return finish(False, refusal=err)
        if dry_run and not spec.dry_run:
            return finish(False, refusal={
                "refusal": "PF-OPS-NO-DRYRUN",
                "unlock": f"{action} does not support dry-run"})
        if spec.mutating and transport is None:
            return finish(False, refusal={
                "refusal": "PF-OPS-NO-TRANSPORT",
                "unlock": "mutating actions require an injected host "
                          "transport — the core never executes alone"})
        argv = self.argv_for(action, params, dry_run)
        if isinstance(argv, dict):            # refusal from builder
            return finish(False, refusal=argv)
        r.argv_hash = "sha256:" + canonical_hash(argv)
        r.side_effects = spec.side_effects
        if transport is None:                  # non-mutating, no transport
            return finish(True, outputs={"skipped": "no transport"})
        try:
            rc, out, err_s = transport(argv, cwd, timeout_s or spec.timeout_s)
        except Exception as exc:  # noqa: BLE001 — adapter failure is evidence
            return finish(False, error=f"transport-error:{exc}")
        r.rc = rc
        outputs = self.parse_outputs(action, rc, out, err_s)
        if rc != 0:
            return finish(False, outputs=outputs, error=err_s[:2000])
        return finish(True, outputs=outputs)

    def parse_outputs(self, action: str, rc: int, out: str, err: str
                      ) -> dict[str, Any]:
        return {"stdout_tail": out[-2000:], "stderr_tail": err[-2000:]}


class ObserveExecutor(Executor):
    """Read-only observation steps — dispatch to the live collectors'
    contract (typed observe actions, never free-form queries)."""
    name = "observe"

    def argv_for(self, action, params, dry_run):
        import json
        return ["observe", action, json.dumps(params, sort_keys=True)]

