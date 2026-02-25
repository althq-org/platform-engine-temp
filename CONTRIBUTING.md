# Contributing to Platform Engine

## Development Setup

```bash
# Clone and install (runtime + dev tools)
uv sync --extra dev

# Verify
uv run test
uv run lint
uv run type-check
```

**Important**: Use `uv sync --extra dev` (not plain `uv sync`) so dev tools (pytest, ruff, pyright) are installed.

## Running Commands

| Command | What It Does |
|---------|-------------|
| `uv run test` | Run all tests |
| `uv run test-cov` | Tests with coverage report |
| `uv run lint` | Ruff check (devops + tests) |
| `uv run lint-fix` | Ruff check --fix |
| `uv run format` | Ruff format |
| `uv run type-check` | Pyright on devops |

These are defined as script entry points in `pyproject.toml`.

## Architecture Overview

```
platform.yaml → Schema Validation → Typed Config → Capability Detection → Resource Provisioning
```

1. Developer writes a `platform.yaml` declaring what infrastructure they need.
2. The engine validates it against the JSON Schema (`devops/schema/platform-spec-v1.json`).
3. Each YAML section is parsed into a typed dataclass (`devops/config.py`).
4. The engine detects which sections are declared and runs the corresponding capabilities.
5. Capabilities call resource modules to create Pulumi resources.

Code is organized by **function/layer**, not by vendor:

| Directory | What It Contains |
|-----------|-----------------|
| `devops/capabilities/` | Capability handlers (one per spec section) |
| `devops/compute/` | ECR, ECS, Lambda resource modules |
| `devops/storage/` | EFS resource module |
| `devops/cache/` | Redis resource module |
| `devops/database/` | RDS resource module |
| `devops/networking/` | Security groups, DNS, Cloud Map, Cloudflare |
| `devops/loadbalancer/` | Target groups, ALB listener rules |
| `devops/iam/` | IAM roles and policies |
| `devops/triggers/` | EventBridge Scheduler |
| `devops/shared/` | Shared infrastructure lookups (VPC, ALB, Cloudflare) |
| `devops/spec/` | Schema validation |

## Adding a New Capability

If you're adding support for a new AWS/Cloudflare resource type (e.g., SQS, S3, Secrets Manager), follow the "Add a Platform Capability" skill in the meta-repo (`skills/add-platform-capability/`). In short:

1. **Schema** — Add section to `devops/schema/platform-spec-v1.json` (strict validation)
2. **Config** — Add typed dataclass to `devops/config.py`
3. **Module** — Create resource module at `devops/<layer>/<module>.py`
4. **Capability** — Create handler at `devops/capabilities/<name>.py`
5. **Tests** — Unit tests for module + capability
6. **Fixture** — Add or update in `fixtures/`
7. **Docs** — Update `docs/spec.md`

Do **not** modify `__main__.py` — the capability registry handles discovery.

## Writing Resource Modules

Resource modules are pure functions that take typed config and return Pulumi resources.

```python
def create_your_resource(
    service_name: str,
    config_value: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.some.Resource:
    return pulumi_aws.some.Resource(
        f"{service_name}_your_resource",
        property=config_value,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
```

Rules:
- Every parameter comes from function arguments (no globals, no env vars, no hardcoded values)
- Use `ResourceOptions(provider=aws_provider)` on every resource
- Tags are handled by the provider's `default_tags` — don't add per-resource tags

## Writing Tests

Mock Pulumi resource constructors and verify arguments:

```python
@patch("devops.your_layer.your_module.pulumi_aws.some.Resource")
def test_create_your_resource(mock_resource):
    mock_resource.return_value.id = "resource-123"
    result = create_your_resource("my-svc", "value", MagicMock())
    assert result.id == "resource-123"
    call_kw = mock_resource.call_args[1]
    assert call_kw["property"] == "value"
```

## PR Checklist

- [ ] `uv run test` passes
- [ ] `uv run lint` passes
- [ ] `uv run type-check` passes
- [ ] New modules have unit tests
- [ ] Schema changes are strict (`additionalProperties: false` on leaf sections)
- [ ] Config values flow from YAML (no hardcoded values in capabilities)
- [ ] Fixtures validate in CI
- [ ] `docs/spec.md` updated if schema changed

## Key Documentation

| File | What It Covers |
|------|---------------|
| `docs/spec.md` | Full YAML contract — all sections, fields, defaults, outputs |
| `docs/design-decisions.md` | Architecture rationale and key decisions |
| `README.md` | How to use the engine (CLI, workflows) |
| `fixtures/README.md` | Available test fixtures |
