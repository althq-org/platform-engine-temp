"""ECS Fargate service."""

import pulumi
import pulumi_aws

from devops.config import PlatformConfig


def _sanitize_ecs_service_name(service_name: str) -> str:
    """ECS service name must be <= 32 chars; replace . and / with _."""
    return service_name.replace(".", "_").replace("/", "_")[:32]


def _sanitize_container_name(service_name: str) -> str:
    """Container name for ECS; replace . and / with -."""
    return service_name.replace(".", "-").replace("/", "-")[:255]


def create_ecs_service(
    config: PlatformConfig,
    cluster: pulumi_aws.ecs.Cluster,
    task_def: pulumi_aws.ecs.TaskDefinition,
    target_group: pulumi_aws.lb.TargetGroup,
    security_group: pulumi_aws.ec2.SecurityGroup,
    subnet_ids: list[str],
    listener_rule: pulumi_aws.lb.ListenerRule,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ecs.Service:
    """Create ECS Fargate service with load balancer attachment."""
    return pulumi_aws.ecs.Service(
        f"{config.service_name}_svc",
        name=_sanitize_ecs_service_name(config.service_name),
        cluster=cluster.arn,
        task_definition=task_def.arn,
        desired_count=config.min_capacity,
        launch_type="FARGATE",
        load_balancers=[
            pulumi_aws.ecs.ServiceLoadBalancerArgs(
                target_group_arn=target_group.arn,
                container_name=_sanitize_container_name(config.service_name),
                container_port=config.container_port,
            )
        ],
        network_configuration=pulumi_aws.ecs.ServiceNetworkConfigurationArgs(
            assign_public_ip=False,
            subnets=subnet_ids,
            security_groups=[security_group.id],
        ),
        deployment_circuit_breaker=pulumi_aws.ecs.ServiceDeploymentCircuitBreakerArgs(
            enable=True,
            rollback=True,
        ),
        opts=pulumi.ResourceOptions(
            provider=aws_provider,
            depends_on=[listener_rule],
        ),
    )
