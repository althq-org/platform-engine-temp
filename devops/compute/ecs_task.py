"""ECS task definition and container definition builder.

Supports optional EFS volume mounts for persistent storage.
"""

import json
from typing import Any

import pulumi
import pulumi_aws

from devops.config import PlatformConfig


def _make_container_def(
    uri: str,
    config: PlatformConfig,
    container_secrets: list[dict[str, Any]],
    efs_mount_path: str | None = None,
) -> str:
    """Build ECS container definition JSON string."""
    container_name = config.service_name.replace(".", "-").replace("/", "-")[:255]
    env_vars = [
        {"name": "PYTHONUNBUFFERED", "value": "1"},
        {"name": "UVICORN_HOST", "value": "0.0.0.0"},
        {"name": "UVICORN_PORT", "value": str(config.container_port)},
        *container_secrets,
    ]
    container_spec: dict[str, Any] = {
        "name": container_name,
        "image": uri,
        "essential": True,
        "portMappings": [
            {
                "containerPort": config.container_port,
                "protocol": "tcp",
                "name": "http",
            }
        ],
        "environment": env_vars,
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-create-group": "true",
                "awslogs-region": config.region,
                "awslogs-group": config.service_name,
                "awslogs-stream-prefix": config.service_name,
            },
        },
    }
    if efs_mount_path is not None:
        container_spec["mountPoints"] = [
            {"containerPath": efs_mount_path, "sourceVolume": "efs-volume", "readOnly": False}
        ]
    return json.dumps([container_spec])


def create_task_definition(
    config: PlatformConfig,
    ecr_repo: pulumi_aws.ecr.Repository,
    task_role: pulumi_aws.iam.Role,
    exec_role: pulumi_aws.iam.Role,
    container_secrets: list[dict[str, Any]],
    aws_provider: pulumi_aws.Provider,
    efs_filesystem_id: pulumi.Output[str] | None = None,
    efs_access_point_arn: pulumi.Output[str] | None = None,
    efs_mount_path: str = "/mnt/efs",
) -> pulumi_aws.ecs.TaskDefinition:
    """Create ECS Fargate task definition with container from ECR."""
    image_uri = pulumi.Output.concat(ecr_repo.repository_url, ":latest")
    container_def = image_uri.apply(
        lambda uri: _make_container_def(
            uri, config, container_secrets, efs_mount_path=efs_mount_path if efs_filesystem_id else None
        )
    )
    task_def_args: dict[str, Any] = {
        "family": config.service_name,
        "cpu": config.cpu,
        "memory": config.memory,
        "network_mode": "awsvpc",
        "requires_compatibilities": ["FARGATE"],
        "execution_role_arn": exec_role.arn,
        "task_role_arn": task_role.arn,
        "container_definitions": container_def,
    }
    if efs_filesystem_id and efs_access_point_arn:
        task_def_args["volumes"] = [
            pulumi_aws.ecs.TaskDefinitionVolumeArgs(
                name="efs-volume",
                efs_volume_configuration=pulumi_aws.ecs.TaskDefinitionVolumeEfsVolumeConfigurationArgs(
                    file_system_id=efs_filesystem_id,
                    transit_encryption="ENABLED",
                    authorization_config=pulumi_aws.ecs.TaskDefinitionVolumeEfsVolumeConfigurationAuthorizationConfigArgs(
                        access_point_id=efs_access_point_arn,
                        iam="ENABLED",
                    ),
                ),
            ),
        ]
    return pulumi_aws.ecs.TaskDefinition(
        f"{config.service_name}_task",
        opts=pulumi.ResourceOptions(provider=aws_provider),
        **task_def_args,
    )
