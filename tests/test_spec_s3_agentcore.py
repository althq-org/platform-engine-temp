"""Tests for S3 and AgentCore Runtime schema validation."""

import pytest

from devops.spec.validator import validate_platform_spec


def _base(spec: dict) -> dict:
    return {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "test-svc"},
        "spec": spec,
    }


def test_s3_valid_minimal() -> None:
    validate_platform_spec(_base({"s3": {"buckets": [{"name": "my-svc-state"}]}}))


def test_s3_valid_full() -> None:
    validate_platform_spec(_base({
        "s3": {
            "buckets": [
                {
                    "name": "my-svc-state",
                    "versioning": True,
                    "encryption": "aws:kms",
                    "lifecycleRules": [
                        {"prefix": "logs/", "transitionToIA": 30, "expirationDays": 90},
                        {"prefix": "temp/", "expirationDays": 7},
                    ],
                },
                {"name": "my-svc-uploads"},
            ]
        }
    }))


def test_s3_requires_buckets() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"s3": {}}))


def test_s3_requires_at_least_one_bucket() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"s3": {"buckets": []}}))


def test_s3_bucket_name_too_short() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"s3": {"buckets": [{"name": "ab"}]}}))


def test_s3_bucket_name_invalid_uppercase() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"s3": {"buckets": [{"name": "MyBucket"}]}}))


def test_s3_bucket_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"s3": {"buckets": [{"name": "ok-name", "badField": 1}]}}))


def test_s3_invalid_encryption_value() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"s3": {"buckets": [{"name": "ok-name", "encryption": "none"}]}}))


def test_agentcore_valid_minimal() -> None:
    validate_platform_spec(_base({
        "agentcoreRuntime": {
            "runtimes": [{"name": "my_agent", "image": "my-agent"}]
        }
    }))


def test_agentcore_valid_full() -> None:
    validate_platform_spec(_base({
        "agentcoreRuntime": {
            "runtimes": [
                {
                    "name": "claude_agent",
                    "image": "claude-agent",
                    "description": "Claude SDK runtime",
                    "networkMode": "PUBLIC",
                    "environmentVariables": {"WORK_DIR": "/tmp/agent"},
                },
                {
                    "name": "pi_agent",
                    "image": "pi-agent",
                    "networkMode": "VPC",
                },
            ],
            "authorizer": {
                "type": "jwt",
                "discoveryUrl": "https://accounts.google.com/.well-known/openid-configuration",
                "allowedAudiences": ["my-app"],
                "allowedClients": ["client-1"],
            },
        }
    }))


def test_agentcore_requires_runtimes() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"agentcoreRuntime": {}}))


def test_agentcore_requires_at_least_one_runtime() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({"agentcoreRuntime": {"runtimes": []}}))


def test_agentcore_runtime_name_must_start_with_letter() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({
            "agentcoreRuntime": {"runtimes": [{"name": "1bad", "image": "img"}]}
        }))


def test_agentcore_runtime_name_no_hyphens() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({
            "agentcoreRuntime": {"runtimes": [{"name": "my-agent", "image": "img"}]}
        }))


def test_agentcore_runtime_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({
            "agentcoreRuntime": {"runtimes": [{"name": "ok", "image": "img", "badField": 1}]}
        }))


def test_agentcore_invalid_network_mode() -> None:
    with pytest.raises(Exception):
        validate_platform_spec(_base({
            "agentcoreRuntime": {"runtimes": [{"name": "ok", "image": "img", "networkMode": "PRIVATE"}]}
        }))


def test_s3_and_agentcore_together() -> None:
    validate_platform_spec(_base({
        "s3": {"buckets": [{"name": "my-svc-state"}]},
        "agentcoreRuntime": {"runtimes": [{"name": "my_agent", "image": "my-agent"}]},
    }))


def test_full_stack_validates() -> None:
    validate_platform_spec(_base({
        "compute": {"port": 3000, "cpu": 512, "memory": 1024},
        "dynamodb": {"tables": [{"name": "tbl", "partitionKey": "pk"}]},
        "s3": {"buckets": [{"name": "my-svc-state", "versioning": True}]},
        "agentcoreRuntime": {
            "runtimes": [{"name": "agent_a", "image": "agent-a"}],
            "authorizer": {
                "type": "jwt",
                "discoveryUrl": "https://example.com/.well-known/openid-configuration",
                "allowedAudiences": ["aud"],
            },
        },
        "serviceDiscovery": {"namespace": "test.local"},
        "eventbridge": {"scheduleGroup": "my-group"},
        "secrets": ["API_KEY"],
    }))
