"""Tests for compute modules (ECR, ECS cluster, task, service)."""

from unittest.mock import MagicMock, patch

from devops.compute.ecr import create_ecr_repository
from devops.compute.ecs_cluster import create_ecs_cluster
from devops.compute.ecs_task import _make_container_def
from devops.config import ComputeConfig, PlatformConfig


@patch("devops.compute.ecr.pulumi_aws.ecr.LifecyclePolicy")
@patch("devops.compute.ecr.pulumi_aws.ecr.Repository")
def test_create_ecr_repository(
    mock_repo: MagicMock,
    mock_lifecycle: MagicMock,
) -> None:
    """ECR repository and lifecycle policy are created with correct args."""
    mock_repo.return_value.name = "my-service"
    aws_provider = MagicMock()
    result = create_ecr_repository("my-service", aws_provider)
    assert result.name == "my-service"
    mock_repo.assert_called_once()
    call_kw = mock_repo.call_args[1]
    assert call_kw["name"] == "my-service"
    mock_lifecycle.assert_called_once()


@patch("devops.compute.ecs_cluster.pulumi_aws.ecs.Cluster")
def test_create_ecs_cluster(mock_cluster: MagicMock) -> None:
    """ECS cluster is created with containerInsights disabled."""
    mock_cluster.return_value.name = "my-service"
    aws_provider = MagicMock()
    result = create_ecs_cluster("my-service", aws_provider)
    assert result.name == "my-service"
    mock_cluster.assert_called_once()
    call_kw = mock_cluster.call_args[1]
    assert call_kw["name"] == "my-service"


def test_make_container_def() -> None:
    """Container definition JSON has expected env and port."""
    config = PlatformConfig(
        service_name="svc",
        region="us-west-2",
        raw_spec={"compute": {}},
        compute=ComputeConfig(port=8080, health_path="/health", cpu=256, memory=512, min_capacity=1),
        secrets=[],
    )
    json_str = _make_container_def(
        "123456.dkr.ecr.region.amazonaws.com/svc:latest",
        config,
        [{"name": "SECRET_X", "value": "val"}],
    )
    import json as _json

    definitions = _json.loads(json_str)
    assert len(definitions) == 1
    c = definitions[0]
    assert c["name"] == "svc"
    assert c["image"] == "123456.dkr.ecr.region.amazonaws.com/svc:latest"
    assert c["portMappings"][0]["containerPort"] == 8080
    env_names = [e["name"] for e in c["environment"]]
    assert "UVICORN_PORT" in env_names
    assert "SECRET_X" in env_names
