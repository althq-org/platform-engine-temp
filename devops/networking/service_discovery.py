"""AWS Cloud Map service discovery (private DNS namespace)."""

import pulumi
import pulumi_aws


def create_service_discovery(
    service_name: str,
    vpc_id: str,
    namespace_name: str,
    aws_provider: pulumi_aws.Provider,
) -> tuple[pulumi_aws.servicediscovery.PrivateDnsNamespace, pulumi_aws.servicediscovery.Service]:
    namespace = pulumi_aws.servicediscovery.PrivateDnsNamespace(
        f"{service_name}_dns_namespace",
        name=namespace_name,
        vpc=vpc_id,
        description=f"Private DNS namespace for {service_name}",
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    service = pulumi_aws.servicediscovery.Service(
        f"{service_name}_discovery_svc",
        name=service_name,
        dns_config={
            "namespace_id": namespace.id,
            "dns_records": [{"ttl": 10, "type": "A"}],
            "routing_policy": "MULTIVALUE",
        },
        health_check_custom_config={},
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return namespace, service
