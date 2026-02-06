"""ECR repository and lifecycle policy."""

import json

import pulumi
import pulumi_aws


def create_ecr_repository(
    service_name: str,
    aws_provider: pulumi_aws.Provider,
) -> pulumi_aws.ecr.Repository:
    """Create ECR repository with lifecycle policy (keep last 5 images)."""
    ecr_repo = pulumi_aws.ecr.Repository(
        f"{service_name}_ecr",
        name=service_name,
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=pulumi_aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=False,
        ),
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    pulumi_aws.ecr.LifecyclePolicy(
        f"{service_name}_ecr_lifecycle",
        repository=ecr_repo.name,
        policy=json.dumps(
            {
                "rules": [
                    {
                        "rulePriority": 1,
                        "description": "Keep last 5 images",
                        "selection": {
                            "tagStatus": "any",
                            "countType": "imageCountMoreThan",
                            "countNumber": 5,
                        },
                        "action": {"type": "expire"},
                    }
                ],
            }
        ),
        opts=pulumi.ResourceOptions(provider=aws_provider),
    )
    return ecr_repo
