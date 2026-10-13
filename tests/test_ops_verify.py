"""Phase K gates — verification engine + convergence states."""

from platformforge.ops.verify import freshness_ok, slo_gate, verify, verify_delta


def test_verify_delta_match_miss():
    exp = {"changes": {"resources": [{"id": "dep/web"}]},
           "adds": {"network": ["svc/x"]}}
    obs = {"changes": {"resources": [{"id": "dep/web"}]},
           "adds": {"network": ["svc/x"]}}
    m, mi, u = verify_delta(exp, obs)
    assert len(m) == 2 and not mi and not u
    obs2 = {"changes": {"resources": [{"id": "dep/web"}]}}
    _m2, mi2, _u2 = verify_delta(exp, obs2)
    assert mi2 == ["adds:network:svc/x"]


def test_converged_when_all_windows_pass():
    obs = {"immediate": {"changes": {"resources": [{"id": "a"}]}},
           "stabilization": {"changes": {"resources": [{"id": "a"}]}},
           "extended": {"changes": {"resources": [{"id": "a"}]}}}
    r = verify(expected_delta=obs["immediate"], observations=obs,
               slo_contract={"error_rate_max": 0.01},
               metrics={"error_rate": 0.001})
    assert r.convergence == "converged"


def test_slo_regression_means_not_converged():
    obs = {"immediate": {"changes": {"resources": [{"id": "a"}]}}}
    r = verify(expected_delta=obs["immediate"], observations=obs,
               slo_contract={"error_rate_max": 0.01},
               metrics={"error_rate": 0.5})
    assert r.slo_gate["status"] == "fail"
    assert r.convergence in ("regressed", "partially-converged",
                             "not-converged")
    assert r.convergence != "converged"


def test_no_observation_is_unknown_not_pass():
    r = verify(expected_delta={"changes": {"x": []}}, observations={})
    assert all(w.status == "unknown" for w in r.windows)
    assert r.convergence == "unknown"


def test_command_success_is_not_convergence():
    # executor rc=0 but observed delta mismatches → fail
    r = verify(expected_delta={"changes": {"resources": [{"id": "a"}]}},
               observations={"immediate": {"changes": {"resources": []}}})
    assert r.windows[0].status == "fail"


def test_slo_gate_unknown_inputs():
    assert slo_gate(None, None)["status"] == "unknown"
    assert slo_gate({"error_rate_max": 0.1}, {})["status"] == "unknown"


def test_freshness_windows():
    assert freshness_ok("2999-01-01T00:00:00Z", "immediate")
    assert not freshness_ok("2000-01-01T00:00:00Z", "immediate")
