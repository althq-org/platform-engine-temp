# platform-engine-temp

Temporary repo for developing the Platform Engine. After testing, the reusable workflow and Pulumi logic will move to althq-devops.

## What it does

- **Reusable workflow** (`.github/workflows/provision_from_platform_yaml.yaml`): Called by service repos on push to main. Checks out the service repo, runs Pulumi from `devops/` to provision ECR, ECS cluster, target group, ALB listener rule (on shared 443 listener), and Cloudflare DNS. Then builds and pushes the Docker image, and forces an ECS deployment.
- **Pulumi project** (`devops/`): Reads `platform.yaml` from the service repo (path via `PLATFORM_YAML_PATH`). Uses shared VPC, external ALB, and 443 listener; creates per-service resources. HTTPS is via existing ACM wildcard cert on the ALB and Cloudflare DNS (proxied).

## Prerequisites

- IAM role `platform_engine_temp_workflows` with OIDC trust for `repo:althq-org/*` and permissions for ECR, ECS, EC2, ELB, Cloudflare (via SSM), S3 (Pulumi backend).
- Pulumi backend: `s3://<account_id>-pulumi-backend-software`
- SSM parameters: `/cloudflare/platform_infra_token`, `/cloudflare/zone_id` (same as platform product).
- **Cross-repo checkout:** The workflow runs in the caller repo and checks out this repo (platform-engine-temp) to `engine/`. If your org restricts `GITHUB_TOKEN` to the current repo only, add a `REPO_ACCESS_TOKEN` secret (PAT with read access to `althq-org/platform-engine-temp`) to the caller repo and use `secrets: inherit` when calling this workflow.

## Calling the workflow from a service repo

```yaml
jobs:
  deploy:
    uses: althq-org/platform-engine-temp/.github/workflows/provision_from_platform_yaml.yaml@main
    with:
      service_repo: althq-org/my-ecs-service
      ref: ${{ github.sha }}
      platform_yaml_path: platform.yaml
      stack: dev
      aws_region: us-west-2
      aws_acct_id: "470935583836"
    secrets: inherit
```

## Platform CLI (list, create, destroy)

The CLI lets you manage infrastructure without dealing with infrastructure tooling directly. Run from the repo root.

**One-time setup:** Run once (e.g. after cloning or on a new machine):

```bash
uv run platform setup
```

You will need AWS credentials (e.g. `aws sso login`). S3 state URI and region default to dev (`s3://470935583836-pulumi-backend-software`, `us-west-2`); press Enter to accept or type a value to override. Stored in `.platform-engine/config.yaml` (gitignored).

**Then use:**

| Command | What it does |
|--------|----------------|
| `uv run platform list` | List all engine-managed resources (grouped by service) |
| `uv run platform create <path>` | Provision infrastructure from a platform.yaml (path can be a fixture or another project) |
| `uv run platform destroy <service-name>` | Remove all infrastructure for that service (prompts to confirm) |

You only need to give your intent: list, create, or destroy. Stack selection, config, and state storage are handled for you. **Note:** `platform list` only needs AWS credentials (no setup). Setup is required for `create` and `destroy`. For `create` and `destroy` you must have the [Pulumi CLI](https://www.pulumi.com/docs/install/) on your PATH.

## Development (uv)

**Important:** Use `uv sync --extra dev` so dev tools (pytest, ruff, pyright) are installed. Plain `uv sync` installs only runtime deps and will remove dev tools. Then you can run:

| Command | What it does |
|--------|----------------|
| `uv run lint` | Ruff check (devops + tests) |
| `uv run lint-fix` | Ruff check --fix |
| `uv run format` | Ruff format |
| `uv run type-check` | Pyright on devops |
| `uv run test` | Pytest |
| `uv run test-cov` | Pytest with coverage |

These are defined as **script entry points** in `pyproject.toml` under `[project.scripts]`. Use this table or `pyproject.toml` as the source of truth.

## Scripts

- `scripts/check_workflow.sh` – Poll GitHub Actions run until complete; on failure, show failed logs.
- `scripts/check_endpoint.sh` – Test HTTPS endpoint with retries.

## Organization and design

Code is organized by **function/layer** (compute, networking, IAM, loadbalancer, etc.), not by vendor. Provisioning is **capability-based**: the engine runs only the capabilities implied by `platform.yaml` (today: ECS); the spec is the contract. For design rationale and decisions, see [Design decisions](docs/design-decisions.md).

## Stack naming

One stack per service per env: `{stack}.{service_name}.{region}` (e.g. `dev.my-ecs-service.us-west-2`). The workflow creates the stack if it does not exist.
