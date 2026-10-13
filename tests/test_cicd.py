"""Phase 7 gate: GitOps (ArgoCD/Flux) + GitHub Actions analysis."""

from platformforge.cicd import analyze_gha, analyze_gitops
from platformforge.models import Fact
from platformforge.rules import RuleEngine, load_catalog

ARGO = """
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payments
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/acme/platform-manifests.git
    path: apps/payments
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated:
      prune: false
      selfHeal: false
"""

FLUX = """
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: platform
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/acme/platform
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 5m
  path: ./apps
  prune: true
  sourceRef: {kind: GitRepository, name: platform}
"""

GHA = """
name: deploy
on:
  pull_request_target:
permissions: write-all
jobs:
  build:
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v4
      - uses: evilcorp/deploy@main
      - run: echo "${{ github.event.pull_request.title }}"
"""


def test_argocd(tmp_path):
    (tmp_path / "app.yaml").write_text(ARGO)
    doc = analyze_gitops(tmp_path)
    f = doc["facts"][0]
    assert f["kind"] == "gitops.argocd_app"
    a = f["attrs"]
    assert a["automated_sync"] is True and a["prune"] is False
    assert a["self_heal"] is False
    assert a["source_repo"].endswith("platform-manifests.git")
    e = a["graph"]["edges"]
    assert any(x["kind"] == "depends_on" for x in e)
    assert any(x["kind"] == "deploys_to" for x in e)


def test_flux(tmp_path):
    (tmp_path / "flux.yaml").write_text(FLUX)
    doc = analyze_gitops(tmp_path)
    kinds = {f["attrs"]["flux_kind"] for f in doc["facts"]}
    assert kinds == {"GitRepository", "Kustomization"}
    ks = next(f for f in doc["facts"]
               if f["attrs"]["flux_kind"] == "Kustomization")
    assert ks["attrs"]["prune"] is True
    assert ks["attrs"]["source_ref"] == "GitRepository/platform"


def test_gha(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "deploy.yml").write_text(GHA)
    doc = analyze_gha(tmp_path)
    a = doc["facts"][0]["attrs"]
    assert a["dangerous_triggers"] == ["pull_request_target"]
    assert a["write_perms"] == ["*"]
    assert a["unpinned_third_party"] == ["build:evilcorp/deploy@main"]
    assert a["script_injection_risk"] == ["build"]
    assert a["self_hosted_jobs"] == ["build"]
    assert a["actions"][0]["pin"] == "tag"  # actions/checkout@v4 = mutable tag


def test_cicd_rules(tmp_path):
    (tmp_path / "app.yaml").write_text(ARGO)
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "deploy.yml").write_text(GHA)
    facts = [Fact.from_dict(x)
             for x in analyze_gitops(tmp_path)["facts"]
             + analyze_gha(tmp_path)["facts"]]
    rules = load_catalog(
        __import__("pathlib").Path(__file__).parents[1] / "rules/catalog")
    findings, _ = RuleEngine(rules).evaluate(facts)
    v = {f.rule_id for f in findings if f.status == "violated"}
    for rid in ("PF-GITOPS-002", "PF-GITOPS-003", "PF-CICD-001",
                "PF-CICD-002", "PF-CICD-003", "PF-CICD-004", "PF-CICD-005"):
        assert rid in v, rid
