"""EventBridge capability: Scheduler group and IAM role."""

from typing import Any

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register
from devops.triggers.eventbridge import create_eventbridge_scheduler


@register("eventbridge", phase=Phase.COMPUTE)
def eventbridge_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision EventBridge Scheduler group and role; set and export schedule group name.

    section_config may contain scheduleGroup (optional); create_eventbridge_scheduler
    uses service_name as the base for naming.
    """
    schedule_group, _role = create_eventbridge_scheduler(
        service_name=ctx.config.service_name,
        aws_provider=ctx.aws_provider,
    )
    ctx.set("eventbridge.schedule_group", schedule_group.name)
    ctx.export("eventbridge_schedule_group", schedule_group.name)
