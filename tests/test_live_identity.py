"""Phase E gates — identity resolution: strong-id union, weak names
never merge, SA↔role conflicts surface, tf↔arn links carry evidence."""

from platformforge.live.identity import IRSA_ANNOTATION, IdentityResolver, sa_role_claims, strong_ids_of


def _k8s_sa(cluster="c1", ns="prod", name="web-sa", uid="sa-1",
            role=""):
    ann = {IRSA_ANNOTATION: role} if role else {}
    return {"resource_id": f"k8s://{cluster}/{ns}/ServiceAccount/{name}#{uid}",
            "resource_type": "k8s:ServiceAccount", "cluster": cluster,
            "namespace": ns, "name": name, "uid": uid,
            "attributes": {"annotations": ann}}


def _pod_identity(cluster="c1", ns="prod", sa="web-sa", role="arn:aws:iam::1:role/A"):
    return {"resource_id": f"aws:eks-pod-identity/1/us-east-1/{cluster}/pi-1",
            "resource_type": "aws:eks/pod_identity_association",
            "cluster": cluster, "namespace": ns, "name": sa,
            "attributes": {"namespace": ns, "service_account": sa,
                           "role_arn": role, "cluster": cluster}}


def test_strong_ids_extracted():
    o = {"resource_id": "arn:aws:iam::1:role/x",
         "attributes": {"arn": "arn:aws:iam::1:role/x"}}
    assert strong_ids_of(o)["arn"] == "arn:aws:iam::1:role/x"
    o2 = {"resource_id": "k8s://c/p/Pod/a#u9", "uid": "u9"}
    assert strong_ids_of(o2)["uid"] == "u9"


def test_same_arn_unions_objects():
    r = IdentityResolver()
    r.ingest_object({"resource_id": "arn:aws:iam::1:role/x",
                     "resource_type": "aws:iam/role",
                     "attributes": {"arn": "arn:aws:iam::1:role/x"}})
    r.ingest_object({"resource_id": "aws://iam/1/global/role/x",
                     "resource_type": "aws:iam/role",
                     "attributes": {"arn": "arn:aws:iam::1:role/x"}})
    out = r.resolve()
    assert out["counts"]["identities"] == 1
    ident = out["identities"][0]
    assert ident["canonical_id"] == "arn:aws:iam::1:role/x"
    assert len(ident["graph_nodes"]) == 2


def test_weak_name_never_merges():
    r = IdentityResolver()
    # two different objects that only share a weak name shape
    r.ingest_object({"resource_id": "", "resource_type": "k8s:Pod",
                     "namespace": "prod", "name": "web",
                     "attributes": {}})
    r.ingest_object({"resource_id": "", "resource_type": "k8s:Pod",
                     "namespace": "prod", "name": "web",
                     "attributes": {}})
    out = r.resolve()
    assert out["counts"]["identities"] == 0
    assert out["weak_candidates"]                          # reported, not merged


def test_tf_address_links_to_arn():
    r = IdentityResolver()
    r.ingest_terraform("aws_iam_role.web", "arn:aws:iam::1:role/web",
                       fact_id="f1")
    r.ingest_object({"resource_id": "arn:aws:iam::1:role/web",
                     "resource_type": "aws:iam/role",
                     "attributes": {"arn": "arn:aws:iam::1:role/web"}})
    out = r.resolve()
    link = out["links"][0]
    assert link["reason"] == "tf-address" and link["fact_ids"] == ["f1"]
    ident = out["identities"][0]
    assert ident["provider_ids"].get("tf_address") == "aws_iam_role.web"


def test_pod_identity_links_sa_to_role():
    r = IdentityResolver()
    r.ingest_object(_k8s_sa(uid="sa-9"))
    r.ingest_pod_identity(cluster="c1", namespace="prod",
                          service_account="web-sa",
                          role_arn="arn:aws:iam::1:role/A",
                          sa_uid="sa-9")
    out = r.resolve()
    assert any(l["reason"] == "pod-identity" for l in out["links"])
    # SA and role resolve into one identity via uid+arn union
    ident = [i for i in out["identities"]
             if i["canonical_id"] == "arn:aws:iam::1:role/A"]
    assert ident


def test_sa_role_conflict_detected():
    objs = [_k8s_sa(role="arn:aws:iam::1:role/A"),
            _pod_identity(role="arn:aws:iam::1:role/B")]
    conflicts = sa_role_claims(objs)
    assert len(conflicts) == 1
    c = conflicts[0].to_dict()
    assert c["kind"] == "sa-role-conflict"
    assert c["claim_a"]["role_arn"].endswith("role/A")
    assert c["claim_b"]["role_arn"].endswith("role/B")


def test_sa_role_match_no_conflict():
    same = "arn:aws:iam::1:role/A"
    assert sa_role_claims([_k8s_sa(role=same),
                           _pod_identity(role=same)]) == []


def test_resolver_conflict_flows_into_result():
    r = IdentityResolver()
    r.ingest_object(_k8s_sa(role="arn:aws:iam::1:role/A"))
    r.ingest_object(_pod_identity(role="arn:aws:iam::1:role/B"))
    out = r.resolve()
    assert out["counts"]["conflicts"] == 1
    assert out["conflicts"][0]["kind"] == "sa-role-conflict"
