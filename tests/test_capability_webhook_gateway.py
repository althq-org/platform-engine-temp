"""Tests for the webhookGateway capability handler."""

from unittest.mock import MagicMock

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES
import devops.capabilities.webhook_gateway  # noqa: F401 - register webhookGateway capability


def _make_ctx() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "my-svc"
    return CapabilityContext(
        config=config,
        infra=MagicMock(),
        aws_provider=MagicMock(),
    )


def test_webhook_gateway_handler_sets_enabled_and_exports() -> None:
    """WebhookGateway handler sets enabled flag and exports webhook_gateway_enabled."""
    ctx = _make_ctx()
    handler = CAPABILITIES["webhookGateway"].handler
    handler({}, ctx)

    assert ctx.get("webhookGateway.enabled") is True
    assert ctx.exports.get("webhook_gateway_enabled") is True
