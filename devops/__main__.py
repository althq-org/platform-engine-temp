"""
Platform engine: provisions one service from platform.yaml.
Uses shared VPC, external ALB, 443 listener; creates ECR, ECS cluster, target group,
listener rule, Cloudflare DNS. HTTPS via existing ACM wildcard + Cloudflare.
"""
import json
import os
from pathlib import Path

import pulumi
import pulumi_aws
import pulumi_cloudflare
import yaml

# Load platform.yaml
platform_yaml_path = os.environ.get("PLATFORM_YAML_PATH")
if not platform_yaml_path or not Path(platform_yaml_path).exists():
    raise SystemExit("PLATFORM_YAML_PATH must point to platform.yaml")

with open(platform_yaml_path) as f:
    platform = yaml.safe_load(f)

metadata = platform["metadata"]
spec = platform["spec"]
compute = spec["compute"]
access = spec.get("access", {})

service_name = metadata["name"]
container_port = compute.get("port", 80)
health_path = compute.get("healthCheck", {}).get("path", "/health")
cpu = str(compute.get("cpu", 256))
memory = str(compute.get("memory", 512))
min_capacity = compute.get("instances", {}).get("min", 1)
max_capacity = compute.get("instances", {}).get("max", 10)

# Hostname: service_name.<zone> (zone from Cloudflare below)

aws_config = pulumi.Config("aws")
region = aws_config.require("region")

# --- Look up shared infrastructure ---
# Private subnets (tag network=private)
private_subnets = pulumi_aws.ec2.get_subnets(
    filters=[
        pulumi_aws.ec2.GetSubnetsFilterArgs(name="tag:network", values=["private"])
    ]
)
if not private_subnets.ids:
    raise SystemExit("No private subnets found (tag network=private)")

# VPC from first subnet
first_subnet = pulumi_aws.ec2.get_subnet(id=private_subnets.ids[0])
vpc = pulumi_aws.ec2.get_vpc(id=first_subnet.vpc_id)

# External ALB (product-external-alb)
external_alb = pulumi_aws.lb.get_load_balancer(name="product-external-alb")

# 443 listener on external ALB
listener_443 = pulumi_aws.lb.get_listener(
    load_balancer_arn=external_alb.arn,
    port=443,
)

# Cloudflare: SSM has token and zone_id (same as platform product)
cf_token_param = pulumi_aws.ssm.get_parameter(name="/cloudflare/platform_infra_token")
cf_zone_id_param = pulumi_aws.ssm.get_parameter(name="/cloudflare/zone_id")
cf_provider = pulumi_cloudflare.Provider(
    "cf",
    api_token=cf_token_param.value,
    opts=pulumi.ResourceOptions(additional_secret_outputs=["api_token"]),
)
zone = pulumi_cloudflare.get_zone(
    zone_id=cf_zone_id_param.value,
    opts=pulumi.InvokeOptions(provider=cf_provider),
)
# get_zone returns plain values; zone.name is str
zone_name = zone.name
hostname = pulumi.Output.from_input(f"{service_name}.{zone_name}")

# --- Per-service resources ---
# ECR repository
ecr_repo = pulumi_aws.ecr.Repository(
    f"{service_name}_ecr",
    name=service_name,
    image_tag_mutability="MUTABLE",
    image_scanning_configuration=pulumi_aws.ecr.RepositoryImageScanningConfigurationArgs(
        scan_on_push=False,
    ),
)
ecr_lifecycle = pulumi_aws.ecr.LifecyclePolicy(
    f"{service_name}_ecr_lifecycle",
    repository=ecr_repo.name,
    policy=json.dumps({
        "rules": [{
            "rulePriority": 1,
            "description": "Keep last 5 images",
            "selection": {"tagStatus": "any", "countType": "imageCountMoreThan", "countNumber": 5},
            "action": {"type": "expire"},
        }],
    }),
)

# ECS cluster
cluster = pulumi_aws.ecs.Cluster(
    f"{service_name}_cluster",
    name=service_name,
    settings=[pulumi_aws.ecs.ClusterSettingArgs(name="containerInsights", value="disabled")],
)

# Security group for ECS tasks (allow 80 from VPC)
ecs_sg = pulumi_aws.ec2.SecurityGroup(
    f"{service_name}_ecs_sg",
    name=f"{service_name}-ecs",
    vpc_id=vpc.id,
    description=f"ECS tasks for {service_name}",
    ingress=[
        pulumi_aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=[vpc.cidr_block],
            description="HTTP from VPC",
        ),
    ],
    egress=[
        pulumi_aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
)

