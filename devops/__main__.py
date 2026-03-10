"""
Platform engine: provisions services from platform.yaml.
Loads config, validates capability requirements, runs foundation then capability handlers by phase.
"""

import pulumi

import devops.capabilities.agentcore_runtime
import devops.capabilities.cache

# Register capability handlers (import side-effect)
import devops.capabilities.compute
from devops.capabilities.context import CapabilityContext
import devops.capabilities.database
import devops.capabilities.dynamodb
import devops.capabilities.eventbridge
from devops.capabilities.foundation import provision_foundation
import devops.capabilities.lambda_functions
from devops.capabilities.registry import CAPABILITIES, Phase
import devops.capabilities.s3
import devops.capabilities.service_discovery
import devops.capabilities.storage
from devops.config import create_aws_provider, load_platform_config
from devops.shared.lookups import lookup_shared_infrastructure


def _topo_sort(names: list[str], after_map: dict[str, list[str]]) -> list[str]:
    """Stable Kahn's-algorithm topological sort.

    ``after_map[A]`` contains names that must run *before* A.
    Names absent from ``after_map`` have no ordering constraint.
    If a cycle is detected, raises SystemExit with a clear message.
    """
    name_set = set(names)
    # Build in-degree and adjacency list (predecessor -> successors)
    in_degree: dict[str, int] = {n: 0 for n in names}
    successors: dict[str, list[str]] = {n: [] for n in names}
    for node, preds in after_map.items():
        if node not in name_set:
            continue
        for pred in preds:
            if pred not in name_set:
                # Soft dependency: ignore missing capabilities
                continue
            successors[pred].append(node)
            in_degree[node] += 1

    # Initialise queue with zero-in-degree nodes in original declaration order
    queue: list[str] = [n for n in names if in_degree[n] == 0]
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        # Preserve original declaration order among newly-ready nodes
        for succ in sorted(successors[node], key=lambda s: names.index(s)):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    if len(result) != len(names):
        remaining = [n for n in names if n not in result]
        raise SystemExit(f"Circular capability ordering: {remaining}")

    return result


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
    phase_names = [
        name
        for name, section_config in declared_sections.items()
        if (cap_def := CAPABILITIES.get(name)) and cap_def.phase == phase
    ]

    # Build after_map: merge registry-declared after + user-declared after from platform.yaml
    after_map: dict[str, list[str]] = {}
    for name in phase_names:
        cap_def = CAPABILITIES[name]
        section_config = declared_sections[name]
        merged_after = list(cap_def.after) + list(
            section_config.get("after", []) if isinstance(section_config, dict) else []
        )
        if merged_after:
            after_map[name] = merged_after

    sorted_names = _topo_sort(phase_names, after_map)

    for name in sorted_names:
        section_config = declared_sections[name]
        CAPABILITIES[name].handler(section_config, ctx)

for key, value in ctx.exports.items():
    pulumi.export(key, value)
