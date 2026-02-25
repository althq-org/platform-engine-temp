"""EventBridge Scheduler group and IAM role for agent triggers."""

import json

import pulumi
import pulumi_aws


def create_eventbridge_scheduler(
    service_name: str,
    aws_provider: pulumi_aws.Provider,
) -> tuple[pulumi_aws.scheduler.ScheduleGroup, pulumi_aws.iam.Role]:
    schedule_group = pulumi_aws.scheduler.ScheduleGroup(
        f"{service_name}_schedule_group",
        name=f"{service_name}-schedules",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    assume_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "scheduler.amazonaws.com"},
                }
            ],
        }
    )
    eventbridge_role = pulumi_aws.iam.Role(
        f"{service_name}_eventbridge_role",
        name=f"{service_name}-eventbridge-scheduler",
        assume_role_policy=assume_policy,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.iam.RolePolicy(
        f"{service_name}_eventbridge_policy",
        role=eventbridge_role.name,
        policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "lambda:InvokeFunction",
                        "Effect": "Allow",
                        "Resource": "*",
                    }
                ],
            }
        ),
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return schedule_group, eventbridge_role
