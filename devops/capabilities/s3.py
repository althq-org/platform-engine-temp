"""S3 capability: object storage buckets with automatic IAM wiring."""

import json
from typing import Any

import pulumi
import pulumi_aws

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("s3", phase=Phase.INFRASTRUCTURE)
def s3_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision S3 buckets and grant IAM access to compute roles.

    Bucket names are prefixed with the AWS account ID for global uniqueness:
    user writes 'agent-factory-state', AWS gets '470935583836-agent-factory-state'.
    """
    from devops.storage.s3 import create_s3_bucket

    aws_account_id = ctx.infra.aws_account_id
    buckets_config: list[dict[str, Any]] = section_config.get("buckets") or []
    if not buckets_config:
        return

    service_name = ctx.config.service_name
    bucket_arns: list[Any] = []
    bucket_env_vars: dict[str, Any] = {}

    for bucket_cfg in buckets_config:
        logical_name: str = bucket_cfg["name"]
        real_name = f"{aws_account_id}-{logical_name}"

        lifecycle_rules = []
        for rule in bucket_cfg.get("lifecycleRules", []):
            lifecycle_rules.append({
                "prefix": rule.get("prefix", ""),
                "transition_to_ia": rule.get("transitionToIA"),
                "expiration_days": rule.get("expirationDays"),
            })

        bucket = create_s3_bucket(
            service_name=service_name,
            bucket_name=real_name,
            aws_provider=ctx.aws_provider,
            versioning=bucket_cfg.get("versioning", False),
            encryption=bucket_cfg.get("encryption", "AES256"),
            lifecycle_rules=lifecycle_rules if lifecycle_rules else None,
        )

        ctx.set(f"s3.buckets.{logical_name}.arn", bucket.arn)
        ctx.set(f"s3.buckets.{logical_name}.name", bucket.bucket)
        bucket_arns.append(bucket.arn)

        export_key = f"s3_bucket_{logical_name.replace('-', '_')}"
        ctx.export(export_key, bucket.bucket)

        env_key = f"S3_BUCKET_{logical_name.upper().replace('-', '_')}"
        bucket_env_vars[env_key] = bucket.bucket

    ctx.set("s3.bucket_arns", bucket_arns)
    ctx.set("s3.bucket_env_vars", bucket_env_vars)

    task_role = ctx.get("iam.task_role")
    if task_role is not None:
        _grant_s3_access(ctx, task_role, bucket_arns, service_name, "task")


def _grant_s3_access(
    ctx: CapabilityContext,
    role: pulumi_aws.iam.Role,
    bucket_arns: list[Any],
    service_name: str,
    role_label: str,
) -> None:
    """Attach an inline policy granting s3:* on the given bucket ARNs."""
    policy_doc = pulumi.Output.all(*bucket_arns).apply(
        lambda arns: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:*",
                        "Resource": arns + [f"{arn}/*" for arn in arns],
                    }
                ],
            }
        )
    )
    pulumi_aws.iam.RolePolicy(
        f"{service_name}_s3_{role_label}_policy",
        role=role.name,
        policy=policy_doc,
        opts=pulumi.ResourceOptions(provider=ctx.aws_provider),
    )
