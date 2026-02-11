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
