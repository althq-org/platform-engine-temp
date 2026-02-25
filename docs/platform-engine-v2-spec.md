# Platform Engine v2 — Specification

**Status**: Draft  
**Author**: AI Architect  
**Date**: 2026-02-24  
**Related**: `design-decisions.md`, `spec.md`, `platform-engine-v2-design.md`

---

## 1. Problem Statement

The platform engine exists to let developers declare what infrastructure they need in a `platform.yaml` file and have it provisioned automatically. Today it does this well for one pattern: ECS services with ALB + DNS + Cloudflare Access.

But when we extended it for the Agent Factory (EFS, Redis, RDS, Lambda, Cloud Map, EventBridge), we introduced structural problems:

1. **Capability routing via environment variable** — `PLATFORM_CAPABILITY=agent-factory` bypasses the spec. The developer must know out-of-band which orchestrator to invoke, defeating the purpose of a declarative spec.
2. **Hollow schema** — New sections (`storage`, `cache`, `database`, `serviceDiscovery`, `triggers`, `lambda`) accept `additionalProperties: true` with zero validation. You can write `cache: { flavor: chocolate }` and it passes.
3. **Broken config pipeline** — `PlatformConfig` only parses `compute`. The agent factory orchestrator hardcodes all values instead of reading them from the fixture. The YAML is decorative.
4. **Monolithic capability orchestrators** — `agent_factory.py` is a 150-line function that hardcodes which resources to create. If someone wants EFS + Redis but not RDS, they can't. If someone wants Lambda for a non-agent-factory project, they must write a new orchestrator.
5. **No tests for new modules** — 6 new modules and 3 extended modules have zero test coverage.
6. **No cross-capability wiring** — Security groups created by one capability are manually threaded to others inside monolithic orchestrators. There's no shared context.

The engine's original design principles are sound. The problem is that we didn't follow them when extending.

---

## 2. Vision

The platform engine is a **declarative infrastructure platform**. You describe what you need; it provisions it.

### Principles (unchanged from v1, but now enforced)

| Principle | What It Means | Current State |
|-----------|---------------|---------------|
| **Spec as contract** | `platform.yaml` is the single source of truth. Nothing is provisioned that isn't in the spec. Nothing outside the spec drives provisioning. | Violated: env var routing, hardcoded values |
| **Validated before provisioning** | The JSON Schema catches errors before any resource is created. | Violated: new sections have no validation |
| **Capability-based** | The engine runs only the capabilities implied by the spec. | Violated: monolithic orchestrators, env var dispatch |
| **Additive evolution** | New optional sections, never breaking changes. New `apiVersion` for breaking changes. | Followed |
| **Function/layer organization** | Code grouped by function (compute, networking, storage), not vendor. | Followed |
| **Shared infra is looked up, not created** | VPC, ALB, Cloudflare zone are pre-existing. The engine creates per-service resources. | Followed |

### New Principles (v2)

| Principle | What It Means |
|-----------|---------------|
| **Compositional capabilities** | Each spec section maps to an independent capability. Capabilities compose; you mix and match by declaring sections in YAML. |
| **Flat stack model** | One `platform.yaml` = one stack = one of each resource type. Everything in the stack can see everything else. If you need selective access between resources, use multiple stacks. |
| **Config flows from spec** | Every module argument originates from `platform.yaml`, through typed config, to resource creation. No hardcoded values. |
| **Capabilities share context** | Resources created by one capability (SG IDs, ARNs) are available to dependent capabilities via a shared context bag. |
| **Every capability has tests** | No module ships without unit tests that mock Pulumi resources and verify arguments. |
| **Workspace-friendly** | Rules, skills, and documentation guide the next developer to extend the engine correctly. |

---

## 3. Architecture

### 3.1 The Flat Stack Model

Each `platform.yaml` provisions one isolated stack. Within a stack, every resource has access to every other resource. There is one security group topology per stack — compute can reach storage, cache, and database; storage is reachable by compute; etc.

This is a deliberate simplification. The engine does NOT support:
- Multiple databases in one spec (one `database` section, not an array)
- Selective access (ECS A talks to DB A but not DB B)
- Fine-grained security group wiring between individual resources

If an application needs multiple databases or selective access between resources, it should use **multiple stacks** — each with its own `platform.yaml`. Cross-stack communication goes through Cloud Map, explicit endpoints, or VPC-internal networking.

