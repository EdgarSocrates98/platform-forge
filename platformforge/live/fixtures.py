"""Fixture transports — deterministic offline replay for collectors
(cycle §258 "collector fixtures").

A fixture dir mirrors the transport contract so collectors run their
real code path end-to-end with zero network:

    fixture/kubectl/
      get_deployments.json           # `kubectl get deployments …`
      get_deployments.cont.json      # continuation page (--continue)
      get_secrets.denied.txt         # rc=1 Forbidden stderr
      auth_can-i_get.txt             # "yes"/"no"
      config_current-context.txt     # "kind-lab"
    fixture/aws/
      sts_get-caller-identity.json
      ec2_describe-vpcs.json                 # any region
      ec2_describe-vpcs__us-east-1.json      # region-scoped wins
      iam_list-users.denied.txt              # rc=1 AccessDenied

Missing fixture → rc=2 "no fixture" (never silently empty).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def k8s_fixture_transport(fixture_dir: str | Path):
    """Replay kubectl responses from fixture_dir/kubectl/."""
    root = Path(fixture_dir) / "kubectl"
    calls: list[str] = []
    pages: dict[str, int] = {}

    _VALUE_FLAGS = {"-o", "--output", "-n", "--namespace",
                    "--context", "--chunk-size", "-l", "--selector",
                    "--continue", "--sort-by", "--field-selector"}

    def _slug(args: list[str]) -> str:
        words: list[str] = []
        skip_next = False
        for a in args:
            if skip_next:
                skip_next = False
                continue
            if a in _VALUE_FLAGS:
                skip_next = True
                continue
            if a.startswith("-"):
                continue
            words.append(a)
        if "auth" in words and "can-i" in words:
            verb = words[words.index("can-i") + 1] \
                if len(words) > words.index("can-i") + 1 else ""
            return f"auth_can-i_{verb}"
        if "config" in words:
            sub = words[words.index("config") + 1] \
                if len(words) > words.index("config") + 1 else ""
            return f"config_{sub}"
        if words and words[0] == "version":
            return "version"
        if words and words[0] == "get" and len(words) > 1:
            return f"get_{words[1]}"
        return "_".join(words) or "empty"

    def transport(args: list[str]) -> tuple[int, str, str]:
        slug = _slug(args)
        calls.append(slug)
        n = pages.get(slug, 0)
        pages[slug] = n + 1
        base = root / f"{slug}.cont{n}.json" if n else root / slug
        denied = root / f"{slug}.denied.txt"
        if denied.exists():
            return 1, "", denied.read_text().strip()
        cand = [base.with_suffix(".json")] if base.suffix != ".json" \
            else [base]
        cand += [root / f"{slug}.cont{n}.json",
                 root / f"{slug}.json",
                 root / f"{slug}.txt"]
        for f in cand:
            if f.exists():
                return 0, f.read_text(), ""
        return 2, "", f"no fixture for kubectl {slug}"

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def aws_fixture_transport(fixture_dir: str | Path):
    """Replay aws CLI responses from fixture_dir/aws/."""
    root = Path(fixture_dir) / "aws"
    calls: list[str] = []

    def transport(service: str, operation: str,
                  params: dict | None = None) -> tuple[int, Any]:
        region = (params or {}).get("region", "")
        calls.append(f"{service}.{operation}@{region}")
        for slug in ([f"{service}_{operation}__{region}"] if region
                     else []) + [f"{service}_{operation}"]:
            denied = root / f"{slug}.denied.txt"
            if denied.exists():
                return 1, denied.read_text().strip()
            f = root / f"{slug}.json"
            if f.exists():
                return 0, json.loads(f.read_text())
        return 2, {"error": f"no fixture for {service} {operation}"}

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def collect_fixture(provider: str, fixture_dir: str | Path,
                    **collector_kw) -> Any:
    """Run the real collector over a fixture dir → ObservationEnvelope."""
    from platformforge.live.models import ObservationScope
    scope = collector_kw.pop("scope", None) or ObservationScope(
        provider=provider)
    if provider == "kubernetes":
        from platformforge.live.collectors.k8s import K8sCollector
        return K8sCollector(
            transport=k8s_fixture_transport(fixture_dir),
            **collector_kw).collect(scope)
    if provider == "aws":
        from platformforge.live.collectors.aws import AwsCollector
        c = AwsCollector(transport=aws_fixture_transport(fixture_dir),
                         **collector_kw)
        c.preflight()
        return c.collect(scope)
    raise ValueError(f"unknown fixture provider {provider}")


def fixture_facts(provider: str, fixture_dir: str | Path) -> dict[str, Any]:
    """Lab-analyzer shape: run the collector over fixtures → facts.

    Emits one `live.observation` fact per envelope plus one
    `live.object` fact per observed resource — rule-evaluable and
    honest about coverage (envelope attrs carry the coverage dict)."""
    from platformforge.models.base import stable_id
    env = collect_fixture(provider, fixture_dir)
    facts = [{
        "fact_id": stable_id("PF-LIVE", env.observation_id),
        "kind": "live.observation", "source": f"fixture:{provider}",
        "location": str(fixture_dir), "tier": 0,
        "attrs": {"observation_id": env.observation_id,
                  "provider": env.provider,
                  "coverage": env.coverage,
                  "objects": len(env.objects),
                  "errors": env.errors}}]
    for o in env.objects:
        facts.append({
            "fact_id": stable_id("PF-LIVE", env.observation_id,
                                 o.get("resource_id", "?")),
            "kind": "live.object", "source": f"fixture:{provider}",
            "location": o.get("resource_id", ""),
            "tier": 0,
            "attrs": {k: o.get(k) for k in
                      ("resource_id", "resource_type", "lifecycle",
                       "namespace", "cluster", "account", "region")
                      if o.get(k)}})
    return {"facts": facts, "envelope": env.to_dict()}


def collect_fixture_k8s(fixture_dir: str | Path) -> dict[str, Any]:
    return fixture_facts("kubernetes", fixture_dir)


def collect_fixture_aws(fixture_dir: str | Path) -> dict[str, Any]:
    return fixture_facts("aws", fixture_dir)
