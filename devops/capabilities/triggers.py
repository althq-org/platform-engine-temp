"""Triggers capability: EventBridge Scheduler group and IAM role."""

from typing import Any

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register
from devops.triggers.eventbridge import create_eventbridge_scheduler


@register("triggers", phase=Phase.COMPUTE)
def triggers_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision EventBridge Scheduler group and role; set and export schedule group name.

    section_config may have eventbridge.scheduleGroup (optional); create_eventbridge_scheduler
    only takes service_name, so service_name=ctx.config.service_name is used.
    """
    schedule_group, _role = create_eventbridge_scheduler(
        service_name=ctx.config.service_name,
        aws_provider=ctx.aws_provider,
    )
    ctx.set("triggers.eventbridge.schedule_group", schedule_group.name)
    ctx.export("eventbridge_schedule_group", schedule_group.name)
