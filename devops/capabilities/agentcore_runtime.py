"""AgentCore Runtime capability: managed microVM agent compute with bundled Memory."""

import base64
import json
import os
from typing import Any

import boto3
import pulumi
import pulumi_aws

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("agentcoreRuntime", phase=Phase.INFRASTRUCTURE, after=["s3", "dynamodb"])
def agentcore_runtime_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision AgentCore runtimes, ECR repos, Memory, and cross-capability IAM."""
    from devops.compute.agentcore_memory import create_agentcore_memory
    from devops.compute.agentcore_runtime import create_agentcore_runtime
    from devops.compute.ecr import create_ecr_repository

    service_name = ctx.config.service_name
    region = ctx.config.region
    aws_provider = ctx.aws_provider
    agentcore_role = ctx.require("iam.agentcore_runtime_role")

    memory_role = ctx.require("iam.agentcore_memory_role")
    memory = create_agentcore_memory(
        service_name=service_name,
        memory_role_arn=memory_role.arn,
        region=region,
    )
    ctx.set("agentcore.memory.id", memory.memory_id)
    ctx.export("agentcore_memory_id", memory.memory_id)

    # Seed task env outputs with memory ID so compute picks it up
    task_env_outputs: dict[str, Any] = {"AGENTCORE_MEMORY_ID": memory.memory_id}

    _grant_memory_access(ctx, agentcore_role, memory.memory_arn, service_name)

    bucket_arns = ctx.get("s3.bucket_arns")
    if bucket_arns:
        _grant_s3_access(ctx, agentcore_role, bucket_arns, service_name)

    secrets_env = _resolve_secrets(ctx.config.secrets, ctx.config.region)

    runtimes_config: list[dict[str, Any]] = section_config.get("runtimes") or []
    authorizer_config = section_config.get("authorizer")

    authorizer_dict = None
    if authorizer_config:
        authorizer_dict = {
            "discovery_url": authorizer_config.get("discoveryUrl", ""),
            "allowed_audiences": authorizer_config.get("allowedAudiences", []),
            "allowed_clients": authorizer_config.get("allowedClients", []),
        }

    for rt in runtimes_config:
        image_name: str = rt["image"]
        repo_name = f"{service_name}-{image_name}"
        ecr_repo = create_ecr_repository(repo_name, aws_provider)
        image_tag = os.environ.get("DEPLOY_IMAGE_TAG", "latest")
        image_uri = pulumi.Output.concat(ecr_repo.repository_url, f":{image_tag}")

        env_vars = {
            **rt.get("environmentVariables", {}),
            **secrets_env,
        }

        bucket_env_vars = ctx.get("s3.bucket_env_vars")
        if bucket_env_vars:
            env_vars.update(bucket_env_vars)

        runtime = create_agentcore_runtime(
            service_name=service_name,
            runtime_name=rt["name"],
            image_uri=image_uri,
            role_arn=agentcore_role.arn,
            region=region,
            network_mode=rt.get("networkMode", "PUBLIC"),
            environment_variables=env_vars,
            memory_id=memory.memory_id,
            description=rt.get("description", ""),
            authorizer=authorizer_dict,
            subnet_ids=ctx.infra.private_subnet_ids if rt.get("networkMode") == "VPC" else None,
            security_group_ids=[ctx.get("security_groups.agentcore.id")] if rt.get("networkMode") == "VPC" else None,
        )

        ctx.set(f"agentcore.runtimes.{rt['name']}.arn", runtime.agent_runtime_arn)
        ctx.export(
            f"agentcore_runtime_{rt['name'].replace('-', '_')}_arn",
            runtime.agent_runtime_arn,
        )
        ctx.export(f"ecr_{image_name.replace('-', '_')}_uri", ecr_repo.repository_url)
        # First runtime becomes the primary ARN injected into the ECS task
        if "AGENTCORE_RUNTIME_ARN" not in task_env_outputs:
            task_env_outputs["AGENTCORE_RUNTIME_ARN"] = runtime.agent_runtime_arn

    # Expose all agentcore outputs as task env vars so compute picks them up
    ctx.set("agentcore.task_env_outputs", task_env_outputs)

    task_role = ctx.get("iam.task_role")
    if task_role is not None:
        _grant_invoke_permission(ctx, task_role, agentcore_role, service_name)


def _resolve_secrets(
    secrets_config: list[str] | dict[str, dict[str, str]],
    region: str,
) -> dict[str, str]:
    """Resolve secrets to plaintext key-value pairs.

    Legacy format (list of names): reads values from environment variables.
    KMS-encrypted format (dict): decrypts values for the current Pulumi stack environment.
    """
    if isinstance(secrets_config, list):
        return {
            name: value
            for name in secrets_config
            if (value := os.environ.get(name))
        }

    if not secrets_config:
        return {}

    environment = pulumi.get_stack().split(".")[0]
    kms = boto3.client("kms", region_name=region)
    result: dict[str, str] = {}

    for secret_name, env_values in secrets_config.items():
        encrypted = env_values.get(environment)
        if not encrypted:
            pulumi.log.warn(
                f"Secret '{secret_name}' has no value for environment '{environment}'"
            )
            continue
        response = kms.decrypt(CiphertextBlob=base64.b64decode(encrypted))
        result[secret_name] = response["Plaintext"].decode("utf-8")

    return result


def _grant_s3_access(
    ctx: CapabilityContext,
    role: pulumi_aws.iam.Role,
    bucket_arns: list[Any],
    service_name: str,
) -> None:
    """Attach an inline policy granting s3:* on bucket ARNs to the AgentCore role."""
    policy_doc = pulumi.Output.all(*bucket_arns).apply(
        lambda arns: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:*",
                        "Resource": arns + [f"{arn}/*" for arn in arns],
                    }
                ],
            }
        )
    )
    pulumi_aws.iam.RolePolicy(
        f"{service_name}_s3_agentcore_policy",
        role=role.name,
        policy=policy_doc,
        opts=pulumi.ResourceOptions(provider=ctx.aws_provider),
    )


def _grant_memory_access(
    ctx: CapabilityContext,
    role: pulumi_aws.iam.Role,
    memory_arn: pulumi.Output[str],
    service_name: str,
) -> None:
    """Grant the AgentCore role access to the Memory instance."""
    policy_doc = memory_arn.apply(
        lambda arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "bedrock-agentcore:*",
                        "Resource": arn,
                    }
                ],
            }
        )
    )
    pulumi_aws.iam.RolePolicy(
        f"{service_name}_agentcore_memory_policy",
        role=role.name,
        policy=policy_doc,
        opts=pulumi.ResourceOptions(provider=ctx.aws_provider),
    )


def _grant_invoke_permission(
    ctx: CapabilityContext,
    task_role: pulumi_aws.iam.Role,
    agentcore_role: pulumi_aws.iam.Role,
    service_name: str,
) -> None:
    """Grant ECS task role permission to invoke AgentCore runtimes and pass the AgentCore role."""
    policy_doc = agentcore_role.arn.apply(
        lambda role_arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "bedrock-agentcore:InvokeAgentRuntime",
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": "iam:PassRole",
                        "Resource": role_arn,
                    },
                ],
            }
        )
    )
    pulumi_aws.iam.RolePolicy(
        f"{service_name}_agentcore_invoke_policy",
        role=task_role.name,
        policy=policy_doc,
        opts=pulumi.ResourceOptions(provider=ctx.aws_provider),
    )
