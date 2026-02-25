"""RDS SubnetGroup + Instance."""

import pulumi
import pulumi_aws


def create_rds_instance(
    service_name: str,
    private_subnet_ids: list[str],
    security_group_id: pulumi.Output[str],
    db_name: str,
    db_username: str,
    db_password: pulumi.Output[str],
    aws_provider: pulumi_aws.Provider,
    instance_class: str = "db.t3.micro",
    allocated_storage: int = 20,
    engine_version: str = "16.4",
    multi_az: bool = False,
) -> tuple[pulumi_aws.rds.SubnetGroup, pulumi_aws.rds.Instance]:
    subnet_group = pulumi_aws.rds.SubnetGroup(
        f"{service_name}_db_subnets",
        name=f"{service_name}-db-subnets",
        subnet_ids=private_subnet_ids,
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    rds_instance = pulumi_aws.rds.Instance(
        f"{service_name}_db",
        identifier=f"{service_name}-db",
        engine="postgres",
        engine_version=engine_version,
        instance_class=instance_class,
        allocated_storage=allocated_storage,
        db_name=db_name,
        username=db_username,
        password=db_password,
        db_subnet_group_name=subnet_group.name,
        vpc_security_group_ids=[security_group_id],
        multi_az=multi_az,
        publicly_accessible=False,
        storage_encrypted=True,
        skip_final_snapshot=True,
        backup_retention_period=7,
        tags={"Name": f"{service_name}-db"},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return (subnet_group, rds_instance)
