"""Tests for capability registry (Phase, register, CAPABILITIES)."""

from devops.capabilities.context import CapabilityContext
from devops.capabilities.registry import (
    CAPABILITIES,
    CapabilityDef,
    Phase,
    register,
)


def test_register_adds_to_capabilities() -> None:
    """A function decorated with @register appears in CAPABILITIES."""
    # Use a unique name to avoid clashing with other tests
    name = "test_foo_cap"

    @register(name, phase=Phase.INFRASTRUCTURE)
    def foo_handler(section_config: dict, ctx: CapabilityContext) -> None:
        pass

    assert name in CAPABILITIES
    cap = CAPABILITIES[name]
    assert isinstance(cap, CapabilityDef)
    assert cap.handler is foo_handler
    assert cap.phase == Phase.INFRASTRUCTURE
    assert cap.requires == []

    # Clean up so other tests don't see this
    del CAPABILITIES[name]


def test_register_with_requires() -> None:
    """@register(requires=[...]) sets CapabilityDef.requires."""
    name = "test_bar_cap"

    @register(name, phase=Phase.COMPUTE, requires=["vpc", "cluster"])
    def bar_handler(section_config: dict, ctx: CapabilityContext) -> None:
        pass

    assert CAPABILITIES[name].requires == ["vpc", "cluster"]
    del CAPABILITIES[name]


def test_phase_ordering() -> None:
    """Phase enum values enforce ordering (e.g. FOUNDATION < INFRASTRUCTURE < COMPUTE)."""
    assert Phase.FOUNDATION < Phase.INFRASTRUCTURE
    assert Phase.INFRASTRUCTURE < Phase.COMPUTE
    assert Phase.COMPUTE < Phase.NETWORKING
    assert int(Phase.FOUNDATION) == 0
    assert int(Phase.INFRASTRUCTURE) == 1
    assert int(Phase.COMPUTE) == 2
    assert int(Phase.NETWORKING) == 3
