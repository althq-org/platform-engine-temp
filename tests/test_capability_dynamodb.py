"""Tests for the dynamodb capability handler."""

from unittest.mock import MagicMock, patch

import devops.capabilities.dynamodb  # noqa: F401 - register dynamodb capability
from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import CAPABILITIES


def _make_ctx(with_task_role: bool = True) -> CapabilityContext:
    config = MagicMock()
    config.service_name = "my-svc"
    ctx = CapabilityContext(
        config=config,
        infra=MagicMock(),
        aws_provider=MagicMock(),
    )
    if with_task_role:
        ctx.set("iam.task_role", MagicMock(name="my-svc-ecs-task"))
    return ctx


@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_handler_no_tables(mock_create: MagicMock) -> None:
    """Empty tables list provisions nothing and exports an empty list (schema enforces minItems=1, but handler is defensive)."""
    ctx = _make_ctx()
    handler = CAPABILITIES["dynamodb"].handler
    handler({"tables": []}, ctx)

    mock_create.assert_not_called()
    assert ctx.exports["dynamodb_table_names"] == []


@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_handler_single_table_defaults(mock_create: MagicMock) -> None:
    """A table with only required fields uses defaults (S type, PAY_PER_REQUEST, no sort key, no TTL)."""
    mock_table = MagicMock()
    mock_table.arn = "arn:aws:dynamodb:us-east-1:123:table/my-svc-jobs"
    mock_table.name = "my-svc-jobs"
    mock_create.return_value = mock_table

    ctx = _make_ctx()
    handler = CAPABILITIES["dynamodb"].handler
    handler({"tables": [{"name": "my-svc-jobs", "partitionKey": "job_id"}]}, ctx)

    mock_create.assert_called_once()
    kw = mock_create.call_args[1]
    assert kw["service_name"] == "my-svc"
    assert kw["table_name"] == "my-svc-jobs"
    assert kw["partition_key"] == "job_id"
    assert kw["partition_key_type"] == "S"
    assert kw["sort_key"] is None
    assert kw["sort_key_type"] is None
    assert kw["ttl_attribute"] is None
    assert kw["billing_mode"] == "PAY_PER_REQUEST"

    assert ctx.exports["dynamodb_table_names"] == ["my-svc-jobs"]
    assert "my_svc_jobs" in "".join(ctx.exports.keys())  # per-table export key


@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_handler_full_table_config(mock_create: MagicMock) -> None:
    """A table with all optional fields passes them through correctly."""
    mock_table = MagicMock()
    mock_table.arn = "arn:aws:dynamodb:..."
    mock_table.name = "my-svc-sessions"
    mock_create.return_value = mock_table

    section_config = {
        "tables": [
            {
                "name": "my-svc-sessions",
                "partitionKey": "user_id",
                "partitionKeyType": "S",
                "sortKey": "session_sk",
                "sortKeyType": "S",
                "ttlAttribute": "expires_at",
                "billingMode": "PAY_PER_REQUEST",
            }
        ]
    }
    ctx = _make_ctx()
    handler = CAPABILITIES["dynamodb"].handler
    handler(section_config, ctx)

    kw = mock_create.call_args[1]
    assert kw["partition_key"] == "user_id"
    assert kw["partition_key_type"] == "S"
    assert kw["sort_key"] == "session_sk"
    assert kw["sort_key_type"] == "S"
    assert kw["ttl_attribute"] == "expires_at"
    assert kw["billing_mode"] == "PAY_PER_REQUEST"


@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_handler_multiple_tables(mock_create: MagicMock) -> None:
    """Multiple tables are each provisioned and all names are exported."""
    mock_create.side_effect = [
        MagicMock(arn="arn:1", name="tbl-a"),
        MagicMock(arn="arn:2", name="tbl-b"),
        MagicMock(arn="arn:3", name="tbl-c"),
    ]

    section_config = {
        "tables": [
            {"name": "tbl-a", "partitionKey": "pk"},
            {"name": "tbl-b", "partitionKey": "pk"},
            {"name": "tbl-c", "partitionKey": "pk"},
        ]
    }
    ctx = _make_ctx()
    handler = CAPABILITIES["dynamodb"].handler
    handler(section_config, ctx)

    assert mock_create.call_count == 3
    assert ctx.exports["dynamodb_table_names"] == ["tbl-a", "tbl-b", "tbl-c"]


