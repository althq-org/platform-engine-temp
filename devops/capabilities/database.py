"""Database capability: RDS instance (Postgres)."""

import os
from typing import Any

import pulumi

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import Phase, register


@register("database", phase=Phase.INFRASTRUCTURE)
def database_handler(
    section_config: dict[str, Any],
    ctx: CapabilityContext,
) -> None:
    """Provision RDS from spec.database; requires foundation to have set security_groups.database.id."""
    from devops.database.rds import create_rds_instance

    sg_id = ctx.require("security_groups.database.id")
    db_password = pulumi.Output.secret(
        os.environ.get("DIFY_DB_PASSWORD", "changeme")
    )

    _subnet_group, rds_instance = create_rds_instance(
        service_name=ctx.config.service_name,
        private_subnet_ids=ctx.infra.private_subnet_ids,
        security_group_id=sg_id,
        db_name=section_config.get("dbName") or f"{ctx.config.service_name}_db",
        db_username=section_config.get("dbUsername") or "admin",
        db_password=db_password,
        aws_provider=ctx.aws_provider,
        instance_class=section_config.get("instanceClass", "db.t3.micro"),
        allocated_storage=section_config.get("allocatedStorage", 20),
    )

    ctx.set("database.rds.endpoint", rds_instance.endpoint)
    ctx.export("rds_endpoint", rds_instance.endpoint)
