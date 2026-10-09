"""Phase D gates — AWS collector: sts preflight, per-type coverage,
AccessDenied→permission-limited, Pod Identity evidence, CloudTrail→T1
ChangeEvents, minimal-permission IAM generation, transport allowlist."""

import pytest

from platformforge.live.collectors import aws_transport
from platformforge.live.collectors.aws import AwsCollector, cloudtrail_events, required_permissions
from platformforge.live.models import ObservationScope


def fake_aws():
    calls = []

    def t(service, op, params):
        calls.append((service, op, params))
        if (service, op) == ("sts", "get-caller-identity"):
            return 0, {"Account": "111122223333",
                       "Arn": "arn:aws:sts::111122223333:assumed-role/x",
                       "UserId": "AIDAX"}
        if op == "describe-vpcs":
            return 0, {"Vpcs": [{"VpcId": "vpc-1",
                                 "CidrBlock": "10.0.0.0/16",
                                 "Tags": [{"Key": "Name", "Value": "main"}],
                                 "State": "available"}]}
        if op == "describe-security-groups":
            return 1, "AccessDenied: not authorized to perform "
            "ec2:DescribeSecurityGroups"
        if op == "list-clusters":
            return 0, {"clusters": ["prod-eks"]}
        if op == "list-pod-identity-associations":
            return 0, {"associations": [
                {"associationId": "a-1", "cluster": "prod-eks",
                 "namespace": "prod", "serviceAccount": "web-sa",
                 "roleArn": "arn:aws:iam::111122223333:role/web"}]}
        if op == "describe-eks-cluster" or op == "describe-cluster":
            return 0, {"cluster": {"name": "prod-eks"}}
        # everything else: empty list
        paths = {"describe-subnets": "Subnets",
                 "describe-instances": "Reservations",
                 "describe-route-tables": "RouteTables",
                 "describe-nat-gateways": "NatGateways",
                 "describe-addresses": "Addresses",
                 "describe-load-balancers": "LoadBalancers",
                 "describe-db-instances": "DBInstances",
                 "list-functions": "Functions", "list-buckets": "Buckets",
                 "list-roles": "Roles", "list-users": "Users"}
        return 0, {paths.get(op, "Items"): []}
    t.calls = calls
    return t


def test_preflight_resolves_account():
    c = AwsCollector(transport=fake_aws())
    out = c.preflight()
    assert out["ok"] and out["account"] == "111122223333"


def test_preflight_denied_is_honest():
    def bad(s, o, p):
        return 1, "Unable to locate credentials"
    c = AwsCollector(transport=bad)
    out = c.preflight()
    assert out["ok"] is False and "credentials" in out["hint"]


def test_collect_coverage_and_denied_scope():
    c = AwsCollector(transport=fake_aws())
    c.preflight()
    env = c.collect(ObservationScope(regions=["us-east-1"],
                                     services=["ec2"]))
    pt = env.coverage["per_resource_type"]
    assert pt["aws:ec2/vpc"] == "complete"
    assert pt["aws:ec2/security_group"] == "permission-limited"
    assert env.coverage["status"] == "partial"
    denied = env.receipt["permission_denied"]
    assert any(d["resource_type"] == "aws:ec2/security_group"
               for d in denied)
    vpcs = [o for o in env.objects if o["resource_type"] == "aws:ec2/vpc"]
    assert vpcs[0]["name"] == "main"
    assert "10.0.0.0/16" == vpcs[0]["attributes"]["CidrBlock"]


def test_collect_pod_identity_evidence():
    c = AwsCollector(transport=fake_aws())
    c.preflight()
    env = c.collect(ObservationScope(regions=["us-east-1"],
                                     services=["eks"]))
    pia = [o for o in env.objects
           if o["resource_type"] == "aws:eks/pod_identity_association"]
    assert pia and pia[0]["attributes"]["role_arn"].endswith(":role/web")
    assert pia[0]["attributes"]["service_account"] == "web-sa"


def test_cloudtrail_events_are_t1():
    doc = {"Events": [{"EventId": "e1", "EventName": "PutBucketPolicy",
                       "EventTime": "2025-01-01T00:00:00Z",
                       "Username": "alice",
                       "EventSource": "s3.amazonaws.com",
                       "Resources": [{"ResourceName": "bucket-x"}]}]}
    evs = cloudtrail_events(doc, account="1111")
    assert evs[0].source == "cloudtrail"
    assert evs[0].action == "PutBucketPolicy"
    assert evs[0].resource_ids == ["bucket-x"]
    assert evs[0].evidence["aws_service"] == "s3"


def test_required_permissions_readonly_only():
    out = required_permissions()
    actions = [a for s in out["policy"]["Statement"]
               for a in s["Action"]]
    assert out["cluster_admin"] is False and out["mutates"] is False
    assert not any(a.startswith(("iam:Create", "iam:Put", "iam:Attach",
                               "ec2:Create", "ec2:Delete", "*"))
                 for a in actions)
    assert "sts:GetCallerIdentity" in actions
    assert "cloudtrail:LookupEvents" in actions


def test_transport_allowlist_refuses_writes(monkeypatch):
    monkeypatch.setattr(aws_transport.shutil, "which", lambda x: "/bin/aws")
    rc, doc = aws_transport.aws_call("ec2", "create-vpc", {})
    assert rc == 2 and "refused" in doc["error"]
    rc, doc = aws_transport.aws_call("iam", "attach-role-policy", {})
    assert rc == 2


def test_budget_truncates_plan():
    c = AwsCollector(transport=fake_aws())
    c.preflight()
    from platformforge.live.budget import ObservationBudget
    env = c.collect(ObservationScope(regions=["us-east-1"]),
                    budget=ObservationBudget(max_api_calls=2))
    assert env.coverage["status"] in ("partial", "truncated")
    assert any("budget" in r for r in env.coverage["reasons"])


def test_no_transport_raises():
    with pytest.raises(RuntimeError, match="transport"):
        AwsCollector().collect(ObservationScope())


def test_lookup_events():
    c = AwsCollector(transport=fake_aws())
    c.preflight()
    assert c.lookup_events(region="us-east-1") == []  # empty doc path
    calls = [c for c in c.transport.calls
             if c[0] == "cloudtrail" and c[1] == "lookup-events"]
    assert calls and calls[0][2]["region"] == "us-east-1"
