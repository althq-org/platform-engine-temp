"""Storage capability: EFS filesystem and access point."""

from typing import Any

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("storage", phase=Phase.INFRASTRUCTURE)
def storage_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision EFS from spec.storage.efs; requires foundation to have set security_groups.efs.id."""
    from devops.storage.efs import create_efs_filesystem

    sg_id = ctx.require("security_groups.efs.id")
    efs_cfg = section_config.get("efs", {})
    access_point_cfg = efs_cfg.get("accessPoint", {})

    efs_fs, efs_ap, _mts = create_efs_filesystem(
        service_name=ctx.config.service_name,
        private_subnet_ids=ctx.infra.private_subnet_ids,
        security_group_id=sg_id,
        aws_provider=ctx.aws_provider,
        encrypted=efs_cfg.get("encrypted", True),
        lifecycle_policy=efs_cfg.get("lifecycle", "AFTER_30_DAYS"),
        access_point_path=access_point_cfg.get("path", "/data"),
        posix_uid=access_point_cfg.get("uid", 1000),
        posix_gid=access_point_cfg.get("gid", 1000),
    )

    ctx.set("storage.efs.filesystem_id", efs_fs.id)
    ctx.set("storage.efs.access_point_arn", efs_ap.arn)
    ctx.export("efs_filesystem_id", efs_fs.id)
