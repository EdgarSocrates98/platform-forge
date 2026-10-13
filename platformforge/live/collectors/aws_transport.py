"""Host-side `aws` CLI transport — THE network boundary for aws live.

boto3 stays out of the core package by repo rule; the AWS CLI is the
user-authenticated host tool — credentials (env/SSO/profile/IRSA) never
enter platformforge. Read-only by construction: only known read
operations pass the allowlist.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

# operation → (cli_service, extra_argv). All are read APIs.
_ALLOWED: dict[str, dict[str, Any]] = {
    "sts.get-caller-identity": ["sts", "get-caller-identity"],
    "ec2.describe-vpcs": ["ec2", "describe-vpcs"],
    "ec2.describe-subnets": ["ec2", "describe-subnets"],
    "ec2.describe-security-groups": ["ec2", "describe-security-groups"],
    "ec2.describe-instances": ["ec2", "describe-instances"],
    "ec2.describe-route-tables": ["ec2", "describe-route-tables"],
    "ec2.describe-nat-gateways": ["ec2", "describe-nat-gateways"],
    "ec2.describe-addresses": ["ec2", "describe-addresses"],
    "elbv2.describe-load-balancers": ["elbv2", "describe-load-balancers"],
    "rds.describe-db-instances": ["rds", "describe-db-instances"],
    "lambda.list-functions": ["lambda", "list-functions"],
    "s3.list-buckets": ["s3api", "list-buckets"],
    "iam.list-roles": ["iam", "list-roles"],
    "iam.list-users": ["iam", "list-users"],
    "eks.list-clusters": ["eks", "list-clusters"],
    "eks.describe-cluster": ["eks", "describe-cluster"],
    "eks.list-pod-identity-associations":
        ["eks", "list-pod-identity-associations"],
    "cloudtrail.lookup-events": ["cloudtrail", "lookup-events"],
    "configservice.describe-configuration-recorders":
        ["configservice", "describe-configuration-recorders"],
    "configservice.select-resource-config":
        ["configservice", "select-resource-config"],
    "resource-explorer-2.search": ["resource-explorer-2", "search"],
}

_PARAM_FLAGS = {"region": "--region", "clusterName": "--cluster-name",
                "MaxResults": "--max-results",
                "StartTime": "--start-time", "EndTime": "--end-time",
                "Expression": "--expression",
                "ViewArn": "--view-arn", "QueryString": "--query-string"}


def aws_available() -> bool:
    return shutil.which("aws") is not None


def aws_call(service: str, operation: str,
             params: dict | None = None) -> tuple[int, Any]:
    """Run `aws <svc> <op>` for an allowlisted read operation."""
    key = f"{service}.{operation}"
    argv = _ALLOWED.get(key)
    if argv is None:
        return 2, {"error": f"refused: {key} not in read-only allowlist"}
    args = [*argv, "--output", "json"]
    for k, v in (params or {}).items():
        flag = _PARAM_FLAGS.get(k)
        if flag and v not in ("", None):
            args += [flag, str(v)]
    try:
        r = subprocess.run(["aws", *args], capture_output=True,
                           text=True, timeout=120, check=False)
    except FileNotFoundError:
        return 127, {"error": "aws CLI not on PATH"}
    except subprocess.TimeoutExpired:
        return 124, {"error": "aws CLI timed out"}
    if r.returncode != 0:
        return r.returncode, r.stderr.strip()
    try:
        return 0, json.loads(r.stdout)
    except json.JSONDecodeError:
        return 0, {"raw": r.stdout}


def make_transport() -> Any:
    return aws_call


def preflight() -> dict[str, Any]:
    """`live doctor` probe — never inventories."""
    if not aws_available():
        return {"ok": False, "aws_cli": False,
                "error": "aws CLI not on PATH"}
    rc, doc = aws_call("sts", "get-caller-identity", {})
    if rc != 0:
        return {"ok": False, "aws_cli": True,
                "error": str(doc)[:200],
                "hint": "aws sso login / AWS_PROFILE / env creds"}
    return {"ok": True, "aws_cli": True,
            "account": doc.get("Account", ""),
            "arn": doc.get("Arn", "")}
