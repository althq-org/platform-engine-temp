# Platform.yaml fixtures

Use these with the platform CLI for local testing:

```bash
# After `uv run platform setup`, from repo root:
uv run platform create fixtures/platform-minimal.yaml
# ... later ...
uv run platform destroy platform-engine-test
```

- **platform-minimal.yaml** – Minimal valid spec (one instance, port 80, no secrets). Service name: `platform-engine-test`.
