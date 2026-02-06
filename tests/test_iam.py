"""Tests for IAM roles module."""

from unittest.mock import MagicMock, patch

from devops.iam.roles import create_task_roles


@patch("devops.iam.roles.pulumi_aws.iam.RolePolicyAttachment")
@patch("devops.iam.roles.pulumi_aws.iam.Role")
def test_create_task_roles(
    mock_role: MagicMock,
    mock_attach: MagicMock,
) -> None:
    """Task role and execution role are created with correct names."""
    task_mock = MagicMock()
    task_mock.name = "my-service-ecs-task"
    exec_mock = MagicMock()
    exec_mock.name = "my-service-ecs-exec"
    mock_role.side_effect = [task_mock, exec_mock]
    aws_provider = MagicMock()
    task_role, exec_role = create_task_roles("my-service", aws_provider)
    assert task_role.name == "my-service-ecs-task"
    assert exec_role.name == "my-service-ecs-exec"
    assert mock_role.call_count == 2
    assert mock_attach.call_count == 4
