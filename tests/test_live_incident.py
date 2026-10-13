"""Phase J — incident intelligence V3."""

from __future__ import annotations

from platformforge.live.incident import build_timeline, normalize_event, postmortem_v3, score_candidates

NOW = "2025-06-10T12:00:00Z"
EARLIER = "2025-06-10T11:30:00Z"
LATER = "2025-06-10T12:30:00Z"


def _inc(at=NOW, resources=None, **kw):
    return {"incident_id": "INC-1", "title": "payments down",
            "timestamp": at,
            "resources": resources or ["service/payments-api"], **kw}


class TestNormalize:

    def test_canonical_fields(self):
        e = normalize_event({"kind": "cloudtrail", "timestamp": EARLIER,
                             "actor": "alice", "target": "s3/app",
                             "facts": ["f1"], "confidence": 0.9})
        assert e["kind"] == "cloudtrail" and e["actor"] == "alice"
        assert e["at"] > 0 and e["resources"] == ["s3/app"]

    def test_timeline_sorted_with_counts(self):
        tl = build_timeline([
            {"kind": "alert", "timestamp": NOW, "summary": "5xx"},
            {"kind": "deployment", "timestamp": EARLIER,
             "summary": "v2 deployed"},
            {"kind": "git_change", "timestamp": "2025-06-10T10:00:00Z"}])
        assert tl["counts"]["events"] == 3
        assert tl["timeline"][0]["kind"] == "git_change"
        assert tl["timeline"][-1]["kind"] == "alert"


class TestScoreCandidates:

    def test_mutating_before_incident_ranks_high(self):
        inc = _inc()
        ranked = score_candidates(inc, [
            {"kind": "deployment", "timestamp": EARLIER,
             "action": "deploy", "resources": ["service/payments-api"],
             "tier": 1, "freshness": "fresh"},
            {"kind": "cloudtrail", "timestamp": LATER,
             "action": "DescribeInstances",
             "resources": ["service/other"]}])["ranked"]
        assert ranked[0]["candidate"] == "deploy"
        assert ranked[0]["explain"]["weights"]["temporal"] == 0.25

    def test_change_after_incident_contradicted(self):
        inc = _inc()
        ranked = score_candidates(inc, [
            {"kind": "deployment", "timestamp": LATER, "action": "deploy",
             "resources": ["service/payments-api"]}])["ranked"]
        assert ranked[0]["status"] == "contradicted"

    def test_confirmed_requires_causal_evidence(self):
        inc = _inc()
        base = {"kind": "deployment", "timestamp": EARLIER,
                "action": "deploy", "resources": ["service/payments-api"],
                "tier": 1, "freshness": "fresh", "blast_radius": 0.5,
                "runtime_correlated": True}
        no_causal = score_candidates(inc, [base])["ranked"][0]
        assert no_causal["status"] == "supported"
        causal = score_candidates(
            inc, [{**base, "causal": True, "facts": ["f1"]}]
        )["ranked"][0]
        assert causal["status"] == "confirmed"

    def test_unknown_for_irrelevant_change(self):
        ranked = score_candidates(_inc(), [
            {"kind": "cloudtrail", "timestamp": EARLIER,
             "action": "GetItem", "resources": ["x"],
             "tier": 5, "freshness": "expired"}])["ranked"]
        assert ranked[0]["status"] in ("candidate", "unknown")


class TestPostmortemV3:

    def _ranked(self, inc):
        return score_candidates(inc, [
            {"kind": "deployment", "timestamp": EARLIER,
             "action": "deploy", "resources": ["service/payments-api"],
             "tier": 1, "freshness": "fresh"}])

    def test_root_cause_unresolved_without_causal(self):
        inc = _inc()
        pm = postmortem_v3(inc, build_timeline([]), self._ranked(inc))
        assert pm["postmortem"]["root_cause"]["status"] == "unresolved"

    def test_all_required_sections(self):
        inc = _inc()
        tl = build_timeline(
            [{"kind": "alert", "timestamp": NOW, "summary": "5xx"}])
        pm = postmortem_v3(inc, tl, self._ranked(inc))["postmortem"]
        for key in ("timeline", "impact", "observed_changes",
                    "runtime_signals", "candidate_causes", "root_cause",
                    "unknowns", "follow_ups"):
            assert key in pm
        assert pm["runtime_signals"][0]["summary"] == "5xx"

    def test_confirmed_candidate_promoted(self):
        inc = _inc()
        ranked = score_candidates(inc, [
            {"kind": "deploy", "timestamp": EARLIER, "action": "deploy",
             "resources": ["service/payments-api"], "tier": 1,
             "freshness": "fresh", "causal": True, "facts": ["f1"]}])
        pm = postmortem_v3(inc, build_timeline([]), ranked)["postmortem"]
        assert pm["root_cause"]["status"] == "confirmed-candidate"
        assert "sign-off" in pm["root_cause"]["note"]


class TestCli:

    def test_live_incident_verb(self, tmp_path, capsys):
        import json

        from platformforge.cli.main import main
        inc = tmp_path / "inc.json"
        ch = tmp_path / "changes.json"
        inc.write_text(json.dumps(_inc()))
        ch.write_text(json.dumps([
            {"kind": "deploy", "timestamp": EARLIER, "action": "deploy",
             "resources": ["service/payments-api"], "tier": 1,
             "freshness": "fresh"}]))
        code = main(["live", "incident", "--repo", str(tmp_path),
                     "--incident", str(inc), "--changes", str(ch)])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["ranked"][0]["status"] == "candidate"
        assert out["postmortem"]["root_cause"]["status"] == "unresolved"

    def test_live_incident_requires_incident(self, tmp_path, capsys):
        from platformforge.cli.main import main
        code = main(["live", "incident", "--repo", str(tmp_path)])
        out = __import__("json").loads(capsys.readouterr().out)
        assert code == 2 and out["refusal"] == "PF-LIVE-NO-INCIDENT"
