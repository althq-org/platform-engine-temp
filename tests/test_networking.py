"""Tests for networking modules (security groups, DNS)."""

from unittest.mock import MagicMock, patch

from devops.networking.dns import create_dns_record
from devops.networking.security_groups import create_ecs_security_group


@patch("devops.networking.security_groups.pulumi_aws.ec2.SecurityGroup")
def test_create_ecs_security_group(mock_sg: MagicMock) -> None:
    """Security group allows TCP 80 from VPC CIDR."""
    mock_sg.return_value.id = "sg-123"
    aws_provider = MagicMock()
    result = create_ecs_security_group(
        "my-service",
        "vpc-1",
        "10.0.0.0/16",
        aws_provider,
    )
    assert result.id == "sg-123"
    call_kw = mock_sg.call_args[1]
    assert call_kw["vpc_id"] == "vpc-1"
    assert len(call_kw["ingress"]) == 1
    assert call_kw["ingress"][0].cidr_blocks == ["10.0.0.0/16"]


@patch("devops.networking.dns.pulumi_cloudflare.DnsRecord")
def test_create_dns_record(mock_record: MagicMock) -> None:
    """DNS CNAME record points to ALB and is proxied."""
    cf_provider = MagicMock()
    create_dns_record(
        "my-service",
        "alb-xyz.us-west-2.elb.amazonaws.com",
        "zone-123",
        cf_provider,
    )
    mock_record.assert_called_once()
    call_kw = mock_record.call_args[1]
    assert call_kw["name"] == "my-service"
    assert call_kw["content"] == "alb-xyz.us-west-2.elb.amazonaws.com"
    assert call_kw["type"] == "CNAME"
    assert call_kw["proxied"] is True
