"""ALB target group for ECS tasks (HTTP 80, health check)."""

import pulumi
import pulumi_aws

from devops.config import PlatformConfig


def create_target_group(
    config: PlatformConfig,
    vpc_id: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.lb.TargetGroup:
    """Create target group on port 80 with health check path from config."""
    name = f"{config.service_name}-tg"[:32]
    return pulumi_aws.lb.TargetGroup(
        f"{config.service_name}_tg",
        name=name,
        port=80,
        protocol="HTTP",
        vpc_id=vpc_id,
        target_type="ip",
        health_check=pulumi_aws.lb.TargetGroupHealthCheckArgs(
            path=config.health_path,
            protocol="HTTP",
            interval=30,
            timeout=5,
            healthy_threshold=2,
            unhealthy_threshold=3,
        ),
        deregistration_delay=60,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
