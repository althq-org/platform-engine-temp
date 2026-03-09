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
    global_secondary_indexes: list[dict] | None = None,
) -> pulumi_aws.dynamodb.Table:
    """Create a DynamoDB table with the given key schema."""
    resource_name = f"{service_name}_{table_name.replace('-', '_')}_table"

    defined_attrs: set[str] = {partition_key}
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
        defined_attrs.add(sort_key)

    gsi_args: list[pulumi_aws.dynamodb.TableGlobalSecondaryIndexArgs] = []
    for gsi in global_secondary_indexes or []:
        gsi_pk: str = gsi["partition_key"]
        gsi_pk_type: str = gsi.get("partition_key_type", "S")
        gsi_sk: str | None = gsi.get("sort_key")
        gsi_sk_type: str | None = gsi.get("sort_key_type", "S") if gsi_sk else None
        projection: str = gsi.get("projection_type", "ALL")

        if gsi_pk not in defined_attrs:
            attribute_defs.append(
                pulumi_aws.dynamodb.TableAttributeArgs(name=gsi_pk, type=gsi_pk_type)
            )
            defined_attrs.add(gsi_pk)

        if gsi_sk and gsi_sk not in defined_attrs:
            attribute_defs.append(
                pulumi_aws.dynamodb.TableAttributeArgs(name=gsi_sk, type=gsi_sk_type)
            )
            defined_attrs.add(gsi_sk)

        gsi_args.append(
            pulumi_aws.dynamodb.TableGlobalSecondaryIndexArgs(
                name=gsi["name"],
                hash_key=gsi_pk,
                range_key=gsi_sk,
                projection_type=projection,
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
        global_secondary_indexes=gsi_args if gsi_args else None,
        point_in_time_recovery=pulumi_aws.dynamodb.TablePointInTimeRecoveryArgs(
            enabled=True,
        ),
        tags={"Name": table_name, "managed-by": "platform-engine", "service": service_name},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return table
