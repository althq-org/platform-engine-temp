# Platform Engine v2 — Technical Design

**Status**: Draft  
**Date**: 2026-02-24  
**Spec**: `platform-engine-v2-spec.md`

---

## 1. Capability Context

The shared context is the central mechanism for cross-capability communication. It replaces the monolithic orchestrator pattern where one function manually wires resources together.

### Implementation

```python
# devops/capabilities/context.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

import pulumi
import pulumi_aws

from devops.config import PlatformConfig
from devops.shared.lookups import SharedInfrastructure


@dataclass
class CapabilityContext:
    config: PlatformConfig
    infra: SharedInfrastructure
    aws_provider: pulumi_aws.Provider
    _outputs: dict[str, Any] = field(default_factory=dict)
    _exports: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """Register a resource output for other capabilities to consume.

        Keys are dotted paths: 'security_groups.database.id', 'storage.efs.filesystem_id'
        """
        self._outputs[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a registered output. Returns default if not found."""
        return self._outputs.get(key, default)

    def require(self, key: str) -> Any:
        """Get a registered output. Raises if not found."""
        if key not in self._outputs:
            raise RuntimeError(
                f"Capability context missing required key '{key}'. "
                f"Available: {sorted(self._outputs.keys())}"
            )
        return self._outputs[key]

    def export(self, key: str, value: Any) -> None:
        """Register a Pulumi export (will be exported at end of run)."""
        self._exports[key] = value

    @property
    def exports(self) -> dict[str, Any]:
        return dict(self._exports)
```

### Key Design Choices

- **Dotted keys** over nested dicts — flat namespace is simpler to query and debug
- **`require()` with clear error** — fails fast with available keys listed, instead of a cryptic `KeyError`
- **Separate `set`/`export`** — internal references (`set`) are different from Pulumi exports (`export`). A security group ID is shared between capabilities but not exported to the user; a Lambda URL is exported to the user.

---

## 2. Capability Registry

### Implementation

```python
# devops/capabilities/registry.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Protocol

from devops.capabilities.context import CapabilityContext


class Phase(IntEnum):
    FOUNDATION = 0      # SGs, IAM (auto-derived)
    INFRASTRUCTURE = 1  # EFS, Redis, RDS, Cloud Map
    COMPUTE = 2         # ECS, Lambda, triggers
    NETWORKING = 3      # ALB rules, DNS, Cloudflare Access


class CapabilityHandler(Protocol):
    def __call__(self, section_config: dict[str, Any], ctx: CapabilityContext) -> None: ...


@dataclass
class CapabilityDef:
    handler: CapabilityHandler
    phase: Phase
    requires: list[str] = field(default_factory=list)


CAPABILITIES: dict[str, CapabilityDef] = {}


def register(name: str, phase: Phase, requires: list[str] | None = None):
    """Decorator to register a capability handler."""
    def decorator(fn: CapabilityHandler) -> CapabilityHandler:
        CAPABILITIES[name] = CapabilityDef(
            handler=fn,
            phase=phase,
            requires=requires or [],
        )
        return fn
    return decorator
```

### Capability Handler Example

```python
# devops/capabilities/storage.py
from devops.capabilities.registry import register, Phase


@register("storage", phase=Phase.INFRASTRUCTURE)
def provision_storage(section_config, ctx):
    from devops.storage.efs import create_efs_filesystem

    sg_id = ctx.require("security_groups.efs.id")

    efs_fs, efs_ap, _mts = create_efs_filesystem(
        service_name=ctx.config.service_name,
        private_subnet_ids=ctx.infra.private_subnet_ids,
        security_group_id=sg_id,
        aws_provider=ctx.aws_provider,
        encrypted=section_config.get("encrypted", True),
        lifecycle_policy=section_config.get("lifecyclePolicy", "AFTER_30_DAYS"),
        access_point_path=section_config.get("accessPoint", {}).get("path", "/data"),
        posix_uid=section_config.get("accessPoint", {}).get("uid", 1000),
        posix_gid=section_config.get("accessPoint", {}).get("gid", 1000),
    )

    ctx.set("storage.efs.filesystem_id", efs_fs.id)
    ctx.set("storage.efs.access_point_arn", efs_ap.arn)
    ctx.export("storage.efs.filesystem_id", efs_fs.id)
```

