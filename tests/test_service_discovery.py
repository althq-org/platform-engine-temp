"""Unit tests for create_service_discovery (Cloud Map PrivateDnsNamespace and Service)."""

from unittest.mock import MagicMock, patch

from devops.networking.service_discovery import create_service_discovery


@patch("devops.networking.service_discovery.pulumi_aws.servicediscovery.Service")
@patch("devops.networking.service_discovery.pulumi_aws.servicediscovery.PrivateDnsNamespace")
def test_create_service_discovery_creates_namespace_and_service(
    mock_namespace: MagicMock,
    mock_service: MagicMock,
) -> None:
    """create_service_discovery creates PrivateDnsNamespace and Service with expected args."""
    mock_namespace.return_value.id = "ns-abc123"
    mock_namespace.return_value.name = "my-svc.local"
    mock_service.return_value.id = "srv-xyz789"

    aws_provider = MagicMock()

    namespace, service = create_service_discovery(
        service_name="my-svc",
        vpc_id="vpc-123",
        namespace_name="my-svc.local",
        aws_provider=aws_provider,
    )

    assert namespace.id == "ns-abc123"
    assert service.id == "srv-xyz789"

    ns_kw = mock_namespace.call_args[1]
    assert ns_kw["name"] == "my-svc.local"
    assert ns_kw["vpc"] == "vpc-123"
    assert "my-svc" in str(mock_namespace.call_args[0])

    svc_kw = mock_service.call_args[1]
    assert svc_kw["name"] == "my-svc"
    assert svc_kw["dns_config"]["namespace_id"] == namespace.id
    assert svc_kw["dns_config"]["routing_policy"] == "MULTIVALUE"


@patch("devops.networking.service_discovery.pulumi_aws.servicediscovery.Service")
@patch("devops.networking.service_discovery.pulumi_aws.servicediscovery.PrivateDnsNamespace")
def test_create_service_discovery_custom_namespace_name(
    mock_namespace: MagicMock,
    mock_service: MagicMock,
) -> None:
    """create_service_discovery uses provided namespace_name."""
    mock_namespace.return_value.id = "ns-custom"
    mock_service.return_value.id = "srv-custom"

    aws_provider = MagicMock()

    _namespace, _ = create_service_discovery(
        service_name="test-svc",
        vpc_id="vpc-456",
        namespace_name="agents.local",
        aws_provider=aws_provider,
    )

    ns_kw = mock_namespace.call_args[1]
    assert ns_kw["name"] == "agents.local"
    assert ns_kw["vpc"] == "vpc-456"
