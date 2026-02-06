"""Security group for ECS tasks (allow HTTP from VPC)."""

import pulumi
import pulumi_aws


def create_ecs_security_group(
    service_name: str,
    vpc_id: str,
    vpc_cidr: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ec2.SecurityGroup:
    """Create security group for ECS tasks: ingress TCP 80 from VPC, egress all."""
    return pulumi_aws.ec2.SecurityGroup(
        f"{service_name}_ecs_sg",
        name=f"{service_name}-ecs",
        vpc_id=vpc_id,
        description=f"ECS tasks for {service_name}",
        ingress=[
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=80,
                to_port=80,
                cidr_blocks=[vpc_cidr],
                description="HTTP from VPC",
            ),
        ],
        egress=[
            pulumi_aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
            ),
        ],
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
