"""Capability modules: each provisions one slice of a service (ECS, S3, DB, etc.)."""

from devops.capabilities.ecs import provision_ecs

__all__ = ["provision_ecs"]
