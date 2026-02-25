"""Tests for the storage capability handler (config → create_efs_filesystem, ctx.set/export)."""

from unittest.mock import MagicMock, patch

import devops.capabilities.storage  # noqa: F401 - register storage capability
from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES


def _make_ctx_with_efs_sg() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "platform-v2-test"
    infra = MagicMock()
    infra.private_subnet_ids = ["subnet-a", "subnet-b"]
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    ctx.set("security_groups.efs.id", MagicMock())
    return ctx


@patch("devops.storage.efs.create_efs_filesystem")
def test_storage_handler_calls_create_efs_with_config_and_sets_context(
    mock_create_efs: MagicMock,
) -> None:
    """Storage handler reads section_config, calls create_efs_filesystem, sets and exports in ctx."""
    mock_fs = MagicMock()
    mock_fs.id = "fs-123"
    mock_ap = MagicMock()
    mock_ap.arn = "arn:aws:elasticfilesystem:us-west-2:123:access-point/fsap-123"
    mock_create_efs.return_value = (mock_fs, mock_ap, [])

    section_config = {
        "efs": {
            "encrypted": True,
            "lifecycle": "AFTER_30_DAYS",
            "accessPoint": {
                "path": "/data",
                "uid": 1000,
                "gid": 1000,
            },
        },
    }
    ctx = _make_ctx_with_efs_sg()
    handler = CAPABILITIES["storage"].handler
    handler(section_config, ctx)

    mock_create_efs.assert_called_once()
    call_kw = mock_create_efs.call_args[1]
    assert call_kw["service_name"] == "platform-v2-test"
    assert call_kw["private_subnet_ids"] == ["subnet-a", "subnet-b"]
    assert call_kw["encrypted"] is True
    assert call_kw["lifecycle_policy"] == "AFTER_30_DAYS"
    assert call_kw["access_point_path"] == "/data"
    assert call_kw["posix_uid"] == 1000
    assert call_kw["posix_gid"] == 1000

    assert ctx.get("storage.efs.filesystem_id") == "fs-123"
    assert ctx.get("storage.efs.access_point_arn") == "arn:aws:elasticfilesystem:us-west-2:123:access-point/fsap-123"
    assert ctx.exports["efs_filesystem_id"] == "fs-123"


@patch("devops.storage.efs.create_efs_filesystem")
def test_storage_handler_uses_defaults_when_efs_section_minimal(
    mock_create_efs: MagicMock,
) -> None:
    """Storage handler uses default encrypted, lifecycle, path, uid, gid when efs config is minimal."""
    mock_fs = MagicMock()
    mock_fs.id = "fs-default"
    mock_ap = MagicMock()
    mock_ap.arn = "arn:aws:elasticfilesystem:...:access-point/fsap-default"
    mock_create_efs.return_value = (mock_fs, mock_ap, [])

    section_config = {"efs": {}}
    ctx = _make_ctx_with_efs_sg()
    handler = CAPABILITIES["storage"].handler
    handler(section_config, ctx)

    call_kw = mock_create_efs.call_args[1]
    assert call_kw["encrypted"] is True
    assert call_kw["lifecycle_policy"] == "AFTER_30_DAYS"
    assert call_kw["access_point_path"] == "/data"
    assert call_kw["posix_uid"] == 1000
    assert call_kw["posix_gid"] == 1000
