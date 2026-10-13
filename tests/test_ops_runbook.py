"""Phase O gates — structured runbooks."""

from platformforge.ops.runbook import BUILTIN_RUNBOOKS, Runbook, RunbookStep


def test_builtin_runbooks_all_valid():
    for rb in BUILTIN_RUNBOOKS.values():
        assert rb.audit() == [], rb.runbook_id
        bound = rb.bind()
        assert bound["ok"] and bound["steps"]


def test_unknown_action_refused():
    rb = Runbook(runbook_id="x", trigger={"a": 1},
                 steps=[RunbookStep("s1", "shell.exec")],
                 sources=["src"])
    codes = {v["refusal"] for v in rb.audit()}
    assert "PF-OPS-UNKNOWN-ACTION" in codes


def test_no_trigger_refused():
    rb = Runbook(runbook_id="x", sources=["s"],
                 steps=[RunbookStep("s", "kubernetes.scale")])
    codes = {v["refusal"] for v in rb.audit()}
    assert "PF-OPS-RUNBOOK-NO-TRIGGER" in codes


def test_diagnostics_need_source():
    rb = Runbook(runbook_id="x", trigger={"a": 1}, sources=["s"],
                 diagnostics=[{"check": "look around"}],
                 steps=[RunbookStep("s", "kubernetes.scale")])
    codes = {v["refusal"] for v in rb.audit()}
    assert "PF-OPS-RUNBOOK-DIAG-NO-SOURCE" in codes


def test_bind_carries_depends_on():
    rb = Runbook(runbook_id="x", trigger={"a": 1}, sources=["s"],
                 steps=[RunbookStep("a", "git.create_branch",
                                    params={"branch": "b"}),
                        RunbookStep("b", "git.commit",
                                    depends_on=["a"])])
    bound = rb.bind({"extra": 1})
    steps = {s.step_id: s for s in bound["steps"]}
    assert steps["b"].params["__depends_on__"] == ["a"]


def test_runbook_hash_stable():
    rb = BUILTIN_RUNBOOKS["replica-drift-restore"]
    assert rb.hash() == rb.hash()
