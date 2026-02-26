"""Tests for the serviceDiscovery capability handler (config → create_service_discovery, ctx.set/export)."""

from unittest.mock import MagicMock, patch

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES
import devops.capabilities.service_discovery  # noqa: F401 - register serviceDiscovery capability


def _make_ctx() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "platform-v2-test"
    infra = MagicMock()
    infra.vpc_id = "vpc-abc123"
    return CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )


@patch("devops.networking.service_discovery.create_service_discovery")
def test_service_discovery_handler_calls_create_and_sets_context(
    mock_create: MagicMock,
) -> None:
    """ServiceDiscovery handler reads section_config, calls create_service_discovery, sets and exports namespace_id."""
    mock_ns = MagicMock()
    mock_ns.id = "ns-platform-v2-test-xyz"
    mock_svc = MagicMock()
    mock_create.return_value = (mock_ns, mock_svc)

    section_config = {"namespace": "platform-v2-test.local"}
    ctx = _make_ctx()
    handler = CAPABILITIES["serviceDiscovery"].handler
    handler(section_config, ctx)

    mock_create.assert_called_once()
    call_kw = mock_create.call_args[1]
    assert call_kw["service_name"] == "platform-v2-test"
    assert call_kw["vpc_id"] == "vpc-abc123"
    assert call_kw["namespace_name"] == "platform-v2-test.local"

    assert ctx.get("serviceDiscovery.namespace_id") == "ns-platform-v2-test-xyz"
    assert ctx.exports["cloudmap_namespace_id"] == "ns-platform-v2-test-xyz"


@patch("devops.networking.service_discovery.create_service_discovery")
def test_service_discovery_handler_uses_default_namespace_when_omitted(
    mock_create: MagicMock,
) -> None:
    """ServiceDiscovery handler uses {service_name}.local when namespace not in section_config."""
    mock_ns = MagicMock()
    mock_ns.id = "ns-default"
    mock_create.return_value = (mock_ns, MagicMock())

    section_config = {}
    ctx = _make_ctx()
    handler = CAPABILITIES["serviceDiscovery"].handler
    handler(section_config, ctx)

    call_kw = mock_create.call_args[1]
    assert call_kw["namespace_name"] == "platform-v2-test.local"
