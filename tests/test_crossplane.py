"""Cycle 2.1 §51–59 — explicit Crossplane/Upbound classification."""


from platformforge.models import Fact
from platformforge.product.crossplane import (
    analyze_crossplane,
    classify_object,
)
from platformforge.resources import data_path
from platformforge.rules import RuleEngine, load_catalog

FIXTURE = "lab/scenarios/crossplane-platform/fixture"


def _doc(yaml_text):
    import yaml
    return yaml.safe_load(yaml_text)


def test_xrd_and_composition_classified():
    r = analyze_crossplane(FIXTURE)
    kinds = {f["kind"] for f in r["facts"]}
    assert {"platform.xrd", "platform.composition",
            "platform.crossplane_provider", "platform.provider_config",
            "platform.managed_resource", "platform.xr"} <= kinds


def test_upbound_managed_resource():
    r = analyze_crossplane(FIXTURE)
    mr = next(f for f in r["facts"]
              if f["kind"] == "platform.managed_resource")
    a = mr["attrs"]
    assert a["provider_family"] == "aws"
    assert a["provider_group"] == "s3.aws.upbound.io"
    assert "spec.forProvider" in a["mr_evidence"]


def test_upbound_suffix_alone_not_enough():
    """§53 — spaces.upbound.io ControlPlane has only weak MR signals."""
    doc = _doc("""
apiVersion: spaces.upbound.io/v1beta1
kind: ControlPlane
metadata: {name: ctp}
spec:
  writeConnectionSecretToRef: {name: kc, namespace: ns}
""")
    assert classify_object(doc) is None


def test_non_crossplane_crd_rejected():
    """§58 — a plain CRD is never a ManagedResource, even with MR-shaped
    fields on a non-provider group."""
    doc = _doc("""
apiVersion: foo.example.com/v1
kind: Widget
metadata: {name: w}
spec:
  forProvider: {region: us-east-1}
  deletionPolicy: Delete
""")
    assert classify_object(doc) is None


def test_negative_fixture_produces_zero_facts(tmp_path):
    (tmp_path / "neg.yaml").write_text("""
apiVersion: foo.example.com/v1
kind: Widget
metadata: {name: w}
spec: {size: big}
""")
    assert analyze_crossplane(tmp_path)["facts"] == []


def test_v1_v2_signals():
    v1 = _doc("""
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata: {name: x.example.org}
spec: {group: example.org, claimNames: {kind: C}, scope: Cluster}
""")
    v2 = _doc("""
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata: {name: x.example.org}
spec: {group: example.org, scope: Namespaced}
""")
    a1 = classify_object(v1)[1]["version_signals"]
    a2 = classify_object(v2)[1]["version_signals"]
    assert "v1:claim-names" in a1 and "v1:cluster-xr" in a1
    assert "v2:namespaced-xr" in a2


def test_xr_resolves_through_xrd_table():
    r = analyze_crossplane(FIXTURE)
    xr = next(f for f in r["facts"] if f["kind"] == "platform.xr")
    assert xr["attrs"]["xrd"] == "xbuckets.platform.example.org"
    assert xr["attrs"]["classification"] == "declared-xrd"


def test_graph_chain():
    from platformforge.graph import GraphBuilder
    from platformforge.graph.query import blast_radius
    r = analyze_crossplane(FIXTURE)
    g = GraphBuilder().from_facts(r["facts"]).graph
    # blast(nid) = things that break if nid breaks — the dependents.
    assert "crossplane_managed_resource/data-lake-prod" in blast_radius(
        g, "crossplane_provider/aws-prod")["nodes"]
    assert "crossplane_xr/analytics-bucket" in blast_radius(
        g, "crossplane_composition/bucket-aws")["nodes"]


def test_mr_delete_policy_rule_fires_on_upbound():
    r = analyze_crossplane(FIXTURE)
    engine = RuleEngine(load_catalog(data_path("rules", "catalog")))
    findings, _ = engine.evaluate(
        [Fact.from_dict(f) for f in r["facts"]])
    fired = {f.rule_id for f in findings if f.status == "violated"}
    assert "PF-XR-001" in fired


