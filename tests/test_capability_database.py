"""Tests for the database capability handler (config → create_rds_instance, ctx.set/export)."""

from unittest.mock import MagicMock, patch

import devops.capabilities.database  # noqa: F401 - register database capability
from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES


def _make_ctx_with_db_sg() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "platform-v2-test"
    infra = MagicMock()
    infra.private_subnet_ids = ["subnet-a", "subnet-b"]
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    ctx.set("security_groups.database.id", MagicMock())
    return ctx


@patch("devops.capabilities.database.pulumi.Output.secret")
@patch("devops.database.rds.create_rds_instance")
def test_database_handler_calls_create_rds_and_sets_context(
    mock_create_rds: MagicMock,
    mock_secret: MagicMock,
) -> None:
    """Database handler reads section_config, calls create_rds_instance, sets and exports endpoint."""
    mock_secret.return_value = MagicMock()
    mock_subnet = MagicMock()
    mock_instance = MagicMock()
    mock_instance.endpoint = "platform-v2-test-db.abc123.us-east-1.rds.amazonaws.com:5432"
    mock_create_rds.return_value = (mock_subnet, mock_instance)

    section_config = {
        "engine": "postgres",
        "instanceClass": "db.t3.micro",
        "allocatedStorage": 20,
    }
    ctx = _make_ctx_with_db_sg()
    handler = CAPABILITIES["database"].handler
    handler(section_config, ctx)

    mock_create_rds.assert_called_once()
    call_kw = mock_create_rds.call_args[1]
    assert call_kw["service_name"] == "platform-v2-test"
    assert call_kw["private_subnet_ids"] == ["subnet-a", "subnet-b"]
    assert call_kw["instance_class"] == "db.t3.micro"
    assert call_kw["allocated_storage"] == 20
    assert call_kw["db_name"] == "platform-v2-test_db"
    assert call_kw["db_username"] == "admin"

    assert ctx.get("database.rds.endpoint") == mock_instance.endpoint
    assert ctx.exports["rds_endpoint"] == mock_instance.endpoint


@patch("devops.capabilities.database.pulumi.Output.secret")
@patch("devops.database.rds.create_rds_instance")
def test_database_handler_uses_custom_db_name_and_username(
    mock_create_rds: MagicMock,
    mock_secret: MagicMock,
) -> None:
    """Database handler uses dbName and dbUsername from section_config when provided."""
    mock_secret.return_value = MagicMock()
    mock_subnet = MagicMock()
    mock_instance = MagicMock()
    mock_instance.endpoint = "custom.xyz.rds.amazonaws.com:5432"
    mock_create_rds.return_value = (mock_subnet, mock_instance)

    section_config = {
        "engine": "postgres",
        "dbName": "dify_production",
        "dbUsername": "dify_admin",
        "instanceClass": "db.t3.small",
        "allocatedStorage": 50,
    }
    ctx = _make_ctx_with_db_sg()
    handler = CAPABILITIES["database"].handler
    handler(section_config, ctx)

    call_kw = mock_create_rds.call_args[1]
    assert call_kw["db_name"] == "dify_production"
    assert call_kw["db_username"] == "dify_admin"
    assert call_kw["instance_class"] == "db.t3.small"
    assert call_kw["allocated_storage"] == 50


@patch("devops.capabilities.database.pulumi.Output.secret")
@patch("devops.capabilities.database.os.environ.get", return_value="secret123")
@patch("devops.database.rds.create_rds_instance")
def test_database_handler_uses_env_for_password(
    mock_create_rds: MagicMock,
    mock_env_get: MagicMock,
    mock_secret: MagicMock,
) -> None:
    """Database handler uses DIFY_DB_PASSWORD from env for secret."""
    mock_secret.return_value = MagicMock()
    mock_create_rds.return_value = (MagicMock(), MagicMock())

    section_config = {"engine": "postgres"}
    ctx = _make_ctx_with_db_sg()
    handler = CAPABILITIES["database"].handler
    handler(section_config, ctx)

    mock_env_get.assert_called_with("DIFY_DB_PASSWORD", "changeme")
    mock_secret.assert_called_once_with("secret123")


@patch("devops.capabilities.database.pulumi.Output.secret")
@patch("devops.capabilities.database.os.environ.get", return_value="changeme")
@patch("devops.database.rds.create_rds_instance")
def test_database_handler_fallback_password_when_env_unset(
    mock_create_rds: MagicMock,
    mock_env_get: MagicMock,
    mock_secret: MagicMock,
) -> None:
    """Database handler uses default 'changeme' when DIFY_DB_PASSWORD not set."""
    mock_secret.return_value = MagicMock()
    mock_create_rds.return_value = (MagicMock(), MagicMock())

    section_config = {"engine": "postgres"}
    ctx = _make_ctx_with_db_sg()
    handler = CAPABILITIES["database"].handler
    handler(section_config, ctx)

    mock_secret.assert_called_once_with("changeme")
