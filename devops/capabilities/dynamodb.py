"""DynamoDB capability: managed NoSQL tables."""

import json
from typing import Any

import pulumi
import pulumi_aws

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("dynamodb", phase=Phase.INFRASTRUCTURE)
def dynamodb_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision DynamoDB tables and grant the ECS task full access to them.

    Tables declared under spec.dynamodb.tables are provisioned by Pulumi.
    The application is also expected to call CreateTable on startup for any
    tables it needs that may not exist yet (idempotent — safe to call every boot).

    IAM: dynamodb:* scoped to the declared table ARNs + their sub-resources
    (indexes, streams). The declared names act as the security boundary.
    """
    from devops.database.dynamodb import create_dynamodb_table

    tables_config: list[dict[str, Any]] = section_config.get("tables") or []
    if not tables_config:
        ctx.export("dynamodb_table_names", [])
        return

    table_names: list[str] = []
    table_arns: list[Any] = []
    service_name = ctx.config.service_name

    for tbl in tables_config:
        name: str = tbl["name"]
        pk: str = tbl["partitionKey"]
        pk_type: str = tbl.get("partitionKeyType", "S")
        sk: str | None = tbl.get("sortKey")
        sk_type: str | None = tbl.get("sortKeyType", "S") if sk else None
        ttl: str | None = tbl.get("ttlAttribute")
        billing: str = tbl.get("billingMode", "PAY_PER_REQUEST")

        table = create_dynamodb_table(
            service_name=service_name,
            table_name=name,
            partition_key=pk,
            partition_key_type=pk_type,
            sort_key=sk,
            sort_key_type=sk_type,
            ttl_attribute=ttl,
            billing_mode=billing,
            aws_provider=ctx.aws_provider,
        )

        ctx.set(f"dynamodb.tables.{name}.arn", table.arn)
        ctx.set(f"dynamodb.tables.{name}.name", table.name)
        table_names.append(name)
        table_arns.append(table.arn)
        ctx.export(f"dynamodb_table_{name.replace('-', '_')}", table.name)

    ctx.export("dynamodb_table_names", table_names)

    # Grant the ECS task role least-privilege access to exactly these table ARNs.
    # Without this the container will get AccessDeniedException at runtime.
    task_role = ctx.get("iam.task_role")
    if task_role is not None:
        # dynamodb:* scoped to the declared table ARNs (+ their index/stream sub-resources).
        # Broad on these tables — the declared names act as the security boundary, not the action list.
        policy_doc = pulumi.Output.all(*table_arns).apply(
            lambda arns: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "dynamodb:*",
                            "Resource": arns + [f"{arn}/*" for arn in arns],
                        }
                    ],
                }
            )
        )
        pulumi_aws.iam.RolePolicy(
            f"{service_name}_dynamodb_policy",
            role=task_role.name,
            policy=policy_doc,
            opts=pulumi.ResourceOptions(provider=ctx.aws_provider),
        )

    agentcore_role = ctx.get("iam.agentcore_runtime_role")
    if agentcore_role is not None:
        agentcore_policy_doc = pulumi.Output.all(*table_arns).apply(
            lambda arns: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "dynamodb:*",
                            "Resource": arns + [f"{arn}/*" for arn in arns],
                        }
                    ],
                }
            )
        )
        pulumi_aws.iam.RolePolicy(
            f"{service_name}_dynamodb_agentcore_policy",
            role=agentcore_role.name,
            policy=agentcore_policy_doc,
            opts=pulumi.ResourceOptions(provider=ctx.aws_provider),
        )