**Why**: The engine's value is that you don't think about security groups, IAM roles, or wiring. You declare what you need; the engine creates a secure-by-default topology for the whole stack. Introducing per-resource wiring would make the spec as complex as Terraform, defeating the purpose.

**Escape hatch**: If someone genuinely needs multi-resource wiring in a single stack, we assess the use case and decide whether the engine should evolve or whether multiple stacks is the right answer.

### 3.2 Shared Infrastructure

The engine runs within an existing VPC with shared resources (ALB, subnets, Cloudflare zone). These are discovered at runtime via tag lookups and name lookups — the same pattern used by all other services in the organization.

Shared infra lookup (`devops/shared/lookups.py`) finds:
- **VPC**: via private subnets tagged `network=private`
- **ALB**: by name `product-external-alb`
- **HTTPS listener**: port 443 on the ALB
- **Cloudflare zone**: from SSM parameters (`/cloudflare/zone_id`, `/cloudflare/platform_infra_token`)

This pattern is established across the org. The engine does not create or manage shared infrastructure — it only creates per-service resources within the shared environment.

### 3.3 Execution Model

Today:
```
__main__.py → env var → monolithic orchestrator → hardcoded resources
```

Target:
```
__main__.py → parse spec → detect sections → run matching capabilities in order → export outputs
```

The entry point reads `platform.yaml`, determines which sections are declared, and runs the corresponding capability for each section. No env var. No monolithic orchestrator.

### 3.4 Capability Registry

A capability is a Python module that:
1. Reads its section config from the parsed spec
2. Receives a shared context containing outputs from prior capabilities and shared infrastructure
3. Creates resources via the existing module functions (EFS, Redis, etc.)
4. Registers its outputs (resource IDs, ARNs, endpoints) in the shared context

```python
# devops/capabilities/registry.py

CAPABILITIES: dict[str, CapabilityDef] = {
    "compute":          CapabilityDef(handler=provision_compute, phase=Phase.COMPUTE),
    "storage":          CapabilityDef(handler=provision_storage, phase=Phase.INFRASTRUCTURE),
    "cache":            CapabilityDef(handler=provision_cache, phase=Phase.INFRASTRUCTURE),
    "database":         CapabilityDef(handler=provision_database, phase=Phase.INFRASTRUCTURE),
    "serviceDiscovery": CapabilityDef(handler=provision_service_discovery, phase=Phase.INFRASTRUCTURE),
    "triggers":         CapabilityDef(handler=provision_triggers, phase=Phase.COMPUTE),
    "lambda":           CapabilityDef(handler=provision_lambda, phase=Phase.COMPUTE),
}
```

### 3.5 Execution Phases

Capabilities run in dependency order, grouped by phase:

| Phase | Order | What It Creates | Example Sections |
|-------|-------|-----------------|------------------|
| **Foundation** | 1 | Security groups, IAM roles | (auto-derived from other sections) |
| **Infrastructure** | 2 | Persistent resources: storage, databases, caches, service discovery | `storage`, `cache`, `database`, `serviceDiscovery` |
| **Compute** | 3 | Things that run: ECS services, Lambda functions, triggers | `compute`, `lambda`, `triggers` |
| **Networking** | 4 | Things that expose: load balancer rules, DNS, Cloudflare Access | (auto-derived from `compute`) |

The Foundation and Networking phases are implicit — the engine derives what's needed from the declared capabilities. Because of the flat stack model, the Foundation phase is simple: it creates one set of security groups for the stack based on which resource types are declared, and every compute resource gets access to every data resource.

### 3.6 Shared Context

```python
@dataclass
class CapabilityContext:
    """Shared bag for cross-capability references."""
    config: PlatformConfig
    infra: SharedInfrastructure
    aws_provider: pulumi_aws.Provider
    outputs: dict[str, Any]  # e.g. "storage.efs.filesystem_id", "security_groups.database.id"

    def set(self, key: str, value: Any) -> None: ...
    def get(self, key: str) -> Any: ...
    def require(self, key: str) -> Any: ...  # raises if missing
```

Security groups are a special case. They need cross-references (database SG allows traffic from compute SG). The Foundation phase resolves this by analyzing which sections exist and creating the appropriate SG topology before any infrastructure capabilities run. With the flat model, this is straightforward — every data resource allows traffic from the single compute security group.

