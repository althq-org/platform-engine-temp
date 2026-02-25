"""Security groups for ECS, control plane, agents, database, and EFS."""

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


def create_control_plane_security_group(
    service_name: str,
    vpc_id: str,
    vpc_cidr: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ec2.SecurityGroup:
    """Create security group for control plane: HTTP/HTTPS from VPC, TCP 8000 self-ref, egress all."""
    return pulumi_aws.ec2.SecurityGroup(
        f"{service_name}_control_plane_sg",
        name=f"{service_name}-control-plane",
        vpc_id=vpc_id,
        description=f"Control plane for {service_name}",
        ingress=[
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=80,
                to_port=80,
                cidr_blocks=[vpc_cidr],
                description="HTTP from ALB",
            ),
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=443,
                to_port=443,
                cidr_blocks=[vpc_cidr],
                description="HTTPS from ALB",
            ),
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=8000,
                to_port=8000,
                self=True,
                description="Dify to Dispatcher",
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


def create_agent_security_group(
    service_name: str,
    vpc_id: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ec2.SecurityGroup:
    """Create security group for agents: no ingress, egress all."""
    return pulumi_aws.ec2.SecurityGroup(
        f"{service_name}_agent_sg",
        name=f"{service_name}-agents",
        vpc_id=vpc_id,
        description=f"Agent compute for {service_name}",
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


def create_database_security_group(
    service_name: str,
    vpc_id: str,
    control_plane_sg_id: pulumi.Output[str],
    agent_sg_id: pulumi.Output[str],
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ec2.SecurityGroup:
    """Create security group for database: PostgreSQL and Redis from control plane and agents."""
    return pulumi_aws.ec2.SecurityGroup(
        f"{service_name}_database_sg",
        name=f"{service_name}-database",
        vpc_id=vpc_id,
        description=f"Database + cache for {service_name}",
        ingress=[
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=5432,
                to_port=5432,
                security_groups=[control_plane_sg_id],
                description="PostgreSQL from control plane",
            ),
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=5432,
                to_port=5432,
                security_groups=[agent_sg_id],
                description="PostgreSQL from agents",
            ),
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=6379,
                to_port=6379,
                security_groups=[control_plane_sg_id],
                description="Redis from control plane",
            ),
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=6379,
                to_port=6379,
                security_groups=[agent_sg_id],
                description="Redis from agents",
            ),
        ],
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )


def create_efs_security_group(
    service_name: str,
    vpc_id: str,
    control_plane_sg_id: pulumi.Output[str],
    agent_sg_id: pulumi.Output[str],
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ec2.SecurityGroup:
    """Create security group for EFS: NFS from control plane and agents."""
    return pulumi_aws.ec2.SecurityGroup(
        f"{service_name}_efs_sg",
        name=f"{service_name}-efs",
        vpc_id=vpc_id,
        description=f"EFS mount targets for {service_name}",
        ingress=[
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=2049,
                to_port=2049,
                security_groups=[control_plane_sg_id],
                description="NFS from control plane",
            ),
            pulumi_aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=2049,
                to_port=2049,
                security_groups=[agent_sg_id],
                description="NFS from agents",
            ),
        ],
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
