"""AWS dump analyzers (§50–§55) — offline, reads CLI/Config exports only.

Accepted shapes (any file or dir):
  organizations list-accounts / describe-organization
  iam list-roles | list-policies | get-policy | list-users
  ec2 describe-vpcs | describe-subnets | describe-route-tables |
      describe-nat-gateways | describe-internet-gateways | describe-instances |
      describe-security-groups | describe-load-balancers (ELBv2)
  route53 list-hosted-zones
  eks/ecs describe-cluster | list-clusters
  lambda list-functions
  s3 list-buckets | get-bucket-policy-status dumps
  rds describe-db-instances | dynamodb list/describe | sqs/sns list
  config select-resource-config / snapshot exports (generic)

Everything emits EvidenceTier.PROVIDER_OBSERVED facts (§55). Live calls are
host-side — this module never imports boto3 or hits an endpoint.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from platformforge.cloud.common import resource_fact


def _org(doc: dict[str, Any], src: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    org = doc.get("Organization", {})
    org_id = org.get("Id") or doc.get("OrganizationId") or "org"
    if org:
        facts.append(resource_fact(
            "aws", "organization", org_id, source=src,
            attrs={"arn": org.get("Arn"), "master": org.get("MasterAccountId")}))
    for a in doc.get("Accounts", []):
        facts.append(resource_fact(
            "aws", "account", a["Id"], source=src,
            attrs={"name": a.get("Name"), "email_hash": bool(a.get("Email")),
                   "status": a.get("Status")},
            edges=[{"src_kind": "cloud_account", "src": a["Id"],
                    "dst_kind": "organization", "dst": org_id,
                    "kind": "contained_by"}]))
    for ou in doc.get("OrganizationalUnits", []):
        facts.append(resource_fact(
            "aws", "account", ou["Id"], source=src,  # OU modeled as account-scope
            attrs={"name": ou.get("Name"), "ou": True}))
    return facts


def _iam(doc: dict[str, Any], src: str) -> list[dict[str, Any]]:
    facts = []
    for r in doc.get("Roles", []):
        facts.append(resource_fact(
            "aws", "role", r["Arn"], source=src,
            attrs={"name": r.get("RoleName"),
                   "trust": sorted(
                       p.get("Service", p.get("AWS", "?"))
                       for p in (r.get("AssumeRolePolicyDocument") or {})
                       .get("Statement", [])
                       for p in [p.get("Principal", {})])}))
    for p in doc.get("Policies", []):
        facts.append(resource_fact(
            "aws", "policy", p["Arn"], source=src,
            attrs={"name": p.get("PolicyName"),
                   "attachment_count": p.get("AttachmentCount"),
                   "is_aws_managed": bool((p.get("Arn") or "")
                                          .startswith("arn:aws:iam::aws:"))}))
    for u in doc.get("Users", []):
        facts.append(resource_fact(
            "aws", "principal", u["Arn"], source=src,
            attrs={"name": u.get("UserName"),
                   "has_mfa": bool(u.get("Mfa")),
                   "password_last_used": bool(u.get("PasswordLastUsed"))}))
    # get-policy-version doc → policy graph contribution with statement analysis
    pv = doc.get("PolicyVersion") or {}
    if pv.get("Document"):
        arn = doc.get("Policy", {}).get("Arn", "policy:unknown")
        stmts = pv["Document"].get("Statement", [])
        wild = any(
            ("*" in str(s.get("Action")) or "*" in str(s.get("Resource")))
            and str(s.get("Effect")) == "Allow" for s in stmts)
        facts.append(resource_fact(
            "aws", "policy", arn, source=src,
            attrs={"wildcard": wild, "statements": len(stmts)}))
    return facts


def _network(doc: dict[str, Any], src: str) -> list[dict[str, Any]]:
    facts = []
    for v in doc.get("Vpcs", []):
        facts.append(resource_fact(
            "aws", "vpc", v["VpcId"], source=src, account=v.get("OwnerId", ""),
            attrs={"cidr": v.get("CidrBlock"), "is_default": v.get("IsDefault")}))
    for s in doc.get("Subnets", []):
        facts.append(resource_fact(
            "aws", "subnet", s["SubnetId"], source=src,
            attrs={"cidr": s.get("CidrBlock"), "az": s.get("AvailabilityZone"),
                   "public_ip_on_launch": s.get("MapPublicIpOnLaunch")},
            edges=[{"src_kind": "subnet", "src": s["SubnetId"],
                    "dst_kind": "vpc_vnet", "dst": s.get("VpcId", "?"),
                    "kind": "contained_by"}]))
    for ig in doc.get("InternetGateways", []):
        for att in ig.get("Attachments", []):
            facts.append(resource_fact(
                "aws", "internet_gateway", ig["InternetGatewayId"], source=src,
                edges=[{"src_kind": "gateway", "src": ig["InternetGatewayId"],
                        "dst_kind": "vpc_vnet", "dst": att.get("VpcId", "?"),
                        "kind": "routes_to"}]))
    for n in doc.get("NatGateways", []):
        facts.append(resource_fact(
            "aws", "nat_gateway", n["NatGatewayId"], source=src,
            attrs={"state": n.get("State")},
            edges=[{"src_kind": "nat", "src": n["NatGatewayId"],
                    "dst_kind": "subnet", "dst": n.get("SubnetId", "?"),
                    "kind": "contained_by"}]))
    for rt in doc.get("RouteTables", []):
        routes = rt.get("Routes", [])
        public = any(r.get("GatewayId", "").startswith("igw-")
                     for r in routes)
        for assoc in rt.get("Associations", []):
            sid = assoc.get("SubnetId")
            if sid:
                facts.append(resource_fact(
                    "aws", "route_table", rt["RouteTableId"], source=src,
                    attrs={"public_route": public},
                    edges=[{"src_kind": "route", "src": rt["RouteTableId"],
                            "dst_kind": "subnet", "dst": sid,
                            "kind": "routes_to"}]))
    for sg in doc.get("SecurityGroups", []):
        open_ingress = [p for p in sg.get("IpPermissions", [])
                        if any(r.get("CidrIp") == "0.0.0.0/0"
                               for r in p.get("IpRanges", []))]
        facts.append(resource_fact(
            "aws", "policy", sg["GroupId"], source=src,  # sg as policy node
            attrs={"sg": True, "name": sg.get("GroupName"),
                   "open_ingress": bool(open_ingress),
                   "open_ports": sorted({p.get("FromPort", 0)
                                         for p in open_ingress})}))
    for lb in doc.get("LoadBalancers", []):
        facts.append(resource_fact(
            "aws", "load_balancer", lb["LoadBalancerArn"], source=src,
            attrs={"scheme": lb.get("Scheme"), "type": lb.get("Type"),
                   "public": lb.get("Scheme") == "internet-facing"},
            edges=[{"src_kind": "load_balancer", "src": lb["LoadBalancerArn"],
                    "dst_kind": "vpc_vnet", "dst": lb.get("VpcId", "?"),
                    "kind": "routes_to"}]))
    for z in doc.get("HostedZones", []):
        facts.append(resource_fact(
            "aws", "dns_zone", z["Id"], source=src,
            attrs={"name": z.get("Name"), "private": z.get("Config", {})
                   .get("PrivateZone")}))
    return facts


def _compute(doc: dict[str, Any], src: str) -> list[dict[str, Any]]:
    facts = []
    for res in doc.get("Reservations", []):
        for i in res.get("Instances", []):
            public = bool(i.get("PublicIpAddress"))
            facts.append(resource_fact(
                "aws", "instance", i["InstanceId"], source=src,
                attrs={"type": i.get("InstanceType"),
                       "state": i.get("State", {}).get("Name"),
                       "public_ip": public,
                       "subnet": i.get("SubnetId")},
                edges=[{"src_kind": "node", "src": i["InstanceId"],
                        "dst_kind": "subnet",
                        "dst": i.get("SubnetId", "?"),
                        "kind": "contained_by"}] if i.get("SubnetId") else []))
    for fn in doc.get("Functions", []):
        facts.append(resource_fact(
            "aws", "function", fn["FunctionArn"], source=src,
            attrs={"runtime": fn.get("Runtime"), "name": fn.get("FunctionName")}))
    for c in doc.get("Clusters", []):
        name = c.get("clusterName") or c.get("name") or c.get("clusterArn")
        eks = "version" in c or c.get("arn", "").startswith("arn:aws:eks")
        facts.append(resource_fact(
            "aws", "cluster", c.get("arn") or c.get("clusterArn") or name,
            source=src,
            attrs={"name": name, "engine": "eks" if eks else "ecs",
                   "version": c.get("version"), "status": c.get("status")}))
    return facts


def _storage(doc: dict[str, Any], src: str) -> list[dict[str, Any]]:
    facts = []
    for b in doc.get("Buckets", []):
        facts.append(resource_fact("aws", "bucket", b["Name"], source=src))
    for db in doc.get("DBInstances", []):
        facts.append(resource_fact(
            "aws", "database", db["DBInstanceArn"], source=src,
            attrs={"engine": db.get("Engine"), "public": db.get("PubliclyAccessible"),
                   "encrypted": db.get("StorageEncrypted"),
                   "multi_az": db.get("MultiAZ")}))
    for q in doc.get("QueueUrls", doc.get("Queues", [])):
        name = q if isinstance(q, str) else q.get("QueueUrl") or q.get("QueueArn")
        facts.append(resource_fact("aws", "queue", str(name), source=src))
    for t in doc.get("Topics", []):
        facts.append(resource_fact(
            "aws", "topic", t.get("TopicArn", t), source=src))
    for tbl in doc.get("Tables", doc.get("TableNames", [])):
        name = tbl if isinstance(tbl, str) else tbl.get("TableArn") or tbl.get("TableName")
        facts.append(resource_fact("aws", "database", str(name), source=src,
                                   attrs={"engine": "dynamodb"}))
    return facts


_SHAPE_MAP: list[tuple[tuple[str, ...], Callable]] = [
    (("Organization", "Accounts", "OrganizationalUnits"), _org),
    (("Roles", "Policies", "Users", "PolicyVersion"), _iam),
    (("Vpcs", "Subnets", "InternetGateways", "NatGateways", "RouteTables",
      "SecurityGroups", "LoadBalancers", "HostedZones"), _network),
    (("Reservations", "Functions", "Clusters"), _compute),
    (("Buckets", "DBInstances", "QueueUrls", "Queues", "Topics", "Tables",
      "TableNames"), _storage),
]


def detect_shape(doc: dict[str, Any]) -> str | None:
    keys = set(doc)
    for shape_keys, _ in _SHAPE_MAP:
        if keys & set(shape_keys):
            return shape_keys[0]
    return None


def analyze_aws_dump(path: str | Path) -> dict[str, Any]:
    """Analyze one AWS CLI/Config dump or a dir of dumps → T1 facts."""
    p = Path(path)
    files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
    facts: list[dict[str, Any]] = []
    unrecognized: list[str] = []
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError) as e:
            unrecognized.append(f"{f.name}: unparseable ({e})")
            continue
        if not isinstance(doc, dict):
            unrecognized.append(f"{f.name}: not a JSON object")
            continue
        matched = False
        for shape_keys, fn in _SHAPE_MAP:
            if set(doc) & set(shape_keys):
                facts.extend(fn(doc, str(f)))
                matched = True
        if not matched:
            unrecognized.append(f.name)
    return {"facts": facts, "unresolved": unrecognized,
            "counts": {"facts": len(facts), "unrecognized": len(unrecognized)},
            "provenance": "provider-observed-dump"}
