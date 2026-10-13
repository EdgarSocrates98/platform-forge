"""Phase M — security property tests for the live boundary (§266).

Property-style: sweep representative hostile inputs through projection
and persistence; secrets must never reach stored artifacts, envelopes,
or MCP output.
"""

from __future__ import annotations

import json

from platformforge.live.collectors.aws import to_object
from platformforge.live.collectors.k8s import project_object
from platformforge.live.envelope import dumps
from platformforge.live.fixtures import collect_fixture
from platformforge.live.models import ObservationEnvelope, ObservationScope

SECRET_TOKENS = ("c3VwZXJzZWNyZXQ=", "supersecret",
                 "AKIAIOSFODNN7EXAMPLE", "-----BEGIN PRIVATE KEY-----",
                 "xoxb-", "ghp_")


def _secret_k8s() -> dict:
    return {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {"namespace": "prod", "name": "db",
                     "uid": "u1",
                     "annotations": {"auth.token": "supersecret"}},
        "data": {"password": "c3VwZXJzZWNyZXQ="},
        "stringData": {"key": "supersecret"}}


class TestSecretBlanking:

    def test_secret_object_never_leaks_payload(self):
        obj = project_object(_secret_k8s())
        blob = json.dumps(obj.to_dict())
        for tok in ("c3VwZXJzZWNyZXQ=", "supersecret"):
            assert tok not in blob
        assert obj.attributes["secret_payload_blank"] is True

    def test_sensitive_annotations_stripped(self):
        blob = json.dumps(project_object(_secret_k8s()).to_dict())
        assert "auth.token" not in blob

    def test_secret_in_envelope_serialization(self):
        env = ObservationEnvelope.new(
            collector="k", version="v", provider="kubernetes",
            source_type="observed", scope={})
        env.objects.append(project_object(_secret_k8s()).to_dict())
        blob = dumps(env)
        for tok in ("c3VwZXJzZWNyZXQ=", "supersecret"):
            assert tok not in blob

    def test_aws_object_never_emits_credentials(self):
        item = {"Arn": "arn:aws:iam::1:user/x",
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "SecretAccessKey": "supersecret",
                "Tags": []}
        blob = json.dumps(to_object(
            "iam", "user", item, account="1", region="",
            id_field="Arn", observed_at="t").to_dict())
        for tok in ("AKIAIOSFODNN7EXAMPLE", "supersecret"):
            assert tok not in blob


class TestFixtureEndToEnd:

    def test_collected_secret_stays_redacted(self, tmp_path):
        fx = tmp_path / "fx"
        (fx / "kubectl").mkdir(parents=True)
        (fx / "kubectl" / "get_secrets.json").write_text(json.dumps({
            "kind": "List",
            "items": [_secret_k8s()]}))
        env = collect_fixture(
            "kubernetes", fx,
            scope=ObservationScope(provider="kubernetes",
                                   resource_types=["secrets"]))
        blob = json.dumps(env.to_dict())
        assert len(env.objects) == 1
        for tok in ("c3VwZXJzZWNyZXQ=", "supersecret"):
            assert tok not in blob


class TestTransportBoundaries:

    def test_k8s_transport_refuses_credential_flags(self):
        from platformforge.live.collectors.k8s_transport import kubectl
        for bad in (["get", "pods", "--token", "x"],
                    ["get", "secrets", "--password", "x"]):
            rc, _o, err = kubectl(bad)
            assert rc == 2 and "refused" in err

    def test_k8s_transport_refuses_mutating_verbs(self):
        from platformforge.live.collectors.k8s_transport import kubectl
        for bad in (["apply", "-f", "x.yaml"], ["delete", "pods", "a"],
                    ["exec", "x", "--", "ls"], ["edit", "deploy/x"],
                    ["drain", "node1"], ["create", "ns", "x"]):
            rc, _o, err = kubectl(bad)
            assert rc == 2 and "refused" in err

    def test_aws_transport_refuses_write_ops(self):
        from platformforge.live.collectors.aws_transport import aws_call
        for svc, op in (("s3", "put-object"), ("iam", "create-user"),
                        ("ec2", "terminate-instances"),
                        ("eks", "update-cluster-config")):
            rc, doc = aws_call(svc, op, {})
            assert rc == 2 and "refused" in str(doc)
