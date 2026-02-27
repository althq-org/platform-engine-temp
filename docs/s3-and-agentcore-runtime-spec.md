# S3 and AgentCore Runtime Capabilities — Specification

**Status**: Draft
**Date**: 2026-02-27
**Related**: `design-decisions.md`, `platform-engine-v2-spec.md`, `capabilities.md`

---

## 1. Problem Context

The platform engine provisions infrastructure from `platform.yaml`. It currently supports eight capabilities: `compute` (ECS), `storage` (EFS), `cache` (Redis), `database` (RDS), `dynamodb`, `lambda`, `serviceDiscovery` (Cloud Map), and `eventbridge`.

Two categories of AWS resource are missing.

### 1.1 Object Storage (S3)

S3 is the most fundamental storage primitive in AWS. Any project that stores files, uploads, artifacts, backups, or state needs an S3 bucket. Today there is no way to declare one. Projects that need object storage must provision it manually outside the engine, which breaks the principle that `platform.yaml` is the single source of truth.

This is not a niche need. S3 is the most widely used AWS service. The engine should have had it before EFS.

### 1.2 AI Agent Compute (AgentCore Runtime)

AWS Bedrock AgentCore Runtime is a managed compute service for AI agents. It is a session-based microVM environment — a different compute model from ECS (long-running service) and Lambda (event-driven function). Key properties:

- **Consumption-based pricing.** You pay only for active CPU/memory. I/O wait (30–70% of agentic workloads) is free. No charge when no sessions are running.
- **MicroVM isolation.** Firecracker-class per-session isolation — stronger than Docker containers.
- **Session lifecycle.** 15-minute idle timeout, 8-hour max lifetime. AWS manages reaping.
- **HTTP + WebSocket.** Each runtime exposes `/invocations` (HTTP), `/ws` (WebSocket), and `/ping` (health) on port 8080.
- **ARM64 containers.** Images pushed to ECR, pulled by the runtime.

The platform engine already has two compute capabilities (`compute` for ECS, `lambda` for Lambda). AgentCore Runtime is a third compute model. Any team building AI features — not just one project — would use this.

AgentCore Runtime comes with several companion services (Memory, Identity, Observability, Gateway, Browser, Code Interpreter). Some of these are plumbing that should be auto-provisioned; others are specialized and project-specific.

---

## 2. Principles

These capabilities follow the existing platform engine principles (see `design-decisions.md` and `platform-engine-v2-spec.md` §2). No new principles are introduced. This section restates how each principle applies.

| Principle | How it applies |
|---|---|
| **Spec as contract** | Declaring `s3` or `agentcoreRuntime` in `platform.yaml` is the only way to get these resources. The YAML defines exactly what is provisioned. |
| **Validated before provisioning** | Both capabilities get full JSON Schema validation — `additionalProperties: false`, typed fields, enums, ranges. |
| **Capability-based** | Two new capability handlers, registered in the existing registry. No changes to `__main__.py` orchestration logic. |
| **Flat stack model** | One S3 section = a set of buckets in the stack. One `agentcoreRuntime` section = a set of runtime definitions. Everything in the stack can access everything else. |
| **Config flows from spec** | Every resource argument traces back to `platform.yaml` through typed dataclasses. No hardcoded values. |
| **Compositional** | `s3` works alone. `agentcoreRuntime` works alone. When combined, cross-capability IAM grants appear automatically. |
| **Plumbing is hidden** | ECR repos, IAM roles, AgentCore Memory, policy attachments — users don't declare these. The engine derives them from what capabilities are declared together. |

---

## 3. Summary

Two new capabilities:

| Capability | What the user declares | What the engine provisions (hidden plumbing in italics) |
|---|---|---|
| **`s3`** | Logical bucket names, versioning, lifecycle rules | S3 buckets *(named `{account_id}-{logical_name}`)*, *bucket name env var injection*, *IAM grants to ECS task role (if `compute` declared)*, *IAM grants to AgentCore role (if `agentcoreRuntime` declared)* |
| **`agentcoreRuntime`** | Runtime names, image names, network mode, env vars, authorizer | AgentCore Runtime definitions, *ECR repositories (one per image)*, *IAM role (trusted by `bedrock-agentcore.amazonaws.com`)*, *ECR pull + CloudWatch Logs policy*, *AgentCore Memory instance (shared, SEMANTIC strategy, 365-day expiry)*, *Memory execution role*, *`AGENTCORE_MEMORY_ID` env var injection*, *secrets injection from top-level `secrets`*, *IAM grants to S3 buckets (if `s3` declared)*, *IAM grants to DynamoDB tables (if `dynamodb` declared)*, *`bedrock-agentcore:InvokeAgentRuntime` permission on ECS task role (if `compute` declared)* |

---

## 4. Architecture

### 4.1 Capability Placement

```
Execution Phases
────────────────────────────────────────────────────────────

FOUNDATION          Security groups, IAM roles
(auto-derived)      ├── ECS SG + task role + exec role       (if compute)
                    ├── Agent SG                              (if storage/database/cache)
                    ├── Database SG, EFS SG                   (if database/cache/storage)
                    ├── Lambda execution role                  (if lambda)
                    └── AgentCore role + memory role    ◄──── NEW (if agentcoreRuntime)

INFRASTRUCTURE      Persistent resources
                    ├── storage  (EFS)
                    ├── cache    (Redis)
                    ├── database (RDS)
                    ├── dynamodb
                    ├── serviceDiscovery (Cloud Map)
                    └── s3                             ◄──── NEW

COMPUTE             Things that run
                    ├── compute  (ECS Fargate service)
                    ├── lambda   (Lambda functions)
                    ├── eventbridge (Scheduler)
                    └── agentcoreRuntime               ◄──── NEW

NETWORKING          Things that expose
(auto-derived)      └── ALB rule, DNS, Cloudflare Access     (from compute)
```

