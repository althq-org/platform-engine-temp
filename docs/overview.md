# What is the Platform Engine?

The Platform Engine provisions cloud infrastructure from a single file: **`platform.yaml`**. You describe what you need (compute, storage, database, etc.); the engine creates and wires the AWS (and related) resources.

## For someone new

- **You provide:** A YAML spec (e.g. “I need an ECS service on port 80, a Redis cache, and a Postgres database”).
- **The engine does:** Validates the spec, creates the right resources (ECR, ECS, ALB rules, EFS, ElastiCache, RDS, Lambda, EventBridge, etc.), and connects them (security groups, IAM, DNS).
- **You get:** A live stack you can deploy to, plus outputs (URLs, endpoints, IDs) for your app.

No need to write Terraform/Pulumi or click through the AWS console. One spec, one flow.

## Flow

1. **Validate** — `platform validate <path>` checks your YAML against the schema.
2. **Preview** — `platform preview <path>` shows what would be created (no resources created).
3. **Create** — `platform create <path>` provisions the stack (Pulumi under the hood).
4. **Preflight** (optional) — A small task runs inside the VPC to verify EFS, Redis, RDS, and DNS work.

## Key ideas

- **Spec as contract** — `platform.yaml` is versioned (`apiVersion: platform.althq.com/v1`) and validated. Only what you declare is provisioned.
- **Capabilities** — Each section (compute, storage, cache, database, etc.) maps to a capability. The engine runs only the capabilities you use.
- **One stack per spec** — One `platform.yaml` = one logical stack. Everything in that stack can talk to everything else (same VPC, security groups).

## Where to go next

- [Capabilities reference](capabilities.md) — What each section does and example snippets.
- [Schema guide](schema-guide.md) — What each field means and allowed values.
- [Admin console integration](admin-console.md) — How to load schema and docs from this repo (e.g. for wizards and help).
