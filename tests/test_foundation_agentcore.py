"""Tests for foundation provisioning of AgentCore roles."""

from unittest.mock import MagicMock, patch

from devops.capabilities.context import CapabilityContext
from devops.capabilities.foundation import provision_foundation


def _make_ctx() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "my-svc"
    infra = MagicMock()
    infra.vpc_id = "vpc-123"
    infra.vpc_cidr = "10.0.0.0/16"
    return CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )


@patch("devops.iam.roles.create_agentcore_memory_role")
@patch("devops.iam.roles.create_agentcore_runtime_role")
def test_foundation_creates_agentcore_roles(
    mock_runtime_role: MagicMock,
    mock_memory_role: MagicMock,
) -> None:
    mock_runtime_role.return_value = MagicMock()
    mock_memory_role.return_value = MagicMock()

    ctx = _make_ctx()
    provision_foundation({"agentcoreRuntime": {}}, ctx)

    mock_runtime_role.assert_called_once()
    mock_memory_role.assert_called_once()
    assert ctx.get("iam.agentcore_runtime_role") is not None
    assert ctx.get("iam.agentcore_memory_role") is not None


def test_foundation_skips_agentcore_when_not_declared() -> None:
    ctx = _make_ctx()
    provision_foundation({"s3": {}}, ctx)

    assert ctx.get("iam.agentcore_runtime_role") is None
    assert ctx.get("iam.agentcore_memory_role") is None
