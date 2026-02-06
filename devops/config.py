"""Platform.yaml configuration loading and validation."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import pulumi
import pulumi_aws
import yaml


@dataclass
class PlatformConfig:
    """Parsed and validated platform.yaml configuration."""

    service_name: str
    container_port: int
    health_path: str
    cpu: str
    memory: str
    min_capacity: int
    secrets: list[str]
    region: str

    @classmethod
    def from_file(cls, path: str) -> "PlatformConfig":
        """Load and validate platform.yaml from file path."""
        if not Path(path).exists():
            raise SystemExit(f"platform.yaml not found: {path}")

        with open(path, encoding="utf-8") as f:
            platform: dict[str, Any] = yaml.safe_load(f)

        metadata = platform["metadata"]
        spec = platform["spec"]
        compute = spec["compute"]

        aws_config = pulumi.Config("aws")
        region = aws_config.require("region")

        return cls(
            service_name=metadata["name"],
            container_port=compute.get("port", 80),
            health_path=compute.get("healthCheck", {}).get("path", "/health"),
            cpu=str(compute.get("cpu", 256)),
            memory=str(compute.get("memory", 512)),
            min_capacity=compute.get("instances", {}).get("min", 1),
            secrets=spec.get("secrets", []),
            region=region,
        )


def load_platform_config() -> PlatformConfig:
    """Load platform.yaml from PLATFORM_YAML_PATH environment variable."""
    path = os.environ.get("PLATFORM_YAML_PATH")
    if not path:
        raise SystemExit("PLATFORM_YAML_PATH environment variable required")
    if not Path(path).exists():
        raise SystemExit("PLATFORM_YAML_PATH must point to platform.yaml")
    return PlatformConfig.from_file(path)


def create_aws_provider(service_name: str, region: str) -> pulumi_aws.Provider:
    """Create AWS provider with default resource tags."""
    return pulumi_aws.Provider(
        "aws-tagged",
        region=region,
        default_tags=pulumi_aws.ProviderDefaultTagsArgs(
            tags={
                "service": service_name,
                "platform-engine-managed": "true",
            }
        ),
    )
