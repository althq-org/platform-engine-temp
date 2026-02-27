"""Tests for platform spec schema validation."""

from pathlib import Path

import pytest
import yaml

from devops.spec.validator import validate_platform_spec


def test_all_fixtures_validate() -> None:
    """All fixtures must pass schema validation (keeps fixtures in sync with schema)."""
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures"
    for path in sorted(fixture_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        validate_platform_spec(data)


def test_validate_platform_spec_invalid_missing_api_version() -> None:
    """Missing apiVersion raises ValidationError."""
    data = {"kind": "Service", "metadata": {"name": "ab"}, "spec": {"compute": {}}}
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "apiVersion" in str(exc_info.value)


def test_validate_platform_spec_invalid_unsupported_version() -> None:
    """Unsupported apiVersion raises."""
    data = {
        "apiVersion": "platform.althq.com/v99",
        "kind": "Service",
        "metadata": {"name": "ab"},
        "spec": {"compute": {}},
    }
    with pytest.raises(ValueError, match="Unsupported apiVersion"):
        validate_platform_spec(data)


def test_validate_platform_spec_invalid_missing_metadata_name() -> None:
    """Missing metadata.name raises ValidationError."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {},
        "spec": {"compute": {"port": 80}},
    }
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "name" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


def test_validate_platform_spec_invalid_compute_extra_field() -> None:
    """Compute section with invalid extra field raises ValidationError."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "my-svc"},
        "spec": {"compute": {"port": 80, "invalidKey": True}},
    }
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "invalid" in str(exc_info.value).lower() or "additional" in str(exc_info.value).lower()


def test_validate_platform_spec_invalid_storage_extra_field() -> None:
    """Storage section with invalid extra field raises ValidationError."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "my-svc"},
        "spec": {
            "storage": {
                "efs": {"encrypted": True, "typoKey": "x"},
            },
        },
    }
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "typo" in str(exc_info.value).lower() or "additional" in str(exc_info.value).lower()


def test_validate_platform_spec_invalid_cache_extra_field() -> None:
    """Cache section with invalid extra field raises ValidationError."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "my-svc"},
        "spec": {"cache": {"engine": "redis", "badField": 1}},
    }
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "bad" in str(exc_info.value).lower() or "additional" in str(exc_info.value).lower()


def test_validate_platform_spec_invalid_database_extra_field() -> None:
    """Database section with invalid extra field raises ValidationError."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "my-svc"},
        "spec": {"database": {"engine": "postgres", "typo": "x"}},
    }
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "typo" in str(exc_info.value).lower() or "additional" in str(exc_info.value).lower()


def test_validate_platform_spec_dynamodb_requires_tables() -> None:
    """DynamoDB section without tables raises ValidationError."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "my-svc"},
        "spec": {"dynamodb": {}},
    }
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "tables" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


def test_validate_platform_spec_dynamodb_requires_at_least_one_table() -> None:
    """DynamoDB tables array must have at least one entry."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "my-svc"},
        "spec": {"dynamodb": {"tables": []}},
    }
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "minitems" in str(exc_info.value).lower() or "too short" in str(exc_info.value).lower() or "1" in str(exc_info.value)


def test_validate_platform_spec_dynamodb_valid_table() -> None:
    """DynamoDB with a valid table declaration passes validation."""
    data = {
        "apiVersion": "platform.althq.com/v1",
        "kind": "Service",
        "metadata": {"name": "my-svc"},
        "spec": {
            "dynamodb": {
                "tables": [{"name": "my-svc-jobs", "partitionKey": "job_id"}]
            }
        },
    }
    validate_platform_spec(data)  # should not raise
