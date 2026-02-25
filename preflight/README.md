# Preflight

**The Agent Factory's infrastructure verification system.**

Preflight is a one-shot Fargate task that runs inside the VPC with `sg_agents` after every `pulumi up`. It proves that infrastructure actually works — not just exists.

## What It Does

Mounts EFS and writes a file. Connects to Redis and does SET/GET. Connects to RDS and runs SELECT 1. Resolves Cloud Map DNS. Reaches github.com outbound. Each check retries 3 times with backoff.

## How to Run Locally

```bash
docker build -t af-preflight .
docker run --rm \
  -e REDIS_HOST=localhost \
  -e RDS_HOST=localhost \
  -e RDS_USER=postgres \
  -e RDS_PASSWORD=postgres \
  -v ./local-efs:/mnt/efs \
  af-preflight
```

## How to Add Checks

Add a `verify_*()` function and a `check()` call in `__main__`. That's it.

## Integration

```
platform create → pulumi up → launch Preflight → wait for exit code
  ├─ exit 0 → all checks PASSED
  └─ exit 1 → which check failed and why
```
