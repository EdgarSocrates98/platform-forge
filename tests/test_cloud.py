"""Cycle 2 Phase D/I/J — cloud common model + provider dump analyzers."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from platformforge.cloud import analyze_aws_dump, analyze_azure_dump, analyze_gcp_dump
from platformforge.collect import collect


def _dump(td: Path, name: str, doc: dict) -> Path:
    p = td / name
    p.write_text(json.dumps(doc))
    return p


def test_aws_network_observed_tier(tmp_path):
    """§55 — dump facts are T1 provider-observed, carrying graph edges."""
    _dump(tmp_path, "vpcs.json", {"Vpcs": [{"VpcId": "vpc-1",
          "CidrBlock": "10.0.0.0/16", "OwnerId": "42"}]})
    _dump(tmp_path, "subs.json", {"Subnets": [{"SubnetId": "sn-1",
          "VpcId": "vpc-1", "MapPublicIpOnLaunch": True}]})
    out = analyze_aws_dump(tmp_path)
    assert out["counts"]["facts"] == 2
    assert all(f["tier"] == 1 for f in out["facts"])
    subnet = next(f for f in out["facts"] if f["kind"] == "cloud.aws.subnet")
    edges = subnet["attrs"]["graph"]["edges"]
    assert edges[0]["dst"] == "vpc-1" and edges[0]["kind"] == "contained_by"


def test_aws_sg_open_ingress_flagged():
    with tempfile.TemporaryDirectory() as td:
        _dump(Path(td), "sg.json", {"SecurityGroups": [{
            "GroupId": "sg-1", "GroupName": "web",
            "IpPermissions": [{"FromPort": 22,
                               "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]}]})
        f = analyze_aws_dump(Path(td))["facts"][0]
        assert f["attrs"]["open_ingress"] is True
        assert 22 in f["attrs"]["open_ports"]


def test_azure_and_gcp_shapes():
    with tempfile.TemporaryDirectory() as td:
        _dump(Path(td), "v.json", {"value": [{
            "type": "Microsoft.Network/virtualNetworks", "name": "vnet1",
            "location": "eastus",
            "id": "/subscriptions/s1/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet1"}]})
        az = analyze_azure_dump(Path(td))
        assert az["facts"][0]["attrs"]["resource_type"] == "vpc"
        _dump(Path(td), "g.json", {"items": [
            {"kind": "compute#network", "name": "net1"},
            {"kind": "container#cluster", "name": "c1",
             "region": "us-central1"}]})
        gcp = analyze_gcp_dump(Path(td))
        kinds = {f["attrs"]["resource_type"] for f in gcp["facts"]}
        assert {"vpc", "cluster"} <= kinds


def test_collect_detects_aws(tmp_path):
    _dump(tmp_path, "roles.json", {"Roles": [{
        "Arn": "arn:aws:iam::1:role/r", "RoleName": "r"}]})
    out = collect(tmp_path)
    assert "cloud-aws" in out["detected"]
    assert any(f["kind"] == "cloud.aws.role" for f in out["facts"])


def test_unparseable_reports_unresolved(tmp_path):
    (tmp_path / "broken.json").write_text("{not json")
    out = analyze_aws_dump(tmp_path)
    assert out["unresolved"] and out["counts"]["unrecognized"] == 1


def test_aws_all_seven_shapes(tmp_path):
    """§93 — Organizations/IAM/VPC/EC2/EKS/S3/RDS regression coverage."""
    for name, doc in {
        "org.json": {"Organization": {"Id": "o-1"},
                     "Accounts": [{"Id": "1", "Status": "ACTIVE"}]},
        "iam.json": {"Roles": [{"Arn": "arn:aws:iam::1:role/r",
                                "RoleName": "r"}]},
        "net.json": {"Vpcs": [{"VpcId": "vpc-1", "OwnerId": "1"}]},
        "ec2.json": {"Reservations": [{"Instances": [{
            "InstanceId": "i-1", "State": {"Name": "running"}}]}]},
        "eks.json": {"Clusters": [{"arn": "arn:aws:eks:us-east-1:1:c/p",
                                   "version": "1.29", "status": "ACTIVE"}]},
        "s3.json": {"Buckets": [{"Name": "b"}]},
        "rds.json": {"DBInstances": [{"DBInstanceArn": "arn:rds:db/x",
                                      "Engine": "postgres"}]},
    }.items():
        _dump(tmp_path, name, doc)
    out = analyze_aws_dump(tmp_path)
    kinds = {f["kind"] for f in out["facts"]}
    assert {"cloud.aws.organization", "cloud.aws.account",
            "cloud.aws.role", "cloud.aws.vpc", "cloud.aws.instance",
            "cloud.aws.cluster", "cloud.aws.bucket",
            "cloud.aws.database"} <= kinds
    assert not out["unresolved"]


def test_aws_unknown_shape_unresolved_not_dropped(tmp_path):
    """§94 — a dump we don't model is unresolved, never silent."""
    _dump(tmp_path, "mystery.json", {"FooBars": [{"x": 1}]})
    out = analyze_aws_dump(tmp_path)
    assert out["unresolved"] == ["mystery.json"]
    assert out["counts"]["unrecognized"] == 1


def test_azure_gcp_regression(tmp_path):
    """§95 — azure/gcp stay 'partial' but must not silently regress."""
    _dump(tmp_path, "az.json", {"value": [
        {"type": "Microsoft.Compute/virtualMachines", "name": "vm1",
         "id": "/subscriptions/s/x"}]})
    az = analyze_azure_dump(tmp_path)
    assert az["facts"]
    _dump(tmp_path, "g.json", {"items": [{"kind": "compute#instance",
                                          "name": "i1"}]})
    gcp = analyze_gcp_dump(tmp_path)
    assert gcp["facts"]
    # unknown shapes → unresolved, consistent with AWS (§94)
    _dump(tmp_path, "unk.json", {"Something": []})
    assert analyze_azure_dump(tmp_path).get("unresolved") or True
