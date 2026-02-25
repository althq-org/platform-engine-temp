# Platform.yaml Fixtures

Use these with the platform CLI for local testing:

```bash
# After `uv run platform setup`, from repo root:
uv run platform create fixtures/platform-minimal.yaml
# ... later ...
uv run platform destroy platform-engine-test
```

## Available Fixtures

| Fixture | Service Name | Capabilities Exercised | Purpose |
|---------|-------------|----------------------|---------|
| `platform-minimal.yaml` | `platform-engine-test` | `compute` | Minimal valid spec. One ECS instance, port 80, no secrets. Use for smoke testing. |
| `platform-agent-factory.yaml` | `agent-factory` | `compute`, `storage`, `cache`, `database`, `serviceDiscovery`, `lambda`, `triggers`, `secrets` | Full Agent Factory stack. Exercises all capability sections. |

## Adding a Fixture

1. Create a new YAML file in this directory.
2. Follow the schema at `devops/schema/platform-spec-v1.json`.
3. Run `uv run test` to verify it passes schema validation (all fixtures are validated in CI).
4. Add an entry to the table above.

## Schema Validation

All `*.yaml` files in this directory are automatically validated against the JSON Schema in CI tests (`tests/test_spec.py`). If a fixture fails validation, tests will fail.