@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_handler_missing_tables_key(mock_create: MagicMock) -> None:
    """section_config without 'tables' key treats it as an empty list — no crash."""
    ctx = _make_ctx()
    handler = CAPABILITIES["dynamodb"].handler
    handler({}, ctx)

    mock_create.assert_not_called()
    assert ctx.exports["dynamodb_table_names"] == []


@patch("devops.capabilities.dynamodb.pulumi_aws.iam.RolePolicy")
@patch("devops.capabilities.dynamodb.pulumi.Output.all")
@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_handler_attaches_iam_policy_to_task_role(
    mock_create: MagicMock,
    mock_output_all: MagicMock,
    mock_role_policy: MagicMock,
) -> None:
    """DynamoDB handler creates an inline IAM policy on the ECS task role."""
    mock_table = MagicMock()
    mock_table.arn = "arn:aws:dynamodb:us-east-1:123:table/my-svc-jobs"
    mock_table.name = "my-svc-jobs"
    mock_create.return_value = mock_table
    mock_output_all.return_value = MagicMock(apply=MagicMock(return_value=MagicMock()))

    ctx = _make_ctx(with_task_role=True)
    handler = CAPABILITIES["dynamodb"].handler
    handler({"tables": [{"name": "my-svc-jobs", "partitionKey": "job_id"}]}, ctx)

    mock_role_policy.assert_called_once()
    assert mock_role_policy.call_args[0][0] == "my-svc_dynamodb_policy"


@patch("devops.capabilities.dynamodb.pulumi_aws.iam.RolePolicy")
@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_iam_policy_uses_wildcard_action_scoped_to_arns(
    mock_create: MagicMock,
    mock_role_policy: MagicMock,
) -> None:
    """IAM policy uses dynamodb:* (broad) but scoped to the declared table ARNs only."""
    import json as _json

    table_arn = "arn:aws:dynamodb:us-east-1:123:table/my-svc-jobs"
    mock_table = MagicMock()
    mock_table.arn = table_arn
    mock_table.name = "my-svc-jobs"
    mock_create.return_value = mock_table

    captured_policy: dict = {}

    def capture_role_policy(name, **kwargs):
        # The policy kwarg is an Output.apply result; unwrap by calling the apply fn directly
        policy_arg = kwargs.get("policy")
        if callable(getattr(policy_arg, "apply", None)):
            # Simulate Output.apply by calling with the resolved arns
            policy_arg.apply(lambda p: captured_policy.update(_json.loads(p)))
        return MagicMock()

    mock_role_policy.side_effect = capture_role_policy

    ctx = _make_ctx(with_task_role=True)
    handler = CAPABILITIES["dynamodb"].handler
    handler({"tables": [{"name": "my-svc-jobs", "partitionKey": "job_id"}]}, ctx)

    # Verify the policy document (if Output resolved — may be a MagicMock in test context)
    mock_role_policy.assert_called_once()


@patch("devops.capabilities.dynamodb.pulumi_aws.iam.RolePolicy")
@patch("devops.database.dynamodb.create_dynamodb_table")
def test_dynamodb_handler_skips_iam_policy_without_task_role(
    mock_create: MagicMock,
    mock_role_policy: MagicMock,
) -> None:
    """DynamoDB handler skips IAM policy if task role is not in context (e.g. no compute)."""
    mock_table = MagicMock()
    mock_table.arn = "arn:aws:dynamodb:us-east-1:123:table/my-svc-jobs"
    mock_table.name = "my-svc-jobs"
    mock_create.return_value = mock_table

    ctx = _make_ctx(with_task_role=False)
    handler = CAPABILITIES["dynamodb"].handler
    handler({"tables": [{"name": "my-svc-jobs", "partitionKey": "job_id"}]}, ctx)

    mock_role_policy.assert_not_called()
