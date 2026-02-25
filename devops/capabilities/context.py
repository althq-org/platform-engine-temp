"""Capability execution context: config, infra, outputs, and Pulumi exports."""

from dataclasses import dataclass, field
from typing import Any

import pulumi_aws

from devops.config import PlatformConfig
from devops.shared.lookups import SharedInfrastructure


@dataclass
class CapabilityContext:
    """Context passed to capability handlers: config, shared infra, and key-value outputs/exports."""

    config: PlatformConfig
    infra: SharedInfrastructure
    aws_provider: pulumi_aws.Provider
    _outputs: dict[str, Any] = field(default_factory=dict)
    _exports: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """Store a value for later use by other capabilities."""
        self._outputs[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value; return default if key is missing."""
        return self._outputs.get(key, default)

    def require(self, key: str) -> Any:
        """Retrieve a value; raise RuntimeError with available keys if missing."""
        if key not in self._outputs:
            available = ", ".join(sorted(self._outputs.keys())) or "(none)"
            raise RuntimeError(
                f"missing required key: {key!r}. Available keys: {available}"
            )
        return self._outputs[key]

    def export(self, key: str, value: Any) -> None:
        """Register a Pulumi stack export."""
        self._exports[key] = value

    @property
    def exports(self) -> dict[str, Any]:
        """Return all registered Pulumi exports."""
        return dict(self._exports)