Every value passed to `create_efs_filesystem` comes from `section_config` (which comes from `platform.yaml`) or `ctx` (which comes from prior capabilities). Nothing is hardcoded.

---

## 3. Foundation Phase (Security Groups + IAM)

Security groups are the trickiest part of the compositional model because they have cross-references. The database SG needs the compute SG's ID to allow traffic. The EFS SG needs both compute and database SG IDs.

### Flat Stack Model Simplifies This

Because of the flat stack model (see spec Section 3.1), the Foundation phase doesn't need to worry about selective access. Every data resource allows traffic from the single compute security group. The logic is: "which resource types are declared?" → create the corresponding SGs with full stack-internal access.

### Approach: Analyze-Then-Create

The Foundation phase inspects which sections are declared and creates the appropriate security group topology.

```python
# devops/capabilities/foundation.py

def provision_foundation(spec_sections: dict[str, Any], ctx: CapabilityContext) -> None:
    """Create security groups and IAM roles based on which capabilities are declared."""
    declared = set(spec_sections.keys())
    service_name = ctx.config.service_name
    vpc_id = ctx.infra.vpc_id

    # Always create a primary compute SG if compute or lambda is declared
    if "compute" in declared or "lambda" in declared:
        from devops.networking.security_groups import create_ecs_security_group
        compute_sg = create_ecs_security_group(
            service_name, vpc_id, ctx.infra.vpc_cidr, ctx.aws_provider,
        )
        ctx.set("security_groups.compute.id", compute_sg.id)

    # Database SG (allows traffic from compute SG — flat model: all compute can reach all data)
    if "database" in declared or "cache" in declared:
        from devops.networking.security_groups import create_database_security_group
        compute_sg_id = ctx.get("security_groups.compute.id")
        db_sg = create_database_security_group(
            service_name, vpc_id,
            control_plane_sg_id=compute_sg_id,
            agent_sg_id=compute_sg_id,
            aws_provider=ctx.aws_provider,
        )
        ctx.set("security_groups.database.id", db_sg.id)

    # EFS SG (allows NFS from compute — flat model: all compute can mount EFS)
    if "storage" in declared:
        from devops.networking.security_groups import create_efs_security_group
        compute_sg_id = ctx.get("security_groups.compute.id")
        efs_sg = create_efs_security_group(
            service_name, vpc_id,
            control_plane_sg_id=compute_sg_id,
            agent_sg_id=compute_sg_id,
            aws_provider=ctx.aws_provider,
        )
        ctx.set("security_groups.efs.id", efs_sg.id)

    # IAM roles — create based on what's needed
    if "compute" in declared:
        from devops.iam.roles import create_task_roles
        task_role, exec_role = create_task_roles(service_name, ctx.aws_provider)
        ctx.set("iam.task_role", task_role)
        ctx.set("iam.exec_role", exec_role)

    if "lambda" in declared:
        from devops.iam.roles import create_lambda_execution_role
        lambda_role = create_lambda_execution_role(service_name, ctx.aws_provider)
        ctx.set("iam.lambda_execution_role", lambda_role)
```

This is intentionally procedural, not over-abstracted. The logic for "which SGs does this combination of sections need" is domain-specific and benefits from being readable, not hidden behind a framework.

---

## 4. Extended PlatformConfig

### Typed Section Dataclasses

```python
# devops/config.py (additions)

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
    type: str = "efs"
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
class TriggersConfig:
    eventbridge_schedule_group: str | None = None
    webhook_gateway: bool = False
```

### Parsing Logic

