"""Tests for the AgentCore Runtime capability handler."""

from unittest.mock import MagicMock, patch

import devops.capabilities.agentcore_runtime  # noqa: F401 - register capability
from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES


def _make_ctx(
    with_task_role: bool = False,
    with_s3: bool = False,
) -> CapabilityContext:
    config = MagicMock()
    config.service_name = "my-svc"
    config.region = "us-west-2"
    config.secrets = []
    infra = MagicMock()
    infra.private_subnet_ids = ["subnet-1", "subnet-2"]
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    ctx.set("iam.agentcore_runtime_role", MagicMock(arn="arn:role:agentcore"))
    ctx.set("iam.agentcore_memory_role", MagicMock(arn="arn:role:memory"))
    if with_task_role:
        ctx.set("iam.task_role", MagicMock(name="my-svc-ecs-task"))
    if with_s3:
        ctx.set("s3.bucket_arns", [MagicMock()])
        ctx.set("s3.bucket_env_vars", {"S3_BUCKET_STATE": "470935583836-my-svc-state"})
    return ctx


@patch("devops.capabilities.agentcore_runtime._grant_memory_access")
@patch("devops.compute.agentcore_runtime.create_agentcore_runtime")
@patch("devops.compute.agentcore_memory.create_agentcore_memory")
@patch("devops.compute.ecr.create_ecr_repository")
def test_agentcore_handler_creates_memory_and_runtime(
    mock_ecr: MagicMock,
    mock_memory: MagicMock,
    mock_runtime: MagicMock,
    mock_grant_memory: MagicMock,
) -> None:
    mock_memory.return_value = MagicMock(memory_id="mem-123", memory_arn="arn:memory")
    mock_ecr.return_value = MagicMock(repository_url="123.dkr.ecr.us-west-2.amazonaws.com/my-svc-my-agent")
    mock_runtime.return_value = MagicMock(agent_runtime_arn="arn:runtime")

    ctx = _make_ctx()
    handler = CAPABILITIES["agentcoreRuntime"].handler
    handler({"runtimes": [{"name": "my_agent", "image": "my-agent"}]}, ctx)

    mock_memory.assert_called_once()
    mock_ecr.assert_called_once()
    mock_runtime.assert_called_once()
    assert "agentcore_memory_id" in ctx.exports


@patch("devops.capabilities.agentcore_runtime._grant_memory_access")
@patch("devops.capabilities.agentcore_runtime._grant_invoke_permission")
@patch("devops.compute.agentcore_runtime.create_agentcore_runtime")
@patch("devops.compute.agentcore_memory.create_agentcore_memory")
@patch("devops.compute.ecr.create_ecr_repository")
def test_agentcore_handler_grants_invoke_when_task_role_present(
    mock_ecr: MagicMock,
    mock_memory: MagicMock,
    mock_runtime: MagicMock,
    mock_grant_invoke: MagicMock,
    mock_grant_memory: MagicMock,
) -> None:
    mock_memory.return_value = MagicMock(memory_id="mem-123", memory_arn="arn:memory")
    mock_ecr.return_value = MagicMock(repository_url="url")
    mock_runtime.return_value = MagicMock(agent_runtime_arn="arn:rt")

    ctx = _make_ctx(with_task_role=True)
    handler = CAPABILITIES["agentcoreRuntime"].handler
    handler({"runtimes": [{"name": "my_agent", "image": "my-agent"}]}, ctx)

    mock_grant_invoke.assert_called_once()


@patch("devops.capabilities.agentcore_runtime._grant_memory_access")
@patch("devops.capabilities.agentcore_runtime._grant_invoke_permission")
@patch("devops.compute.agentcore_runtime.create_agentcore_runtime")
@patch("devops.compute.agentcore_memory.create_agentcore_memory")
@patch("devops.compute.ecr.create_ecr_repository")
def test_agentcore_handler_skips_invoke_without_task_role(
    mock_ecr: MagicMock,
    mock_memory: MagicMock,
    mock_runtime: MagicMock,
    mock_grant_invoke: MagicMock,
    mock_grant_memory: MagicMock,
) -> None:
    mock_memory.return_value = MagicMock(memory_id="mem-123", memory_arn="arn:memory")
    mock_ecr.return_value = MagicMock(repository_url="url")
    mock_runtime.return_value = MagicMock(agent_runtime_arn="arn:rt")

    ctx = _make_ctx(with_task_role=False)
    handler = CAPABILITIES["agentcoreRuntime"].handler
    handler({"runtimes": [{"name": "my_agent", "image": "my-agent"}]}, ctx)

    mock_grant_invoke.assert_not_called()


@patch("devops.capabilities.agentcore_runtime._grant_s3_access")
@patch("devops.capabilities.agentcore_runtime._grant_memory_access")
@patch("devops.compute.agentcore_runtime.create_agentcore_runtime")
@patch("devops.compute.agentcore_memory.create_agentcore_memory")
@patch("devops.compute.ecr.create_ecr_repository")
def test_agentcore_handler_grants_s3_when_buckets_present(
    mock_ecr: MagicMock,
    mock_memory: MagicMock,
    mock_runtime: MagicMock,
    mock_grant_memory: MagicMock,
    mock_grant_s3: MagicMock,
) -> None:
    mock_memory.return_value = MagicMock(memory_id="mem-123", memory_arn="arn:memory")
    mock_ecr.return_value = MagicMock(repository_url="url")
    mock_runtime.return_value = MagicMock(agent_runtime_arn="arn:rt")

    ctx = _make_ctx(with_s3=True)
    handler = CAPABILITIES["agentcoreRuntime"].handler
    handler({"runtimes": [{"name": "my_agent", "image": "my-agent"}]}, ctx)

    mock_grant_s3.assert_called_once()


@patch("devops.capabilities.agentcore_runtime._grant_memory_access")
@patch("devops.compute.agentcore_runtime.create_agentcore_runtime")
@patch("devops.compute.agentcore_memory.create_agentcore_memory")
@patch("devops.compute.ecr.create_ecr_repository")
def test_agentcore_handler_multiple_runtimes(
    mock_ecr: MagicMock,
    mock_memory: MagicMock,
    mock_runtime: MagicMock,
    mock_grant_memory: MagicMock,
) -> None:
    mock_memory.return_value = MagicMock(memory_id="mem-123", memory_arn="arn:memory")
    mock_ecr.return_value = MagicMock(repository_url="url")
    mock_runtime.return_value = MagicMock(agent_runtime_arn="arn:rt")

    ctx = _make_ctx()
    handler = CAPABILITIES["agentcoreRuntime"].handler
    handler({
        "runtimes": [
            {"name": "agent_a", "image": "agent-a"},
            {"name": "agent_b", "image": "agent-b"},
        ]
    }, ctx)

    assert mock_ecr.call_count == 2
    assert mock_runtime.call_count == 2
    assert mock_memory.call_count == 1  # Memory is shared
