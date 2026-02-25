"""Unit tests for create_efs_filesystem (EFS filesystem, mount targets, access point)."""

from unittest.mock import MagicMock, patch

from devops.storage.efs import create_efs_filesystem


@patch("devops.storage.efs.pulumi_aws.efs.AccessPoint")
@patch("devops.storage.efs.pulumi_aws.efs.MountTarget")
@patch("devops.storage.efs.pulumi_aws.efs.FileSystem")
def test_create_efs_filesystem_defaults(
    mock_fs: MagicMock,
    mock_mt: MagicMock,
    mock_ap: MagicMock,
) -> None:
    """create_efs_filesystem uses default encrypted=True, lifecycle, path, uid/gid."""
    mock_fs.return_value.id = "fs-123"
    mock_fs.return_value.arn = "arn:aws:elasticfilesystem:..."
    mock_ap.return_value.arn = "arn:aws:elasticfilesystem:...:access-point/fsap-123"
    mock_mt.return_value = MagicMock()

    aws_provider = MagicMock()
    sg_id = MagicMock()

    fs, ap, mts = create_efs_filesystem(
        service_name="my-svc",
        private_subnet_ids=["subnet-a", "subnet-b"],
        security_group_id=sg_id,
        aws_provider=aws_provider,
    )

    assert fs.id == "fs-123"
    assert ap.arn == "arn:aws:elasticfilesystem:...:access-point/fsap-123"
    assert len(mts) == 2

    fs_kw = mock_fs.call_args[1]
    assert fs_kw["encrypted"] is True
    assert fs_kw["creation_token"] == "my-svc-efs"
    assert fs_kw["lifecycle_policies"][0].transition_to_ia == "AFTER_30_DAYS"

    ap_kw = mock_ap.call_args[1]
    assert ap_kw["posix_user"].uid == 1000
    assert ap_kw["posix_user"].gid == 1000
    assert ap_kw["root_directory"].path == "/agent-factory"


@patch("devops.storage.efs.pulumi_aws.efs.AccessPoint")
@patch("devops.storage.efs.pulumi_aws.efs.MountTarget")
@patch("devops.storage.efs.pulumi_aws.efs.FileSystem")
def test_create_efs_filesystem_custom_config(
    mock_fs: MagicMock,
    mock_mt: MagicMock,
    mock_ap: MagicMock,
) -> None:
    """create_efs_filesystem passes through custom encrypted, lifecycle, path, uid, gid."""
    mock_fs.return_value.id = "fs-456"
    mock_ap.return_value.arn = "arn:aws:elasticfilesystem:...:access-point/fsap-456"
    mock_mt.return_value = MagicMock()

    aws_provider = MagicMock()
    sg_id = MagicMock()

    _fs, _ap, _mts = create_efs_filesystem(
        service_name="test-svc",
        private_subnet_ids=["subnet-1"],
        security_group_id=sg_id,
        aws_provider=aws_provider,
        encrypted=False,
        lifecycle_policy="AFTER_14_DAYS",
        access_point_path="/data",
        posix_uid=2000,
        posix_gid=2000,
    )

    fs_kw = mock_fs.call_args[1]
    assert fs_kw["encrypted"] is False
    assert fs_kw["lifecycle_policies"][0].transition_to_ia == "AFTER_14_DAYS"

    ap_kw = mock_ap.call_args[1]
    assert ap_kw["posix_user"].uid == 2000
    assert ap_kw["posix_user"].gid == 2000
    assert ap_kw["root_directory"].path == "/data"
    assert ap_kw["root_directory"].creation_info.owner_uid == 2000
    assert ap_kw["root_directory"].creation_info.owner_gid == 2000

    assert mock_mt.call_count == 1
    mt_kw = mock_mt.call_args[1]
    assert mt_kw["file_system_id"] == "fs-456"
    assert mt_kw["subnet_id"] == "subnet-1"
    assert mt_kw["security_groups"] == [sg_id]
