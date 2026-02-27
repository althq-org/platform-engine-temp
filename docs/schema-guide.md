# Schema guide

This doc explains the **platform spec schema** in plain language. The machine-readable schema is `devops/schema/platform-spec-v1.json` (JSON Schema draft 2020-12). Use it for validation and wizard UIs; use this guide for help text and tooltips.

## Top-level

| Field       | Required | Meaning |
|------------|----------|---------|
| `apiVersion` | Yes   | Must be `platform.althq.com/v1`. |
| `kind`       | Yes   | Must be `Service`. |
| `metadata`   | Yes   | Name and optional description. |
| `spec`       | Yes   | The capabilities and options. |

## metadata

| Field         | Required | Rules |
|---------------|----------|--------|
| `name`        | Yes      | 2–63 chars, lowercase letters/numbers/hyphens, must not start or end with hyphen. Used for stack names and DNS. |
| `description` | No       | Free text. |

## spec (sections)

You can include any subset. Order does not matter. All are optional in the schema, but you typically need at least one of `compute`, `storage`, `cache`, `database`, `lambda`, etc.

### compute

| Field                | Type     | Default | Notes |
|----------------------|----------|---------|--------|
| `type`               | string   | `ecs`   | Only `ecs` today. |
| `port`               | int      | 80      | 1–65535. Container port. |
| `cpu`                | int      | 256     | Min 256 (CPU units). |
| `memory`             | int      | 512     | Min 512 (MiB). |
| `instances.min`      | int      | 1       | Min 0. Minimum task count. |
| `healthCheck.path`   | string   | —       | HTTP path for ALB health checks. |
| `publicPaths`        | string[] | —       | URL path patterns excluded from Zero Trust auth (e.g. `/webhooks/*`). All other paths require Google OAuth. Creates a Cloudflare bypass app per entry. |

### storage.efs

| Field                 | Type   | Default        | Notes |
|-----------------------|--------|----------------|--------|
| `encrypted`           | bool   | true           | EFS encryption. |
| `lifecycle`           | string | `AFTER_30_DAYS`| One of: `AFTER_7_DAYS`, `AFTER_14_DAYS`, `AFTER_30_DAYS`, `AFTER_90_DAYS`. |
| `accessPoint.path`    | string | `/data`        | Root path for the access point. |
| `accessPoint.uid`     | int    | 1000           | POSIX uid. |
| `accessPoint.gid`     | int    | 1000           | POSIX gid. |

### cache

| Field       | Type   | Default           | Notes |
|-------------|--------|-------------------|--------|
| `engine`    | string | `redis`           | Only `redis`. |
| `nodeType`  | string | `cache.t3.micro`   | ElastiCache node type. |
| `numNodes`  | int    | 1                 | Min 1. Cache nodes. |

### database

| Field               | Type   | Default       | Notes |
|---------------------|--------|---------------|--------|
| `engine`            | string | `postgres`    | Only `postgres`. |
| `instanceClass`    | string | `db.t3.micro` | RDS instance class. |
| `allocatedStorage`  | int    | 20            | Min 20 (GB). |

### dynamodb.tables[]

Each item:

| Field              | Type   | Default            | Notes |
|--------------------|--------|--------------------|-------|
| `name`             | string | —                  | Required. Table name (e.g. `my-service-jobs`). |
| `partitionKey`     | string | —                  | Required. Hash key attribute name. |
| `partitionKeyType` | string | `S`                | `S` (String), `N` (Number), `B` (Binary). |
| `sortKey`          | string | —                  | Optional. Range key attribute name. |
| `sortKeyType`      | string | `S`                | Type of sort key. Only used if `sortKey` is set. |
| `ttlAttribute`     | string | —                  | Optional. Attribute name for TTL expiry (Unix epoch seconds). DynamoDB auto-deletes expired items. |
| `billingMode`      | string | `PAY_PER_REQUEST`  | `PAY_PER_REQUEST` (on-demand) or `PROVISIONED`. Start with on-demand. |

### serviceDiscovery

| Field       | Type   | Notes |
|-------------|--------|--------|
| `namespace` | string | Private DNS namespace name (e.g. `myapp.local`). |

### lambda.functions[]

Each item:

| Field    | Type   | Default | Notes |
|----------|--------|---------|--------|
| `name`   | string | —       | Required. Function logical name. |
| `image`  | string | —       | Required. ECR repo name suffix. |
| `memory` | int   | 2048    | Min 128. |
| `timeout`| int   | 120     | Min 1 (seconds). |

### eventbridge

| Field                        | Type   | Default | Notes |
|-----------------------------|--------|---------|--------|
| `eventbridge.scheduleGroup`| string | —       | Optional. EventBridge Scheduler group name (defaults to `<service>-schedules`). |

### secrets

Array of strings (secret names). Values come from the environment; the engine injects them into the compute container. Not a capability — no resources created.

---

## Validation rules

- **metadata.name:** Pattern `^[a-z][a-z0-9-]*[a-z0-9]$` or single alphanumeric.
- **spec sections:** Leaf sections use `additionalProperties: false`; unknown keys in a section are rejected. The root `spec` allows unknown top-level keys (forward compatibility).
- Defaults in this guide match the JSON Schema and the engine’s config dataclasses.
