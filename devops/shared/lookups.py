"""Lookup shared infrastructure (VPC, ALB, Cloudflare)."""

from dataclasses import dataclass

import pulumi
import pulumi_aws
import pulumi_cloudflare


@dataclass
class SharedInfrastructure:
    """Shared resources used by all platform services."""

    vpc_id: str
    vpc_cidr: str
    private_subnet_ids: list[str]
    alb_arn: str
    alb_dns_name: str
    listener_443_arn: str
    zone_id: str
    zone_name: str
    cf_provider: pulumi_cloudflare.Provider


def lookup_shared_infrastructure(
    aws_provider: pulumi_aws.Provider,
) -> SharedInfrastructure:
    """Lookup all shared infrastructure resources.

    Returns dataclass with all shared resource identifiers.
    Does not create any resources.
    """
    # Private subnets
    private_subnets = pulumi_aws.ec2.get_subnets(
        filters=[pulumi_aws.ec2.GetSubnetsFilterArgs(name="tag:network", values=["private"])],
        opts=pulumi.InvokeOptions(provider=aws_provider),
    )
    if not private_subnets.ids:
        raise SystemExit("No private subnets found (tag network=private)")

    # VPC
    first_subnet = pulumi_aws.ec2.get_subnet(
        id=private_subnets.ids[0],
        opts=pulumi.InvokeOptions(provider=aws_provider),
    )
    vpc = pulumi_aws.ec2.get_vpc(
        id=first_subnet.vpc_id,
        opts=pulumi.InvokeOptions(provider=aws_provider),
    )

    # ALB
    alb = pulumi_aws.lb.get_load_balancer(
        name="product-external-alb",
        opts=pulumi.InvokeOptions(provider=aws_provider),
    )

    # ALB Listener
    listener_443 = pulumi_aws.lb.get_listener(
        load_balancer_arn=alb.arn,
        port=443,
        opts=pulumi.InvokeOptions(provider=aws_provider),
    )

    # Cloudflare
    cf_token_param = pulumi_aws.ssm.get_parameter(name="/cloudflare/platform_infra_token")
    cf_zone_id_param = pulumi_aws.ssm.get_parameter(name="/cloudflare/zone_id")
    cf_provider = pulumi_cloudflare.Provider(
        "cf",
        api_token=cf_token_param.value,
        opts=pulumi.ResourceOptions(additional_secret_outputs=["api_token"]),
    )
    cf_zone = pulumi_cloudflare.get_zone(
        zone_id=cf_zone_id_param.value,
        opts=pulumi.InvokeOptions(provider=cf_provider),
    )

    return SharedInfrastructure(
        vpc_id=vpc.id,
        vpc_cidr=vpc.cidr_block,
        private_subnet_ids=list(private_subnets.ids),
        alb_arn=alb.arn,
        alb_dns_name=alb.dns_name,
        listener_443_arn=listener_443.arn,
        zone_id=cf_zone.id,
        zone_name=cf_zone.name,
        cf_provider=cf_provider,
    )
