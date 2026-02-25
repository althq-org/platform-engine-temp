"""Cache capability: ElastiCache Redis cluster."""

from typing import Any

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("cache", phase=Phase.INFRASTRUCTURE)
def cache_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision Redis from spec.cache; requires foundation to have set security_groups.database.id."""
    from devops.cache.redis import create_redis_cluster

    sg_id = ctx.require("security_groups.database.id")
    _subnet_group, redis_cluster = create_redis_cluster(
        service_name=ctx.config.service_name,
        private_subnet_ids=ctx.infra.private_subnet_ids,
        security_group_id=sg_id,
        aws_provider=ctx.aws_provider,
        node_type=section_config.get("nodeType", "cache.t3.micro"),
        num_cache_clusters=section_config.get("numNodes", 1),
    )
    endpoint = (
        redis_cluster.configuration_endpoint_address
        or redis_cluster.primary_endpoint_address
    )
    ctx.set("cache.redis.endpoint", endpoint)
    ctx.export("redis_endpoint", endpoint)
