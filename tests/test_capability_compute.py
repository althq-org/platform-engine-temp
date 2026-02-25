"""Tests for the compute capability handler (registry handler with ctx.require/get and exports)."""

from unittest.mock import MagicMock, patch

import devops.capabilities.compute  # noqa: F401 - register compute capability
from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES


def _make_ctx_with_foundation_outputs() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "test-svc"
    config.secrets = []
    config.container_port = 80
    config.health_path = "/health"
    config.cpu = "256"
    config.memory = "512"
    config.min_capacity = 1
    config.region = "us-west-2"
    infra = MagicMock()
    infra.vpc_id = "vpc-123"
    infra.listener_443_arn = "arn:aws:elasticloadbalancing:..."
    infra.zone_name = "example.com"
    infra.alb_dns_name = "alb.example.com"
    infra.zone_id = "zone-123"
    infra.cf_provider = MagicMock()
    infra.account_id = "123456789"
    infra.private_subnet_ids = ["subnet-a", "subnet-b"]
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    mock_sg = MagicMock()
    mock_sg.id = "sg-compute-123"
    ctx.set("security_groups.compute", mock_sg)
    mock_task_role = MagicMock()
    mock_exec_role = MagicMock()
    ctx.set("iam.task_role", mock_task_role)
    ctx.set("iam.exec_role", mock_exec_role)
    return ctx


@patch("devops.capabilities.compute.create_ecs_service")
@patch("devops.capabilities.compute.create_task_definition")
@patch("devops.capabilities.compute.create_access_application")
@patch("devops.capabilities.compute.create_dns_record")
@patch("devops.capabilities.compute.create_listener_rule")
@patch("devops.capabilities.compute.create_target_group")
@patch("devops.capabilities.compute.create_ecs_cluster")
@patch("devops.capabilities.compute.create_ecr_repository")
def test_compute_handler_exports_service_url_and_ecr_cluster_service(
    mock_ecr: MagicMock,
    mock_cluster: MagicMock,
    mock_tg: MagicMock,
    mock_listener: MagicMock,
    mock_dns: MagicMock,
    mock_access: MagicMock,
    mock_task_def: MagicMock,
    mock_ecs_svc: MagicMock,
) -> None:
    """Compute handler runs; ctx.exports has service_url, ecr_repository_uri, ecs_cluster_name, ecs_service_name."""
    mock_ecr.return_value = MagicMock(repository_url="123456.dkr.ecr.region.amazonaws.com/test-svc")
    mock_cluster.return_value = MagicMock(name="test-svc")
    mock_tg.return_value = MagicMock()
    mock_listener.return_value = MagicMock()
    mock_task_def.return_value = MagicMock()
    mock_ecs_svc.return_value = MagicMock(name="test-svc")

    ctx = _make_ctx_with_foundation_outputs()
    handler = CAPABILITIES["compute"].handler
    handler({}, ctx)

    assert "service_url" in ctx.exports
    assert "ecr_repository_uri" in ctx.exports
    assert "ecs_cluster_name" in ctx.exports
    assert "ecs_service_name" in ctx.exports
    assert ctx.exports["service_url"] is not None
    assert ctx.exports["ecr_repository_uri"] is not None
    assert ctx.exports["ecs_cluster_name"] is not None
    assert ctx.exports["ecs_service_name"] is not None
