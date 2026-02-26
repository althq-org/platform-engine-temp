# Platform Engine Development Rules

## Architecture

- Code is organized by **function/layer** (compute, networking, storage, iam), not by vendor
- The spec (`platform.yaml`) is the single source of truth — nothing is provisioned that isn't declared in it
- Capabilities are **compositional**: each YAML section maps to an independent capability handler
- Shared infrastructure (VPC, ALB, Cloudflare zone) is looked up, never created

## Coding Conventions

### Resource Modules (`devops/<layer>/<module>.py`)

- Each module contains a single `create_*` function
- Functions are pure: take typed config + `aws_provider`, return Pulumi resources
- **No hardcoded values** — every parameter must trace back to `platform.yaml` or `SharedInfrastructure`
- Use Pulumi `ResourceOptions(provider=aws_provider)` on every resource
- Tag resources via the provider's `default_tags`, not per-resource

### Capability Handlers (`devops/capabilities/<name>.py`)

- Each handler reads its section config from the `CapabilityContext`
- Handlers call resource modules — they don't create Pulumi resources directly
- Register outputs in the context for other capabilities to consume
- Register exports for Pulumi output (user-visible values like endpoints, IDs)

### Config (`devops/config.py`)

- Each YAML section has a typed `@dataclass` with defaults matching the JSON Schema
- `PlatformConfig.from_file()` parses all sections into their typed dataclasses
- Capabilities receive typed config, not raw dicts (when possible)

### Schema (`devops/schema/platform-spec-v1.json`)

- Every new section must have full field definitions with types, constraints, and descriptions
- Use `additionalProperties: false` on leaf sections (catches typos)
- Use `required` only for truly required fields; provide sensible defaults for everything else
- Defaults in schema must match defaults in the config dataclass

## Testing Requirements

- **Every resource module** must have unit tests that mock Pulumi constructors and verify arguments
- **Every capability handler** must have tests verifying it reads config correctly and calls modules
- **Every fixture** must pass schema validation (tested in CI via `test_spec.py`)
- Run tests: `uv run test` | Run with coverage: `uv run test-cov`
- Target: >80% coverage on `devops/`

## Adding a New Capability

When adding support for a new AWS/Cloudflare resource type:

1. Add section schema to `devops/schema/platform-spec-v1.json` (strict validation)
2. Add typed dataclass to `devops/config.py` and parse in `from_file()`
3. Create resource module at `devops/<layer>/<module>.py`
4. Create capability handler at `devops/capabilities/<name>.py` using `@register`
5. Add unit tests for both module and capability
6. Add or update a fixture in `fixtures/`
7. **Do not modify `__main__.py`** — the registry handles capability discovery

See the "Add a Platform Capability" skill in the meta-repo for detailed templates.

## Common Mistakes

- Writing `additionalProperties: true` on new schema sections (should be `false` for leaf sections)
- Hardcoding resource parameters in capability handlers instead of reading from config
- Forgetting to register capability outputs that other capabilities depend on
- Skipping tests for "simple" modules — every module needs tests
- Modifying `__main__.py` to add routing logic — use the capability registry instead

## Dev Setup

```bash
uv sync --extra dev    # Install dev tools (pytest, ruff, pyright)
uv run test            # Run tests
uv run lint            # Ruff check
uv run type-check      # Pyright
```

## Key Files

- `devops/__main__.py` — Entry point (thin orchestrator)
- `devops/config.py` — Config loading and typed section dataclasses
- `devops/capabilities/registry.py` — Capability registration and phase ordering
- `devops/capabilities/context.py` — Shared context for cross-capability wiring
- `devops/schema/platform-spec-v1.json` — JSON Schema (source of truth for validation)
- `docs/spec.md` — Human-readable spec contract
- `docs/design-decisions.md` — Architecture rationale
