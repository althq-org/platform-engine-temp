"""Tests for loadbalancer modules (target group, listener rule)."""

from unittest.mock import MagicMock, patch

from devops.config import PlatformConfig
from devops.loadbalancer.listener_rule import _listener_rule_priority
from devops.loadbalancer.target_group import create_target_group


def test_listener_rule_priority() -> None:
    """Priority is stable and in range 200-90200."""
    p1 = _listener_rule_priority("svc-a")
    p2 = _listener_rule_priority("svc-a")
    p3 = _listener_rule_priority("svc-b")
    assert p1 == p2
    assert p1 != p3
    assert 200 <= p1 <= 90200
    assert 200 <= p3 <= 90200


@patch("devops.loadbalancer.target_group.pulumi_aws.lb.TargetGroup")
def test_create_target_group(mock_tg: MagicMock) -> None:
    """Target group uses health path and container port from config."""
    config = PlatformConfig(
        service_name="my-svc",
        container_port=8080,
        health_path="/healthz",
        cpu="256",
        memory="512",
        min_capacity=1,
        secrets=[],
        region="us-west-2",
    )
    mock_tg.return_value.arn = "tg-arn"
    aws_provider = MagicMock()
    result = create_target_group(config, "vpc-1", aws_provider)
    assert result.arn == "tg-arn"
    call_kw = mock_tg.call_args[1]
    assert call_kw["port"] == 8080
    assert call_kw["vpc_id"] == "vpc-1"
    assert call_kw["health_check"].path == "/healthz"


def test_create_listener_rule_priority() -> None:
    """Listener rule priority is computed from service name."""
    config = PlatformConfig(
        service_name="my-svc",
        container_port=80,
        health_path="/health",
        cpu="256",
        memory="512",
        min_capacity=1,
        secrets=[],
        region="us-west-2",
    )
    # create_listener_rule uses pulumi.Output.apply; unit test only priority helper
    priority = _listener_rule_priority(config.service_name)
    assert 200 <= priority <= 90200
