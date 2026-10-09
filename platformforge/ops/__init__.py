"""Cycle 4 — governed operations plane.

The operations plane never acts directly: intent → plan → simulate →
risk → policy → approval → execution envelope → preconditions →
typed-action executors → verify → converge/rollback → audit. The core
package is deterministic and SDK-free; mutation happens only inside
host-side executor transports behind typed actions (ADR-0021/0027).
"""