# IAM task role (ECR pull + CloudWatch logs)
task_role = pulumi_aws.iam.Role(
    f"{service_name}_task_role",
    name=f"{service_name}-ecs-task",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        }],
    }),
)
pulumi_aws.iam.RolePolicyAttachment(
    f"{service_name}_task_ecr",
    role=task_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
)
pulumi_aws.iam.RolePolicyAttachment(
    f"{service_name}_task_logs",
    role=task_role.name,
    policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
)
execution_role = pulumi_aws.iam.Role(
    f"{service_name}_exec_role",
    name=f"{service_name}-ecs-exec",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        }],
    }),
)
pulumi_aws.iam.RolePolicyAttachment(
    f"{service_name}_exec_ecr",
    role=execution_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
)
pulumi_aws.iam.RolePolicyAttachment(
    f"{service_name}_exec_logs",
    role=execution_role.name,
    policy_arn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
)

# Target group (HTTP 80, health check)
target_group = pulumi_aws.lb.TargetGroup(
    f"{service_name}_tg",
    name=f"{service_name}-tg"[:32],
    port=80,
    protocol="HTTP",
    vpc_id=vpc.id,
    target_type="ip",
    health_check=pulumi_aws.lb.TargetGroupHealthCheckArgs(
        path=health_path,
        protocol="HTTP",
        interval=30,
        timeout=5,
        healthy_threshold=2,
        unhealthy_threshold=3,
    ),
    deregistration_delay=60,
)

# Listener rule: hostname -> target group (priority from hash of name)
import hashlib
priority = 200 + (int(hashlib.md5(service_name.encode()).hexdigest()[:4], 16) % 90000)
hostname_str = pulumi.Output.from_input(f"{service_name}.{zone_name}")


def make_listener_conditions(h: str):
    return [pulumi_aws.lb.ListenerRuleConditionArgs(
        host_header=pulumi_aws.lb.ListenerRuleConditionHostHeaderArgs(values=[h]),
    )]


listener_rule = pulumi_aws.lb.ListenerRule(
    f"{service_name}_rule",
    listener_arn=listener_443.arn,
    priority=priority,
    actions=[pulumi_aws.lb.ListenerRuleActionArgs(type="forward", target_group_arn=target_group.arn)],
    conditions=hostname_str.apply(make_listener_conditions),
)

# Image URI: repo:latest (workflow pushes after Pulumi up)
image_uri = pulumi.Output.concat(ecr_repo.repository_url, ":latest")

def make_container_def(uri: str) -> str:
    return json.dumps([{
        "name": service_name.replace(".", "-").replace("/", "-")[:255],
        "image": uri,
        "essential": True,
        "portMappings": [{"containerPort": container_port, "protocol": "tcp", "name": "http"}],
        "environment": [
            {"name": "PYTHONUNBUFFERED", "value": "1"},
            {"name": "UVICORN_HOST", "value": "0.0.0.0"},
            {"name": "UVICORN_PORT", "value": str(container_port)},
        ],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-create-group": "true",
                "awslogs-region": region,
                "awslogs-group": service_name,
                "awslogs-stream-prefix": service_name,
            },
        },
    }])

container_def = image_uri.apply(make_container_def)

task_def = pulumi_aws.ecs.TaskDefinition(
    f"{service_name}_task",
    family=service_name,
    cpu=cpu,
    memory=memory,
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    execution_role_arn=execution_role.arn,
    task_role_arn=task_role.arn,
    container_definitions=container_def,
)

ecs_service = pulumi_aws.ecs.Service(
    f"{service_name}_svc",
    name=service_name.replace(".", "_").replace("/", "_")[:32],
    cluster=cluster.arn,
    task_definition=task_def.arn,
    desired_count=min_capacity,
    launch_type="FARGATE",
    load_balancers=[pulumi_aws.ecs.ServiceLoadBalancerArgs(
        target_group_arn=target_group.arn,
        container_name=service_name.replace(".", "-").replace("/", "-")[:255],
        container_port=container_port,
    )],
    network_configuration=pulumi_aws.ecs.ServiceNetworkConfigurationArgs(
        assign_public_ip=False,
        subnets=private_subnets.ids,
        security_groups=[ecs_sg.id],
    ),
    deployment_circuit_breaker=pulumi_aws.ecs.ServiceDeploymentCircuitBreakerArgs(
        enable=True,
        rollback=True,
    ),
    opts=pulumi.ResourceOptions(depends_on=[listener_rule]),
)

# Cloudflare DNS: service_name -> ALB
dns_record = pulumi_cloudflare.DnsRecord(
    f"{service_name}_dns",
    zone_id=zone.id,
    name=service_name,
    content=external_alb.dns_name,
    type="CNAME",
    ttl=1,
    proxied=True,
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# Outputs
pulumi.export("ecr_repository_uri", ecr_repo.repository_url)
pulumi.export("ecs_cluster_name", cluster.name)
pulumi.export("ecs_service_name", ecs_service.name)
pulumi.export("service_url", hostname_str.apply(lambda h: f"https://{h}"))
