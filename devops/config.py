"""Platform.yaml configuration loading and validation."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

import jsonschema
import pulumi
import pulumi_aws
import yaml

from devops.spec.validator import validate_platform_spec


@dataclass
class ComputeConfig:
    type: str = "ecs"
    port: int = 80
    cpu: int = 256
    memory: int = 512
    min_capacity: int = 1
    health_path: str = "/health"


@dataclass
class StorageConfig:
    encrypted: bool = True
    lifecycle_policy: str = "AFTER_30_DAYS"
    access_point_path: str = "/data"
    access_point_uid: int = 1000
    access_point_gid: int = 1000


@dataclass
class CacheConfig:
    engine: str = "redis"
    engine_version: str = "7.1"
    node_type: str = "cache.t3.micro"
    num_nodes: int = 1
    transit_encryption: bool = True
    at_rest_encryption: bool = True


@dataclass
class DatabaseConfig:
    engine: str = "postgres"
    engine_version: str = "16.4"
    instance_class: str = "db.t3.micro"
    allocated_storage: int = 20
    multi_az: bool = False
    backup_retention_days: int = 7
    db_name: str = ""
    db_username: str = ""


@dataclass
class ServiceDiscoveryConfig:
    namespace: str = ""


@dataclass
class LambdaFunctionConfig:
    name: str = ""
    image: str = ""
    memory: int = 2048
    timeout: int = 120
    environment: dict[str, str] | None = None


@dataclass
class LambdaConfig:
    functions: list[LambdaFunctionConfig] = field(default_factory=list)


@dataclass
class WebhookGatewayConfig:
    """Presence of this config means the webhook gateway is enabled."""


@dataclass
class EventBridgeConfig:
    schedule_group: str | None = None


@dataclass
class S3LifecycleRuleConfig:
    prefix: str = ""
    transition_to_ia: int | None = None
    expiration_days: int | None = None


@dataclass
class S3BucketConfig:
    name: str  # Logical name from YAML. Real bucket = {account_id}-{name}.
    versioning: bool = False
    encryption: str = "AES256"
    lifecycle_rules: list[S3LifecycleRuleConfig] = field(default_factory=list)


@dataclass
class S3Config:
    buckets: list[S3BucketConfig] = field(default_factory=list)


@dataclass
class AgentCoreRuntimeDefConfig:
    name: str
    image: str
    description: str = ""
    network_mode: str = "PUBLIC"
    environment_variables: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentCoreAuthorizerConfig:
    type: str = "jwt"
    discovery_url: str = ""
    allowed_audiences: list[str] = field(default_factory=list)
    allowed_clients: list[str] = field(default_factory=list)


@dataclass
class AgentCoreRuntimeConfig:
    runtimes: list[AgentCoreRuntimeDefConfig] = field(default_factory=list)
    authorizer: AgentCoreAuthorizerConfig | None = None


@dataclass
class PlatformConfig:
    """Parsed and validated platform.yaml configuration."""

    service_name: str
    region: str
    raw_spec: dict[str, Any]
    compute: ComputeConfig | None = None
    storage: StorageConfig | None = None
    cache: CacheConfig | None = None
    database: DatabaseConfig | None = None
    service_discovery: ServiceDiscoveryConfig | None = None
    lambda_config: LambdaConfig | None = None
    webhook_gateway: WebhookGatewayConfig | None = None
    eventbridge: EventBridgeConfig | None = None
    s3: S3Config | None = None
    agentcore_runtime: AgentCoreRuntimeConfig | None = None
    secrets: list[str] = field(default_factory=list)

    # Backward-compat: delegate to compute when present
    @property
    def container_port(self) -> int:
        return self.compute.port if self.compute else 80

    @property
    def health_path(self) -> str:
        return self.compute.health_path if self.compute else "/health"

    @property
    def cpu(self) -> str:
        return str(self.compute.cpu) if self.compute else "256"

    @property
    def memory(self) -> str:
        return str(self.compute.memory) if self.compute else "512"

    @property
    def min_capacity(self) -> int:
        return self.compute.min_capacity if self.compute else 1

    @property
    def spec_sections(self) -> dict[str, Any]:
        """Return declared (non-None) spec section names and their config (for registry)."""
        sections = [
            "compute",
            "storage",
            "cache",
            "database",
            "dynamodb",
            "serviceDiscovery",
            "lambda",
            "eventbridge",
            "s3",
            "agentcoreRuntime",
        ]
        return {
            k: self.raw_spec[k]
            for k in sections
            if k in self.raw_spec and self.raw_spec[k] is not None
        }

    @classmethod
    def from_file(cls, path: str) -> "PlatformConfig":
        """Load and validate platform.yaml from file path."""
        if not Path(path).exists():
            raise SystemExit(f"platform.yaml not found: {path}")

        with open(path, encoding="utf-8") as f:
            platform: dict[str, Any] = yaml.safe_load(f)

        try:
            validate_platform_spec(platform)
        except jsonschema.ValidationError as e:
            raise SystemExit(str(e)) from e

        metadata = platform["metadata"]
        spec = platform["spec"]
        aws_config = pulumi.Config("aws")
        region = aws_config.require("region")

        compute = None
        if "compute" in spec and spec["compute"] is not None:
            c = spec["compute"]
            inst = c.get("instances") or {}
            hc = c.get("healthCheck") or {}
            compute = ComputeConfig(
                type=c.get("type", "ecs"),
                port=c.get("port", 80),
                cpu=c.get("cpu", 256),
                memory=c.get("memory", 512),
                min_capacity=inst.get("min", 1),
                health_path=hc.get("path", "/health"),
            )

        storage = None
        if "storage" in spec and spec["storage"] is not None:
            s = spec["storage"]
            efs = s.get("efs") or {}
            ap = efs.get("accessPoint") or {}
            storage = StorageConfig(
                encrypted=efs.get("encrypted", True),
                lifecycle_policy=efs.get("lifecycle", "AFTER_30_DAYS"),
                access_point_path=ap.get("path", "/data"),
                access_point_uid=ap.get("uid", 1000),
                access_point_gid=ap.get("gid", 1000),
            )

        cache = None
        if "cache" in spec and spec["cache"] is not None:
            c = spec["cache"]
            cache = CacheConfig(
                engine=c.get("engine", "redis"),
                node_type=c.get("nodeType", "cache.t3.micro"),
                num_nodes=c.get("numNodes", 1),
            )

        database = None
        if "database" in spec and spec["database"] is not None:
            d = spec["database"]
            database = DatabaseConfig(
                engine=d.get("engine", "postgres"),
                instance_class=d.get("instanceClass", "db.t3.micro"),
                allocated_storage=d.get("allocatedStorage", 20),
            )

        service_discovery = None
        if "serviceDiscovery" in spec and spec["serviceDiscovery"] is not None:
            sd = spec["serviceDiscovery"]
            service_discovery = ServiceDiscoveryConfig(namespace=sd.get("namespace", ""))

        lambda_config = None
        if "lambda" in spec and spec["lambda"] is not None:
            lam = spec["lambda"]
            funcs = lam.get("functions") or []
            lambda_config = LambdaConfig(
                functions=[
                    LambdaFunctionConfig(
                        name=f.get("name", ""),
                        image=f.get("image", ""),
                        memory=f.get("memory", 2048),
                        timeout=f.get("timeout", 120),
                    )
                    for f in funcs
                ]
            )

        webhook_gateway = None
        if "webhookGateway" in spec and spec["webhookGateway"] is not None:
            webhook_gateway = WebhookGatewayConfig()

        eventbridge = None
        if "eventbridge" in spec and spec["eventbridge"] is not None:
            eb = spec["eventbridge"]
            eventbridge = EventBridgeConfig(
                schedule_group=eb.get("scheduleGroup"),
            )

        s3_config = None
        if "s3" in spec and spec["s3"] is not None:
            s3_raw = spec["s3"]
            buckets = []
            for b in s3_raw.get("buckets", []):
                rules = []
                for r in b.get("lifecycleRules", []):
                    rules.append(S3LifecycleRuleConfig(
                        prefix=r.get("prefix", ""),
                        transition_to_ia=r.get("transitionToIA"),
                        expiration_days=r.get("expirationDays"),
                    ))
                buckets.append(S3BucketConfig(
                    name=b["name"],
                    versioning=b.get("versioning", False),
                    encryption=b.get("encryption", "AES256"),
                    lifecycle_rules=rules,
                ))
            s3_config = S3Config(buckets=buckets)

        agentcore_runtime = None
        if "agentcoreRuntime" in spec and spec["agentcoreRuntime"] is not None:
            ac = spec["agentcoreRuntime"]
            runtimes = []
            for rt in ac.get("runtimes", []):
                runtimes.append(AgentCoreRuntimeDefConfig(
                    name=rt["name"],
                    image=rt["image"],
                    description=rt.get("description", ""),
                    network_mode=rt.get("networkMode", "PUBLIC"),
                    environment_variables=rt.get("environmentVariables", {}),
                ))
            authorizer = None
            auth_raw = ac.get("authorizer")
            if auth_raw:
                authorizer = AgentCoreAuthorizerConfig(
                    type=auth_raw.get("type", "jwt"),
                    discovery_url=auth_raw.get("discoveryUrl", ""),
                    allowed_audiences=auth_raw.get("allowedAudiences", []),
                    allowed_clients=auth_raw.get("allowedClients", []),
                )
            agentcore_runtime = AgentCoreRuntimeConfig(
                runtimes=runtimes,
                authorizer=authorizer,
            )

        return cls(
            service_name=metadata["name"],
            region=region,
            raw_spec=spec,
            compute=compute,
            storage=storage,
            cache=cache,
            database=database,
            service_discovery=service_discovery,
            lambda_config=lambda_config,
            webhook_gateway=webhook_gateway,
            eventbridge=eventbridge,
            s3=s3_config,
            agentcore_runtime=agentcore_runtime,
            secrets=spec.get("secrets", []),
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
                "managed-by": "platform-engine",
            }
        ),
    )
