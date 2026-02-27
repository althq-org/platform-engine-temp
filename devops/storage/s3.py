"""S3 bucket with encryption, versioning, and lifecycle rules."""

import pulumi
import pulumi_aws


def create_s3_bucket(
    service_name: str,
    bucket_name: str,
    aws_provider: pulumi_aws.Provider,
    versioning: bool = False,
    encryption: str = "AES256",
    lifecycle_rules: list[dict] | None = None,
) -> pulumi_aws.s3.BucketV2:
    """Create an S3 bucket with encryption, optional versioning, and optional lifecycle rules.

    bucket_name is the already-prefixed real name (e.g. 470935583836-agent-factory-state).
    """
    safe_name = bucket_name.replace("-", "_")

    bucket = pulumi_aws.s3.BucketV2(
        f"{safe_name}_bucket",
        bucket=bucket_name,
        force_destroy=True,
        tags={"Name": bucket_name},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )

    pulumi_aws.s3.BucketServerSideEncryptionConfigurationV2(
        f"{safe_name}_encryption",
        bucket=bucket.id,
        rules=[
            pulumi_aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=pulumi_aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm=encryption,
                ),
            )
        ],
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )

    pulumi_aws.s3.BucketPublicAccessBlock(
        f"{safe_name}_public_access",
        bucket=bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )

    if versioning:
        pulumi_aws.s3.BucketVersioningV2(
            f"{safe_name}_versioning",
            bucket=bucket.id,
            versioning_configuration=pulumi_aws.s3.BucketVersioningV2VersioningConfigurationArgs(
                status="Enabled",
            ),
            opts=pulumi.ResourceOptions(provider=aws_provider),
        )

    if lifecycle_rules:
        rules = []
        for i, rule in enumerate(lifecycle_rules):
            rule_args: dict = {
                "id": f"rule-{i}",
                "status": "Enabled",
            }
            if rule.get("prefix") is not None:
                rule_args["filter"] = pulumi_aws.s3.BucketLifecycleConfigurationV2RuleFilterArgs(
                    prefix=rule["prefix"],
                )
            transitions = []
            if rule.get("transition_to_ia"):
                transitions.append(
                    pulumi_aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                        days=rule["transition_to_ia"],
                        storage_class="STANDARD_IA",
                    )
                )
            if transitions:
                rule_args["transitions"] = transitions
            if rule.get("expiration_days"):
                rule_args["expiration"] = pulumi_aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                    days=rule["expiration_days"],
                )
            rules.append(
                pulumi_aws.s3.BucketLifecycleConfigurationV2RuleArgs(**rule_args)
            )
        pulumi_aws.s3.BucketLifecycleConfigurationV2(
            f"{safe_name}_lifecycle",
            bucket=bucket.id,
            rules=rules,
            opts=pulumi.ResourceOptions(provider=aws_provider),
        )

    return bucket
