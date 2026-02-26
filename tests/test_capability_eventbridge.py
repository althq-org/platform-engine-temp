"""Tests for the eventbridge capability handler (create_eventbridge_scheduler, ctx.set/export)."""

from unittest.mock import MagicMock, patch

from devops.capabilities.context import CapabilityContext
import devops.capabilities.eventbridge  # noqa: F401 - register eventbridge capability
from devops.capabilities.registry import CAPABILITIES


def _make_ctx() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "platform-v2-test"
    infra = MagicMock()
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    return ctx


@patch("devops.capabilities.eventbridge.create_eventbridge_scheduler")
def test_eventbridge_handler_calls_create_eventbridge_scheduler_and_exports(
    mock_create: MagicMock,
) -> None:
    """EventBridge handler calls create_eventbridge_scheduler; exports eventbridge_schedule_group."""
    mock_schedule_group = MagicMock()
    mock_schedule_group.name = "platform-v2-test-schedules"
    mock_role = MagicMock()
    mock_create.return_value = (mock_schedule_group, mock_role)

    ctx = _make_ctx()
    handler = CAPABILITIES["eventbridge"].handler
    handler({}, ctx)

    mock_create.assert_called_once_with(
        service_name=ctx.config.service_name,
        aws_provider=ctx.aws_provider,
    )
    assert ctx.get("eventbridge.schedule_group") == "platform-v2-test-schedules"
    assert "eventbridge_schedule_group" in ctx.exports
    assert ctx.exports["eventbridge_schedule_group"] == "platform-v2-test-schedules"


@patch("devops.capabilities.eventbridge.create_eventbridge_scheduler")
def test_eventbridge_handler_accepts_section_config_with_schedule_group(
    mock_create: MagicMock,
) -> None:
    """Handler runs with scheduleGroup in section_config (optional)."""
    mock_schedule_group = MagicMock()
    mock_schedule_group.name = "my-svc-schedules"
    mock_create.return_value = (mock_schedule_group, MagicMock())

    ctx = _make_ctx()
    ctx.config.service_name = "my-svc"
    section_config = {"scheduleGroup": "custom-group"}
    handler = CAPABILITIES["eventbridge"].handler
    handler(section_config, ctx)

    mock_create.assert_called_once_with(
        service_name="my-svc",
        aws_provider=ctx.aws_provider,
    )
    assert ctx.exports["eventbridge_schedule_group"] == "my-svc-schedules"