### 3.7 `__main__.py` (Target)

```python
from devops.config import load_platform_config
from devops.shared.lookups import lookup_shared_infrastructure
from devops.capabilities.registry import CAPABILITIES, CapabilityContext, Phase
import pulumi

config = load_platform_config()
aws_provider = create_aws_provider(config.service_name, config.region)
infra = lookup_shared_infrastructure(aws_provider)
context = CapabilityContext(config, infra, aws_provider)

# Foundation phase: auto-derive security groups and IAM from declared sections
provision_foundation(config.spec_sections, context)

# Run declared capabilities in phase order
for phase in [Phase.INFRASTRUCTURE, Phase.COMPUTE, Phase.NETWORKING]:
    for section_name, section_config in config.spec_sections.items():
        cap = CAPABILITIES.get(section_name)
        if cap and cap.phase == phase:
            cap.handler(section_config, context)

# Export all registered outputs
for key, value in context.outputs.items():
    pulumi.export(key, value)
```

---

## 4. The Spec Contract (`platform.yaml`)

### 4.1 Top-Level Structure (unchanged)

```yaml
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: my-service
  description: Optional description
spec:
  # One or more capability sections
  compute: { ... }
  storage: { ... }
  cache: { ... }
  # etc.
```

`kind` remains `Service` for v1 backward compatibility. A service is anything the engine provisions — from a simple ECS container to a complex multi-resource stack. The sections you declare determine what gets created.

### 4.2 Capability Sections

Each section is optional. Declare only what you need. Each section supports exactly one resource instance (flat stack model).

#### `spec.compute` (existing, enhanced)

Container compute (ECS Fargate). This is the only section that was fully specified in v1.

```yaml
spec:
  compute:
    type: ecs          # default: ecs (only supported value in v1)
    port: 8080         # container port, default: 80
    cpu: 512           # CPU units, minimum: 256
    memory: 1024       # Memory in MiB, minimum: 512
    instances:
      min: 1           # minimum task count, default: 1
    healthCheck:
      path: /health    # health check path, default: /health
```

**Networking resources** (target group, ALB listener rule, DNS record, Cloudflare Access) are auto-created when `compute` is declared. This is the "Networking phase" — implicit, not a separate section.

#### `spec.storage` (new, validated)

Elastic File System for persistent shared storage.

```yaml
spec:
  storage:
    type: efs                  # default: efs (only supported value)
    encrypted: true            # default: true
    lifecyclePolicy: AFTER_30_DAYS  # IA transition, default: AFTER_30_DAYS
    # Enum: AFTER_1_DAY, AFTER_7_DAYS, AFTER_14_DAYS, AFTER_30_DAYS,
    #        AFTER_60_DAYS, AFTER_90_DAYS, AFTER_180_DAYS, AFTER_270_DAYS, AFTER_365_DAYS
    accessPoint:
      path: /data              # root directory path, required
      uid: 1000                # POSIX user ID, default: 1000
      gid: 1000                # POSIX group ID, default: 1000
```

#### `spec.cache` (new, validated)

ElastiCache Redis for caching, queuing, and real-time state.

```yaml
spec:
  cache:
    engine: redis              # required, only: redis
    engineVersion: "7.1"       # default: "7.1"
    nodeType: cache.t3.micro   # required
    numNodes: 1                # default: 1 (replication group size)
    transitEncryption: true    # default: true
    atRestEncryption: true     # default: true
```

#### `spec.database` (new, validated)

RDS PostgreSQL for relational data.

```yaml
spec:
  database:
    engine: postgres           # required, only: postgres
    engineVersion: "16.4"      # default: "16.4"
    instanceClass: db.t3.micro # required
    allocatedStorage: 20       # GB, default: 20, minimum: 20
    multiAz: false             # default: false
    backupRetentionDays: 7     # default: 7, range: 0-35
    dbName: my_database        # initial database name, required
    dbUsername: db_admin        # master username, required
```

Database password is provided via the `secrets` section and environment, never in the YAML.

#### `spec.serviceDiscovery` (new, validated)

AWS Cloud Map for internal DNS resolution.

