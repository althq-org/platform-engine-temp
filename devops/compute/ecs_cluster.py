"""ECS cluster."""

import pulumi
import pulumi_aws


def create_ecs_cluster(
    service_name: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ecs.Cluster:
    """Create ECS cluster for the service."""
    return pulumi_aws.ecs.Cluster(
        f"{service_name}_cluster",
        name=service_name,
        settings=[
            pulumi_aws.ecs.ClusterSettingArgs(
                name="containerInsights",
                value="disabled",
            )
        ],
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
