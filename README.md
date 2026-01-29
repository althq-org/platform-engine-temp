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

## Scripts

- `scripts/check_workflow.sh` – Poll GitHub Actions run until complete; on failure, show failed logs.
- `scripts/check_endpoint.sh` – Test HTTPS endpoint with retries.

## Stack naming

One stack per service per env: `{stack}.{service_name}.{region}` (e.g. `dev.my-ecs-service.us-west-2`). The workflow creates the stack if it does not exist.