```python
@classmethod
def from_file(cls, path: str) -> "PlatformConfig":
    # ... existing YAML load + schema validate ...
    spec = platform["spec"]

    compute = None
    if "compute" in spec:
        c = spec["compute"]
        compute = ComputeConfig(
            type=c.get("type", "ecs"),
            port=c.get("port", 80),
            # ... etc
        )

    storage = None
    if "storage" in spec:
        s = spec["storage"]
        ap = s.get("accessPoint", {})
        storage = StorageConfig(
            encrypted=s.get("encrypted", True),
            access_point_path=ap.get("path", "/data"),
            # ... etc
        )

    # ... parse all sections ...

    return cls(
        service_name=metadata["name"],
        region=region,
        compute=compute,
        storage=storage,
        cache=cache,
        database=database,
        # ... etc
        raw_spec=spec,
    )
```

### Backward Compatibility

The old `PlatformConfig` fields (`container_port`, `health_path`, `cpu`, `memory`, `min_capacity`) can become computed properties that delegate to `self.compute`:

```python
@property
def container_port(self) -> int:
    return self.compute.port if self.compute else 80

@property
def health_path(self) -> str:
    return self.compute.health_path if self.compute else "/health"
```

This means existing code that accesses `config.container_port` continues to work during migration.

---

## 5. Refactored `__main__.py`

```python
"""Platform engine entry point. Loads spec, runs capabilities, exports outputs."""

import pulumi

from devops.capabilities.context import CapabilityContext
from devops.capabilities.foundation import provision_foundation
from devops.capabilities.registry import CAPABILITIES, Phase
from devops.config import create_aws_provider, load_platform_config
from devops.shared.lookups import lookup_shared_infrastructure

# Importing capability modules triggers registration via @register decorator
import devops.capabilities.compute   # noqa: F401
import devops.capabilities.storage   # noqa: F401
import devops.capabilities.cache     # noqa: F401
import devops.capabilities.database  # noqa: F401
import devops.capabilities.service_discovery  # noqa: F401
import devops.capabilities.lambda_functions   # noqa: F401
import devops.capabilities.triggers  # noqa: F401

config = load_platform_config()
aws_provider = create_aws_provider(config.service_name, config.region)
infra = lookup_shared_infrastructure(aws_provider)
ctx = CapabilityContext(config, infra, aws_provider)

# Determine which spec sections are declared
declared_sections = {
    k: v for k, v in config.raw_spec.items()
    if k in CAPABILITIES and v is not None
}

# Validate preconditions
for name, cap_def in CAPABILITIES.items():
    if name in declared_sections:
        for req in cap_def.requires:
            if req not in declared_sections:
                raise SystemExit(
                    f"Section '{name}' requires '{req}' to be declared in the spec."
                )

# Phase 0: Foundation (SGs, IAM)
provision_foundation(declared_sections, ctx)

# Phases 1-3: Run capabilities in phase order
for phase in [Phase.INFRASTRUCTURE, Phase.COMPUTE, Phase.NETWORKING]:
    for name, section_config in declared_sections.items():
        cap_def = CAPABILITIES.get(name)
        if cap_def and cap_def.phase == phase:
            cap_def.handler(section_config, ctx)

# Export all registered outputs
for key, value in ctx.exports.items():
    pulumi.export(key, value)
```

Note: the `noqa: F401` imports are the registration mechanism. Importing the module triggers the `@register` decorator, which adds the capability to `CAPABILITIES`. This is a standard Python pattern (used by Flask blueprints, Django apps, etc.).

---

## 6. Schema Updates

The full schema update for `platform-spec-v1.json` is too large to include inline here. The key changes:

### Per-Section Pattern

Every new section follows this pattern:

```json
{
  "sectionName": {
    "type": "object",
    "description": "...",
    "required": ["field1", "field2"],
    "additionalProperties": false,
    "properties": {
      "field1": { "type": "string", "description": "...", "enum": [...] },
      "field2": { "type": "integer", "minimum": 1, "default": 10 }
    }
  }
}
```

Rules:
- `additionalProperties: false` on every leaf section (catches typos)
- `required` lists only truly required fields (everything else has a sensible default)
- `enum` for constrained values (engine types, lifecycle policies)
- `pattern` for format-constrained strings (node types, instance classes)
- `default` in schema matches default in config dataclass (single source of truth)

### `spec` Container

`spec` itself keeps `additionalProperties: true` (forward compatibility — unknown sections are ignored, not rejected). But each *known* section is strictly validated.

