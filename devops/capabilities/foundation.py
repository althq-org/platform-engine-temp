"""Foundation provisioning: security groups and IAM roles shared by capabilities."""

from devops.capabilities.context import CapabilityContext


def provision_foundation(spec_sections: dict, ctx: CapabilityContext) -> None:
    """Create shared security groups and IAM roles based on declared spec sections.

    Imports security_groups and iam.roles inside the function to avoid circular imports.
    """
    declared = set(spec_sections.keys())
    service_name = ctx.config.service_name
    vpc_id = ctx.infra.vpc_id
    vpc_cidr = ctx.infra.vpc_cidr
    aws_provider = ctx.aws_provider

    if "compute" in declared or "lambda" in declared:
        from devops.networking.security_groups import create_ecs_security_group

        compute_sg = create_ecs_security_group(
            service_name, vpc_id, vpc_cidr, aws_provider
        )
        ctx.set("security_groups.compute", compute_sg)
        ctx.set("security_groups.compute.id", compute_sg.id)

    if "database" in declared or "cache" in declared or "storage" in declared:
        from devops.networking.security_groups import create_agent_security_group

        agent_sg = create_agent_security_group(service_name, vpc_id, aws_provider)
        ctx.set("security_groups.agent.id", agent_sg.id)

    if "database" in declared or "cache" in declared:
        from devops.networking.security_groups import create_database_security_group

        db_sg = create_database_security_group(
            service_name,
            vpc_id,
            control_plane_sg_id=ctx.get("security_groups.compute.id"),
            agent_sg_id=ctx.get("security_groups.agent.id"),
            aws_provider=aws_provider,
        )
        ctx.set("security_groups.database.id", db_sg.id)

    if "storage" in declared:
        from devops.networking.security_groups import create_efs_security_group

        efs_sg = create_efs_security_group(
            service_name,
            vpc_id,
            control_plane_sg_id=ctx.get("security_groups.compute.id"),
            agent_sg_id=ctx.get("security_groups.agent.id"),
            aws_provider=aws_provider,
        )
        ctx.set("security_groups.efs.id", efs_sg.id)

    if "compute" in declared:
        from devops.iam.roles import create_task_roles

        task_role, exec_role = create_task_roles(service_name, aws_provider)
        ctx.set("iam.task_role", task_role)
        ctx.set("iam.exec_role", exec_role)

    if "lambda" in declared:
        from devops.iam.roles import create_lambda_execution_role

        lambda_role = create_lambda_execution_role(service_name, aws_provider)
        ctx.set("iam.lambda_execution_role", lambda_role)

    if "agentcoreRuntime" in declared:
        from devops.iam.roles import (
            create_agentcore_memory_role,
            create_agentcore_runtime_role,
        )

        agentcore_role = create_agentcore_runtime_role(service_name, aws_provider)
        ctx.set("iam.agentcore_runtime_role", agentcore_role)

        memory_role = create_agentcore_memory_role(service_name, aws_provider)
        ctx.set("iam.agentcore_memory_role", memory_role)