```yaml
spec:
  serviceDiscovery:
    namespace: internal.local  # private DNS namespace name, required
    # TTL and routing are set to sensible defaults (10s TTL, MULTIVALUE)
```

#### `spec.lambda` (new, validated)

Container-image Lambda functions with VPC, EFS, and Function URLs.

```yaml
spec:
  lambda:
    functions:
      - name: my-function      # function name suffix, required
        image: my-ecr-repo     # ECR repo name suffix (without service prefix), required
        memory: 2048           # MB, default: 2048, range: 128-10240
        timeout: 120           # seconds, default: 120, range: 1-900
        environment:           # optional env vars
          MY_VAR: value
```

Each function gets: ECR repository, Lambda function, Function URL (streaming), VPC attachment, EFS mount (if `storage` is declared).

Note: `lambda.functions` is an array — multiple Lambda functions within a single stack is supported because they all share the same security group and EFS mount. This is different from the "one per section" rule; the Lambda section itself is singular, but it can define multiple functions that share the same access model.

#### `spec.triggers` (new, validated)

Event-driven trigger infrastructure.

```yaml
spec:
  triggers:
    eventbridge:
      scheduleGroup: my-schedules  # EventBridge Scheduler group name, required if eventbridge declared
    webhookGateway: true           # provision webhook gateway Lambda, default: false
```

#### `spec.secrets` (existing, unchanged)

```yaml
spec:
  secrets:
    - DATABASE_URL
    - API_KEY
```

Names of secrets to inject from the environment into containers.

### 4.3 Composability Examples

**Simple ECS service** (existing pattern, unchanged):
```yaml
spec:
  compute:
    port: 8080
    cpu: 256
    memory: 512
  secrets:
    - DATABASE_URL
```

**ECS service with Redis** (new — just add a section):
```yaml
spec:
  compute:
    port: 8080
    cpu: 512
    memory: 1024
  cache:
    engine: redis
    nodeType: cache.t3.micro
  secrets:
    - REDIS_URL
```

**Full Agent Factory stack** (many sections):
```yaml
spec:
  compute:
    cpu: 512
    memory: 1024
  storage:
    accessPoint:
      path: /agent-factory
  cache:
    engine: redis
    nodeType: cache.t3.micro
  database:
    engine: postgres
    instanceClass: db.t3.micro
    dbName: dify_production
    dbUsername: dify_admin
  serviceDiscovery:
    namespace: agents.local
  lambda:
    functions:
      - name: pi-chat
        image: pi-agent-lambda
      - name: claude-chat
        image: claude-agent-lambda
  triggers:
    eventbridge:
      scheduleGroup: agent-factory
    webhookGateway: true
  secrets:
    - ANTHROPIC_API_KEY
    - DIFY_DB_PASSWORD
```

---

## 5. Config Pipeline

### 5.1 Current Problem

```
platform.yaml → PlatformConfig (only compute fields) → capability (ignores config, hardcodes values)
```

### 5.2 Target

```
platform.yaml → schema validation → PlatformConfig (all sections) → capability (reads from config)
```

### 5.3 Extended `PlatformConfig`

```python
@dataclass
class PlatformConfig:
    """Parsed and validated platform.yaml configuration."""

    # Metadata
    service_name: str
    region: str

    # All spec sections (typed)
    compute: ComputeConfig | None
    storage: StorageConfig | None
    cache: CacheConfig | None
    database: DatabaseConfig | None
    service_discovery: ServiceDiscoveryConfig | None
    lambda_functions: LambdaConfig | None
    triggers: TriggersConfig | None
    secrets: list[str]

    # Raw spec dict (for forward compat / custom fields)
    raw_spec: dict[str, Any]

    @property
    def spec_sections(self) -> dict[str, Any]:
        """Return only the declared (non-None) capability sections."""
        ...
```

Each section config is a typed dataclass with defaults matching the schema:

```python
@dataclass
class CacheConfig:
    engine: str           # "redis"
    engine_version: str   # "7.1"
    node_type: str        # "cache.t3.micro"
    num_nodes: int        # 1
    transit_encryption: bool  # True
    at_rest_encryption: bool  # True
```

### 5.4 Flow

1. YAML is loaded and validated against the JSON Schema (catches structural errors early).
2. Each declared section is parsed into its typed dataclass (catches semantic errors).
3. The section dataclass is passed to the capability handler (no hardcoded values).
4. The capability handler passes dataclass fields to module functions as arguments.

