"""EFS FileSystem, MountTargets, AccessPoint."""

import pulumi
import pulumi_aws


def create_efs_filesystem(
    service_name: str,
    private_subnet_ids: list[str],
    security_group_id: pulumi.Output[str],
    aws_provider: pulumi_aws.Provider,
    encrypted: bool = True,
    lifecycle_policy: str = "AFTER_30_DAYS",
    access_point_path: str = "/agent-factory",
    posix_uid: int = 1000,
    posix_gid: int = 1000,
) -> tuple[pulumi_aws.efs.FileSystem, pulumi_aws.efs.AccessPoint, list[pulumi_aws.efs.MountTarget]]:
    """Create EFS filesystem with mount targets and access point."""
    efs_fs = pulumi_aws.efs.FileSystem(
        f"{service_name}_efs",
        creation_token=f"{service_name}-efs",
        encrypted=encrypted,
        performance_mode="generalPurpose",
        throughput_mode="elastic",
        lifecycle_policies=[
            pulumi_aws.efs.FileSystemLifecyclePolicyArgs(
                transition_to_ia=lifecycle_policy,
            ),
        ],
        tags={"Name": f"{service_name}-efs"},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    mount_targets = []
    for i, subnet_id in enumerate(private_subnet_ids):
        mt = pulumi_aws.efs.MountTarget(
            f"{service_name}_efs_mt_{i}",
            file_system_id=efs_fs.id,
            subnet_id=subnet_id,
            security_groups=[security_group_id],
            opts=pulumi.ResourceOptions(provider=aws_provider),
        )
        mount_targets.append(mt)
    access_point = pulumi_aws.efs.AccessPoint(
        f"{service_name}_efs_ap",
        file_system_id=efs_fs.id,
        posix_user=pulumi_aws.efs.AccessPointPosixUserArgs(
            uid=posix_uid,
            gid=posix_gid,
        ),
        root_directory=pulumi_aws.efs.AccessPointRootDirectoryArgs(
            path=access_point_path,
            creation_info=pulumi_aws.efs.AccessPointRootDirectoryCreationInfoArgs(
                owner_uid=posix_uid,
                owner_gid=posix_gid,
                permissions="755",
            ),
        ),
        tags={"Name": f"{service_name}-efs-ap"},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return (efs_fs, access_point, mount_targets)
