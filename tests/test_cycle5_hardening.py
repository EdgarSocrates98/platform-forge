"""Cycle 5 Phase O — store, config v3, flags, privacy, bench smoke."""


def test_analytics_store_roundtrip(tmp_path):
    from platformforge.analytics.store import AnalyticsStore
    st = AnalyticsStore(tmp_path / "a.db")
    st.put_event("incident", "2025-11-01T00:00:00Z", "svc:a",
                 "opened", "test", {"sig": "s1"})
    st.put_events([{"kind": "incident",
                    "ts": "2025-11-02T00:00:00Z", "subject": "svc:a",
                    "outcome": "resolved", "attrs": {"sig": "s1"}}])
    evs = st.events(subject="svc:a")
    assert len(evs) == 2 and evs[0]["attrs"]["sig"] == "s1"


def test_store_refuses_secrets(tmp_path):
    from platformforge.analytics.store import AnalyticsStore
    st = AnalyticsStore(tmp_path / "a.db")
    r = st.put_event("x", "2025-11-01T00:00:00Z", "s", "o", "t",
                     {"api_key": "AKIAIOSFODNN7EXAMPLE"})
    assert r["refusal"] == "PF-ANALYTICS-SECRET"
    assert not st.events()


def test_store_forget_subject(tmp_path):
    from platformforge.analytics.store import AnalyticsStore
    st = AnalyticsStore(tmp_path / "a.db")
    st.put_event("incident", "2025-11-01T00:00:00Z", "person-x",
                 "o", "t", {})
    st.put_event("incident", "2025-11-01T00:00:00Z", "svc:ok",
                 "o", "t", {})
    r = st.forget_subject("person-x")
    assert r["events_deleted"] == 1
    assert all(e["subject"] == "svc:ok" for e in st.events())


def test_store_gc_and_stats(tmp_path):
    from platformforge.analytics.store import AnalyticsStore
    st = AnalyticsStore(tmp_path / "a.db")
    st.put_event("e", "2020-01-01T00:00:00Z", "s", "o", "t", {})
    r = st.gc(event_days=30)
    assert r["events_deleted"] == 1
    stats = st.stats()
    assert stats["telemetry"] == "local-only" and \
        stats["storage_bytes"] > 0


def test_hydrate_engine(tmp_path):
    from platformforge.analytics.history import HistoryEngine
    from platformforge.analytics.store import AnalyticsStore
    st = AnalyticsStore(tmp_path / "a.db")
    st.put_event("incident", "2025-11-01T00:00:00Z", "svc:a",
                 "opened", "t", {"subject": "svc:a"})
    eng = HistoryEngine()
    assert st.hydrate_engine(eng) == 1


def test_config_v3_migration(tmp_path):
    import yaml

    from platformforge.ops.config import CONFIG_SCHEMA_VERSION, load_config
    (tmp_path / ".platformforge").mkdir()
    (tmp_path / ".platformforge" / "config.yaml").write_text(
        yaml.safe_dump({"schema_version": 1,
                        "autonomy": {"max": "A4"}}))
    r = load_config(root=tmp_path)
    assert CONFIG_SCHEMA_VERSION == 3
    assert r["config"]["schema_version"] == 3
    assert "features" in r["config"] and "privacy" in r["config"]
    assert r["config"]["retention"]["telemetry"] == "local-only"


def test_feature_flags_defaults():
    from platformforge.ops.config import feature_enabled
    assert feature_enabled("fleet")
    assert feature_enabled("analytics")
    assert not feature_enabled("federation")   # boundary is opt-in
    assert not feature_enabled("does-not-exist")


def test_privacy_not_configurable_downward():
    from platformforge.ops.config import validate_config
    bad = {"privacy": {"dx_metrics": "per-person"},
           "retention": {"telemetry": "local-only"}}
    v = validate_config(bad)
    assert any(x["refusal"] == "PF-OPS-CONFIG-PRIVACY" for x in v)
    bad2 = {"privacy": {}, "retention": {"telemetry": "cloud-export"}}
    v2 = validate_config(bad2)
    assert any(x["refusal"] == "PF-OPS-CONFIG-TELEMETRY" for x in v2)


def test_scale_bench_smoke():
    from platformforge.graph.bench import benchmark_summary, run_scale_benchmarks
    r = run_scale_benchmarks((20,))
    m = r["sizes"]["20"]
    assert m["build_ms"] >= 0 and m["nodes"] > 0
    assert benchmark_summary(r)


def test_scale_bench_deterministic_shape():
    from platformforge.graph.bench import synthetic_graph
    a, b = synthetic_graph(30), synthetic_graph(30)
    assert sorted(a.nodes) == sorted(b.nodes)
    assert sorted(a.edges) == sorted(b.edges)
