"""
Platform engine CLI: list, create, destroy. Hides infrastructure tooling from the user.
Run `platform setup` once; then use `platform list`, `platform create`, `platform destroy`.
"""

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml

CONFIG_DIR = ".platform-engine"
CONFIG_FILENAME = "config.yaml"
TAG_MANAGED = "platform-engine-managed"
TAG_SERVICE = "service"
DEFAULT_STACK_PREFIX = "dev"
KMS_SECRETS_PROVIDER_TEMPLATE = "awskms://alias/pulumi_backend_software?region={region}"


def _project_root() -> Path:
    """Directory containing devops/ (and pyproject.toml). Use cwd as default."""
    cwd = Path.cwd()
    if (cwd / "devops" / "Pulumi.yaml").exists():
        return cwd
    if (cwd / "Pulumi.yaml").exists():
        return cwd
    # When run as `uv run platform` from repo root, cwd is repo root
    return cwd


def _config_path() -> Path:
    return _project_root() / CONFIG_DIR / CONFIG_FILENAME


def _load_config() -> dict[str, Any] | None:
    path = _config_path()
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else None


def _save_config(backend_url: str, region: str, stack_prefix: str = DEFAULT_STACK_PREFIX) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "backend_url": backend_url,
                "region": region,
                "stack_prefix": stack_prefix,
            },
            f,
            default_flow_style=False,
        )
    print(f"Configuration saved to {path}")


def _require_config() -> dict[str, Any]:
    config = _load_config()
    if not config or not config.get("backend_url") or not config.get("region"):
        print("Configuration missing or incomplete. Run: platform setup", file=sys.stderr)
        sys.exit(1)
    return config


def _check_aws_credentials() -> bool:
    try:
        subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run(cmd: list[str], env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        cmd,
        cwd=_project_root(),
        env=full_env,
        check=check,
    )


def _service_name_from_yaml(path: Path) -> str:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["metadata"]["name"]


def _stack_name(service_name: str, config: dict[str, Any]) -> str:
    prefix = config.get("stack_prefix", DEFAULT_STACK_PREFIX)
    region = config["region"]
    return f"{prefix}.{service_name}.{region}"


# --- setup ---


def _cmd_setup() -> None:
    print("First-time setup. You will need:")
    print("  1) AWS credentials (e.g. run: aws sso login)")
    print("  2) S3 URI for infrastructure state (e.g. s3://your-account-pulumi-backend-software)")
    print("  3) Default AWS region (e.g. us-west-2)")
    print()

    if not _check_aws_credentials():
        print("AWS credentials not found. Log in (e.g. aws sso login) and try again.", file=sys.stderr)
        sys.exit(1)
    print("AWS credentials OK.")

    backend_url = os.environ.get("PLATFORM_ENGINE_BACKEND_URL", "").strip()
    if not backend_url:
        backend_url = input("S3 URI for infrastructure state: ").strip()
    if not backend_url:
        print("Backend URL is required.", file=sys.stderr)
        sys.exit(1)

    region = os.environ.get("PLATFORM_ENGINE_REGION", "").strip()
    if not region:
        region = input("Default AWS region (e.g. us-west-2): ").strip()
    if not region:
        print("Region is required.", file=sys.stderr)
        sys.exit(1)

    stack_prefix = os.environ.get("PLATFORM_ENGINE_STACK_PREFIX", DEFAULT_STACK_PREFIX).strip() or DEFAULT_STACK_PREFIX
    _save_config(backend_url, region, stack_prefix)
    print("Setup complete. You can now use: platform list, platform create <path>, platform destroy <service-name>")


# --- list ---


def _cmd_list() -> None:
    try:
        import boto3
    except ImportError:
        print("Listing requires boto3. Install with: uv sync (boto3 is a dependency)", file=sys.stderr)
        sys.exit(1)

    config = _load_config()
    region = config.get("region") if config else os.environ.get("AWS_REGION", "us-west-2")
    client = boto3.client("resourcegroupstaggingapi", region_name=region)
    services: dict[str, list[dict[str, str]]] = {}

    paginator = client.get_paginator("get_resources")
    for page in paginator.paginate(
        TagFilters=[{"Key": TAG_MANAGED, "Values": ["true"]}],
        ResourcesPerPage=100,
    ):
        for r in page.get("ResourceTagList", []):
            arn = r.get("ResourceARN", "")
            tags = {t["Key"]: t["Value"] for t in r.get("Tags", [])}
            svc = tags.get(TAG_SERVICE, "?")
            if svc not in services:
                services[svc] = []
            resource_type = arn.split(":")[2] if ":" in arn else "resource"
            services[svc].append({"arn": arn, "type": resource_type})

    if not services:
        print("No platform-engine-managed resources found.")
        return
    for name in sorted(services.keys()):
        print(f"\n{name}")
        for r in services[name]:
            print(f"  {r['type']}: {r['arn']}")


