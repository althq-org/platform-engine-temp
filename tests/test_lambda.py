"""Unit tests for create_lambda_function (compute module)."""

from unittest.mock import MagicMock, patch

from devops.compute.lambda_function import create_lambda_function


@patch("devops.compute.lambda_function.pulumi_aws.lambda_.FunctionUrl")
@patch("devops.compute.lambda_function.pulumi_aws.lambda_.Function")
def test_create_lambda_function_creates_function_and_url_with_defaults(
    mock_fn: MagicMock,
    mock_url: MagicMock,
) -> None:
    """create_lambda_function creates Function and FunctionUrl with default memory and timeout."""
    mock_fn.return_value = MagicMock(name="svc-myfn")
    mock_url.return_value = MagicMock(function_url="https://abc123.lambda-url.us-west-2.on.aws/")

    ecr_image_uri = MagicMock()
    execution_role = MagicMock(arn=MagicMock())
    security_group_id = MagicMock()
    efs_access_point_arn = MagicMock()
    aws_provider = MagicMock()

    fn, function_url = create_lambda_function(
        service_name="svc",
        function_name="myfn",
        ecr_image_uri=ecr_image_uri,
        execution_role=execution_role,
        subnet_ids=["subnet-a", "subnet-b"],
        security_group_id=security_group_id,
        efs_access_point_arn=efs_access_point_arn,
        efs_mount_path="/mnt/efs",
        aws_provider=aws_provider,
    )

    mock_fn.assert_called_once()
    call_kw = mock_fn.call_args[1]
    assert call_kw["name"] == "svc-myfn"
    assert call_kw["memory_size"] == 2048
    assert call_kw["timeout"] == 120
    assert call_kw["package_type"] == "Image"
    assert call_kw["image_uri"] is ecr_image_uri
    mock_url.assert_called_once()
    assert fn == mock_fn.return_value
    assert function_url == mock_url.return_value


@patch("devops.compute.lambda_function.pulumi_aws.lambda_.FunctionUrl")
@patch("devops.compute.lambda_function.pulumi_aws.lambda_.Function")
def test_create_lambda_function_uses_custom_memory_and_timeout(
    mock_fn: MagicMock,
    mock_url: MagicMock,
) -> None:
    """create_lambda_function passes through memory_size and timeout."""
    mock_fn.return_value = MagicMock(name="svc-other")
    mock_url.return_value = MagicMock()

    create_lambda_function(
        service_name="svc",
        function_name="other",
        ecr_image_uri=MagicMock(),
        execution_role=MagicMock(arn=MagicMock()),
        subnet_ids=["subnet-1"],
        security_group_id=MagicMock(),
        efs_access_point_arn=MagicMock(),
        efs_mount_path="/mnt/efs",
        aws_provider=MagicMock(),
        memory_size=512,
        timeout=30,
    )

    call_kw = mock_fn.call_args[1]
    assert call_kw["memory_size"] == 512
    assert call_kw["timeout"] == 30