S3 is `Phase.INFRASTRUCTURE` — it creates persistent resources that compute capabilities depend on. AgentCore Runtime is `Phase.COMPUTE` — it creates things that run and may need references to infrastructure resources (bucket names, table ARNs).

### 4.2 Cross-Capability Wiring

The platform engine hides IAM plumbing. When capabilities are declared together, the engine automatically creates IAM grants between them. This diagram shows the new wiring (bold = new, regular = existing):

```
                    ┌──────────┐
                    │ dynamodb │
                    └────┬─────┘
                         │ dynamodb:* on declared table ARNs
                         │
         ┌───────────────┼───────────────────┐
         ▼               ▼                   ▼
   ┌──────────┐   ┌──────────────┐   ┌──────────────────┐
   │ compute  │   │    lambda    │   │ agentcoreRuntime │
   │ (ECS)    │   │              │   │                  │
   └────┬─────┘   └──────────────┘   └───────┬──────────┘
        │                                     │
        │  s3:* on declared bucket ARNs       │  s3:* on declared bucket ARNs
        │                                     │
        └──────────────┬──────────────────────┘
                       ▼
                  ┌─────────┐
                  │   s3    │
                  └─────────┘

   compute + agentcoreRuntime declared together:
   ┌──────────┐  bedrock-agentcore:InvokeAgentRuntime  ┌──────────────────┐
   │ compute  │ ──────────────────────────────────────► │ agentcoreRuntime │
   │ (ECS)    │                                         │                  │
   └──────────┘                                         └──────────────────┘
```

Complete wiring matrix:

| Capabilities declared together | Automatic plumbing |
|---|---|
| `compute` + `dynamodb` | ECS task role gets `dynamodb:*` on declared tables *(existing)* |
| `compute` + `storage` | ECS task def gets EFS volume mount *(existing)* |
| `lambda` + `storage` | Lambda gets EFS mount *(existing)* |
| **`compute` + `s3`** | ECS task role gets `s3:*` on declared bucket ARNs |
| **`agentcoreRuntime` + `s3`** | AgentCore role gets `s3:*` on declared bucket ARNs |
| **`agentcoreRuntime` + `dynamodb`** | AgentCore role gets `dynamodb:*` on declared table ARNs |
| **`compute` + `agentcoreRuntime`** | ECS task role gets `bedrock-agentcore:InvokeAgentRuntime` + `iam:PassRole` (for the AgentCore role) |

### 4.3 AgentCore Bundled Resources

When `agentcoreRuntime` is declared, the engine provisions these resources as plumbing. The user does not declare them — they are intrinsic to the capability, like how `compute` auto-creates a target group and listener rule.

```
agentcoreRuntime declared
    │
    ├── ECR repository (per runtime image)
    │   └── Lifecycle policy (keep last 5 images)
    │
    ├── IAM role: {service}-agentcore-runtime
    │   ├── Trust: bedrock-agentcore.amazonaws.com
    │   ├── Policy: ECR pull (GetAuthorizationToken, BatchGetImage, GetDownloadUrlForLayer)
    │   ├── Policy: CloudWatch Logs (CreateLogGroup, CreateLogStream, PutLogEvents)
    │   ├── Policy: S3 access (if s3 declared) — scoped to declared bucket ARNs
    │   ├── Policy: DynamoDB access (if dynamodb declared) — scoped to declared table ARNs
    │   └── Policy: AgentCore Memory (bedrock-agentcore:* on memory ARN)
    │
    ├── AgentCore Memory instance
    │   ├── Strategy: SEMANTIC (summarization, fact extraction, preferences)
    │   ├── Event expiry: 365 days
    │   └── IAM execution role: {service}-agentcore-memory-exec
    │       └── Policy: AmazonBedrockAgentCoreMemoryBedrockModelInferenceExecutionRolePolicy
    │
    ├── AgentCore Runtime definition (per runtime)
    │   ├── Container URI: {ecr-repo}:latest
    │   ├── Network mode: from config
    │   ├── Environment variables: from config + AGENTCORE_MEMORY_ID + secrets
    │   ├── Authorizer: from config (optional)
    │   └── Role ARN: {service}-agentcore-runtime role
    │
    └── (if compute declared) IAM grant on ECS task role:
        └── bedrock-agentcore:InvokeAgentRuntime + iam:PassRole
```

**Why bundle Memory?** AgentCore Memory costs $0 when unused (consumption-based: you pay per event created, per memory stored, per retrieval). Provisioning it is free. Projects that don't need cross-session memory simply never call it — zero cost. Projects that do need it get it automatically without extra YAML. The Memory ID is injected as `AGENTCORE_MEMORY_ID` so agent code can use it if desired. See §8.1 for the full decision rationale.

---

## 5. Schema Design

### 5.1 `spec.s3`

