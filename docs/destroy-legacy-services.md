# Destroy legacy services (no destroy workflow in repo)

Run these from **platform-engine-temp** repo root. You need a `platform.yaml` for each service (clone the repo or use a minimal one). Backend and stack naming match the GitHub destroy workflow.

**One-time setup:** Ensure AWS credentials and Pulumi are set up (`platform setup` and `aws sso login` if needed). Set backend:

```bash
export PULUMI_BACKEND_URL=s3://470935583836-pulumi-backend-software
```

Clone each repo once (e.g. to `/tmp/<service-name>`), then for each service set `PLATFORM_YAML_PATH` and run the three commands.

---

## my-new-service

```bash
# If you haven't cloned: git clone git@github.com:althq-org/my-new-service.git /tmp/my-new-service
export PLATFORM_YAML_PATH=/tmp/my-new-service/platform.yaml
cd /path/to/platform-engine-temp
uv run pulumi stack select dev.my-new-service.us-west-2 -C devops
uv run pulumi destroy --yes --non-interactive -C devops
uv run pulumi stack rm --yes -C devops
```

---

## my-fast-api

```bash
# If you haven't cloned: git clone git@github.com:althq-org/my-fast-api.git /tmp/my-fast-api
export PLATFORM_YAML_PATH=/tmp/my-fast-api/platform.yaml
cd /path/to/platform-engine-temp
uv run pulumi stack select dev.my-fast-api.us-west-2 -C devops
uv run pulumi destroy --yes --non-interactive -C devops
uv run pulumi stack rm --yes -C devops
```

---

## tuan-test-2

```bash
# If you haven't cloned: git clone git@github.com:althq-org/tuan-test-2.git /tmp/tuan-test-2
export PLATFORM_YAML_PATH=/tmp/tuan-test-2/platform.yaml
cd /path/to/platform-engine-temp
uv run pulumi stack select dev.tuan-test-2.us-west-2 -C devops
uv run pulumi destroy --yes --non-interactive -C devops
uv run pulumi stack rm --yes -C devops
```

---

## test-platform-engine-1

```bash
# If you haven't cloned: git clone git@github.com:althq-org/test-platform-engine-1.git /tmp/test-platform-engine-1
export PLATFORM_YAML_PATH=/tmp/test-platform-engine-1/platform.yaml
cd /path/to/platform-engine-temp
uv run pulumi stack select dev.test-platform-engine-1.us-west-2 -C devops
uv run pulumi destroy --yes --non-interactive -C devops
uv run pulumi stack rm --yes -C devops
```

---

## my-ecs-service

```bash
# If you haven't cloned: git clone git@github.com:althq-org/my-ecs-service.git /tmp/my-ecs-service
export PLATFORM_YAML_PATH=/tmp/my-ecs-service/platform.yaml
cd /path/to/platform-engine-temp
uv run pulumi stack select dev.my-ecs-service.us-west-2 -C devops
uv run pulumi destroy --yes --non-interactive -C devops
uv run pulumi stack rm --yes -C devops
```

---

**Note:** Replace `/path/to/platform-engine-temp` with your actual path (e.g. `~/Workspace/platform-engine-temp`). If a stack doesn’t exist, `pulumi stack select` will fail; that’s expected for services that were never provisioned or already destroyed.
