"""Phase V gates — config schema/migrations + operation store."""

import json

from platformforge.ops.config import DEFAULTS, load_config, validate_config
from platformforge.ops.operation import Operation, OperationLedger
from platformforge.ops.store import OperationStore


def test_defaults_when_no_file(tmp_path):
    r = load_config(root=tmp_path)
    assert r["source"] == "defaults"
    assert r["config"]["autonomy"]["max"] == "A4"
    assert r["config"]["operations"]["default_dry_run"] is True


def test_migration_v0_to_v2(tmp_path):
    cfg = tmp_path / ".platformforge"
    cfg.mkdir()
    (cfg / "config.yaml").write_text(
        "approval_ttl: 3600\n")
    r = load_config(root=tmp_path)
    assert r["config"]["schema_version"] == 2
    assert r["config"]["approval"]["default_ttl_s"] == 3600
    assert r["migrated"] == [0, 1]
    assert r["config"]["rbac"]["roles"]["oncall"]["break_glass"]


def test_future_version_refused(tmp_path):
    cfg = tmp_path / ".platformforge"
    cfg.mkdir()
    (cfg / "config.yaml").write_text("schema_version: 99\n")
    r = load_config(root=tmp_path)
    assert r["refusal"] == "PF-OPS-CONFIG-VERSION"


def test_autonomy_a6_refused(tmp_path):
    cfg = dict(DEFAULTS)
    cfg["autonomy"] = {"max": "A6", "a5_environments": ["lab"]}
    v = validate_config(cfg)
    assert any(x["refusal"] == "PF-OPS-CONFIG-AUTONOMY" for x in v)


def test_unknown_keys_reported(tmp_path):
    cfg = tmp_path / ".platformforge"
    cfg.mkdir()
    (cfg / "config.yaml").write_text(
        "schema_version: 2\nbogus_domain: {x: 1}\n")
    r = load_config(root=tmp_path)
    assert "bogus_domain" in r["unknown_keys"]


def test_store_append_and_verify(tmp_path):
    st = OperationStore(tmp_path / "ops")
    op = Operation(operation_id="o1", resources=["r1"])
    led = OperationLedger()
    led.append("created", "o1")
    led.append("approved", "o1", actor="human")
    st.save(op, led)
    # append more, save again — no dup lines
    led.append("executed", "o1")
    st.save(op, led)
    back = st.load_ledger("o1")
    assert len(back.entries) == 3
    assert st.verify("o1")["chain_valid"]
    lines = (tmp_path / "ops" / "o1.ledger.jsonl").read_text()
    assert lines.count("\n") == 3


def test_store_schema_migrate(tmp_path):
    d = tmp_path / "ops"
    d.mkdir()
    (d / "_schema_version").write_text("1")
    (d / "x.ledger.jsonl").write_text(json.dumps({
        "seq": 1, "event": "a", "operation_id": "x", "actor": "system",
        "at": "t", "data": {}, "prev_hash": "genesis",
        "entry_hash": "sha256:abc"}) + "\n")
    OperationStore(d)
    assert (d / "_schema_version").read_text() == "2"
    rec = json.loads((d / "x.ledger.jsonl").read_text().strip())
    assert rec["schema"] >= 1


def test_audit_digest_tamper_evident(tmp_path):
    st = OperationStore(tmp_path / "ops")
    led = OperationLedger()
    led.append("e1", "o1")
    st.save(Operation(operation_id="o1"), led)
    d1 = st.audit_digest()
    led2 = OperationLedger()
    led2.append("e1", "o2")
    st.save(Operation(operation_id="o2"), led2)
    assert st.audit_digest() != d1
