"""DynamoDB Table provisioning."""

import pulumi
import pulumi_aws


def create_dynamodb_table(
    service_name: str,
    table_name: str,
    partition_key: str,
    partition_key_type: str,
    sort_key: str | None,
    sort_key_type: str | None,
    ttl_attribute: str | None,
    billing_mode: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.dynamodb.Table:
    """Create a DynamoDB table with the given key schema."""
    resource_name = f"{service_name}_{table_name.replace('-', '_')}_table"

    attribute_defs = [
        pulumi_aws.dynamodb.TableAttributeArgs(
            name=partition_key,
            type=partition_key_type,
        )
    ]

    if sort_key and sort_key_type:
        attribute_defs.append(
            pulumi_aws.dynamodb.TableAttributeArgs(
                name=sort_key,
                type=sort_key_type,
            )
        )

    ttl_spec = None
    if ttl_attribute:
        ttl_spec = pulumi_aws.dynamodb.TableTtlArgs(
            attribute_name=ttl_attribute,
            enabled=True,
        )

    table = pulumi_aws.dynamodb.Table(
        resource_name,
        name=table_name,
        billing_mode=billing_mode,
        hash_key=partition_key,
        range_key=sort_key,
        attributes=attribute_defs,
        ttl=ttl_spec,
        point_in_time_recovery=pulumi_aws.dynamodb.TablePointInTimeRecoveryArgs(
            enabled=True,
        ),
        tags={"Name": table_name, "managed-by": "platform-engine", "service": service_name},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return table
