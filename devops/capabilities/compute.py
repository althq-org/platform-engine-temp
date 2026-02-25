"""Compute capability: ECS (ECR, cluster, ALB, DNS, Cloudflare Access, task, service)."""

import os
from typing import Any

import pulumi

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register
from devops.compute.ecr import create_ecr_repository
from devops.compute.ecs_cluster import create_ecs_cluster
from devops.compute.ecs_service import create_ecs_service
from devops.compute.ecs_task import create_task_definition
from devops.loadbalancer.listener_rule import create_listener_rule
from devops.loadbalancer.target_group import create_target_group
from devops.networking.cloudflare_access import create_access_application
from devops.networking.dns import create_dns_record


@register("compute", phase=Phase.COMPUTE)
def compute_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision ECS path: ECR, cluster, target group, listener rule, DNS, Access, task, service.

    Uses foundation outputs: security_groups.compute, iam.task_role, iam.exec_role.
    Section_config is ignored; config comes from ctx.config.
    """
    config = ctx.config
    infra = ctx.infra
    aws_provider = ctx.aws_provider

    security_group = ctx.require("security_groups.compute")
    task_role = ctx.require("iam.task_role")
    exec_role = ctx.require("iam.exec_role")

    ecr_repo = create_ecr_repository(config.service_name, aws_provider)
    cluster = create_ecs_cluster(config.service_name, aws_provider)
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
            pulumi.log.warn(
                f"Secret '{name}' declared in platform.yaml but not found in environment"
            )

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

    service_url = pulumi.Output.from_input(
        f"https://{config.service_name}.{infra.zone_name}"
    )
    ctx.export("service_url", service_url)
    ctx.export("ecr_repository_uri", ecr_repo.repository_url)
    ctx.export("ecs_cluster_name", cluster.name)
    ctx.export("ecs_service_name", ecs_service.name)
