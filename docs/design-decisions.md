# Design decisions

## Function/layer-first organization

Code is grouped by **capability or layer** (compute, networking, IAM, loadbalancer) rather than by vendor (AWS, Cloudflare). This matches Pulumi and industry guidance: structure by architecture and provisioning pipeline, not by provider. Benefits:

- The main program reads as a pipeline (compute, then load balancing, then networking).
- Shared infra (VPC, ALB, zone) lives in `shared/`; each capability receives it and creates only its own resources.
- Adding a new vendor product (e.g. another Cloudflare feature) goes into the layer that owns that concern (e.g. networking), not a separate vendor tree.

## Spec as contract

`platform.yaml` is the contract between services and the engine. It is versioned (`apiVersion`), validated with a JSON Schema before any provisioning, and extended **additively** (new optional sections) to avoid breaking changes. Breaking changes require a new `apiVersion`. This keeps existing service configs valid as the engine evolves and supports future "manage" and wizard tooling that read or edit the spec.

## Capability-based provisioning

`devops/__main__.py` is a thin **orchestrator**: it loads config, looks up shared infra, runs the capabilities implied by the spec, and exports outputs. Each capability (e.g. ECS) is a self-contained module under `devops/capabilities/` that takes config and shared infra and creates its resources. Future capabilities (S3, database, Lambda) are added as new modules and conditional steps in the orchestrator, so the codebase scales without a single giant pipeline.

## Schema and validation

A single JSON Schema per supported `apiVersion` (e.g. `devops/schema/platform-spec-v1.json`) is the source of truth for validity. Validation runs when config is loaded, so invalid spec never reaches provisioning. The same schema can drive IDE hints, CI checks, and future manage/wizard UIs.

## Compositional capability model

The engine detects which spec sections are declared and runs only the corresponding capabilities, in phase order (Foundation → Infrastructure → Compute → Networking). This replaces the earlier pattern of environment variable routing (`PLATFORM_CAPABILITY=...`) with spec-driven auto-detection. Adding a new infrastructure type means adding a schema section, config dataclass, resource module, and capability handler — without changing `__main__.py`.

## Shared context for cross-capability wiring

Capabilities produce resources that other capabilities depend on (e.g., storage creates a security group, Lambda needs it). A `CapabilityContext` object acts as a shared bag where capabilities register outputs (resource IDs, ARNs) and dependent capabilities retrieve them. This replaces monolithic orchestrator functions that manually wire resources together.

## Schema strictness

Leaf sections in the schema use `additionalProperties: false` to catch typos and invalid fields early. The `spec` container itself uses `additionalProperties: true` for forward compatibility (unknown sections are ignored). Every field has a type, constraints (minimum, maximum, enum, pattern), and description. Defaults in the schema match defaults in the config dataclasses — one source of truth.

## Config flows from spec

Every resource module parameter traces back to `platform.yaml` through typed config dataclasses. No hardcoded values in capability handlers. This ensures the YAML is the contract — not decoration — and that changing a value in the YAML changes the provisioned resource.

## Testing requirements

Every resource module and capability handler must have unit tests. Tests mock Pulumi resource constructors and assert they're called with arguments derived from config. All fixture files are validated against the schema in CI. This catches regressions when the schema or config parsing evolves.

## Flat stack model

One `platform.yaml` = one stack = one of each resource type. Everything in the stack can see everything else — compute can reach storage, cache, and database without exception. The engine does not support selective access (ECS A talks to DB A but not DB B) within a single stack. If you need that, use multiple stacks with separate `platform.yaml` files. This keeps the security group and IAM logic simple and the spec approachable — you don't think about wiring, you just declare what you need.

## Shared infrastructure via runtime lookup

The engine discovers VPC, ALB, subnets, and Cloudflare zone at runtime through tag lookups and name lookups (`devops/shared/lookups.py`). This matches how all other services in the org find shared infrastructure. The engine does not create or manage shared infrastructure — it only creates per-service resources within the shared environment. This pattern was established by the platform team and is consistent across the org; changing it would add complexity without immediate benefit.
