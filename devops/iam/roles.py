"""ECS task role and execution role with ECR and CloudWatch attachments."""

import json

import pulumi
import pulumi_aws


def create_task_roles(
    service_name: str,
    aws_provider: pulumi_aws.Provider,
) -> tuple[pulumi_aws.iam.Role, pulumi_aws.iam.Role]:
    """Create ECS task role and execution role with ECR + CloudWatch policy attachments."""
    assume_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                }
            ],
        }
    )

    task_role = pulumi_aws.iam.Role(
        f"{service_name}_task_role",
        name=f"{service_name}-ecs-task",
        assume_role_policy=assume_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_task_ecr",
        role=task_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_task_logs",
        role=task_role.name,
        policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )

    execution_role = pulumi_aws.iam.Role(
        f"{service_name}_exec_role",
        name=f"{service_name}-ecs-exec",
        assume_role_policy=assume_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_exec_ecr",
        role=execution_role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_exec_logs",
        role=execution_role.name,
        policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )

    return task_role, execution_role
