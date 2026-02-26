"""Tests for config loading and validation."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops.config import (
    ComputeConfig,
    EventBridgeConfig,
    PlatformConfig,
    StorageConfig,
    WebhookGatewayConfig,
    create_aws_provider,
    load_platform_config,
)


def test_platform_config_from_file(tmp_path: Path) -> None:
    """Test loading valid platform.yaml."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: test-service
  description: Test service
spec:
  compute:
    port: 8080
    cpu: 512
    memory: 1024
    healthCheck:
      path: /healthz
    instances:
      min: 2
  secrets:
    - DATABASE_URL
    - API_KEY
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)

    mock_config = MagicMock()
    mock_config.require.return_value = "us-west-2"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        config = PlatformConfig.from_file(str(yaml_file))

    assert config.service_name == "test-service"
    assert config.container_port == 8080
    assert config.cpu == "512"
    assert config.memory == "1024"
    assert config.health_path == "/healthz"
    assert config.min_capacity == 2
    assert config.secrets == ["DATABASE_URL", "API_KEY"]
    assert config.region == "us-west-2"


def test_platform_config_defaults(tmp_path: Path) -> None:
    """Test default values when fields are missing."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: minimal-service
spec:
  compute:
    cpu: 256
    memory: 512
    instances:
      min: 1
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)

    mock_config = MagicMock()
    mock_config.require.return_value = "us-east-1"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        config = PlatformConfig.from_file(str(yaml_file))

    assert config.container_port == 80  # default
    assert config.health_path == "/health"  # default
    assert config.secrets == []  # default


def test_load_platform_config_missing_env_var() -> None:
    """Test error when PLATFORM_YAML_PATH not set."""
    saved = os.environ.pop("PLATFORM_YAML_PATH", None)
    try:
        with pytest.raises(SystemExit):
            load_platform_config()
    finally:
        if saved is not None:
            os.environ["PLATFORM_YAML_PATH"] = saved


def test_load_platform_config_file_not_found() -> None:
    """Test error when file does not exist."""
    os.environ["PLATFORM_YAML_PATH"] = "/nonexistent/platform.yaml"
    try:
        with pytest.raises(SystemExit):
            load_platform_config()
    finally:
        os.environ.pop("PLATFORM_YAML_PATH", None)


def test_platform_config_file_not_found_from_file() -> None:
    """Test error when file does not exist in from_file."""
    with pytest.raises(SystemExit):
        PlatformConfig.from_file("/nonexistent/platform.yaml")


def test_platform_config_invalid_spec_fails_validation(tmp_path: Path) -> None:
    """Test that invalid platform.yaml (fails schema) raises SystemExit."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: ok
spec:
  compute: null
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)
    mock_config = MagicMock()
    mock_config.require.return_value = "us-west-2"
    with patch("devops.config.pulumi.Config", return_value=mock_config), pytest.raises(SystemExit) as exc_info:
        PlatformConfig.from_file(str(yaml_file))
    assert "validation failed" in str(exc_info.value).lower()


def test_platform_config_parses_storage_section(tmp_path: Path) -> None:
    """Test parsing storage section with EFS options."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  compute:
    port: 80
  storage:
    efs:
      encrypted: false
      lifecycle: AFTER_14_DAYS
      accessPoint:
        path: /app-data
        uid: 2000
        gid: 2000
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)
    mock_config = MagicMock()
    mock_config.require.return_value = "us-west-2"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        config = PlatformConfig.from_file(str(yaml_file))
    assert config.storage is not None
    assert config.storage.encrypted is False
    assert config.storage.lifecycle_policy == "AFTER_14_DAYS"
    assert config.storage.access_point_path == "/app-data"
    assert config.storage.access_point_uid == 2000
    assert config.storage.access_point_gid == 2000


def test_platform_config_parses_cache_and_database_sections(tmp_path: Path) -> None:
    """Test parsing cache and database sections."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  compute:
    port: 80
  cache:
    engine: redis
    nodeType: cache.t3.small
    numNodes: 2
  database:
    engine: postgres
    instanceClass: db.t3.small
    allocatedStorage: 30
    dbName: my_db
    dbUsername: my_admin
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)
    mock_config = MagicMock()
    mock_config.require.return_value = "us-east-1"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        config = PlatformConfig.from_file(str(yaml_file))
    assert config.cache is not None
    assert config.cache.engine == "redis"
    assert config.cache.node_type == "cache.t3.small"
    assert config.cache.num_nodes == 2
    assert config.database is not None
    assert config.database.engine == "postgres"
    assert config.database.instance_class == "db.t3.small"
    assert config.database.allocated_storage == 30