# --- create ---


def _cmd_create(platform_yaml_path: str) -> None:
    config = _require_config()
    path = Path(platform_yaml_path)
    if not path.is_absolute():
        path = _project_root() / path
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    service_name = _service_name_from_yaml(path)
    stack = _stack_name(service_name, config)
    backend_url = config["backend_url"]
    region = config["region"]
    devops_dir = _project_root() / "devops"
    if not (devops_dir / "Pulumi.yaml").exists():
        print("devops/Pulumi.yaml not found. Run this from the platform-engine-temp repo root.", file=sys.stderr)
        sys.exit(1)

    env = {
        "PLATFORM_YAML_PATH": str(path.resolve()),
        "PULUMI_BACKEND_URL": backend_url,
    }
    # Select or create stack
    select = _run(
        [sys.executable, "-m", "pulumi", "stack", "select", stack, "-C", "devops"],
        env=env,
        check=False,
    )
    if select.returncode != 0:
        kms = KMS_SECRETS_PROVIDER_TEMPLATE.format(region=region)
        _run(
            [
                sys.executable,
                "-m",
                "pulumi",
                "stack",
                "init",
                stack,
                "--secrets-provider",
                kms,
                "-C",
                "devops",
            ],
            env=env,
        )
    _run(
        [sys.executable, "-m", "pulumi", "config", "set", "aws:region", region, "-C", "devops"],
        env=env,
    )
    print(f"Provisioning infrastructure for service '{service_name}'...")
    _run([sys.executable, "-m", "pulumi", "up", "-C", "devops", "-y"], env=env)
    print(f"Service '{service_name}' provisioned. URL: https://{service_name}.althq-dev.com (if DNS is configured)")


# --- destroy ---


def _cmd_destroy(service_name: str) -> None:
    config = _require_config()
    stack = _stack_name(service_name, config)
    backend_url = config["backend_url"]
    devops_dir = _project_root() / "devops"
    if not (devops_dir / "Pulumi.yaml").exists():
        print("devops/Pulumi.yaml not found. Run this from the platform-engine-temp repo root.", file=sys.stderr)
        sys.exit(1)

    env = {"PULUMI_BACKEND_URL": backend_url}
    select = _run(
        [sys.executable, "-m", "pulumi", "stack", "select", stack, "-C", "devops"],
        env=env,
        check=False,
    )
    if select.returncode != 0:
        print(f"No infrastructure found for service '{service_name}' (stack {stack}).", file=sys.stderr)
        sys.exit(1)
    confirm = input(f"This will remove all infrastructure for service '{service_name}'. Continue? [y/N]: ")
    if confirm.strip().lower() != "y":
        print("Cancelled.")
        sys.exit(0)
    _run([sys.executable, "-m", "pulumi", "destroy", "-C", "devops", "-y"], env=env)
    rm = _run(
        [sys.executable, "-m", "pulumi", "stack", "rm", stack, "-C", "devops", "--yes"],
        env=env,
        check=False,
    )
    if rm.returncode != 0:
        pass  # Stack rm can fail if already gone; ignore
    print(f"Service '{service_name}' removed.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage platform-engine infrastructure (list, create, destroy). Run 'platform setup' first."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="One-time setup: AWS, state storage, region")
    sub.add_parser("list", help="List engine-managed resources by service")
    create_p = sub.add_parser("create", help="Provision infrastructure from a platform.yaml")
    create_p.add_argument("platform_yaml", help="Path to platform.yaml (file or fixture)")
    destroy_p = sub.add_parser("destroy", help="Remove all infrastructure for a service")
    destroy_p.add_argument("service_name", help="Service name (from platform.yaml metadata.name)")
    args = parser.parse_args()

    if args.command == "setup":
        _cmd_setup()
    elif args.command == "list":
        _cmd_list()
    elif args.command == "create":
        _cmd_create(args.platform_yaml)
    elif args.command == "destroy":
        _cmd_destroy(args.service_name)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