---

## 7. File Structure (Target)

```
devops/
├── __main__.py                    # Entry point (thin: load, detect, run)
├── config.py                      # PlatformConfig + all section dataclasses
├── cli.py                         # Platform CLI (list, create, destroy, validate, preview)
├── _scripts.py                    # Dev script entry points
│
├── capabilities/                  # Capability handlers
│   ├── __init__.py
│   ├── context.py                 # CapabilityContext
│   ├── registry.py                # CAPABILITIES dict, @register, Phase enum
│   ├── foundation.py              # Security groups + IAM (auto-derived)
│   ├── compute.py                 # ECS provisioning (refactored from ecs.py)
│   ├── storage.py                 # EFS provisioning
│   ├── cache.py                   # Redis provisioning
│   ├── database.py                # RDS provisioning
│   ├── service_discovery.py       # Cloud Map provisioning
│   ├── lambda_functions.py        # Lambda provisioning
│   └── triggers.py                # EventBridge + webhook gateway
│
├── compute/                       # Resource modules (unchanged)
│   ├── ecr.py
│   ├── ecs_cluster.py
│   ├── ecs_service.py
│   ├── ecs_task.py
│   └── lambda_function.py
│
├── storage/
│   └── efs.py
├── cache/
│   └── redis.py
├── database/
│   └── rds.py
├── triggers/
│   └── eventbridge.py
│
├── networking/
│   ├── security_groups.py
│   ├── service_discovery.py
│   ├── dns.py
│   └── cloudflare_access.py
│
├── loadbalancer/
│   ├── target_group.py
│   └── listener_rule.py
│
├── iam/
│   └── roles.py
│
├── shared/
│   └── lookups.py
│
├── spec/
│   └── validator.py
│
└── schema/
    └── platform-spec-v1.json
```

Changes from current:
- `capabilities/ecs.py` → `capabilities/compute.py` (renamed for consistency)
- `capabilities/agent_factory.py` → removed (split into individual capability handlers)
- New: `capabilities/context.py`, `capabilities/registry.py`, `capabilities/foundation.py`
- New: individual capability handlers for storage, cache, database, etc.

The resource modules (`compute/`, `storage/`, `cache/`, etc.) remain **unchanged**. They're already well-structured pure functions. Only the wiring layer (capabilities + __main__) changes.

---

## 8. Migration Implementation Order

### Step 1: Schema + Config (safe, no behavior change)

1. Tighten `platform-spec-v1.json` with full field definitions for all sections
2. Add section dataclasses to `config.py`
3. Extend `PlatformConfig.from_file()` to parse all sections
4. Add backward-compat properties for old field names
5. Add schema tests for all fixtures
6. Add config parsing tests for all section types
7. Run `uv run test` — all existing tests pass

### Step 2: Context + Registry (additive, no behavior change)

1. Create `capabilities/context.py`
2. Create `capabilities/registry.py`
3. Existing capabilities still work (not yet registered)
4. Run `uv run test`

### Step 3: Refactor ECS capability (behavior-preserving)

1. Create `capabilities/compute.py` using `@register("compute", phase=Phase.COMPUTE)`
2. It calls the same module functions as `capabilities/ecs.py`
3. It reads from `section_config` (backed by the new `ComputeConfig`)
4. Refactor `__main__.py` to use registry when ECS capability is registered
5. Run `uv run test` + manually verify ECS fixture still works

### Step 4: Individual capability handlers

1. Create `capabilities/storage.py`, `cache.py`, `database.py`, `service_discovery.py`, `lambda_functions.py`, `triggers.py`
2. Each reads from context, calls module functions, registers outputs
3. Add unit tests for each capability handler
4. Create `capabilities/foundation.py` for SG/IAM auto-derivation

### Step 5: Wire up and remove old code

1. Update `__main__.py` to the target (Section 5 above)
2. Remove `capabilities/ecs.py` (replaced by `capabilities/compute.py`)
3. Remove `capabilities/agent_factory.py` (replaced by individual handlers)
4. Remove `PLATFORM_CAPABILITY` env var handling
5. Verify both fixtures work end-to-end

