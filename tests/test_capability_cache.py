"""Tests for the cache capability handler (config → create_redis_cluster, ctx.set/export)."""

from unittest.mock import MagicMock, patch

import devops.capabilities.cache  # noqa: F401 - register cache capability
from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES


def _make_ctx_with_db_sg() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "platform-v2-test"
    infra = MagicMock()
    infra.private_subnet_ids = ["subnet-a", "subnet-b"]
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    ctx.set("security_groups.database.id", MagicMock())
    return ctx


@patch("devops.cache.redis.create_redis_cluster")
def test_cache_handler_calls_create_redis_cluster_and_sets_context(
    mock_create_redis: MagicMock,
) -> None:
    """Cache handler reads section_config, calls create_redis_cluster, sets and exports endpoint."""
    mock_subnet = MagicMock()
    mock_cluster = MagicMock()
    mock_cluster.configuration_endpoint_address = None
    mock_cluster.primary_endpoint_address = "platform-v2-test.abc123.0001.use1.cache.amazonaws.com"
    mock_create_redis.return_value = (mock_subnet, mock_cluster)

    section_config = {
        "engine": "redis",
        "nodeType": "cache.t3.micro",
        "numNodes": 1,
    }
    ctx = _make_ctx_with_db_sg()
    handler = CAPABILITIES["cache"].handler
    handler(section_config, ctx)

    mock_create_redis.assert_called_once()
    call_kw = mock_create_redis.call_args[1]
    assert call_kw["service_name"] == "platform-v2-test"
    assert call_kw["private_subnet_ids"] == ["subnet-a", "subnet-b"]
    assert call_kw["node_type"] == "cache.t3.micro"
    assert call_kw["num_cache_clusters"] == 1

    assert ctx.get("cache.redis.endpoint") == "platform-v2-test.abc123.0001.use1.cache.amazonaws.com"
    assert ctx.exports["redis_endpoint"] == "platform-v2-test.abc123.0001.use1.cache.amazonaws.com"


@patch("devops.cache.redis.create_redis_cluster")
def test_cache_handler_uses_configuration_endpoint_when_available(
    mock_create_redis: MagicMock,
) -> None:
    """Cache handler uses configuration_endpoint_address when set (cluster mode)."""
    mock_subnet = MagicMock()
    mock_cluster = MagicMock()
    mock_cluster.configuration_endpoint_address = "clustercfg.abc123.0001.use1.cache.amazonaws.com"
    mock_cluster.primary_endpoint_address = "primary.abc123.0001.use1.cache.amazonaws.com"
    mock_create_redis.return_value = (mock_subnet, mock_cluster)

    section_config = {"engine": "redis", "numNodes": 2}
    ctx = _make_ctx_with_db_sg()
    handler = CAPABILITIES["cache"].handler
    handler(section_config, ctx)

    assert ctx.get("cache.redis.endpoint") == "clustercfg.abc123.0001.use1.cache.amazonaws.com"
    assert ctx.exports["redis_endpoint"] == "clustercfg.abc123.0001.use1.cache.amazonaws.com"


@patch("devops.cache.redis.create_redis_cluster")
def test_cache_handler_uses_defaults_when_section_minimal(
    mock_create_redis: MagicMock,
) -> None:
    """Cache handler uses default nodeType and numNodes when section config is minimal."""
    mock_subnet = MagicMock()
    mock_cluster = MagicMock()
    mock_cluster.configuration_endpoint_address = None
    mock_cluster.primary_endpoint_address = "default.abc.0001.use1.cache.amazonaws.com"
    mock_create_redis.return_value = (mock_subnet, mock_cluster)

    section_config = {}
    ctx = _make_ctx_with_db_sg()
    handler = CAPABILITIES["cache"].handler
    handler(section_config, ctx)

    call_kw = mock_create_redis.call_args[1]
    assert call_kw["node_type"] == "cache.t3.micro"
    assert call_kw["num_cache_clusters"] == 1