No value ever goes from "hardcoded in orchestrator" to "module parameter." Every value traces back to the YAML.

---

## 6. Schema Design

### 6.1 Current Problem

New sections are `additionalProperties: true` with no field definitions. They validate nothing.

### 6.2 Target

Every section has the same rigor as `compute`:

```json
{
  "cache": {
    "type": "object",
    "description": "ElastiCache Redis configuration",
    "required": ["engine", "nodeType"],
    "additionalProperties": false,
    "properties": {
      "engine": {
        "type": "string",
        "enum": ["redis"],
        "description": "Cache engine type"
      },
      "engineVersion": {
        "type": "string",
        "default": "7.1",
        "description": "Redis engine version"
      },
      "nodeType": {
        "type": "string",
        "pattern": "^cache\\.",
        "description": "ElastiCache node type (e.g. cache.t3.micro)"
      },
      "numNodes": {
        "type": "integer",
        "minimum": 1,
        "maximum": 6,
        "default": 1,
        "description": "Number of cache nodes"
      },
      "transitEncryption": {
        "type": "boolean",
        "default": true
      },
      "atRestEncryption": {
        "type": "boolean",
        "default": true
      }
    }
  }
}
```

Key design choices:
- `additionalProperties: false` on leaf sections (catch typos)
- `additionalProperties: true` only on extensible containers (`spec`, `metadata`)
- `required` fields clearly marked
- `enum` for constrained values
- `pattern` for format validation (e.g., instance class prefixes)
- `default` values documented in schema (single source of truth for defaults)

### 6.3 Schema Versioning

The schema file `platform-spec-v1.json` evolves additively:
- New optional sections can be added at any time
- New optional fields within existing sections can be added at any time
- Removing, renaming, or changing the meaning of a field requires `platform.althq.com/v2`

The existing `compute` section remains as-is. All new sections are optional. This means every existing `platform.yaml` continues to validate without changes.

---

## 7. Guard Rails

### 7.1 Validation Layers

| Layer | What It Catches | When |
|-------|-----------------|------|
| **JSON Schema** | Structural errors: missing fields, wrong types, invalid values | Config load time |
| **Typed config parsing** | Semantic errors: incompatible combinations, invalid references | Config load time |
| **Capability preconditions** | Dependency errors: "Lambda requires storage to be declared for EFS mount" | Before provisioning |
| **Pulumi preview** | Resource-level errors: invalid ARNs, permission issues | Preview/up time |
| **Preflight** | Functional errors: can't connect to Redis, can't mount EFS | Post-provision |

### 7.2 Capability Preconditions

Each capability can declare what it depends on:

```python
@dataclass
class CapabilityDef:
    handler: Callable
    phase: Phase
    requires: list[str] = field(default_factory=list)  # section names
```

Example: the `lambda` capability requires `storage` (for EFS mount). If `lambda` is declared without `storage`, the engine raises a clear error at config time, not during Pulumi provisioning.

### 7.3 Name Validation

Service names flow into DNS records, ECR repos, IAM roles, and stack names. The schema should enforce:

```json
"name": {
  "type": "string",
  "minLength": 1,
  "maxLength": 40,
  "pattern": "^[a-z][a-z0-9-]*[a-z0-9]$",
  "description": "Service name (lowercase, hyphens, used for DNS/ECR/IAM)"
}
```

This prevents names that break downstream resources (uppercase, underscores, too long for ECR, etc.).

---

## 8. Testing Strategy

### 8.1 Current State

| Module | Tests |
|--------|-------|
| `compute/ecr.py` | Yes |
| `compute/ecs_cluster.py` | Yes |
| `compute/ecs_task.py` | Yes (partial) |
| `compute/ecs_service.py` | No |
| `compute/lambda_function.py` | **No** |
| `storage/efs.py` | **No** |
| `cache/redis.py` | **No** |
| `database/rds.py` | **No** |
| `networking/security_groups.py` (new functions) | **No** |
| `networking/service_discovery.py` | **No** |
| `triggers/eventbridge.py` | **No** |
| `iam/roles.py` (new functions) | **No** |
| `capabilities/agent_factory.py` | **No** |
| Schema (new sections) | **No** |

### 8.2 Target Coverage

