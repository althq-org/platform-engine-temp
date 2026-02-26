"""Tests for the lambda capability handler (requires storage, ctx.require/set/export)."""

from unittest.mock import MagicMock, patch

from devops.capabilities.context import CapabilityContext
import devops.capabilities.lambda_functions  # noqa: F401 - register lambda capability
from devops.capabilities.registry import CAPABILITIES


def _make_ctx_with_storage_and_foundation() -> CapabilityContext:
    config = MagicMock()
    config.service_name = "platform-v2-test"
    infra = MagicMock()
    infra.private_subnet_ids = ["subnet-a", "subnet-b"]
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    ctx.set("security_groups.compute.id", MagicMock())
    ctx.set("iam.lambda_execution_role", MagicMock())
    ctx.set("storage.efs.access_point_arn", MagicMock())
    return ctx


@patch("devops.capabilities.lambda_functions.create_lambda_function")
@patch("devops.capabilities.lambda_functions.create_ecr_repository")
def test_lambda_handler_calls_ecr_and_lambda_and_sets_exports(
    mock_ecr: MagicMock,
    mock_lambda_fn: MagicMock,
) -> None:
    """Lambda handler creates ECR repo and Lambda per function, sets ctx and exports URL."""
    mock_repo = MagicMock()
    mock_repo.repository_url = MagicMock()
    mock_ecr.return_value = mock_repo
    mock_fn = MagicMock()
    mock_url = MagicMock()
    mock_url.function_url = "https://xyz.lambda-url.us-west-2.on.aws/"
    mock_lambda_fn.return_value = (mock_fn, mock_url)

    section_config = {
        "functions": [
            {"name": "test-fn", "image": "test-lambda", "memory": 512, "timeout": 30},
        ],
    }
    ctx = _make_ctx_with_storage_and_foundation()
    handler = CAPABILITIES["lambda"].handler
    handler(section_config, ctx)

    mock_ecr.assert_called_once()
    assert mock_ecr.call_args[0][0] == "platform-v2-test-test-lambda"
    mock_lambda_fn.assert_called_once()
    call_kw = mock_lambda_fn.call_args[1]
    assert call_kw["function_name"] == "test-fn"
    assert call_kw["memory_size"] == 512
    assert call_kw["timeout"] == 30
    assert call_kw["efs_mount_path"] == "/mnt/efs"

    assert ctx.get("lambda.test-fn.url") == "https://xyz.lambda-url.us-west-2.on.aws/"
    assert ctx.exports["lambda_test_fn_url"] == "https://xyz.lambda-url.us-west-2.on.aws/"


@patch("devops.capabilities.lambda_functions.create_lambda_function")
@patch("devops.capabilities.lambda_functions.create_ecr_repository")
def test_lambda_handler_uses_default_memory_and_timeout(
    mock_ecr: MagicMock,
    mock_lambda_fn: MagicMock,
) -> None:
    """Lambda handler uses default memory 2048 and timeout 120 when not in function spec."""
    mock_repo = MagicMock()
    mock_repo.repository_url = MagicMock()
    mock_ecr.return_value = mock_repo
    mock_lambda_fn.return_value = (MagicMock(), MagicMock(function_url="https://u/"))

    section_config = {
        "functions": [{"name": "default-fn", "image": "img"}],
    }
    ctx = _make_ctx_with_storage_and_foundation()
    handler = CAPABILITIES["lambda"].handler
    handler(section_config, ctx)

    call_kw = mock_lambda_fn.call_args[1]
    assert call_kw["memory_size"] == 2048
    assert call_kw["timeout"] == 120


def test_lambda_capability_requires_storage() -> None:
    """Lambda capability has requires=['storage']; missing storage in declared_sections would fail precondition."""
    assert "lambda" in CAPABILITIES
    assert CAPABILITIES["lambda"].requires == ["storage"]


def test_lambda_handler_requires_storage_efs_access_point_arn() -> None:
    """Handler calls ctx.require('storage.efs.access_point_arn'); missing storage would raise."""
    section_config = {"functions": [{"name": "x", "image": "y"}]}
    ctx = _make_ctx_with_storage_and_foundation()
    ctx._outputs.pop("storage.efs.access_point_arn", None)

    handler = CAPABILITIES["lambda"].handler
    try:
        handler(section_config, ctx)
    except RuntimeError as e:
        assert "storage.efs.access_point_arn" in str(e) or "missing required key" in str(e)
        return
    raise AssertionError("Expected RuntimeError from ctx.require('storage.efs.access_point_arn')")


@patch("devops.capabilities.lambda_functions.create_lambda_function")
@patch("devops.capabilities.lambda_functions.create_ecr_repository")
def test_lambda_handler_empty_functions_does_nothing(
    mock_ecr: MagicMock,
    mock_lambda_fn: MagicMock,
) -> None:
    """Lambda handler with empty functions list does not call ECR or Lambda."""
    ctx = _make_ctx_with_storage_and_foundation()
    handler = CAPABILITIES["lambda"].handler
    handler({"functions": []}, ctx)
    mock_ecr.assert_not_called()
    mock_lambda_fn.assert_not_called()
