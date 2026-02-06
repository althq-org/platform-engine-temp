"""Tests for shared infrastructure lookups."""

from unittest.mock import MagicMock, patch

import pytest

from devops.shared.lookups import SharedInfrastructure, lookup_shared_infrastructure


@patch("devops.shared.lookups.pulumi_cloudflare.get_zone")
@patch("devops.shared.lookups.pulumi_cloudflare.Provider")
@patch("devops.shared.lookups.pulumi_aws.ssm.get_parameter")
@patch("devops.shared.lookups.pulumi_aws.lb.get_listener")
@patch("devops.shared.lookups.pulumi_aws.lb.get_load_balancer")
@patch("devops.shared.lookups.pulumi_aws.ec2.get_vpc")
@patch("devops.shared.lookups.pulumi_aws.ec2.get_subnet")
@patch("devops.shared.lookups.pulumi_aws.ec2.get_subnets")
def test_lookup_shared_infrastructure(
    mock_get_subnets: MagicMock,
    mock_get_subnet: MagicMock,
    mock_get_vpc: MagicMock,
    mock_get_alb: MagicMock,
    mock_get_listener: MagicMock,
    mock_get_param: MagicMock,
    mock_cf_provider: MagicMock,
    mock_get_zone: MagicMock,
) -> None:
    """Test successful lookup of all shared resources."""
    mock_get_subnets.return_value.ids = ["subnet-1", "subnet-2"]
    mock_get_subnet.return_value.vpc_id = "vpc-123"
    mock_get_vpc.return_value.id = "vpc-123"
    mock_get_vpc.return_value.cidr_block = "10.0.0.0/16"
    mock_get_alb.return_value.arn = "alb-arn"
    mock_get_alb.return_value.dns_name = "alb.example.com"
    mock_get_listener.return_value.arn = "listener-arn"
    mock_get_param.return_value.value = "mock-value"
    mock_get_zone.return_value.id = "zone-123"
    mock_get_zone.return_value.name = "althq-dev.com"

    aws_provider = MagicMock()

    infra = lookup_shared_infrastructure(aws_provider)

    assert isinstance(infra, SharedInfrastructure)
    assert infra.vpc_id == "vpc-123"
    assert infra.vpc_cidr == "10.0.0.0/16"
    assert infra.private_subnet_ids == ["subnet-1", "subnet-2"]
    assert infra.alb_arn == "alb-arn"
    assert infra.alb_dns_name == "alb.example.com"
    assert infra.listener_443_arn == "listener-arn"
    assert infra.zone_id == "zone-123"
    assert infra.zone_name == "althq-dev.com"


@patch("devops.shared.lookups.pulumi_aws.ec2.get_subnets")
def test_lookup_no_private_subnets(mock_get_subnets: MagicMock) -> None:
    """Test error when no private subnets found."""
    mock_get_subnets.return_value.ids = []

    aws_provider = MagicMock()

    with pytest.raises(SystemExit):
        lookup_shared_infrastructure(aws_provider)