Every module must have unit tests that:
1. Mock the Pulumi resource constructor
2. Assert it's called with the correct arguments (derived from config, not hardcoded)
3. Return a mock that downstream code can reference
4. Cover edge cases (optional fields, defaults, boundary values)

Every fixture must pass schema validation in CI.

### 8.3 Test Categories

| Category | What | How |
|----------|------|-----|
| **Schema tests** | All fixtures validate. Invalid inputs are rejected with clear errors. | `test_spec.py` |
| **Config tests** | Each section parses correctly. Defaults applied. Missing required fields error. | `test_config.py` |
| **Module tests** | Each `create_*` function is called with correct args from config. | `test_<module>.py` |
| **Capability tests** | Capabilities read from context, call modules, register outputs. | `test_capabilities.py` |
| **Integration tests** | `__main__.py` runs with a fixture, correct capabilities are selected. | `test_integration.py` |

---

## 9. Extensibility: Adding a New Capability

This is the primary measure of whether the architecture is right. Adding support for a new AWS service (e.g., SQS, S3, Secrets Manager) should require:

### Steps to Add a Capability

| Step | File | What |
|------|------|------|
| 1 | `devops/schema/platform-spec-v1.json` | Add section schema with full validation |
| 2 | `devops/config.py` | Add typed `@dataclass` and parse section |
| 3 | `devops/<layer>/<module>.py` | Create resource module (e.g., `devops/messaging/sqs.py`) |
| 4 | `devops/capabilities/<name>.py` | Create capability handler that reads config, calls module, registers outputs |
| 5 | `devops/capabilities/registry.py` | Register capability in `CAPABILITIES` dict |
| 6 | `tests/test_<module>.py` | Unit tests for the module |
| 7 | `tests/test_<capability>.py` | Unit tests for the capability |
| 8 | `fixtures/platform-<example>.yaml` | Fixture that uses the new section |

That's 8 touch points, but each is small and self-contained. No changes to `__main__.py`. No changes to existing capabilities. No env var routing. The registry and auto-detection handle everything.

---

## 10. CLI Enhancements

### 10.1 Current CLI

| Command | Status |
|---------|--------|
| `platform setup` | Working |
| `platform list` | Working |
| `platform create <path>` | Working |
| `platform destroy <name>` | Working |

### 10.2 New Commands

| Command | What It Does |
|---------|-------------|
| `platform validate <path>` | Validate a `platform.yaml` against the schema without provisioning. Print which capabilities would run. Show warnings for common mistakes. |
| `platform preview <path>` | Dry run: show what resources would be created, grouped by capability. Wraps `pulumi preview`. |

`platform validate` is especially useful for CI and for developers writing a new `platform.yaml`. It catches errors before they reach Pulumi.

---

## 11. Outputs

### 11.1 Current Problem

Pulumi exports are hardcoded per capability orchestrator. The agent factory exports `efs_filesystem_id`, `redis_endpoint`, etc. The ECS capability exports `service_url`, `ecr_repository_uri`, etc. There's no consistency or discoverability.

### 11.2 Target

Each capability handler registers its outputs in the shared context with namespaced keys:

```python
context.export("compute.service_url", service_url)
context.export("compute.ecr_repository_uri", ecr_repo.repository_url)
context.export("storage.efs.filesystem_id", efs_fs.id)
context.export("cache.redis.endpoint", redis.primary_endpoint_address)
```

The engine's `__main__.py` exports everything in the context's output bag. Output keys are predictable and documented.

### 11.3 Output Documentation

The spec contract doc (`docs/spec.md`) lists which outputs each capability produces, so consumers (CI workflows, admin-console, other tools) know what to expect.

---

## 12. Workspace Friendliness

The platform engine is infrastructure that other developers will extend and depend on. The following artifacts make that safe and productive.

### 12.1 Cursor Rule

`.cursor/rules/platform-engine.md` — guides AI agents working on the engine to follow its conventions (code organization, no hardcoded values, testing requirements, how to add capabilities).

### 12.2 Contributing Guide

`CONTRIBUTING.md` — development setup, how to run tests/lint/type-check, how to add a capability, PR checklist.

### 12.3 Documentation