```json
{
  "s3": {
    "type": "object",
    "title": "Object Storage (S3)",
    "description": "Creates S3 buckets for file and object storage. Use for uploads, artifacts, state, backups, or any unstructured data. Each bucket gets encryption, optional versioning, and optional lifecycle rules. IAM access is automatically granted to your ECS task role (if compute is declared) and AgentCore runtime role (if agentcoreRuntime is declared) — no manual wiring needed.\n\nNaming convention: You provide a logical bucket name (e.g. agent-factory-state). The engine automatically prefixes it with the AWS account ID to ensure global uniqueness and environment isolation (e.g. 470935583836-agent-factory-state in dev, 207964198595-agent-factory-state in prod). This matches the established S3 naming convention across the organization. The full bucket name (with prefix) is exported as a Pulumi stack output and injected into environment variables so your app never needs to know the account ID.",
    "additionalProperties": false,
    "required": ["buckets"],
    "x-order": ["buckets"],
    "properties": {
      "buckets": {
        "type": "array",
        "title": "Buckets",
        "description": "One or more S3 buckets to create. The engine prefixes each name with the AWS account ID for global uniqueness (e.g. you write agent-factory-state, AWS gets 470935583836-agent-factory-state). Convention: prefix your logical name with the service name (e.g. agent-factory-state, agent-factory-uploads). The engine creates the bucket, encryption, versioning, and lifecycle rules. Your app reads/writes objects using the AWS SDK — the full bucket name is available as a Pulumi stack output and environment variable.",
        "minItems": 1,
        "items": {
          "type": "object",
          "title": "Bucket",
          "additionalProperties": false,
          "required": ["name"],
          "x-order": ["name", "versioning", "encryption", "lifecycleRules"],
          "properties": {
            "name": {
              "type": "string",
              "title": "Bucket name (logical)",
              "minLength": 3,
              "maxLength": 50,
              "pattern": "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
              "description": "Logical bucket name. Must be lowercase, numbers, and hyphens. Convention: prefix with your service name (e.g. agent-factory-state, my-service-uploads). The engine automatically prepends the AWS account ID to create the real bucket name ({account_id}-{name}), ensuring global uniqueness across environments. Max 50 characters to leave room for the 12-digit account ID prefix."
            },
            "versioning": {
              "type": "boolean",
              "title": "Versioning",
              "default": false,
              "description": "Enable S3 versioning to keep previous versions of every object. Useful for state files, configs, or anything you might need to roll back. Increases storage cost since old versions are retained. If unsure, leave off — you can enable it later without data loss."
            },
            "encryption": {
              "type": "string",
              "title": "Encryption",
              "enum": ["AES256", "aws:kms"],
              "default": "AES256",
              "description": "Server-side encryption method. AES256 (SSE-S3) is free and transparent — AWS manages the keys. aws:kms uses AWS KMS and costs $1/month per key plus $0.03 per 10K requests — only use if you have compliance requirements for key management. AES256 is the right choice for almost everyone."
            },
            "lifecycleRules": {
              "type": "array",
              "title": "Lifecycle rules",
              "description": "Optional rules to automatically transition or expire objects. Use to control storage costs for data with known access patterns (e.g. move logs to cheaper storage after 30 days, delete temp files after 7 days).",
              "items": {
                "type": "object",
                "title": "Lifecycle rule",
                "additionalProperties": false,
                "required": ["prefix"],
                "x-order": ["prefix", "transitionToIA", "expirationDays"],
                "properties": {
                  "prefix": {
                    "type": "string",
                    "title": "Object prefix",
                    "description": "S3 key prefix this rule applies to (e.g. 'logs/', 'cache/', 'temp/'). Use '' (empty string) to apply to all objects in the bucket. The rule only affects objects whose key starts with this prefix."
                  },
                  "transitionToIA": {
                    "type": "integer",
                    "title": "Transition to Infrequent Access (days)",
                    "minimum": 1,
                    "description": "Move objects to S3 Infrequent Access storage after this many days. IA storage is ~45% cheaper but charges per retrieval ($0.01/1K requests). Good for data accessed less than once a month (old logs, archived artifacts). Objects are still fully accessible — AWS handles the transition transparently."
                  },
                  "expirationDays": {
                    "type": "integer",
                    "title": "Expire after (days)",
                    "minimum": 1,
                    "description": "Permanently delete objects after this many days. Use for temporary data, caches, or anything with a natural expiry. Cannot be undone — once deleted, the data is gone (unless versioning is enabled, in which case a delete marker is placed and old versions are retained)."
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### 5.2 `spec.agentcoreRuntime`

```json
{
  "agentcoreRuntime": {
    "type": "object",
    "title": "AI Agent Compute (AgentCore Runtime)",
    "description": "Creates AWS Bedrock AgentCore Runtime definitions — managed microVM execution environments for AI agents. Each runtime is backed by a container image from ECR (ARM64) and supports HTTP invocations (/invocations) and WebSocket sessions (/ws). Sessions run in isolated microVMs with consumption-based pricing — you pay only for active CPU and memory. I/O wait (LLM responses, API calls) is free. No charge when no sessions are running.\n\nThe engine automatically provisions: ECR repositories (one per image), an IAM role trusted by AgentCore, and an AgentCore Memory instance for cross-session context. Memory costs nothing when unused — it is consumption-based. The Memory ID is injected as AGENTCORE_MEMORY_ID so your agent code can use it if desired.\n\nIf S3 or DynamoDB are also declared, IAM access is automatically granted to the AgentCore role. If compute (ECS) is also declared, the ECS task role is automatically granted permission to invoke these runtimes. Top-level secrets are injected as environment variables alongside any runtime-specific variables.",
    "additionalProperties": false,
    "required": ["runtimes"],
    "x-order": ["runtimes", "authorizer"],
    "properties": {
      "runtimes": {
        "type": "array",
        "title": "Runtimes",
        "description": "One or more AgentCore Runtime definitions. Each maps to a container image and becomes an independently invokable agent runtime. Think of these like Lambda function definitions — you declare them here, push container images via CI, and invoke them from your app.",
        "minItems": 1,
        "items": {
          "type": "object",
          "title": "Runtime",
          "additionalProperties": false,
          "required": ["name", "image"],
          "x-order": ["name", "image", "description", "networkMode", "environmentVariables"],
          "properties": {
            "name": {
              "type": "string",
              "title": "Runtime name",
              "minLength": 1,
              "maxLength": 48,
              "pattern": "^[a-zA-Z][a-zA-Z0-9_]*$",
              "description": "Unique name for this runtime definition within the service. Used as the AgentCore runtime name in AWS. Must start with a letter, followed by letters, numbers, or underscores (AWS naming constraint). Examples: claude_agent, pi_agent, rag_bot."
            },
            "image": {
              "type": "string",
              "title": "ECR image name",
              "minLength": 1,
              "description": "ECR repository name for this runtime's container image (without tag or registry prefix). The engine creates the ECR repository and resolves the full URI as <account>.dkr.ecr.<region>.amazonaws.com/<service>-<image>:latest. Your CI/CD workflow must push an ARM64 image to this repository. You can use a placeholder name now — the runtime won't be invokable until an image is pushed. Example: claude-agent, pi-agent."
            },
            "description": {
              "type": "string",
              "title": "Description",
              "maxLength": 1200,
              "description": "Optional human-readable description of what this runtime does. Shown in the AWS console."
            },
            "networkMode": {
              "type": "string",
              "title": "Network mode",
              "enum": ["PUBLIC", "VPC"],
              "default": "PUBLIC",
              "description": "How the runtime accesses the network. PUBLIC: runtime can reach the internet directly (simplest, good for agents that call external APIs). VPC: runtime runs with ENIs in your VPC's private subnets — required if the agent needs to reach VPC-internal resources (databases, Redis, internal services). VPC mode uses the same private subnets and adds egress-only security group rules."
            },
            "environmentVariables": {
              "type": "object",
              "title": "Environment variables",
              "description": "Key-value pairs injected into the runtime container as environment variables. Use for non-secret configuration (log level, work directory, feature flags). Secrets should go in the top-level 'secrets' section — they are automatically injected into all runtimes. The engine also auto-injects AGENTCORE_MEMORY_ID.",
              "additionalProperties": {
                "type": "string"
              }
            }
          }
        }
      },
      "authorizer": {
        "type": "object",
        "title": "Authorizer",
        "description": "Optional JWT authorizer configuration. When set, AgentCore validates incoming requests (HTTP and WebSocket) against your identity provider before they reach the runtime container. Recommended for production — without it, anyone with the runtime endpoint can invoke your agent.",
        "additionalProperties": false,
        "x-order": ["type", "discoveryUrl", "allowedAudiences", "allowedClients"],
        "properties": {
          "type": {
            "type": "string",
            "title": "Authorizer type",
            "enum": ["jwt"],
            "default": "jwt",
            "description": "Authorization method. Only JWT (via OIDC discovery) is supported."
          },
          "discoveryUrl": {
            "type": "string",
            "title": "OIDC discovery URL",
            "format": "uri",
            "description": "The OpenID Connect discovery endpoint for your identity provider. AgentCore fetches signing keys from this URL to validate JWT tokens. Examples: https://accounts.google.com/.well-known/openid-configuration (Google), https://cognito-idp.us-west-2.amazonaws.com/<pool-id>/.well-known/openid-configuration (Cognito)."
          },
          "allowedAudiences": {
            "type": "array",
            "title": "Allowed audiences",
            "description": "List of accepted 'aud' (audience) values in the JWT. The token's audience must match at least one entry. Typically your app's client ID or a custom audience string.",
            "items": {
              "type": "string"
            }
          },
          "allowedClients": {
            "type": "array",
            "title": "Allowed clients",
            "description": "Optional list of accepted 'azp' (authorized party) or 'client_id' values. Adds an extra layer of validation beyond audience. Leave empty to skip client validation.",
            "items": {
              "type": "string"
            }
          }
        }
      }
    }
  }
}
```

### 5.3 Composability Examples

**S3 only** — static file storage for any project:
```yaml
spec:
  s3:
    buckets:
      - name: my-service-uploads
        versioning: true
