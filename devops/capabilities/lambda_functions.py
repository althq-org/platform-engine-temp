"""Lambda capability: container-image Lambdas with VPC, EFS, and Function URLs."""

from typing import Any

import pulumi

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register
from devops.compute.ecr import create_ecr_repository
from devops.compute.lambda_function import create_lambda_function


@register("lambda", phase=Phase.COMPUTE, requires=["storage"])
def lambda_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision Lambdas from spec.lambda.functions; requires storage (EFS access point)."""
    functions = section_config.get("functions", [])
    if not functions:
        return

    service_name = ctx.config.service_name
    aws_provider = ctx.aws_provider
    private_subnet_ids = ctx.infra.private_subnet_ids

    security_group_id = ctx.require("security_groups.compute.id")
    execution_role = ctx.require("iam.lambda_execution_role")
    efs_access_point_arn = ctx.require("storage.efs.access_point_arn")

    for fn in functions:
        name = fn["name"]
        image = fn["image"]
        memory_size = fn.get("memory", 2048)
        timeout = fn.get("timeout", 120)

        repo_name = f"{service_name}-{image}"
        repo = create_ecr_repository(repo_name, aws_provider)
        image_uri = pulumi.Output.concat(repo.repository_url, ":latest")

        _fn, function_url = create_lambda_function(
            service_name=service_name,
            function_name=name,
            ecr_image_uri=image_uri,
            execution_role=execution_role,
            subnet_ids=private_subnet_ids,
            security_group_id=security_group_id,
            efs_access_point_arn=efs_access_point_arn,
            efs_mount_path="/mnt/efs",
            aws_provider=aws_provider,
            memory_size=memory_size,
            timeout=timeout,
        )

        ctx.set(f"lambda.{name}.url", function_url.function_url)
        export_key = f"lambda_{name.replace('-', '_')}_url"
        ctx.export(export_key, function_url.function_url)
