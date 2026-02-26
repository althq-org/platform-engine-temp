"""
Platform engine: provisions services from platform.yaml.
Loads config, validates capability requirements, runs foundation then capability handlers by phase.
"""

import pulumi

import devops.capabilities.cache

# Register capability handlers (import side-effect)
import devops.capabilities.compute
from devops.capabilities.context import CapabilityContext
import devops.capabilities.database
import devops.capabilities.eventbridge
from devops.capabilities.foundation import provision_foundation
import devops.capabilities.lambda_functions
from devops.capabilities.registry import CAPABILITIES, Phase
import devops.capabilities.service_discovery
import devops.capabilities.storage
import devops.capabilities.webhook_gateway  # noqa: F401
from devops.config import create_aws_provider, load_platform_config
from devops.shared.lookups import lookup_shared_infrastructure

config = load_platform_config()
aws_provider = create_aws_provider(config.service_name, config.region)
infra = lookup_shared_infrastructure(aws_provider)
ctx = CapabilityContext(config=config, infra=infra, aws_provider=aws_provider)

declared_sections = {
    k: v for k, v in config.spec_sections.items() if k in CAPABILITIES and v is not None
}

for name in declared_sections:
    cap_def = CAPABILITIES.get(name)
    if cap_def:
        for req in cap_def.requires:
            if req not in declared_sections:
                raise SystemExit(
                    f"Capability {name!r} requires {req!r} but it is not declared in spec."
                )

provision_foundation(declared_sections, ctx)

for phase in [Phase.INFRASTRUCTURE, Phase.COMPUTE, Phase.NETWORKING]:
    for name, section_config in declared_sections.items():
        cap_def = CAPABILITIES.get(name)
        if cap_def and cap_def.phase == phase:
            cap_def.handler(section_config, ctx)

for key, value in ctx.exports.items():
    pulumi.export(key, value)
