"""Tests for config loading and validation."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops.config import (
    PlatformConfig,
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
