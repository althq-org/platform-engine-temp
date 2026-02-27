"""Tests for S3 and AgentCore Runtime config parsing."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from devops.config import (
    AgentCoreRuntimeConfig,
    PlatformConfig,
    S3Config,
)


def _load(tmp_path: Path, yaml_content: str) -> PlatformConfig:
    yaml_file = tmp_path / "platform.yaml"
    yaml_file.write_text(yaml_content)
    mock_config = MagicMock()
    mock_config.require.return_value = "us-west-2"
    with patch("devops.config.pulumi.Config", return_value=mock_config):
        return PlatformConfig.from_file(str(yaml_file))


def test_parses_s3_minimal(tmp_path: Path) -> None:
    config = _load(tmp_path, """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  s3:
    buckets:
      - name: my-svc-state
""")
    assert config.s3 is not None
    assert isinstance(config.s3, S3Config)
    assert len(config.s3.buckets) == 1
    assert config.s3.buckets[0].name == "my-svc-state"
    assert config.s3.buckets[0].versioning is False
    assert config.s3.buckets[0].encryption == "AES256"
    assert config.s3.buckets[0].lifecycle_rules == []


def test_parses_s3_full(tmp_path: Path) -> None:
    config = _load(tmp_path, """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  s3:
    buckets:
      - name: my-svc-state
        versioning: true
        encryption: "aws:kms"
        lifecycleRules:
          - prefix: "logs/"
            transitionToIA: 30
            expirationDays: 90
""")
    assert config.s3 is not None
    b = config.s3.buckets[0]
    assert b.versioning is True
    assert b.encryption == "aws:kms"
    assert len(b.lifecycle_rules) == 1
    assert b.lifecycle_rules[0].prefix == "logs/"
    assert b.lifecycle_rules[0].transition_to_ia == 30
    assert b.lifecycle_rules[0].expiration_days == 90


def test_parses_agentcore_minimal(tmp_path: Path) -> None:
    config = _load(tmp_path, """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  agentcoreRuntime:
    runtimes:
      - name: my_agent
        image: my-agent
""")
    assert config.agentcore_runtime is not None
    assert isinstance(config.agentcore_runtime, AgentCoreRuntimeConfig)
    assert len(config.agentcore_runtime.runtimes) == 1
    rt = config.agentcore_runtime.runtimes[0]
    assert rt.name == "my_agent"
    assert rt.image == "my-agent"
    assert rt.network_mode == "PUBLIC"
    assert rt.environment_variables == {}
    assert config.agentcore_runtime.authorizer is None


def test_parses_agentcore_full(tmp_path: Path) -> None:
    config = _load(tmp_path, """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  agentcoreRuntime:
    runtimes:
      - name: claude_agent
        image: claude-agent
        description: Claude runtime
        networkMode: VPC
        environmentVariables:
          WORK_DIR: /tmp/agent
      - name: pi_agent
        image: pi-agent
    authorizer:
      type: jwt
      discoveryUrl: https://example.com/.well-known/openid-configuration
      allowedAudiences:
        - my-app
      allowedClients:
        - client-1
""")
    ac = config.agentcore_runtime
    assert ac is not None
    assert len(ac.runtimes) == 2
    assert ac.runtimes[0].name == "claude_agent"
    assert ac.runtimes[0].network_mode == "VPC"
    assert ac.runtimes[0].environment_variables == {"WORK_DIR": "/tmp/agent"}
    assert ac.runtimes[1].name == "pi_agent"
    assert ac.authorizer is not None
    assert ac.authorizer.type == "jwt"
    assert ac.authorizer.discovery_url == "https://example.com/.well-known/openid-configuration"
    assert ac.authorizer.allowed_audiences == ["my-app"]
    assert ac.authorizer.allowed_clients == ["client-1"]


def test_spec_sections_includes_s3_and_agentcore(tmp_path: Path) -> None:
    config = _load(tmp_path, """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  s3:
    buckets:
      - name: my-svc-state
  agentcoreRuntime:
    runtimes:
      - name: my_agent
        image: my-agent
""")
    sections = config.spec_sections
    assert "s3" in sections
    assert "agentcoreRuntime" in sections


def test_s3_absent_when_not_declared(tmp_path: Path) -> None:
    config = _load(tmp_path, """
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-svc
spec:
  compute:
    port: 80
""")
    assert config.s3 is None
    assert config.agentcore_runtime is None
    assert "s3" not in config.spec_sections
    assert "agentcoreRuntime" not in config.spec_sections
