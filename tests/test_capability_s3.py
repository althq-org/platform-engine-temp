"""Tests for the S3 capability handler."""

from unittest.mock import MagicMock, patch

import devops.capabilities.s3  # noqa: F401 - register s3 capability
from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES


def _make_ctx(with_task_role: bool = False, aws_account_id: str = "470935583836") -> CapabilityContext:
    config = MagicMock()
    config.service_name = "my-svc"
    infra = MagicMock()
    infra.aws_account_id = aws_account_id
    ctx = CapabilityContext(
        config=config,
        infra=infra,
        aws_provider=MagicMock(),
    )
    if with_task_role:
        ctx.set("iam.task_role", MagicMock(name="my-svc-ecs-task"))
    return ctx


@patch("devops.storage.s3.create_s3_bucket")
def test_s3_handler_creates_bucket_with_account_prefix(mock_create: MagicMock) -> None:
    mock_bucket = MagicMock()
    mock_bucket.arn = "arn:aws:s3:::470935583836-my-svc-state"
    mock_bucket.bucket = "470935583836-my-svc-state"
    mock_create.return_value = mock_bucket

    ctx = _make_ctx()
    handler = CAPABILITIES["s3"].handler
    handler({"buckets": [{"name": "my-svc-state"}]}, ctx)

    mock_create.assert_called_once()
    kw = mock_create.call_args[1]
    assert kw["bucket_name"] == "470935583836-my-svc-state"


@patch("devops.storage.s3.create_s3_bucket")
def test_s3_handler_exports_bucket_name(mock_create: MagicMock) -> None:
    mock_bucket = MagicMock()
    mock_bucket.arn = "arn:aws:s3:::470935583836-my-svc-state"
    mock_bucket.bucket = "470935583836-my-svc-state"
    mock_create.return_value = mock_bucket

    ctx = _make_ctx()
    handler = CAPABILITIES["s3"].handler
    handler({"buckets": [{"name": "my-svc-state"}]}, ctx)

    assert "s3_bucket_my_svc_state" in ctx.exports


@patch("devops.storage.s3.create_s3_bucket")
def test_s3_handler_sets_env_vars(mock_create: MagicMock) -> None:
    mock_bucket = MagicMock()
    mock_bucket.arn = "arn:aws:s3:::470935583836-my-svc-state"
    mock_bucket.bucket = "470935583836-my-svc-state"
    mock_create.return_value = mock_bucket

    ctx = _make_ctx()
    handler = CAPABILITIES["s3"].handler
    handler({"buckets": [{"name": "my-svc-state"}]}, ctx)

    env_vars = ctx.get("s3.bucket_env_vars")
    assert "S3_BUCKET_MY_SVC_STATE" in env_vars


@patch("devops.storage.s3.create_s3_bucket")
def test_s3_handler_multiple_buckets(mock_create: MagicMock) -> None:
    mock_create.side_effect = [
        MagicMock(arn="arn:1", bucket="470935583836-svc-a"),
        MagicMock(arn="arn:2", bucket="470935583836-svc-b"),
    ]

    ctx = _make_ctx()
    handler = CAPABILITIES["s3"].handler
    handler({"buckets": [{"name": "svc-a"}, {"name": "svc-b"}]}, ctx)

    assert mock_create.call_count == 2
    arns = ctx.get("s3.bucket_arns")
    assert len(arns) == 2


@patch("devops.capabilities.s3.pulumi_aws.iam.RolePolicy")
@patch("devops.capabilities.s3.pulumi.Output.all")
@patch("devops.storage.s3.create_s3_bucket")
def test_s3_handler_grants_task_role_when_present(
    mock_create: MagicMock,
    mock_output_all: MagicMock,
    mock_role_policy: MagicMock,
) -> None:
    mock_bucket = MagicMock()
    mock_bucket.arn = "arn:aws:s3:::470935583836-my-svc-state"
    mock_bucket.bucket = "470935583836-my-svc-state"
    mock_create.return_value = mock_bucket
    mock_output_all.return_value = MagicMock(apply=MagicMock(return_value=MagicMock()))

    ctx = _make_ctx(with_task_role=True)
    handler = CAPABILITIES["s3"].handler
    handler({"buckets": [{"name": "my-svc-state"}]}, ctx)

    mock_role_policy.assert_called_once()
    assert "s3_task_policy" in mock_role_policy.call_args[0][0]


@patch("devops.capabilities.s3.pulumi_aws.iam.RolePolicy")
@patch("devops.storage.s3.create_s3_bucket")
def test_s3_handler_skips_iam_without_task_role(
    mock_create: MagicMock,
    mock_role_policy: MagicMock,
) -> None:
    mock_create.return_value = MagicMock(arn="arn:x", bucket="x")
    ctx = _make_ctx(with_task_role=False)
    handler = CAPABILITIES["s3"].handler
    handler({"buckets": [{"name": "my-svc-state"}]}, ctx)

    mock_role_policy.assert_not_called()


@patch("devops.storage.s3.create_s3_bucket")
def test_s3_handler_empty_buckets_returns_early(mock_create: MagicMock) -> None:
    ctx = _make_ctx()
    handler = CAPABILITIES["s3"].handler
    handler({"buckets": []}, ctx)
    mock_create.assert_not_called()
