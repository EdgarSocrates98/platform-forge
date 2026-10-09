# CLOUD — provider-observed facts from dumps (read-only)

The core never calls a cloud API. `analyze cloud-*` reads CLI JSON dumps
you produced elsewhere — observed state is T1 evidence, never inferred.

## Common model (ADR-0009)

Every provider normalizes into `cloud.*` fact kinds:

`account, region, vpc_vnet, subnet, route, gateway, nat, load_balancer,
dns, cluster, node_pool, database, bucket, function, queue, topic,
iam_principal, role, policy, security_group`

## AWS first (§50)

`analyze cloud-aws <dump-dir>` sniffs `describe-*`/`list-*` JSON shapes:
organizations → account graph; IAM policies → principal/role/policy
nodes + `assumes` edges; VPCs/subnets/SGs → network graph; EKS/ECS,
RDS/DynamoDB, S3, Lambda, SQS/SNS.

## Azure / GCP (§175–176)

`analyze cloud-azure` / `analyze cloud-gcp` cover the same common model
on ARM/GCP export shapes — partial coverage, declared as such.

## Cost signals

`finops ingest` accepts AWS CUR, Azure cost export, GCP billing export,
OpenCost and Kubecost JSON → normalized rows → FOCUS 1.0 validation +
unit economics + idle/rightsizing/anomaly insights.

## Boundaries

Live collectors are explicitly out of the core (`collect` is dump-only).
Any observed-vs-declared disagreement lands as `state.contradiction`
(§116) — `analyze drift` reports both states.
