"""Capability registry: phase ordering and handler registration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Protocol

from devops.capabilities.context import CapabilityContext


class Phase(IntEnum):
    """Execution phase order for capabilities (lower runs first)."""

    FOUNDATION = 0
    INFRASTRUCTURE = 1
    COMPUTE = 2
    NETWORKING = 3


class CapabilityHandler(Protocol):
    """Protocol for capability handler functions."""

    def __call__(self, section_config: dict[str, Any], ctx: CapabilityContext) -> None:
        ...


@dataclass
class CapabilityDef:
    """Registered capability: handler, phase, and optional dependencies."""

    handler: Callable[[dict[str, Any], CapabilityContext], None]
    phase: Phase
    requires: list[str]


CAPABILITIES: dict[str, CapabilityDef] = {}


def register(
    name: str,
    phase: Phase,
    requires: list[str] | None = None,
) -> Callable[[CapabilityHandler], CapabilityHandler]:
    """Decorator to register a capability handler in CAPABILITIES."""

    def decorator(fn: CapabilityHandler) -> CapabilityHandler:
        CAPABILITIES[name] = CapabilityDef(
            handler=fn,
            phase=phase,
            requires=requires or [],
        )
        return fn

    return decorator