### Step 6: Module tests

1. Add unit tests for: `lambda_function.py`, `efs.py`, `redis.py`, `rds.py`, `service_discovery.py`, `eventbridge.py`
2. Add unit tests for new SG functions and IAM role functions
3. Target: >80% coverage

### Step 7: CLI + Docs

1. Add `platform validate` command
2. Add `platform preview` command
3. Update `README.md`

---

## 9. Testing Approach

### Module Tests (existing pattern, extend to all modules)

```python
@patch("devops.storage.efs.pulumi_aws.efs.FileSystem")
@patch("devops.storage.efs.pulumi_aws.efs.AccessPoint")
@patch("devops.storage.efs.pulumi_aws.efs.MountTarget")
def test_create_efs_filesystem(mock_mt, mock_ap, mock_fs):
    mock_fs.return_value.id = "fs-123"
    mock_ap.return_value.arn = "arn:aws:efs:..."
    aws_provider = MagicMock()

    fs, ap, mts = create_efs_filesystem(
        "my-service", ["subnet-1", "subnet-2"], MagicMock(), aws_provider,
    )

    assert fs.id == "fs-123"
    call_kw = mock_fs.call_args[1]
    assert call_kw["encrypted"] is True
    assert call_kw["throughput_mode"] == "elastic"
```

### Capability Tests (new)

```python
def test_storage_capability_reads_from_config():
    """Storage capability passes config values to create_efs_filesystem."""
    ctx = make_test_context()
    ctx.set("security_groups.efs.id", MagicMock())

    section_config = {
        "encrypted": False,
        "lifecyclePolicy": "AFTER_7_DAYS",
        "accessPoint": {"path": "/custom", "uid": 2000, "gid": 2000},
    }

    with patch("devops.capabilities.storage.create_efs_filesystem") as mock:
        mock.return_value = (MagicMock(), MagicMock(), [])
        provision_storage(section_config, ctx)

    call_kw = mock.call_args[1]
    assert call_kw["encrypted"] is False
    assert call_kw["lifecycle_policy"] == "AFTER_7_DAYS"
    assert call_kw["access_point_path"] == "/custom"
    assert call_kw["posix_uid"] == 2000
```

### Schema Tests (extend)

```python
def test_all_fixtures_validate():
    """Every YAML file in fixtures/ must pass schema validation."""
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures"
    for fixture_path in fixture_dir.glob("*.yaml"):
        with open(fixture_path) as f:
            data = yaml.safe_load(f)
        validate_platform_spec(data)  # should not raise


def test_cache_rejects_invalid_node_type():
    data = valid_spec_with(cache={"engine": "redis", "nodeType": "wrong.t3.micro"})
    with pytest.raises(Exception, match="pattern"):
        validate_platform_spec(data)


def test_cache_rejects_unknown_fields():
    data = valid_spec_with(cache={"engine": "redis", "nodeType": "cache.t3.micro", "flavor": "chocolate"})
    with pytest.raises(Exception, match="additionalProperties"):
        validate_platform_spec(data)
```

---

## 10. Open Questions

| # | Question | Default / Recommendation |
|---|----------|--------------------------|
| 1 | Should `kind` accept values other than `Service`? | Keep `Service` only for v1. The composability makes kind mostly irrelevant — a "service" can be simple or complex based on which sections it declares. |
| 2 | Should capability registration use decorators or explicit dict? | Decorators (`@register`) are more Pythonic and self-documenting but require importing modules for side effects. Explicit dict is simpler to reason about. Recommend decorators for developer experience. |
| 3 | Should the Foundation phase be a capability or special-cased? | Special-cased. SG/IAM logic is cross-cutting and depends on the *combination* of declared sections, not a single section's config. |
| 4 | Should we support `platform.yaml` with NO `compute` section? | Yes, for infrastructure-only stacks (just storage + cache). Remove `compute` from the schema's `required` list. |
| 5 | When should `additionalProperties: true` be kept on `spec`? | Keep it. Unknown sections should be silently ignored (forward compat). But known sections are strictly validated. |
