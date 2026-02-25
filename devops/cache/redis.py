"""ElastiCache SubnetGroup and ReplicationGroup for Redis."""

import pulumi
import pulumi_aws


def create_redis_cluster(
    service_name: str,
    private_subnet_ids: list[str],
    security_group_id: pulumi.Output[str],
    aws_provider: pulumi_aws.Provider,
    node_type: str = "cache.t3.micro",
    num_cache_clusters: int = 1,
    engine_version: str = "7.1",
    parameter_group: str = "default.redis7",
) -> tuple[pulumi_aws.elasticache.SubnetGroup, pulumi_aws.elasticache.ReplicationGroup]:
    """Create ElastiCache Redis subnet group and replication group."""
    subnet_group = pulumi_aws.elasticache.SubnetGroup(
        f"{service_name}_redis_subnets",
        name=f"{service_name}-redis-subnets",
        subnet_ids=private_subnet_ids,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    replication_group_id = f"{service_name[:34]}-redis" if len(service_name) > 34 else f"{service_name}-redis"
    replication_group = pulumi_aws.elasticache.ReplicationGroup(
        f"{service_name}_redis",
        replication_group_id=replication_group_id,
        description=f"Redis for {service_name}",
        node_type=node_type,
        num_cache_clusters=num_cache_clusters,
        engine="redis",
        engine_version=engine_version,
        parameter_group_name=parameter_group,
        subnet_group_name=subnet_group.name,
        security_group_ids=[security_group_id],
        at_rest_encryption_enabled=True,
        transit_encryption_enabled=True,
        automatic_failover_enabled=False,
        tags={"Name": f"{service_name}-redis"},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return (subnet_group, replication_group)
