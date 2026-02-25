"""Unit tests for create_rds_instance (RDS subnet group and instance)."""

from unittest.mock import MagicMock, patch

from devops.database.rds import create_rds_instance


@patch("devops.database.rds.pulumi_aws.rds.Instance")
@patch("devops.database.rds.pulumi_aws.rds.SubnetGroup")
def test_create_rds_instance_defaults(
    mock_subnet_group: MagicMock,
    mock_instance: MagicMock,
) -> None:
    """create_rds_instance uses default instance_class, allocated_storage, engine postgres."""
    mock_subnet_group.return_value.name = "my-svc-db-subnets"
    mock_instance.return_value.endpoint = "my-svc-db.abc123.us-east-1.rds.amazonaws.com:5432"

    aws_provider = MagicMock()
    sg_id = MagicMock()
    db_password = MagicMock()

    subnet_group, rds_instance = create_rds_instance(
        service_name="my-svc",
        private_subnet_ids=["subnet-a", "subnet-b"],
        security_group_id=sg_id,
        db_name="my_svc_db",
        db_username="admin",
        db_password=db_password,
        aws_provider=aws_provider,
    )

    assert subnet_group.name == "my-svc-db-subnets"
    assert rds_instance.endpoint == "my-svc-db.abc123.us-east-1.rds.amazonaws.com:5432"

    sg_kw = mock_subnet_group.call_args[1]
    assert sg_kw["name"] == "my-svc-db-subnets"
    assert sg_kw["subnet_ids"] == ["subnet-a", "subnet-b"]

    inst_kw = mock_instance.call_args[1]
    assert inst_kw["engine"] == "postgres"
    assert inst_kw["instance_class"] == "db.t3.micro"
    assert inst_kw["allocated_storage"] == 20
    assert inst_kw["db_name"] == "my_svc_db"
    assert inst_kw["username"] == "admin"
    assert inst_kw["password"] == db_password
    assert inst_kw["vpc_security_group_ids"] == [sg_id]
    assert inst_kw["publicly_accessible"] is False
    assert inst_kw["storage_encrypted"] is True
    assert inst_kw["skip_final_snapshot"] is True


@patch("devops.database.rds.pulumi_aws.rds.Instance")
@patch("devops.database.rds.pulumi_aws.rds.SubnetGroup")
def test_create_rds_instance_custom_config(
    mock_subnet_group: MagicMock,
    mock_instance: MagicMock,
) -> None:
    """create_rds_instance passes through custom instance_class, allocated_storage, multi_az."""
    mock_subnet_group.return_value.name = "test-svc-db-subnets"
    mock_instance.return_value.endpoint = "test-svc-db.xyz.us-west-2.rds.amazonaws.com:5432"

    aws_provider = MagicMock()
    sg_id = MagicMock()
    db_password = MagicMock()

    create_rds_instance(
        service_name="test-svc",
        private_subnet_ids=["subnet-1"],
        security_group_id=sg_id,
        db_name="custom_db",
        db_username="dify_admin",
        db_password=db_password,
        aws_provider=aws_provider,
        instance_class="db.t3.small",
        allocated_storage=50,
        engine_version="16.3",
        multi_az=True,
    )

    inst_kw = mock_instance.call_args[1]
    assert inst_kw["instance_class"] == "db.t3.small"
    assert inst_kw["allocated_storage"] == 50
    assert inst_kw["engine_version"] == "16.3"
    assert inst_kw["multi_az"] is True
    assert inst_kw["db_name"] == "custom_db"
    assert inst_kw["username"] == "dify_admin"