def test_platform_config_parses_service_discovery_and_eventbridge(tmp_path: Path) -> None:
    """Test parsing serviceDiscovery and eventbridge sections."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  compute:
    port: 80
  serviceDiscovery:
    namespace: agents.local
  eventbridge:
    scheduleGroup: my-schedules
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)
    mock_config = MagicMock()
    mock_config.require.return_value = "us-west-2"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        config = PlatformConfig.from_file(str(yaml_file))
    assert config.service_discovery is not None
    assert config.service_discovery.namespace == "agents.local"
    assert config.eventbridge is not None
    assert isinstance(config.eventbridge, EventBridgeConfig)
    assert config.eventbridge.schedule_group == "my-schedules"


def test_platform_config_parses_webhook_gateway(tmp_path: Path) -> None:
    """Test parsing webhookGateway section."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  compute:
    port: 80
  webhookGateway: {}
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)
    mock_config = MagicMock()
    mock_config.require.return_value = "us-west-2"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        config = PlatformConfig.from_file(str(yaml_file))
    assert config.webhook_gateway is not None
    assert isinstance(config.webhook_gateway, WebhookGatewayConfig)


def test_platform_config_parses_lambda_section(tmp_path: Path) -> None:
    """Test parsing lambda.functions section."""
    yaml_content = """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  compute:
    port: 80
  lambda:
    functions:
      - name: my-fn
        image: my-image
        memory: 1024
        timeout: 60
"""
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)
    mock_config = MagicMock()
    mock_config.require.return_value = "us-west-2"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        config = PlatformConfig.from_file(str(yaml_file))
    assert config.lambda_config is not None
    assert len(config.lambda_config.functions) == 1
    assert config.lambda_config.functions[0].name == "my-fn"
    assert config.lambda_config.functions[0].image == "my-image"
    assert config.lambda_config.functions[0].memory == 1024
    assert config.lambda_config.functions[0].timeout == 60


def test_platform_config_backward_compat_properties_without_compute() -> None:
    """Backward-compat: config without compute returns defaults for port, health_path, cpu, memory, min_capacity."""
    config = PlatformConfig(
        service_name="lambda-only",
        region="us-west-2",
        raw_spec={"lambda": {"functions": [{"name": "f", "image": "img"}]}},
        compute=None,
        secrets=[],
    )
    assert config.container_port == 80
    assert config.health_path == "/health"
    assert config.cpu == "256"
    assert config.memory == "512"
    assert config.min_capacity == 1


def test_platform_config_spec_sections_returns_only_declared() -> None:
    """spec_sections returns only declared (present and non-None) sections."""
    config = PlatformConfig(
        service_name="svc",
        region="us-west-2",
        raw_spec={
            "compute": {"port": 80},
            "storage": {"efs": {}},
            "secrets": [],
        },
        compute=ComputeConfig(port=80),
        storage=StorageConfig(),
        secrets=[],
    )
    sections = config.spec_sections
    assert "compute" in sections
    assert "storage" in sections
    assert "cache" not in sections
    assert "lambda" not in sections


def test_create_aws_provider() -> None:
    """Test AWS provider creation (smoke test; returns Pulumi resource)."""
    with patch("devops.config.pulumi_aws.Provider") as mock_provider:
        create_aws_provider("my-service", "us-west-2")
        mock_provider.assert_called_once()
        call_kw = mock_provider.call_args[1]
        assert call_kw["region"] == "us-west-2"
        assert call_kw["default_tags"].tags == {
            "service": "my-service",
            "managed-by": "platform-engine",
        }
