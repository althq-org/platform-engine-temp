"""WebhookGateway capability: inbound HTTP webhook endpoint."""

from typing import Any

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("webhookGateway", phase=Phase.COMPUTE)
def webhook_gateway_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Mark webhook gateway as enabled; export flag for downstream consumers.

    Infrastructure provisioning (ALB listener rule or API Gateway route) is
    handled by the compute layer when this flag is present. This capability
    registers the intent so other capabilities can depend on it.
    """
    ctx.set("webhookGateway.enabled", True)
    ctx.export("webhook_gateway_enabled", True)
