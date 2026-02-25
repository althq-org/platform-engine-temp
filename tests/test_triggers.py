"""Unit tests for create_eventbridge_scheduler (ScheduleGroup and Role)."""

from unittest.mock import MagicMock, patch

from devops.triggers.eventbridge import create_eventbridge_scheduler


@patch("devops.triggers.eventbridge.pulumi_aws.iam.RolePolicy")
@patch("devops.triggers.eventbridge.pulumi_aws.iam.Role")
@patch("devops.triggers.eventbridge.pulumi_aws.scheduler.ScheduleGroup")
def test_create_eventbridge_scheduler_returns_schedule_group_and_role(
    mock_schedule_group: MagicMock,
    mock_role: MagicMock,
    mock_role_policy: MagicMock,
) -> None:
    """create_eventbridge_scheduler creates ScheduleGroup and Role, returns (schedule_group, role)."""
    mock_schedule_group.return_value.name = "my-svc-schedules"
    mock_role.return_value.name = "my-svc-eventbridge-scheduler"

    aws_provider = MagicMock()
    schedule_group, role = create_eventbridge_scheduler(
        service_name="my-svc",
        aws_provider=aws_provider,
    )

    assert schedule_group.name == "my-svc-schedules"
    assert role.name == "my-svc-eventbridge-scheduler"

    mock_schedule_group.assert_called_once()
    sg_kw = mock_schedule_group.call_args[1]
    assert sg_kw["name"] == "my-svc-schedules"

    mock_role.assert_called_once()
    mock_role_policy.assert_called_once()


@patch("devops.triggers.eventbridge.pulumi_aws.iam.RolePolicy")
@patch("devops.triggers.eventbridge.pulumi_aws.iam.Role")
@patch("devops.triggers.eventbridge.pulumi_aws.scheduler.ScheduleGroup")
def test_create_eventbridge_scheduler_uses_service_name_in_resource_names(
    mock_schedule_group: MagicMock,
    mock_role: MagicMock,
    mock_role_policy: MagicMock,
) -> None:
    """ScheduleGroup and Role use service_name in logical names and display names."""
    mock_schedule_group.return_value.name = "platform-v2-test-schedules"
    mock_role.return_value.name = "platform-v2-test-eventbridge-scheduler"

    aws_provider = MagicMock()
    create_eventbridge_scheduler(
        service_name="platform-v2-test",
        aws_provider=aws_provider,
    )

    assert mock_schedule_group.call_args[0][0] == "platform-v2-test_schedule_group"
    assert mock_schedule_group.call_args[1]["name"] == "platform-v2-test-schedules"
    assert mock_role.call_args[0][0] == "platform-v2-test_eventbridge_role"
    assert mock_role.call_args[1]["name"] == "platform-v2-test-eventbridge-scheduler"
