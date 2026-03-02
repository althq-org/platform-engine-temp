"""AgentCore Runtime definition (Pulumi dynamic resource wrapping boto3)."""

from __future__ import annotations

from typing import Any

import pulumi
import pulumi.dynamic


class _AgentCoreRuntimeProvider(pulumi.dynamic.ResourceProvider):
    """Dynamic provider for AgentCore Runtime using boto3."""

    def __init__(self, region: str) -> None:
        super().__init__()
        self._region = region

    def _client(self):
        import boto3
        return boto3.client("bedrock-agentcore-control", region_name=self._region)

    def create(self, props: dict[str, Any]) -> pulumi.dynamic.CreateResult:
        client = self._client()

        network_config: dict[str, Any] = {
            "networkMode": props.get("network_mode", "PUBLIC"),
        }
        if props.get("network_mode") == "VPC":
            vpc_config: dict[str, Any] = {}
            if props.get("subnet_ids"):
                vpc_config["subnetIds"] = props["subnet_ids"]
            if props.get("security_group_ids"):
                vpc_config["securityGroupIds"] = props["security_group_ids"]
            if vpc_config:
                network_config["vpcConfig"] = vpc_config

        create_args: dict[str, Any] = {
            "agentRuntimeName": props["runtime_name"],
            "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": props["image_uri"]}},
            "roleArn": props["role_arn"],
            "networkConfiguration": network_config,
        }

        env_vars = props.get("environment_variables") or {}
        if env_vars:
            create_args["environmentVariables"] = env_vars

        if props.get("description"):
            create_args["description"] = props["description"]

        if props.get("authorizer"):
            auth = props["authorizer"]
            if auth.get("discovery_url"):
                create_args["authorizerConfiguration"] = {
                    "customJWTAuthorizer": {
                        "discoveryUrl": auth["discovery_url"],
                        "allowedAudiences": auth.get("allowed_audiences", []),
                        "allowedClients": auth.get("allowed_clients", []),
                    }
                }

        resp = client.create_agent_runtime(**create_args)
        runtime_id = resp["agentRuntimeId"]
        runtime_arn = resp["agentRuntimeArn"]

        return pulumi.dynamic.CreateResult(
            id_=runtime_id,
            outs={
                **props,
                "agent_runtime_id": runtime_id,
                "agent_runtime_arn": runtime_arn,
            },
        )

    def read(self, id_: str, props: dict[str, Any]) -> pulumi.dynamic.ReadResult:
        try:
            client = self._client()
            resp = client.get_agent_runtime(agentRuntimeId=id_)
            return pulumi.dynamic.ReadResult(
                id_=id_,
                outs={
                    **props,
                    "agent_runtime_id": id_,
                    "agent_runtime_arn": resp["agentRuntimeArn"],
                },
            )
        except Exception:
            return pulumi.dynamic.ReadResult(id_="", outs={})

    def update(
        self, id_: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> pulumi.dynamic.UpdateResult:
        client = self._client()

        update_args: dict[str, Any] = {
            "agentRuntimeId": id_,
            "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": new_props["image_uri"]}},
        }

        env_vars = new_props.get("environment_variables") or {}
        if env_vars:
            update_args["environmentVariables"] = env_vars

        if new_props.get("description"):
            update_args["description"] = new_props["description"]

        client.update_agent_runtime(**update_args)

        return pulumi.dynamic.UpdateResult(outs={
            **new_props,
            "agent_runtime_id": id_,
            "agent_runtime_arn": old_props.get("agent_runtime_arn", ""),
        })

    def delete(self, id_: str, props: dict[str, Any]) -> None:
        try:
            client = self._client()
            client.delete_agent_runtime(agentRuntimeId=id_)
        except Exception:
            pass


class AgentCoreRuntime(pulumi.dynamic.Resource):
    """AgentCore Runtime definition."""

    agent_runtime_id: pulumi.Output[str]
    agent_runtime_arn: pulumi.Output[str]

    def __init__(
        self,
        resource_name: str,
        runtime_name: str,
        image_uri: pulumi.Input[str],
        role_arn: pulumi.Input[str],
        region: str,
        network_mode: str = "PUBLIC",
        environment_variables: dict[str, str] | None = None,
        description: str = "",
        authorizer: dict[str, Any] | None = None,
        subnet_ids: list[str] | None = None,
        security_group_ids: list[str] | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__(
            _AgentCoreRuntimeProvider(region),
            resource_name,
            {
                "runtime_name": runtime_name,
                "image_uri": image_uri,
                "role_arn": role_arn,
                "network_mode": network_mode,
                "environment_variables": environment_variables or {},
                "description": description,
                "authorizer": authorizer,
                "subnet_ids": subnet_ids,
                "security_group_ids": security_group_ids,
                "agent_runtime_id": None,
                "agent_runtime_arn": None,
            },
            opts,
        )


def create_agentcore_runtime(
    service_name: str,
    runtime_name: str,
    image_uri: pulumi.Input[str],
    role_arn: pulumi.Input[str],
    region: str,
    network_mode: str = "PUBLIC",
    environment_variables: dict[str, str] | None = None,
    memory_id: pulumi.Input[str] | None = None,
    description: str = "",
    authorizer: dict[str, Any] | None = None,
    subnet_ids: list[str] | None = None,
    security_group_ids: list[str] | None = None,
) -> AgentCoreRuntime:
    """Create an AgentCore Runtime definition."""
    env_vars = dict(environment_variables or {})
    if memory_id is not None:
        env_vars["AGENTCORE_MEMORY_ID"] = memory_id

    return AgentCoreRuntime(
        f"{service_name}_{runtime_name}_agentcore_runtime",
        runtime_name=runtime_name,
        image_uri=image_uri,
        role_arn=role_arn,
        region=region,
        network_mode=network_mode,
        environment_variables=env_vars,
        description=description,
        authorizer=authorizer,
        subnet_ids=subnet_ids,
        security_group_ids=security_group_ids,
    )
