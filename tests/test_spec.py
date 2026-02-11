"""Tests for platform spec schema validation."""

from pathlib import Path

import pytest
import yaml

from devops.spec.validator import validate_platform_spec


def test_fixture_validates() -> None:
    """Fixtures must pass schema validation (keeps fixtures in sync with schema)."""
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures"
    fixture_path = fixture_dir / "platform-minimal.yaml"
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
    with open(fixture_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    validate_platform_spec(data)


def test_validate_platform_spec_invalid_missing_api_version() -> None:
    """Missing apiVersion raises ValidationError."""
    data = {"kind": "Service", "metadata": {"name": "x"}, "spec": {"compute": {}}}
    with pytest.raises(Exception) as exc_info:
        validate_platform_spec(data)
    assert "apiVersion" in str(exc_info.value)


def test_validate_platform_spec_invalid_unsupported_version() -> None:
    """Unsupported apiVersion raises."""
    data = {
        "apiVersion": "platform.althq.com/v99",
        "kind": "Service",
        "metadata": {"name": "x"},
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
