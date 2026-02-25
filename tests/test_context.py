"""Tests for CapabilityContext (set/get/require/export)."""

from unittest.mock import MagicMock

import pytest

from devops.capabilities.context import CapabilityContext


def _make_ctx() -> CapabilityContext:
    """Build a minimal context with mocked config, infra, and provider."""
    return CapabilityContext(
        config=MagicMock(),
        infra=MagicMock(),
        aws_provider=MagicMock(),
    )


def test_set_and_get() -> None:
    """set stores a value; get retrieves it."""
    ctx = _make_ctx()
    ctx.set("foo", 42)
    assert ctx.get("foo") == 42


def test_get_missing_returns_default() -> None:
    """get with missing key returns default."""
    ctx = _make_ctx()
    assert ctx.get("missing") is None
    assert ctx.get("missing", 99) == 99


def test_require_returns_value_when_present() -> None:
    """require returns value when key exists."""
    ctx = _make_ctx()
    ctx.set("key", "value")
    assert ctx.require("key") == "value"


def test_require_raises_runtime_error_when_missing() -> None:
    """require raises RuntimeError when key is missing; message lists available keys."""
    ctx = _make_ctx()
    ctx.set("a", 1)
    ctx.set("b", 2)

    with pytest.raises(RuntimeError) as exc_info:
        ctx.require("missing")

    msg = str(exc_info.value)
    assert "missing required key" in msg
    assert "missing" in msg or "missing required key" in msg
    assert "a" in msg
    assert "b" in msg


def test_require_message_lists_available_keys_when_empty() -> None:
    """When no keys exist, error message indicates (none) or similar."""
    ctx = _make_ctx()

    with pytest.raises(RuntimeError) as exc_info:
        ctx.require("x")

    msg = str(exc_info.value)
    assert "missing required key" in msg
    assert "x" in msg
    assert "available" in msg.lower() or "keys" in msg.lower()


def test_export_and_exports_property() -> None:
    """export registers a value; exports returns all exports as dict."""
    ctx = _make_ctx()
    ctx.export("out1", "v1")
    ctx.export("out2", 100)

    exports = ctx.exports
    assert exports == {"out1": "v1", "out2": 100}
    assert isinstance(exports, dict)
    # Exports should be a copy so mutating return value doesn't affect context
    exports["out3"] = "extra"
    assert ctx.exports == {"out1": "v1", "out2": 100}
