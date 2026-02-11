"""ECS capability: provision containerized service (ECR, ECS cluster, ALB, DNS, Cloudflare Access)."""

from dataclasses import dataclass
import os

import pulumi
import pulumi_aws

from devops.compute.ecr import create_ecr_repository
from devops.compute.ecs_cluster import create_ecs_cluster
from devops.compute.ecs_service import create_ecs_service
from devops.compute.ecs_task import create_task_definition
from devops.config import PlatformConfig
from devops.iam.roles import create_task_roles
from devops.loadbalancer.listener_rule import create_listener_rule
from devops.loadbalancer.target_group import create_target_group
from devops.networking.cloudflare_access import create_access_application
from devops.networking.dns import create_dns_record
from devops.networking.security_groups import create_ecs_security_group
from devops.shared.lookups import SharedInfrastructure


@dataclass
class EcsOutputs:
    """Outputs from the ECS capability for Pulumi exports."""

    service_url: pulumi.Output[str]
    ecr_repository_uri: pulumi.Output[str]
    ecs_cluster_name: pulumi.Output[str]
    ecs_service_name: pulumi.Output[str]


def provision_ecs(
    config: PlatformConfig,
    infra: SharedInfrastructure,
    aws_provider: pulumi_aws.Provider,
) -> EcsOutputs:
    """Provision full ECS path: ECR, cluster, SG, IAM, target group, listener rule, DNS, Access, task, service."""
    ecr_repo = create_ecr_repository(config.service_name, aws_provider)
    cluster = create_ecs_cluster(config.service_name, aws_provider)
    security_group = create_ecs_security_group(
        config.service_name,
        infra.vpc_id,
        infra.vpc_cidr,
        aws_provider,
    )
    task_role, exec_role = create_task_roles(config.service_name, aws_provider)
    target_group = create_target_group(config, infra.vpc_id, aws_provider)
    listener_rule = create_listener_rule(
        config,
        infra.listener_443_arn,
        target_group,
        infra.zone_name,
        aws_provider,
    )
    create_dns_record(
        config.service_name,
        infra.alb_dns_name,
        infra.zone_id,
        infra.cf_provider,
    )
    create_access_application(
        config.service_name,
        infra.zone_id,
        infra.zone_name,
        infra.account_id,
        infra.cf_provider,
    )

    container_secrets: list[dict[str, str]] = []
    for name in config.secrets:
        value = os.environ.get(name)
        if value:
            container_secrets.append({"name": name, "value": value})
            pulumi.log.info(f"Secret '{name}' will be passed to container")
        else:
            pulumi.log.warn(f"Secret '{name}' declared in platform.yaml but not found in environment")

    task_def = create_task_definition(
        config,
        ecr_repo,
        task_role,
        exec_role,
        container_secrets,
        aws_provider,
    )
    ecs_service = create_ecs_service(
        config=config,
        cluster=cluster,
        task_def=task_def,
        target_group=target_group,
        security_group=security_group,
        subnet_ids=infra.private_subnet_ids,
        listener_rule=listener_rule,
        aws_provider=aws_provider,
    )

    service_url = pulumi.Output.from_input(f"https://{config.service_name}.{infra.zone_name}")
    return EcsOutputs(
        service_url=service_url,
        ecr_repository_uri=ecr_repo.repository_url,
        ecs_cluster_name=cluster.name,
        ecs_service_name=ecs_service.name,
    )
