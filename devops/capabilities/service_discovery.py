"""Service Discovery capability: AWS Cloud Map private DNS namespace."""

from typing import Any

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("serviceDiscovery", phase=Phase.INFRASTRUCTURE)
def service_discovery_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision Cloud Map private DNS namespace from spec.serviceDiscovery; requires foundation (vpc_id)."""
    from devops.networking.service_discovery import create_service_discovery

    namespace_name = section_config.get("namespace") or f"{ctx.config.service_name}.local"
    cloudmap_ns, _cloudmap_svc = create_service_discovery(
        service_name=ctx.config.service_name,
        vpc_id=ctx.infra.vpc_id,
        namespace_name=namespace_name,
        aws_provider=ctx.aws_provider,
    )
    ctx.set("serviceDiscovery.namespace_id", cloudmap_ns.id)
    ctx.export("cloudmap_namespace_id", cloudmap_ns.id)
