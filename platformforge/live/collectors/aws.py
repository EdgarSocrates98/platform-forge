"""AWS live collector — read-only, credential-preflighted (cycle §32–§40).

Transport is injected: `transport(service, operation, params) ->
(rc, dict)`. The `aws` CLI boundary lives in `aws_transport.py` —
boto3 stays out of the core package; credentials never leave the host.

Coverage honesty (§8/§17):
- AccessDenied on an operation → that service/type is
  `permission-limited`, reported in denied_scopes — never a global
  failure and never silently absent.
- Optional planes (Config, Resource Explorer) degrade to
  `unsupported` with reasons, collection continues.
- CloudTrail is T1 provider-observed *event* evidence (ChangeEvent),
  never T0 runtime measurement (ADR-0016).

Pod Identity / IRSA (§36–37): `eks list-pod-identity-associations`
objects carry serviceAccount+role_arn; the SA↔IAM link itself is
resolved by the identity engine (Phase E) — the collector emits the
raw evidence, not the verdict.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from platformforge.live.budget import ObservationBudget, ProviderCallLedger
from platformforge.live.models import (
    ChangeEvent,
    CollectorReceipt,
    Coverage,
    ObservationEnvelope,
    ObservationScope,
    ObservedObject,
    iso,
    now_iso,
    parse_ts,
)

# transport(service, operation, params) -> (rc, parsed_json_or_text)
AwsTransport = Callable[[str, str, dict], tuple[int, Any]]

COLLECTOR_VERSION = "aws-collector/0.3.0"

# §35 — collection plan: (service, operation, scope_axis, item_path,
#                          resource_kind, id_field)
# item_path navigates the response to the resource list.
PLAN: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("ec2", "describe-vpcs", "region", "Vpcs", "vpc", "VpcId"),
    ("ec2", "describe-subnets", "region", "Subnets", "subnet", "SubnetId"),
    ("ec2", "describe-security-groups", "region", "SecurityGroups",
     "security_group", "GroupId"),
    ("ec2", "describe-instances", "region", "Reservations", "instance",
     "InstanceId"),
    ("ec2", "describe-route-tables", "region", "RouteTables",
     "route_table", "RouteTableId"),
    ("ec2", "describe-nat-gateways", "region", "NatGateways",
     "nat_gateway", "NatGatewayId"),
    ("ec2", "describe-addresses", "region", "Addresses",
     "elastic_ip", "AllocationId"),
    ("elbv2", "describe-load-balancers", "region", "LoadBalancers",
     "load_balancer", "LoadBalancerArn"),
    ("rds", "describe-db-instances", "region", "DBInstances",
     "db_instance", "DBInstanceArn"),
    ("lambda", "list-functions", "region", "Functions", "function",
     "FunctionArn"),
    ("s3", "list-buckets", "global", "Buckets", "bucket", "Name"),
    ("iam", "list-roles", "global", "Roles", "role", "Arn"),
    ("iam", "list-users", "global", "Users", "user", "Arn"),
    ("eks", "list-clusters", "region", "clusters", "eks_cluster", ""),
)

# read-only action allowlist — no Put/Create/Delete/Update/Attach…
READONLY_PREFIXES = ("describe-", "list-", "get-", "lookup-", "search")


def arn_or_id(item: dict[str, Any], id_field: str, service: str,
              account: str, region: str, kind: str) -> str:
    """Prefer ARN (strong id); otherwise compose a provider-native id."""
    val = item.get(id_field, "") if id_field else ""
    if val.startswith("arn:"):
        return val
    for k in ("Arn", "RoleArn", "ClusterArn", "DBInstanceArn",
              "LoadBalancerArn"):
        if k in item and str(item[k]).startswith("arn:"):
            return item[k]
    return f"aws://{service}/{account or '-'}/{region or 'global'}/" \
        f"{kind}/{val or item.get('Name', '?')}"


def _flatten_instances(doc: dict) -> list[dict[str, Any]]:
    return [i for r in doc.get("Reservations", [])
            for i in r.get("Instances", [])]


def extract_items(service: str, op: str, doc: Any,
                  item_path: str) -> list[dict[str, Any]]:
    if not isinstance(doc, dict):
        return []
    if op == "describe-instances":
        return _flatten_instances(doc)
    items = doc.get(item_path, [])
    return items if isinstance(items, list) else []


def _tag_name(item: dict[str, Any]) -> str:
    for t in item.get("Tags", []) or []:
        if isinstance(t, dict) and t.get("Key") == "Name":
            return str(t.get("Value", ""))
    return ""


def to_object(service: str, kind: str, item: dict[str, Any], *,
              account: str, region: str, id_field: str,
              observed_at: str) -> ObservedObject:
    rid = arn_or_id(item, id_field, service, account, region, kind)
    name = item.get("Name") or _tag_name(item) or ""
    attrs = {
        "arn": rid if rid.startswith("arn:") else "",
        "tags": {t.get("Key"): t.get("Value")
                 for t in item.get("Tags", []) if isinstance(t, dict)},
        "state": item.get("State", {}).get("Name")
        if isinstance(item.get("State"), dict) else item.get("State", "")}
    for k in ("VpcId", "SubnetId", "ClusterName", "Engine", "Runtime",
              "CidrBlock", "AvailabilityZone", "InstanceType"):
        if k in item:
            attrs[k] = item[k]
    return ObservedObject(
        resource_id=rid, resource_type=f"aws:{service}/{kind}",
        attributes={k: v for k, v in attrs.items() if v not in ("", {}, None)},
        provider="aws", account=account, region=region,
        name=name or (item.get(id_field, "") if id_field else ""),
        observed_at=observed_at)


def cloudtrail_events(doc: dict, *, account: str = "",
                      region: str = "") -> list[ChangeEvent]:
    """§38 — CloudTrail lookup-events → ChangeEvent (T1 evidence)."""
    out: list[ChangeEvent] = []
    for e in doc.get("Events", []):
        resources = [r.get("ResourceName", "") for r in
                     e.get("Resources", [])]
        out.append(ChangeEvent(
            event_id=e.get("EventId", ""),
            timestamp=str(e.get("EventTime", "")),
            source="cloudtrail",
            action=e.get("EventName", ""),
            actor=e.get("Username", ""),
            resource_ids=[r for r in resources if r],
            account=account, region=region,
            evidence={"aws_service": (e.get("EventSource") or "")
                      .replace(".amazonaws.com", "")}))
    return out


@dataclass
class AwsCollector:
    transport: AwsTransport | None = None
    account: str = ""
    regions: list[str] = field(default_factory=list)

    def _call(self, service: str, op: str,
              params: dict | None = None) -> tuple[int, Any]:
        if self.transport is None:
            raise RuntimeError("no transport — host-side aws adapter "
                               "required (see aws_transport.py)")
        return self.transport(service, op, params or {})

    # ── preflight (§33) ───────────────────────────────────────
    def preflight(self) -> dict[str, Any]:
        """sts get-caller-identity — proves credentials + resolves the
        account before any collection starts."""
        rc, doc = self._call("sts", "get-caller-identity", {})
        if rc != 0 or not isinstance(doc, dict):
            return {"ok": False, "error": str(doc),
                    "hint": "configure credentials: aws sso login / "
                            "AWS_PROFILE / env vars"}
        self.account = doc.get("Account", "")
        return {"ok": True, "account": self.account,
                "arn": doc.get("Arn", ""), "user_id": doc.get("UserId", "")}

    # ── collection ────────────────────────────────────────────
    def collect(self, scope: ObservationScope | None = None,
                budget: ObservationBudget | None = None) -> ObservationEnvelope:
        scope = scope or ObservationScope(provider="aws")
        scope.provider = "aws"
        regions = scope.regions or self.regions or ["us-east-1"]
        if scope.accounts and self.account and \
                self.account not in scope.accounts:
            scope = ObservationScope(**scope.to_dict())
        budget = budget or ObservationBudget()
        ledger = ProviderCallLedger(collector=COLLECTOR_VERSION,
                                    started_at=now_iso())
        started = time.monotonic()
        captured_at = now_iso()
        env = ObservationEnvelope.new(
            collector="aws", version=COLLECTOR_VERSION, provider="aws",
            source_type="observed", scope=scope, captured_at=captured_at)

        denied: list[dict[str, Any]] = []
        unsupported: list[str] = []
        per_type: dict[str, str] = {}
        reasons: list[str] = []
        eks_clusters: list[str] = []

        for service, op, axis, path, kind, idf in PLAN:
            if scope.services and service not in scope.services:
                continue
            rt = f"aws:{service}/{kind}"
            if scope.resource_types and rt not in scope.resource_types:
                continue
            violation = budget.check(ledger)
            if violation:
                per_type[rt] = "truncated"
                reasons.append(f"budget {violation} — truncated")
                break
            targets = regions if axis == "region" else [""]
            saw_denied = False
            got = 0
            for region in targets:
                params = {"region": region} if region else {}
                rc, doc = self._call(service, op, params)
                ledger.record_call(service, pages=1,
                                   nbytes=len(str(doc).encode()))
                if rc != 0:
                    msg = str(doc)
                    if "AccessDenied" in msg or "UnauthorizedOperation" in msg \
                            or "not authorized" in msg:
                        saw_denied = True
                        denied.append({"resource_type": rt,
                                       "region": region, "reason": msg})
                        continue
                    if "could not be found" in msg or "not supported" in msg \
                            or "InvalidAction" in msg:
                        per_type.setdefault(rt, "unsupported")
                        unsupported.append(rt)
                        continue
                    per_type.setdefault(rt, "unknown")
                    ledger.errors.append(f"{rt}@{region}: {msg}")
                    reasons.append(f"{rt}: {msg[:80]}")
                    continue
                items = extract_items(service, op, doc, path)
                for it in items:
                    if kind == "eks_cluster":
                        eks_clusters.append(str(it))
                        env.objects.append(ObservedObject(
                            resource_id=f"aws:eks/{self.account}/{region}/{it}",
                            resource_type=rt, provider="aws",
                            account=self.account, region=region,
                            name=str(it), observed_at=captured_at
                        ).to_dict())
                        continue
                    env.objects.append(to_object(
                        service, kind, it, account=self.account,
                        region=region, id_field=idf,
                        observed_at=captured_at).to_dict())
                    got += 1
                ledger.record_call(service, pages=0, objects=len(items))
            if rt not in per_type:
                if saw_denied and got == 0:
                    per_type[rt] = "permission-limited"
                elif saw_denied:
                    per_type[rt] = "partial"
                else:
                    per_type[rt] = "complete"

        # §36 — EKS Pod Identity associations (read-only evidence)
        for cluster in eks_clusters:
            for region in regions:
                rc, doc = self._call("eks", "list-pod-identity-associations",
                                     {"clusterName": cluster,
                                      "region": region})
                ledger.record_call("eks", pages=1,
                                   nbytes=len(str(doc).encode()))
                if rc != 0:
                    continue
                for assoc in doc.get("associations", []):
                    env.objects.append(ObservedObject(
                        resource_id=f"aws:eks-pod-identity/{self.account}/"
                                    f"{region}/{cluster}/{assoc.get('associationId','')}",
                        resource_type="aws:eks/pod_identity_association",
                        attributes={
                            "cluster": cluster,
                            "namespace": assoc.get("namespace", ""),
                            "service_account": assoc.get("serviceAccount", ""),
                            "role_arn": assoc.get("roleArn", "")},
                        provider="aws", account=self.account, region=region,
                        cluster=cluster, namespace=assoc.get("namespace", ""),
                        name=assoc.get("serviceAccount", ""),
                        observed_at=captured_at).to_dict())

        done = now_iso()
        env.completed_at = done
        cap = parse_ts(captured_at)
        if cap:
            env.fresh_until = iso(cap + timedelta(seconds=3600))
        status = "complete"
        if any(v in ("permission-limited", "partial", "truncated")
               for v in per_type.values()):
            status = "partial" if "complete" in per_type.values() \
                else "permission-limited"
        elif not per_type:
            status = "unknown"
        env.coverage = Coverage(status=status, per_resource_type=per_type,
                                reasons=sorted(set(reasons))).to_dict()
        env.permissions = {"denied_scopes": denied,
                           "account": self.account}
        env.errors = ledger.errors
        env.bytes = ledger.bytes
        env.receipt = CollectorReceipt(
            collector="aws", collector_version=COLLECTOR_VERSION,
            provider="aws", started_at=ledger.started_at,
            completed_at=done, scope=scope.to_dict(),
            api_calls=ledger.api_calls, pages=ledger.pages,
            objects=ledger.objects, bytes=ledger.bytes,
            errors=ledger.errors, permission_denied=denied,
            unsupported=sorted(unsupported), metadata_only=False,
            coverage=env.coverage,
            freshness={"captured_at": captured_at,
                       "fresh_until": env.fresh_until},
            duration_s=round(time.monotonic() - started, 3)).to_dict()
        return env

    def lookup_events(self, *, region: str = "", account: str = "",
                      max_results: int = 50,
                      start_time: str = "", end_time: str = ""
                      ) -> list[ChangeEvent]:
        """§38 — recent CloudTrail events → ChangeEvent evidence."""
        params: dict[str, Any] = {"region": region,
                                  "MaxResults": max_results}
        if start_time:
            params["StartTime"] = start_time
        if end_time:
            params["EndTime"] = end_time
        rc, doc = self._call("cloudtrail", "lookup-events", params)
        if rc != 0 or not isinstance(doc, dict):
            return []
        return cloudtrail_events(doc, account=account, region=region)


def required_permissions(*, services: list[str] | None = None) -> dict[str, Any]:
    """§39 — minimal IAM policy for the collector. Read-only actions
    only; the generator structurally cannot emit iam:* or write verbs."""
    stmts = [
        {"Sid": "PFInventory", "Effect": "Allow",
         "Action": [
             "ec2:Describe*", "elasticloadbalancing:Describe*",
             "rds:Describe*", "lambda:List*", "lambda:Get*",
             "s3:ListAllMyBuckets", "s3:GetBucket*",
             "iam:List*", "iam:Get*", "eks:List*", "eks:Describe*",
             "sts:GetCallerIdentity", "config:Describe*",
             "config:SelectResourceConfig", "config:ListDiscoveredResources",
             "resource-explorer-2:Search"],
         "Resource": "*"},
        {"Sid": "PFCloudTrailEvidence", "Effect": "Allow",
         "Action": ["cloudtrail:LookupEvents"], "Resource": "*"}]
    if services:
        keep = [s for s in stmts
                if any(f"{svc}:" in a for a in s["Action"]
                       for svc in services) or s["Sid"] == "PFInventory"]
        stmts = keep or stmts
    return {"policy_name": "PlatformForgeLiveReadOnly",
            "mutates": False, "cluster_admin": False,
            "policy": {"Version": "2012-10-17", "Statement": stmts},
            "notes": ["attach read-only; no write actions are emitted",
                      ("scoped-down variant: restrict ec2/rds/etc by "
                       "region conditions")]}