| File | What It Covers |
|------|---------------|
| `docs/spec.md` | Full YAML contract — all sections, fields, defaults, outputs |
| `docs/design-decisions.md` | Architecture rationale and key decisions |
| `docs/platform-engine-v2-spec.md` | This document — the v2 vision and migration plan |
| `docs/platform-engine-v2-design.md` | Technical implementation details |
| `README.md` | How to use the engine (CLI, workflows) |
| `CONTRIBUTING.md` | How to develop on the engine |
| `fixtures/README.md` | Available test fixtures |

---

## 13. Migration Plan

### 13.1 Strategy: Incremental, Non-Breaking

The existing ECS capability (`capabilities/ecs.py`) continues to work unchanged. The migration adds the new architecture alongside it, then refactors existing code to use it.

### 13.2 Phases

#### Phase 1: Foundation (no behavior change)

1. Tighten JSON Schema — add full validation for all new sections
2. Extend `PlatformConfig` — parse all sections into typed dataclasses
3. Create `CapabilityContext` and registry
4. Refactor `__main__.py` to use registry (ECS routes through registry, not special-cased)
5. Agent factory orchestrator reads from config instead of hardcoding
6. All existing tests still pass

#### Phase 2: Tests

1. Add unit tests for all new modules (EFS, Redis, RDS, Lambda, Cloud Map, EventBridge)
2. Add unit tests for extended modules (new SG functions, new IAM roles)
3. Add schema validation tests for all fixtures
4. Add capability-level tests

#### Phase 3: Compositional Model

1. Break `agent_factory.py` into individual capability handlers (`provision_storage`, `provision_cache`, etc.)
2. Each handler reads from `CapabilityContext`, calls module functions, registers outputs
3. `__main__.py` auto-detects capabilities from spec sections
4. Remove `PLATFORM_CAPABILITY` env var
5. Verify: the minimal fixture still provisions ECS correctly
6. Verify: the agent factory fixture provisions all resources correctly

#### Phase 4: CLI + Docs

1. Add `platform validate` command
2. Add `platform preview` command
3. Update `README.md`

### 13.3 Backward Compatibility

- Every existing `platform.yaml` continues to work without changes
- The `kind: Service` value is accepted for all spec compositions
- The `apiVersion` stays at `platform.althq.com/v1` (all changes are additive)
- The workflow files continue to work (they call Pulumi, which calls `__main__.py`)

---

## 14. What This Spec Does NOT Cover

- **Environment overrides** (dev vs prod config) — Important but a separate spec. v2 gets the foundation right first.
- **Multi-resource wiring** (selective access between resources) — Deliberate omission. Use multiple stacks. See Section 3.1.
- **Drift detection** — Comparing actual state against spec. Future work.
- **Cost estimation** — Showing estimated costs before provisioning. Future work.
- **Multi-region** — Provisioning the same spec across regions. Future work.
- **Secrets Manager integration** — Replacing env var secrets with AWS Secrets Manager. Future work.

These are listed here so they're not forgotten, but they depend on getting the foundation right first. Each would be its own spec.

---

## 15. Success Criteria

| Criterion | How to Verify |
|-----------|--------------|
| Env var routing removed | `PLATFORM_CAPABILITY` no longer referenced anywhere in code |
| Schema validates all sections | Every field in every fixture is covered by schema validation. `additionalProperties: false` on leaf sections. Invalid input is rejected with clear messages. |
| Config flows from spec | No hardcoded resource parameters in capability handlers. Every value traces to `platform.yaml`. |
| Capabilities are compositional | A new fixture declaring only `storage` + `cache` provisions only those resources (no monolithic orchestrator). |
| Test coverage complete | Every module and capability has unit tests. `uv run test` passes. `uv run test-cov` shows >80% coverage on `devops/`. |
| Fixtures validated in CI | `test_spec.py` validates ALL fixtures (not just `platform-minimal.yaml`). |
| Documentation complete | `docs/spec.md` covers all sections. `CONTRIBUTING.md` exists. Cursor rule exists. |
| Backward compatible | Existing `platform-minimal.yaml` still provisions an ECS service with no changes. |

---

## 16. Related Documents

- `docs/design-decisions.md` — Existing design rationale
- `docs/spec.md` — Spec contract (all YAML sections documented)
- `docs/platform-engine-v2-design.md` — Technical implementation details
- `CONTRIBUTING.md` — How to develop on the engine
- `fixtures/README.md` — Available test fixtures
