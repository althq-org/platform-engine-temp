# Platform Spec Contract (`platform.yaml`)

## Overview

`platform.yaml` describes what infrastructure a service needs. The platform engine validates it against a JSON Schema, determines which capabilities are declared, and provisions the corresponding resources. This document is the human-readable contract; the authoritative schema is `devops/schema/platform-spec-v1.json`.

## Versioning

- **apiVersion** (required): `platform.althq.com/v1`. The engine only accepts supported versions.
- **kind** (required): `Service`. Represents any provisioned stack — simple or complex.
- Changes are **additive**: new optional sections or fields. Breaking changes require a new `apiVersion` (e.g., v2) and a migration path.

## Top Level

| Key | Required | Description |
|-----|----------|-------------|
| apiVersion | Yes | `platform.althq.com/v1` |
| kind | Yes | `Service` |
| metadata | Yes | See below |
| spec | Yes | See below |

## `metadata`

| Key | Required | Description |
|-----|----------|-------------|
| name | Yes | Service name. Used for DNS, stack names, ECR repos, IAM roles. Must be lowercase, hyphens only, 1-40 chars. |
| description | No | Human-readable description. |

## `spec`

Declare only the sections you need. Each section maps to a capability that provisions the corresponding AWS resources.

### `spec.compute` — ECS Fargate

Container compute with ALB, DNS, and Cloudflare Access (auto-provisioned).

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| type | No | `ecs` | Compute type. Only `ecs` supported in v1. |
| port | No | 80 | Container port (1-65535). |
| cpu | No | 256 | CPU units (minimum 256). |
| memory | No | 512 | Memory in MiB (minimum 512). |
| instances.min | No | 1 | Minimum task count. |
| healthCheck.path | No | `/health` | Health check path. |

**Auto-provisions**: ECR repository, ECS cluster, security group, IAM roles (task + execution), target group, ALB listener rule, DNS record, Cloudflare Access application.

**Outputs**: `compute.service_url`, `compute.ecr_repository_uri`, `compute.ecs_cluster_name`, `compute.ecs_service_name`

### `spec.storage` — EFS

Elastic File System for persistent, shared storage.

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| type | No | `efs` | Storage type. Only `efs` in v1. |
| encrypted | No | `true` | Encrypt at rest. |
| lifecyclePolicy | No | `AFTER_30_DAYS` | Transition to Infrequent Access. Enum: `AFTER_1_DAY`, `AFTER_7_DAYS`, `AFTER_14_DAYS`, `AFTER_30_DAYS`, `AFTER_60_DAYS`, `AFTER_90_DAYS`, `AFTER_180_DAYS`, `AFTER_270_DAYS`, `AFTER_365_DAYS`. |
| accessPoint.path | Yes (if storage declared) | — | Root directory path for the access point. |
| accessPoint.uid | No | 1000 | POSIX user ID. |
| accessPoint.gid | No | 1000 | POSIX group ID. |

**Auto-provisions**: EFS filesystem, mount targets (per private subnet), access point, EFS security group (NFS from compute).

**Outputs**: `storage.efs.filesystem_id`

### `spec.cache` — ElastiCache Redis

Managed Redis for caching, queuing, and real-time state.

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| engine | Yes | — | `redis` (only supported value). |
| engineVersion | No | `7.1` | Redis engine version. |
| nodeType | Yes | — | ElastiCache node type (e.g., `cache.t3.micro`). |
| numNodes | No | 1 | Number of cache nodes (1-6). |
| transitEncryption | No | `true` | Encrypt in transit. |
| atRestEncryption | No | `true` | Encrypt at rest. |

**Auto-provisions**: Subnet group, replication group, database security group.

**Outputs**: `cache.redis.endpoint`

### `spec.database` — RDS PostgreSQL

Managed relational database.

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| engine | Yes | — | `postgres` (only supported value). |
| engineVersion | No | `16.4` | PostgreSQL version. |
| instanceClass | Yes | — | RDS instance class (e.g., `db.t3.micro`). |
| allocatedStorage | No | 20 | Storage in GB (minimum 20). |
| multiAz | No | `false` | Multi-AZ deployment. |
| backupRetentionDays | No | 7 | Backup retention (0-35). |
| dbName | Yes | — | Initial database name. |
| dbUsername | Yes | — | Master username. |

Database password is provided via `secrets` and the environment — never in the YAML.

**Auto-provisions**: Subnet group, RDS instance (private, encrypted, not publicly accessible), database security group.

**Outputs**: `database.rds.endpoint`

### `spec.serviceDiscovery` — AWS Cloud Map

Private DNS for internal service resolution.

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| namespace | Yes | — | Private DNS namespace name (e.g., `internal.local`). |

**Auto-provisions**: Private DNS namespace, service discovery service (10s TTL, MULTIVALUE routing).

**Outputs**: `serviceDiscovery.namespace_id`

### `spec.lambda` — Container-Image Lambda Functions

Lambda functions from ECR container images with VPC attachment, EFS mount, and streaming Function URLs.

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| functions | Yes | — | Array of function definitions. |
| functions[].name | Yes | — | Function name suffix. |
| functions[].image | Yes | — | ECR repository name suffix. |
| functions[].memory | No | 2048 | Memory in MB (128-10240). |
| functions[].timeout | No | 120 | Timeout in seconds (1-900). |
| functions[].environment | No | `{}` | Environment variables. |

Each function gets an ECR repository and a Function URL. If `storage` is declared, each function gets an EFS mount.

**Requires**: `storage` must be declared (Lambda needs EFS for file system access).

**Auto-provisions**: Per function: ECR repository, Lambda function, Function URL. Shared: Lambda execution IAM role.

**Outputs**: `lambda.<name>.function_url` (per function)

### `spec.triggers` — Event-Driven Infrastructure

EventBridge Scheduler and webhook gateway for agent triggers.

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| eventbridge.scheduleGroup | Yes (if eventbridge declared) | — | EventBridge Scheduler group name. |
| webhookGateway | No | `false` | Provision a webhook gateway Lambda. |

**Auto-provisions**: EventBridge schedule group, scheduler IAM role. If `webhookGateway: true`, provisions a Lambda-based webhook receiver.

**Outputs**: `triggers.eventbridge.schedule_group`

### `spec.secrets`

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| (array of strings) | No | `[]` | Secret names to inject from environment into containers. |

Secrets are read from the CI/CD environment at provisioning time and passed to containers as environment variables. They are never stored in the YAML.

## Composability

Sections are independent and combinable. Declare only what you need:

**Simple ECS service:**
```yaml
spec:
  compute:
    port: 8080
```

**ECS + Redis:**
```yaml
spec:
  compute:
    port: 8080
  cache:
    engine: redis
    nodeType: cache.t3.micro
```

**Full stack (compute + storage + cache + database + Lambda + triggers):**
```yaml
spec:
  compute: { ... }
  storage: { ... }
  cache: { ... }
  database: { ... }
  serviceDiscovery: { ... }
  lambda: { ... }
  triggers: { ... }
```

## Validation

- The engine validates against the JSON Schema for the file's `apiVersion` before creating any resources.
- Invalid specs cause a clear error listing all violations.
- Fixtures under `fixtures/` are tested against the schema in CI.
- `platform validate <path>` validates without provisioning.
