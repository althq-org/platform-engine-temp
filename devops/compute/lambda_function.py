"""Lambda function from container image with VPC, EFS, and Function URL."""

import pulumi
import pulumi_aws


def create_lambda_function(
    service_name: str,
    function_name: str,
    ecr_image_uri: pulumi.Output[str],
    execution_role: pulumi_aws.iam.Role,
    subnet_ids: list[str],
    security_group_id: pulumi.Output[str],
    efs_access_point_arn: pulumi.Output[str],
    efs_mount_path: str,
    aws_provider: pulumi_aws.Provider,
    memory_size: int = 2048,
    timeout: int = 120,
    environment: dict[str, str] | None = None,
) -> tuple[pulumi_aws.lambda_.Function, pulumi_aws.lambda_.FunctionUrl]:
    """Create container-image Lambda with VPC, EFS mount, and streaming Function URL."""
    env_vars = environment or {}
    env_vars.update({
        "AWS_LWA_READINESS_CHECK_PATH": "/health",
        "AWS_LWA_INVOKE_MODE": "response_stream",
    })

    fn = pulumi_aws.lambda_.Function(
        f"{service_name}_{function_name}_lambda",
        name=f"{service_name}-{function_name}",
        package_type="Image",
        image_uri=ecr_image_uri,
        role=execution_role.arn,
        memory_size=memory_size,
        timeout=timeout,
        environment=pulumi_aws.lambda_.FunctionEnvironmentArgs(
            variables=env_vars,
        ),
        vpc_config=pulumi_aws.lambda_.FunctionVpcConfigArgs(
            subnet_ids=subnet_ids,
            security_group_ids=[security_group_id],
        ),
        file_system_config=pulumi_aws.lambda_.FunctionFileSystemConfigArgs(
            arn=efs_access_point_arn,
            local_mount_path=efs_mount_path,
        ),
        tags={"Name": f"{service_name}-{function_name}"},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )

    function_url = pulumi_aws.lambda_.FunctionUrl(
        f"{service_name}_{function_name}_url",
        function_name=fn.name,
        authorization_type="NONE",
        invoke_mode="RESPONSE_STREAM",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )

    return fn, function_url
