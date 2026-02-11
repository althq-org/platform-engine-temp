# Platform spec contract (platform.yaml)

## Overview

`platform.yaml` describes a service for the platform engine. It is validated against a JSON Schema before provisioning. This document is the human-readable contract; the authoritative schema is `devops/schema/platform-spec-v1.json`.

## Versioning

- **apiVersion** (required): e.g. `platform.althq.com/v1`. The engine only accepts supported versions.
- **kind** (required): e.g. `Service`.
- Changes are **additive**: new optional top-level keys or optional fields. Breaking changes (renaming, removing, or changing meaning of existing keys) require a new `apiVersion` (e.g. v2) and a migration path.

## v1 shape

### Top level

| Key         | Required | Description                    |
|------------|----------|--------------------------------|
| apiVersion | Yes      | `platform.althq.com/v1`        |
| kind       | Yes      | `Service`                      |
| metadata   | Yes      | See below                      |
| spec       | Yes      | See below                      |

### metadata

| Key         | Required | Description                          |
|------------|----------|--------------------------------------|
| name       | Yes      | Service name (DNS, stack names).     |
| description| No       | Human-readable description.          |

### spec

| Key     | Required (v1) | Description                                      |
|---------|----------------|--------------------------------------------------|
| compute | Yes            | Compute configuration (see below).               |
| secrets | No             | List of secret names to inject from environment. |

### spec.compute

| Key         | Required | Default   | Description                |
|------------|----------|-----------|----------------------------|
| type       | No       | `ecs`     | Compute type.              |
| port       | No       | 80        | Container port.            |
| cpu        | No       | 256       | CPU units.                 |
| memory     | No       | 512       | Memory in MiB.             |
| instances  | No       | —         | Object with `min` (default 1). |
| healthCheck| No       | —         | Object with `path` (default `/health`). |

## Validation

- The engine validates the parsed YAML against the schema for the file’s `apiVersion` before creating any resources. Invalid spec causes a clear error and exit.
- Fixtures under `fixtures/` are tested against the schema in CI so they stay in sync.
