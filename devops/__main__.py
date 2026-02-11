"""
Platform engine: provisions one service from platform.yaml.
Loads and validates config, then runs capabilities (today: ECS only).
Uses shared VPC, external ALB, 443 listener; ECS capability creates ECR, cluster,
target group, listener rule, Cloudflare DNS, Zero Trust Access. HTTPS via existing ACM + Cloudflare.
"""

import pulumi

from devops.capabilities.ecs import provision_ecs
from devops.config import create_aws_provider, load_platform_config
from devops.shared.lookups import lookup_shared_infrastructure

# Load config (validates against schema) and create provider
config = load_platform_config()
aws_provider = create_aws_provider(config.service_name, config.region)

# Lookup shared infrastructure
infra = lookup_shared_infrastructure(aws_provider)

# Run capabilities: today only ECS
ecs_outputs = provision_ecs(config, infra, aws_provider)

# Export outputs
pulumi.export("service_url", ecs_outputs.service_url)
pulumi.export("ecr_repository_uri", ecs_outputs.ecr_repository_uri)
pulumi.export("ecs_cluster_name", ecs_outputs.ecs_cluster_name)
pulumi.export("ecs_service_name", ecs_outputs.ecs_service_name)
