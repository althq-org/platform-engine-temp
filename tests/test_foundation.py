"""Tests for foundation provisioning (security groups and IAM from declared sections)."""

from unittest.mock import MagicMock, patch

from devops.capabilities.context import CapabilityContext
from devops.capabilities.foundation import provision_foundation


def _make_ctx() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "test-svc"
    infra = MagicMock()
    infra.vpc_id = "vpc-123"
    infra.vpc_cidr = "10.0.0.0/16"
    return CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )


@patch("devops.iam.roles.create_task_roles")
@patch("devops.networking.security_groups.create_ecs_security_group")
def test_provision_foundation_with_compute_sets_compute_sg_and_iam(
    mock_ecs_sg: MagicMock,
    mock_task_roles: MagicMock,
) -> None:
    """provision_foundation with declared={'compute'} sets security_groups.compute.id and iam.task_role/exec_role."""
    mock_sg = MagicMock()
    mock_sg.id = "sg-compute-123"
    mock_ecs_sg.return_value = mock_sg

    mock_task_role = MagicMock()
    mock_exec_role = MagicMock()
    mock_task_roles.return_value = (mock_task_role, mock_exec_role)

    ctx = _make_ctx()
    provision_foundation({"compute": {}}, ctx)

    mock_ecs_sg.assert_called_once()
    assert ctx.get("security_groups.compute.id") == "sg-compute-123"
    assert ctx.get("security_groups.compute") is mock_sg
    mock_task_roles.assert_called_once()
    assert ctx.get("iam.task_role") is mock_task_role
    assert ctx.get("iam.exec_role") is mock_exec_role


@patch("devops.networking.security_groups.create_efs_security_group")
@patch("devops.networking.security_groups.create_agent_security_group")
@patch("devops.iam.roles.create_task_roles")
@patch("devops.networking.security_groups.create_ecs_security_group")
def test_provision_foundation_with_compute_and_storage_sets_efs_sg(
    mock_ecs_sg: MagicMock,
    mock_task_roles: MagicMock,
    mock_agent_sg: MagicMock,
    mock_efs_sg: MagicMock,
) -> None:
    """provision_foundation with declared={'compute', 'storage'} also sets security_groups.efs.id."""
    mock_compute_sg = MagicMock()
    mock_compute_sg.id = "sg-compute-123"
    mock_ecs_sg.return_value = mock_compute_sg

    mock_agent_sg_res = MagicMock()
    mock_agent_sg_res.id = "sg-agent-456"
    mock_agent_sg.return_value = mock_agent_sg_res

    mock_efs_sg_res = MagicMock()
    mock_efs_sg_res.id = "sg-efs-789"
    mock_efs_sg.return_value = mock_efs_sg_res

    mock_task_role = MagicMock()
    mock_exec_role = MagicMock()
    mock_task_roles.return_value = (mock_task_role, mock_exec_role)

    ctx = _make_ctx()
    provision_foundation({"compute": {}, "storage": {}}, ctx)

    assert ctx.get("security_groups.compute.id") == "sg-compute-123"
    assert ctx.get("security_groups.agent.id") == "sg-agent-456"
    assert ctx.get("security_groups.efs.id") == "sg-efs-789"
    mock_efs_sg.assert_called_once()
