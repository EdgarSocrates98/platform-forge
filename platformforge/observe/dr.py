"""§90 DR engine — backup/replication/restore/failover/RTO/RPO as an
evidence model. The core rule is structural, not statistical:

    backup exists  !=  restore works

A resource with a declared backup but no restore *evidence* (a restore
test, a replica that has been cut over, a verified snapshot) is
`protection: unresolved` — never `protected`.
"""

from __future__ import annotations

from typing import Any

PROTECTED_KINDS = {"database", "bucket", "volume", "cluster", "workload"}


def dr_model(facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify each protectable resource's DR posture from facts."""
    resources: dict[str, dict[str, Any]] = {}
    for f in facts:
        a = f.get("attrs") or {}
        kind = (a.get("resource_type") or
                (f.get("kind", "").split(".")[-1]))
        label = a.get("name") or f.get("location", "?")
        if kind not in PROTECTED_KINDS and not any(
                k in a for k in ("backup", "replication", "restore_tested",
                                 "rto", "rpo", "failover")):
            continue
        r = resources.setdefault(label, {
            "kind": kind, "fact_ids": [],
            "backup_declared": False, "replication_declared": False,
            "restore_evidence": False, "failover_evidence": False,
            "rto": None, "rpo": None})
        r["fact_ids"].append(f.get("fact_id", ""))
        for k in a:
            kl = k.lower()
            if "backup" in kl or "snapshot" in kl:
                r["backup_declared"] = True
            if "replicat" in kl or "multi_az" in kl or "multiaz" in kl:
                r["replication_declared"] = True
            if kl in ("restore_tested", "last_restore_at",
                      "restore_verified") and a[k]:
                r["restore_evidence"] = True
            if kl in ("failover_tested", "last_failover_at") and a[k]:
                r["failover_evidence"] = True
        r["rto"] = a.get("rto") or r["rto"]
        r["rpo"] = a.get("rpo") or r["rpo"]

    out = []
    for label, r in sorted(resources.items()):
        if r["restore_evidence"] or r["failover_evidence"]:
            protection = "evidenced"
        elif r["backup_declared"] or r["replication_declared"]:
            protection = "unresolved"   # declared ≠ proven
        else:
            protection = "none"
        out.append({"resource": label, **r,
                    "protection": protection,
                    "note": "backup exists != restore works" if
                            protection == "unresolved" else None})
    counts = {}
    for r in out:
        counts[r["protection"]] = counts.get(r["protection"], 0) + 1
    return {"dr": out, "counts": counts,
            "note": "protection=evidenced requires restore/failover "
                    "evidence, not just declared backups"}
