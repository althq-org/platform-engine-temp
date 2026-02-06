"""ALB listener rule: hostname -> target group (priority from hash)."""

import hashlib

import pulumi
import pulumi_aws

from devops.config import PlatformConfig


def _listener_rule_priority(service_name: str) -> int:
    """Stable priority 200-90200 from service name hash."""
    return 200 + (int(hashlib.md5(service_name.encode()).hexdigest()[:4], 16) % 90000)


def create_listener_rule(
    config: PlatformConfig,
    listener_443_arn: str,
    target_group: pulumi_aws.lb.TargetGroup,
    zone_name: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.lb.ListenerRule:
    """Create listener rule: host header service_name.zone_name -> target group."""
    hostname = f"{config.service_name}.{zone_name}"
    hostname_output = pulumi.Output.from_input(hostname)
    conditions = hostname_output.apply(
        lambda h: [
            pulumi_aws.lb.ListenerRuleConditionArgs(
                host_header=pulumi_aws.lb.ListenerRuleConditionHostHeaderArgs(values=[h]),
            )
        ]
    )
    return pulumi_aws.lb.ListenerRule(
        f"{config.service_name}_rule",
        listener_arn=listener_443_arn,
        priority=_listener_rule_priority(config.service_name),
        actions=[
            pulumi_aws.lb.ListenerRuleActionArgs(
                type="forward",
                target_group_arn=target_group.arn,
            )
        ],
        conditions=conditions,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
