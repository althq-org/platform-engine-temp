"""IAM roles for ECS tasks, Lambda execution, Dispatcher, and agents."""

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


def create_lambda_execution_role(
    service_name: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.iam.Role:
    """Create Lambda execution role with ECR, CloudWatch, EFS, and VPC policy attachments."""
    assume_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                }
            ],
        }
    )
    role = pulumi_aws.iam.Role(
        f"{service_name}_lambda_exec_role",
        name=f"{service_name}-lambda-exec",
        assume_role_policy=assume_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_lambda_ecr",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_lambda_logs",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_lambda_efs",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    vpc_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:CreateNetworkInterface",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DeleteNetworkInterface",
                    ],
                    "Resource": "*",
                }
            ],
        }
    )
    pulumi_aws.iam.RolePolicy(
        f"{service_name}_lambda_vpc_policy",
        role=role.name,
        policy=vpc_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return role


def create_dispatcher_task_role(
    service_name: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.iam.Role:
    """Create Dispatcher ECS task role with ECR, CloudWatch, EFS, and ECS/Scheduler policy attachments."""
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
    role = pulumi_aws.iam.Role(
        f"{service_name}_dispatcher_task_role",
        name=f"{service_name}-dispatcher-task",
        assume_role_policy=assume_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_dispatcher_ecr",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_dispatcher_logs",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_dispatcher_efs",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    ecs_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecs:RunTask",
                        "ecs:StopTask",
                        "ecs:DescribeTasks",
                        "ecs:ListTasks",
                        "iam:PassRole",
                        "scheduler:CreateSchedule",
                        "scheduler:DeleteSchedule",
                        "scheduler:UpdateSchedule",
                        "scheduler:GetSchedule",
                        "scheduler:ListSchedules",
                    ],
                    "Resource": "*",
                }
            ],
        }
    )
    pulumi_aws.iam.RolePolicy(
        f"{service_name}_dispatcher_ecs_policy",
        role=role.name,
        policy=ecs_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return role


def create_agent_task_role(
    service_name: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.iam.Role:
    """Create Agent ECS task role with CloudWatch and EFS policy attachments."""
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
    role = pulumi_aws.iam.Role(
        f"{service_name}_agent_task_role",
        name=f"{service_name}-agent-task",
        assume_role_policy=assume_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_agent_logs",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicyAttachment(
        f"{service_name}_agent_efs",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return role