def test_pkg_family_classified():
    r = analyze_crossplane(FIXTURE)
    prov = next(f for f in r["facts"]
                if f["kind"] == "platform.crossplane_provider")
    assert "provider-aws-s3" in prov["attrs"]["package"]


# ── adversarial classification (cycle 2.1 review hardening) ──


def test_spoofed_provider_suffix_rejected():
    import yaml

    from platformforge.product.crossplane import classify_object
    # `notupbound.io`/`my-upbound.io` must NOT match the `.upbound.io`
    # suffix — a bare-suffix bug let arbitrary groups mint MRs.
    for group in ("notupbound.io", "my-upbound.io", "evil.upbound.io.evil.io"):
        doc = yaml.safe_load(
            f"apiVersion: {group}/v1\nkind: Widget\nmetadata: {{name: w}}\n"
            "spec: {forProvider: {region: x}}")
        assert classify_object(doc) is None, group


def test_junk_providerconfig_rejected():
    import yaml

    from platformforge.product.crossplane import classify_object
    # kind name alone on a non-provider group proves nothing
    doc = yaml.safe_load(
        "apiVersion: myprovider.io/v1\nkind: ProviderConfig\n"
        "metadata: {name: p}\nspec: {}")
    assert classify_object(doc) is None
    # provider group but NO credentials shape — still not a ProviderConfig
    doc = yaml.safe_load(
        "apiVersion: aws.upbound.io/v1beta1\nkind: ProviderConfig\n"
        "metadata: {name: p}\nspec: {}")
    assert classify_object(doc) is None
    # provider group WITH credentials — the real thing
    doc = yaml.safe_load(
        "apiVersion: aws.upbound.io/v1beta1\nkind: ProviderConfig\n"
        "metadata: {name: p}\n"
        "spec: {credentials: {source: Secret}}")
    assert classify_object(doc)[0] == "platform.provider_config"


def test_empty_atprovider_not_evidence():
    import yaml

    from platformforge.product.crossplane import classify_object
    doc = yaml.safe_load(
        "apiVersion: s3.aws.upbound.io/v1beta1\nkind: Bucket\n"
        "metadata: {name: b}\nspec: {}\nstatus: {atProvider: {}}")
    assert classify_object(doc) is None  # empty map proves nothing


def test_spec_resourcerefs_alone_not_xr():
    import yaml

    from platformforge.product.crossplane import _xr_candidate
    # spec.resourceRefs is generic CRD plumbing — must not classify
    doc = yaml.safe_load(
        "apiVersion: custom.example.io/v1\nkind: Database\n"
        "metadata: {name: d}\n"
        "spec: {resourceRefs: [{apiVersion: v1, kind: Pod, name: p}]}")
    assert _xr_candidate(doc, {}) is None
    # status.resourceRefs (composer-populated) is the real XR shape
    doc = yaml.safe_load(
        "apiVersion: custom.example.io/v1\nkind: Database\n"
        "metadata: {name: d}\nspec: {}\n"
        "status: {resourceRefs: [{apiVersion: v1, kind: Pod, name: p}]}")
    assert _xr_candidate(doc, {})[0] == "platform.xr"


def test_conflicting_version_signals_surfaced():
    import yaml

    from platformforge.product.crossplane import classify_object
    # namespaced scope (v2) + claim names (v1) = contradictory, surfaced
    doc = yaml.safe_load(
        "apiVersion: apiextensions.crossplane.io/v2\n"
        "kind: CompositeResourceDefinition\nmetadata: {name: x}\n"
        "spec: {scope: Namespaced, claimNames: {kind: C}, "
        "names: {kind: X, plural: xs}, group: g.example.io}")
    out = classify_object(doc)
    assert out is not None
    assert "conflict:v1+v2-signals" in out[1]["version_signals"]