```
Real bucket name: `{account_id}-my-service-uploads` (e.g. `470935583836-my-service-uploads` in dev).

**ECS + S3** — web app with object storage:
```yaml
spec:
  compute:
    port: 3000
    cpu: 512
    memory: 1024
  s3:
    buckets:
      - name: my-service-uploads
  secrets:
    - AWS_SECRET_KEY
```
Engine auto-grants: ECS task role gets S3 access to `{account_id}-my-service-uploads`. The full bucket name is exported as `s3_bucket_my_service_uploads` and injected as `S3_BUCKET_MY_SERVICE_UPLOADS` into the ECS task definition.

**AgentCore only** — standalone agent runtime (invoked externally):
```yaml
spec:
  agentcoreRuntime:
    runtimes:
      - name: my_agent
        image: my-agent
        networkMode: PUBLIC
  secrets:
    - ANTHROPIC_API_KEY
```
Engine auto-provisions: ECR repo, IAM role, Memory instance, runtime definition.

**Full AI agent platform** — ECS app server + AgentCore runtimes + S3 + DynamoDB:
```yaml
spec:
  compute:
    port: 3000
    cpu: 512
    memory: 1024
    healthCheck:
      path: /health
    publicPaths:
      - /webhooks/*

  dynamodb:
    tables:
      - name: my-service-agents
        partitionKey: agent_id
      - name: my-service-jobs
        partitionKey: job_id
        ttlAttribute: expires_at

  s3:
    buckets:
      - name: my-service-state
        versioning: true

  agentcoreRuntime:
    runtimes:
      - name: claude_agent
        image: claude-agent
        networkMode: PUBLIC
        environmentVariables:
          WORK_DIR: /tmp/agent
      - name: pi_agent
        image: pi-agent
        networkMode: PUBLIC
        environmentVariables:
          WORK_DIR: /tmp/agent
    authorizer:
      type: jwt
      discoveryUrl: https://accounts.google.com/.well-known/openid-configuration
      allowedAudiences:
        - my-service

  serviceDiscovery:
    namespace: agents.local

  eventbridge:
    scheduleGroup: my-service

  secrets:
    - ANTHROPIC_API_KEY
    - GITHUB_PAT
```

Engine auto-provisions for this stack:
- ECS: ECR, cluster, target group, listener rule, DNS, Cloudflare Access, task def, service
- DynamoDB: 3 tables, IAM grant to ECS task role, IAM grant to AgentCore role
- S3: 1 bucket (`{account_id}-my-service-state`), IAM grant to ECS task role, IAM grant to AgentCore role, bucket name env var injection
- AgentCore: 2 ECR repos (claude-agent, pi-agent), IAM role, Memory instance, Memory execution role, 2 runtime definitions, `InvokeAgentRuntime` permission on ECS task role
- Cloud Map: namespace
- EventBridge: scheduler group

The user declared 6 sections. The engine creates ~25 resources. That's the value.

---

## 6. Config Dataclasses

### 6.1 S3

```python
@dataclass
class S3BucketConfig:
    name: str  # Logical name from YAML. Real bucket name = {account_id}-{name}.
    versioning: bool = False
    encryption: str = "AES256"
    lifecycle_rules: list[dict] = field(default_factory=list)

@dataclass
class S3Config:
    buckets: list[S3BucketConfig] = field(default_factory=list)
```

### 6.2 AgentCore Runtime

```python
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
```

### 6.3 PlatformConfig Changes

```python
@dataclass
class PlatformConfig:
    # ... existing fields ...
    s3: S3Config | None = None
    agentcore_runtime: AgentCoreRuntimeConfig | None = None
```

Add `"s3"` and `"agentcoreRuntime"` to the `spec_sections` property.

---

## 7. Implementation

### 7.1 New Files

| File | Purpose |
|---|---|
| `devops/storage/s3.py` | `create_s3_bucket()` — S3 bucket with encryption, versioning, lifecycle. Receives the already-prefixed real bucket name. |
| `devops/compute/agentcore_runtime.py` | `create_agentcore_runtime()` — AgentCore Runtime definition |
| `devops/compute/agentcore_memory.py` | `create_agentcore_memory()` — AgentCore Memory instance |
| `devops/capabilities/s3.py` | S3 capability handler — creates buckets, grants IAM |
| `devops/capabilities/agentcore_runtime.py` | AgentCore Runtime capability handler — creates ECR repos, IAM, memory, runtimes |
| `tests/test_s3.py` | Unit tests for S3 module |
| `tests/test_agentcore_runtime.py` | Unit tests for AgentCore Runtime module |
| `tests/test_agentcore_memory.py` | Unit tests for AgentCore Memory module |
| `tests/test_capability_s3.py` | Unit tests for S3 capability |
| `tests/test_capability_agentcore_runtime.py` | Unit tests for AgentCore Runtime capability |

### 7.2 Modified Files

| File | Change |
|---|---|
| `devops/config.py` | Add `S3BucketConfig`, `S3Config`, `AgentCoreRuntimeDefConfig`, `AgentCoreAuthorizerConfig`, `AgentCoreRuntimeConfig` dataclasses. Add parsing in `PlatformConfig.from_file()`. Add to `spec_sections`. |
| `devops/shared/lookups.py` | Add `aws_account_id` to `SharedInfrastructure` via `pulumi_aws.get_caller_identity()`. Currently `account_id` is the Cloudflare account — the new field is the **AWS** account ID, used for S3 bucket name prefixing. |
| `devops/capabilities/foundation.py` | When `agentcoreRuntime` is declared: create AgentCore IAM role, Memory execution role. When `s3` is declared alongside `compute`: grant ECS task role S3 access. |
| `devops/capabilities/dynamodb.py` | After granting ECS task role (existing), also grant AgentCore role if `iam.agentcore_runtime_role` exists in context. |
| `devops/iam/roles.py` | Add `create_agentcore_runtime_role()` and `create_agentcore_memory_role()`. |
| `devops/schema/platform-spec-v1.json` | Add `s3` and `agentcoreRuntime` sections (see §5). |
| `devops/__main__.py` | Add `import devops.capabilities.s3` and `import devops.capabilities.agentcore_runtime`. |
| `fixtures/platform-agent-factory.yaml` | Update to use `s3` and `agentcoreRuntime` instead of `storage` (EFS). |

### 7.3 Capability Handlers

#### S3 Capability

```python
@register("s3", phase=Phase.INFRASTRUCTURE)
def s3_handler(section_config, ctx):
    """Provision S3 buckets and grant IAM access to compute roles.

    Bucket names are prefixed with the AWS account ID for global uniqueness:
    user writes 'agent-factory-state' → AWS gets '470935583836-agent-factory-state'.
    """
    from devops.storage.s3 import create_s3_bucket

    aws_account_id = ctx.infra.aws_account_id
    buckets_config = section_config.get("buckets", [])
    bucket_arns = []
    bucket_env_vars = {}

    for bucket_cfg in buckets_config:
        logical_name = bucket_cfg["name"]
        real_name = f"{aws_account_id}-{logical_name}"

        bucket = create_s3_bucket(
            service_name=ctx.config.service_name,
            bucket_name=real_name,
            versioning=bucket_cfg.get("versioning", False),
            encryption=bucket_cfg.get("encryption", "AES256"),
            lifecycle_rules=bucket_cfg.get("lifecycleRules", []),
            aws_provider=ctx.aws_provider,
        )
        ctx.set(f"s3.buckets.{logical_name}.arn", bucket.arn)
        ctx.set(f"s3.buckets.{logical_name}.name", bucket.bucket)
        bucket_arns.append(bucket.arn)

        export_key = f"s3_bucket_{logical_name.replace('-', '_')}"
        ctx.export(export_key, bucket.bucket)

        env_key = f"S3_BUCKET_{logical_name.upper().replace('-', '_')}"
        bucket_env_vars[env_key] = bucket.bucket

    ctx.set("s3.bucket_arns", bucket_arns)
    ctx.set("s3.bucket_env_vars", bucket_env_vars)

    # Grant ECS task role access (if compute is declared)
    task_role = ctx.get("iam.task_role")
    if task_role is not None:
        _grant_s3_access(ctx, task_role, bucket_arns, "task")

    # AgentCore role grant happens in agentcore_runtime handler (it runs later, in COMPUTE phase)
```

#### AgentCore Runtime Capability

```python
@register("agentcoreRuntime", phase=Phase.COMPUTE)
def agentcore_runtime_handler(section_config, ctx):
    """Provision AgentCore runtimes, ECR repos, Memory, and cross-capability IAM."""
    from devops.compute.agentcore_runtime import create_agentcore_runtime
    from devops.compute.agentcore_memory import create_agentcore_memory
    from devops.compute.ecr import create_ecr_repository

    service_name = ctx.config.service_name
    aws_provider = ctx.aws_provider
    agentcore_role = ctx.require("iam.agentcore_runtime_role")

    # 1. Create AgentCore Memory (bundled plumbing)
    memory_role = ctx.require("iam.agentcore_memory_role")
    memory = create_agentcore_memory(
        service_name=service_name,
        memory_role=memory_role,
        aws_provider=aws_provider,
    )
    ctx.set("agentcore.memory.id", memory.memory_id)
    ctx.export("agentcore_memory_id", memory.memory_id)

    # 2. Grant AgentCore role access to S3 buckets (if s3 declared)
    bucket_arns = ctx.get("s3.bucket_arns")
    if bucket_arns:
        _grant_s3_access(ctx, agentcore_role, bucket_arns, "agentcore")

    # 3. Grant AgentCore role access to DynamoDB tables (if dynamodb declared)
    # (handled in dynamodb capability via context check)

    # 4. Build secrets list from top-level secrets
    secrets_env = {}
    for name in ctx.config.secrets:
        value = os.environ.get(name)
        if value:
            secrets_env[name] = value

    # 5. Create runtimes
    runtimes = section_config.get("runtimes", [])
    authorizer = section_config.get("authorizer")

    for rt in runtimes:
        image_name = rt["image"]
        repo_name = f"{service_name}-{image_name}"
        ecr_repo = create_ecr_repository(repo_name, aws_provider)
        image_uri = pulumi.Output.concat(ecr_repo.repository_url, ":latest")

        env_vars = {
            **rt.get("environmentVariables", {}),
            **secrets_env,
        }
        # Inject memory ID (resolved at apply time)
        # env_vars["AGENTCORE_MEMORY_ID"] = memory.memory_id

        runtime = create_agentcore_runtime(
            service_name=service_name,
            runtime_name=rt["name"],
            image_uri=image_uri,
            role_arn=agentcore_role.arn,
            network_mode=rt.get("networkMode", "PUBLIC"),
            environment_variables=env_vars,
            memory_id=memory.memory_id,
            description=rt.get("description", ""),
            authorizer=authorizer,
            subnet_ids=ctx.infra.private_subnet_ids if rt.get("networkMode") == "VPC" else None,
            security_group_ids=[ctx.get("security_groups.agentcore.id")] if rt.get("networkMode") == "VPC" else None,
            aws_provider=aws_provider,
        )

        ctx.set(f"agentcore.runtimes.{rt['name']}.arn", runtime.agent_runtime_arn)
        ctx.export(f"agentcore_runtime_{rt['name'].replace('-', '_')}_arn", runtime.agent_runtime_arn)
        ctx.export(f"ecr_{image_name.replace('-', '_')}_uri", ecr_repo.repository_url)

    # 6. Grant ECS task role permission to invoke runtimes (if compute declared)
    task_role = ctx.get("iam.task_role")
    if task_role is not None:
        _grant_invoke_permission(ctx, task_role, agentcore_role)
```

### 7.4 Foundation Changes

```python
# In devops/capabilities/foundation.py → provision_foundation()

if "agentcoreRuntime" in declared:
    from devops.iam.roles import (
        create_agentcore_runtime_role,
        create_agentcore_memory_role,
    )

    agentcore_role = create_agentcore_runtime_role(service_name, aws_provider)
    ctx.set("iam.agentcore_runtime_role", agentcore_role)

    memory_role = create_agentcore_memory_role(service_name, aws_provider)
    ctx.set("iam.agentcore_memory_role", memory_role)

    # VPC mode needs a security group for AgentCore ENIs
    if any_runtime_uses_vpc(spec_sections):
        from devops.networking.security_groups import create_agentcore_security_group
        sg = create_agentcore_security_group(service_name, vpc_id, aws_provider)
        ctx.set("security_groups.agentcore.id", sg.id)
```

### 7.5 IAM Roles

```python
# In devops/iam/roles.py

def create_agentcore_runtime_role(service_name, aws_provider):
    """IAM role trusted by bedrock-agentcore.amazonaws.com.
    ECR pull and CloudWatch Logs are always attached.
    S3 and DynamoDB grants are added by their respective capabilities."""
    # Trust policy: bedrock-agentcore.amazonaws.com
    # Attached policies: ECR read, CloudWatch Logs
    ...

def create_agentcore_memory_role(service_name, aws_provider):
    """IAM execution role for AgentCore Memory strategies.
    Memory strategies call Bedrock models internally for summarization/extraction."""
    # Trust policy: bedrock-agentcore.amazonaws.com
    # Attached policy: AmazonBedrockAgentCoreMemoryBedrockModelInferenceExecutionRolePolicy
    ...
```

---

## 8. Decisions and Tradeoffs

### 8.1 AgentCore Memory is bundled, not a separate capability

**Decision:** Memory is auto-provisioned as plumbing when `agentcoreRuntime` is declared. It is not a top-level capability in the schema.

**Why:**
- Memory costs $0 when unused. Provisioning it has no cost impact.
- Memory is intrinsic to the AgentCore ecosystem — it's the equivalent of CloudWatch Logs being auto-configured for ECS tasks.
- Making it a separate top-level capability adds schema complexity for no user benefit. The user would always declare it alongside `agentcoreRuntime`.
- The Memory ID is injected as an env var. Project code decides whether to use it. This matches the platform engine philosophy: hide plumbing, expose capability.

**Tradeoff:** Users cannot customize Memory strategies or event expiry via YAML. Sensible defaults (SEMANTIC strategy, 365-day expiry) cover all known use cases. If customization becomes necessary, we can add an optional `memory` sub-section within `agentcoreRuntime` — an additive, non-breaking change.

### 8.2 AgentCore Gateway, Browser, Code Interpreter are NOT bundled

**Decision:** These AgentCore services are not auto-provisioned.

**Why:**
- Gateway is for creating MCP servers from APIs — project-specific, not universal.
- Browser is for headless browser automation — specialized.
- Code Interpreter is for sandboxed code execution — specialized.
- Unlike Memory, these have active usage costs and are not "always useful."

**Escape hatch:** If demand arises, any of these can be added as new capabilities or as optional sub-sections of `agentcoreRuntime`. The architecture supports it.

### 8.3 S3 bucket names are auto-prefixed with AWS account ID

**Decision:** The user provides a logical bucket name (e.g. `agent-factory-state`). The engine prepends the AWS account ID to produce the real S3 bucket name (e.g. `470935583836-agent-factory-state`).

**Why:**
- S3 bucket names are **globally unique** across all AWS accounts and regions. A bare logical name like `agent-factory-state` would collide between dev, staging, and production.
- The established convention across the organization is `{account_id}-{purpose}` for S3 buckets. Existing shared buckets in older projects (`althq-services`, `platform`) follow this pattern (e.g. `470935583836-althq-db-dumps`).
- Multi-account isolation: dev (`470935583836`), staging (`297166736412`), and prod (`207964198595`) each get uniquely named buckets with zero risk of collision. No environment suffix needed — the account ID **is** the environment discriminator.
- Users don't need to know or hardcode the account ID. The engine resolves it via `aws.get_caller_identity()` and exports the full bucket name as a Pulumi output and environment variable (`S3_BUCKET_AGENT_FACTORY_STATE`).

**Tradeoff:** The schema field `maxLength` is set to 50 (not S3's max of 63) to leave room for the 12-digit account ID + hyphen prefix. This is intentional — it prevents silent truncation and keeps bucket names readable.

**Note on `lookups.py`:** The existing `SharedInfrastructure.account_id` field is the **Cloudflare** account ID (from `cf_zone.account.id`). A new `aws_account_id` field must be added, resolved via `pulumi_aws.get_caller_identity()`. This is a one-line addition to the lookup module.

### 8.4 S3 is a separate capability, not bundled into anything

**Decision:** S3 is its own top-level capability, independent of `agentcoreRuntime` or `compute`.

**Why:**
- S3 is the most general-purpose AWS primitive. Any project — not just AI agent projects — needs it.
- Bundling it into `agentcoreRuntime` would make it unavailable to projects that just need object storage.
- The existing pattern: `storage` (EFS) is independent of `compute`. S3 follows the same pattern.

### 8.5 Network mode: PUBLIC vs VPC

**Decision:** Each runtime declares its own `networkMode` (default: PUBLIC).

**Why:**
- PUBLIC is simpler and sufficient for agents that call external APIs (LLM providers, GitHub, npm).
- VPC is needed only when agents must reach VPC-internal resources (databases, Redis, internal services).
- Making it per-runtime (not per-section) allows mixed deployments: one agent in PUBLIC mode calling external APIs, another in VPC mode accessing the database.

**Tradeoff:** VPC mode requires a security group for AgentCore ENIs. The foundation phase creates one when any runtime uses VPC. This adds a networking dependency but follows the same pattern as ECS security groups.

### 8.6 Secrets are injected into all runtimes

**Decision:** The top-level `secrets` list is injected as environment variables into every AgentCore runtime (same behavior as `compute` for ECS).

**Why:**
- Consistency with the existing pattern.
- Most secrets (API keys, tokens) are needed by all runtimes in a stack.
- Per-runtime secret scoping adds complexity without clear benefit in the flat stack model.

**Tradeoff:** A runtime that doesn't need `GITHUB_PAT` still receives it. In the flat stack model, this is acceptable — everything in the stack trusts everything else. If per-runtime scoping becomes necessary, it can be added as an optional `secrets` field on each runtime definition.

### 8.7 DynamoDB grants from dynamodb capability, not agentcoreRuntime

**Decision:** The `dynamodb` capability handler is responsible for granting access to both the ECS task role AND the AgentCore role (when present).

**Why:**
- Follows the existing pattern: `dynamodb` already grants access to the ECS task role.
- The DynamoDB handler knows the table ARNs. The AgentCore handler doesn't.
- Cross-capability wiring stays localized: each capability grants access to the resources it owns.

**Alternative considered:** Having the AgentCore handler reach into context for DynamoDB ARNs and create its own policy. Rejected because it duplicates the grant logic and creates a dependency ordering issue (AgentCore runs in COMPUTE phase but needs INFRASTRUCTURE outputs).

**Implementation:** The DynamoDB handler checks `ctx.get("iam.agentcore_runtime_role")` after creating its existing ECS grant. If the role exists, it creates an identical policy attachment. One extra `if` statement.

### 8.8 S3 grants from s3 capability

**Decision:** The `s3` capability handler grants access to the ECS task role (if present). The `agentcoreRuntime` handler grants itself S3 access by reading bucket ARNs from context.

**Why:**
- S3 runs in INFRASTRUCTURE phase (before COMPUTE). It can grant the ECS task role immediately.
- AgentCore runs in COMPUTE phase. It can read the S3 bucket ARNs from context and grant itself access.
- This avoids S3 needing to know about AgentCore (a COMPUTE capability shouldn't be a dependency of an INFRASTRUCTURE capability).

### 8.9 ARM64 requirement is documented, not enforced

**Decision:** The schema description notes that images must be ARM64 but does not enforce it.

**Why:**
- Architecture is a property of the container image, not the YAML spec.
- Enforcement would require inspecting the image at provisioning time — impractical.
- A runtime with an amd64 image will fail at session start with a clear error from AgentCore. This is sufficient.

---

## 9. Testing Strategy

| Category | Tests | Files |
|---|---|---|
| Schema | S3 and AgentCore sections validate. Invalid inputs rejected. | `tests/test_spec.py` (extend) |
| Config | S3Config and AgentCoreRuntimeConfig parse correctly. Defaults applied. | `tests/test_config.py` (extend) |
| S3 module | `create_s3_bucket` called with correct args. Versioning, encryption, lifecycle. | `tests/test_s3.py` |
| AgentCore Runtime module | `create_agentcore_runtime` called with correct args. Network mode, env vars, authorizer. | `tests/test_agentcore_runtime.py` |
| AgentCore Memory module | `create_agentcore_memory` called with correct args. Strategy, expiry. | `tests/test_agentcore_memory.py` |
| S3 capability | Buckets created. IAM grants to ECS role. Export keys correct. | `tests/test_capability_s3.py` |
| AgentCore capability | ECR repos created. Memory created. Runtimes created. Cross-capability grants. | `tests/test_capability_agentcore_runtime.py` |
| Fixtures | Updated `platform-agent-factory.yaml` validates against schema. | `tests/test_spec.py` (existing) |

---

## 10. Updated Fixture: `platform-agent-factory.yaml`

```yaml
apiVersion: platform.althq.com/v1
kind: Service
metadata:
  name: agent-factory
  description: AI agent platform. TanStack Start orchestrator + AgentCore Runtime agents.

spec:
  compute:
    type: ecs
    port: 3000
    cpu: 512
    memory: 1024
    instances:
      min: 1
    healthCheck:
      path: /health
    publicPaths:
      - /webhooks/*

  dynamodb:
    tables:
      - name: agent-factory-agents
        partitionKey: agent_id
      - name: agent-factory-jobs
        partitionKey: job_id
        ttlAttribute: expires_at
      - name: agent-factory-conversations
        partitionKey: agent_id
        sortKey: session_sk
        ttlAttribute: expires_at

  s3:
    buckets:
      - name: agent-factory-state  # real: {account_id}-agent-factory-state
        versioning: true

  agentcoreRuntime:
    runtimes:
      - name: claude_agent
        image: claude-agent
        description: Claude Agent SDK runtime (chat + autonomous)
        networkMode: PUBLIC
        environmentVariables:
          WORK_DIR: /tmp/agent
      - name: pi_agent
        image: pi-agent
        description: Pi Agent runtime (chat + autonomous)
        networkMode: PUBLIC
        environmentVariables:
          WORK_DIR: /tmp/agent
    authorizer:
      type: jwt
      discoveryUrl: https://accounts.google.com/.well-known/openid-configuration
      allowedAudiences:
        - agent-factory

  serviceDiscovery:
    namespace: agents.local

  eventbridge:
    scheduleGroup: agent-factory

  secrets:
    - ANTHROPIC_API_KEY
    - GITHUB_PAT
```

---

## 11. What This Spec Does NOT Cover

- **AgentCore Gateway, Browser, Code Interpreter** — specialized services. Add as new capabilities if demand arises.
- **Memory strategy customization** — sensible defaults. Add optional `memory` sub-section if needed.
- **Per-runtime secret scoping** — flat stack model. All runtimes get all secrets.
- **Cross-stack AgentCore invocation** — one stack = one set of runtimes. Cross-stack communication uses Cloud Map or explicit endpoints.
- **AgentCore Runtime auto-scaling configuration** — AWS manages scaling. No knobs exposed.
- **Cost estimation** — future platform engine feature, not specific to these capabilities.

---

## 12. Success Criteria

| Criterion | How to Verify |
|---|---|
| S3 schema validates | Fixture with S3 section passes schema validation. Invalid bucket names are rejected. |
| AgentCore schema validates | Fixture with AgentCore section passes schema validation. Invalid runtime names are rejected. |
| S3 provisions correctly | `pulumi preview` with S3-only fixture shows bucket named `{account_id}-{logical_name}`, encryption, lifecycle resources. |
| AgentCore provisions correctly | `pulumi preview` with AgentCore fixture shows ECR repos, IAM roles, Memory, runtime definitions. |
| S3 bucket name prefixed | Logical name `agent-factory-state` becomes `{account_id}-agent-factory-state`. Full name exported as `s3_bucket_agent_factory_state` and injected as `S3_BUCKET_AGENT_FACTORY_STATE`. |
| Cross-capability IAM works | Fixture with `compute` + `s3` + `dynamodb` + `agentcoreRuntime` creates correct IAM grants between all roles. |
| Memory bundled automatically | AgentCore fixture provisions Memory without the user declaring it. Memory ID appears as env var. |
| Secrets injected | Secrets from top-level `secrets` appear in AgentCore runtime environment variables. |
| Existing capabilities unaffected | `platform-minimal.yaml` (ECS-only) still provisions correctly. No regressions. |
| Tests pass | All new test files pass. Existing tests still pass. |
| Fixture updated | `platform-agent-factory.yaml` uses new capabilities and validates against schema. |
