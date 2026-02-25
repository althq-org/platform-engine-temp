"""Unit tests for create_redis_cluster (ElastiCache SubnetGroup and ReplicationGroup)."""

from unittest.mock import MagicMock, patch

from devops.cache.redis import create_redis_cluster


@patch("devops.cache.redis.pulumi_aws.elasticache.ReplicationGroup")
@patch("devops.cache.redis.pulumi_aws.elasticache.SubnetGroup")
def test_create_redis_cluster_defaults(
    mock_subnet: MagicMock,
    mock_replication: MagicMock,
) -> None:
    """create_redis_cluster uses default node_type and num_cache_clusters."""
    mock_subnet.return_value.name = "my-svc-redis-subnets"
    mock_replication.return_value.primary_endpoint_address = "my-svc-redis.abc123.0001.use1.cache.amazonaws.com"
    mock_replication.return_value.configuration_endpoint_address = None

    aws_provider = MagicMock()
    sg_id = MagicMock()

    subnet_group, replication_group = create_redis_cluster(
        service_name="my-svc",
        private_subnet_ids=["subnet-a", "subnet-b"],
        security_group_id=sg_id,
        aws_provider=aws_provider,
    )

    assert subnet_group.name == "my-svc-redis-subnets"
    assert replication_group.primary_endpoint_address == "my-svc-redis.abc123.0001.use1.cache.amazonaws.com"

    subnet_kw = mock_subnet.call_args[1]
    assert subnet_kw["name"] == "my-svc-redis-subnets"
    assert subnet_kw["subnet_ids"] == ["subnet-a", "subnet-b"]

    repl_kw = mock_replication.call_args[1]
    assert repl_kw["node_type"] == "cache.t3.micro"
    assert repl_kw["num_cache_clusters"] == 1
    assert repl_kw["engine"] == "redis"
    assert repl_kw["security_group_ids"] == [sg_id]


@patch("devops.cache.redis.pulumi_aws.elasticache.ReplicationGroup")
@patch("devops.cache.redis.pulumi_aws.elasticache.SubnetGroup")
def test_create_redis_cluster_custom_node_type_and_nodes(
    mock_subnet: MagicMock,
    mock_replication: MagicMock,
) -> None:
    """create_redis_cluster passes through custom node_type and num_cache_clusters."""
    mock_subnet.return_value.name = "test-svc-redis-subnets"
    mock_replication.return_value.primary_endpoint_address = "test-svc.xyz.0001.use1.cache.amazonaws.com"
    mock_replication.return_value.configuration_endpoint_address = None

    aws_provider = MagicMock()
    sg_id = MagicMock()

    _subnet_group, _replication_group = create_redis_cluster(
        service_name="test-svc",
        private_subnet_ids=["subnet-1"],
        security_group_id=sg_id,
        aws_provider=aws_provider,
        node_type="cache.r6g.large",
        num_cache_clusters=2,
    )

    repl_kw = mock_replication.call_args[1]
    assert repl_kw["node_type"] == "cache.r6g.large"
    assert repl_kw["num_cache_clusters"] == 2
