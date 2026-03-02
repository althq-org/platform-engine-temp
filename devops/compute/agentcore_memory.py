"""AgentCore Memory instance (Pulumi dynamic resource wrapping boto3)."""

from __future__ import annotations

import json
from typing import Any

import pulumi
import pulumi.dynamic


class _AgentCoreMemoryProvider(pulumi.dynamic.ResourceProvider):
    """Dynamic provider for AgentCore Memory using boto3."""

    def __init__(self, region: str) -> None:
        super().__init__()
        self._region = region

    def _client(self):
        import boto3
        return boto3.client("bedrock-agentcore-control", region_name=self._region)

    def create(self, props: dict[str, Any]) -> pulumi.dynamic.CreateResult:
        client = self._client()
        resp = client.create_memory(
            name=props["name"],
            description=props.get("description", ""),
            memoryExecutionRoleArn=props["memory_execution_role_arn"],
            eventExpiryDuration=props.get("event_expiry_duration", 365),
            memoryStrategies=[
                {
                    "semanticMemoryStrategy": {
                        "name": f"{props['name']}_semantic",
                        "description": "Semantic memory: summarization, fact extraction, preferences",
                        "model": "anthropic.claude-3-haiku-20240307-v1:0",
                        "namespaces": ["default"],
                    }
                }
            ],
        )
        memory_id = resp["memory"]["id"]
        return pulumi.dynamic.CreateResult(
            id_=memory_id,
            outs={
                **props,
                "memory_id": memory_id,
                "memory_arn": resp["memory"]["arn"],
            },
        )

    def read(self, id_: str, props: dict[str, Any]) -> pulumi.dynamic.ReadResult:
        try:
            client = self._client()
            resp = client.get_memory(memoryId=id_)
            return pulumi.dynamic.ReadResult(
                id_=id_,
                outs={
                    **props,
                    "memory_id": id_,
                    "memory_arn": resp["memory"]["arn"],
                },
            )
        except Exception:
            return pulumi.dynamic.ReadResult(id_="", outs={})

    def delete(self, id_: str, props: dict[str, Any]) -> None:
        try:
            client = self._client()
            client.delete_memory(memoryId=id_)
        except Exception:
            pass


class AgentCoreMemory(pulumi.dynamic.Resource):
    """AgentCore Memory instance."""

    memory_id: pulumi.Output[str]
    memory_arn: pulumi.Output[str]

    def __init__(
        self,
        resource_name: str,
        name: str,
        memory_execution_role_arn: pulumi.Input[str],
        region: str,
        description: str = "",
        event_expiry_duration: int = 365,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__(
            _AgentCoreMemoryProvider(region),
            resource_name,
            {
                "name": name,
                "description": description,
                "memory_execution_role_arn": memory_execution_role_arn,
                "event_expiry_duration": event_expiry_duration,
                "memory_id": None,
                "memory_arn": None,
            },
            opts,
        )


def create_agentcore_memory(
    service_name: str,
    memory_role_arn: pulumi.Input[str],
    region: str,
) -> AgentCoreMemory:
    """Create an AgentCore Memory instance with SEMANTIC strategy and 365-day event expiry."""
    return AgentCoreMemory(
        f"{service_name}_agentcore_memory",
        name=f"{service_name}-memory",
        memory_execution_role_arn=memory_role_arn,
        region=region,
        description=f"Shared agent memory for {service_name}",
    )
