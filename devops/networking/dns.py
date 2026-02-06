"""Cloudflare DNS record (CNAME service_name -> ALB)."""

import pulumi
import pulumi_cloudflare


def create_dns_record(
    service_name: str,
    alb_dns_name: str,
    zone_id: str,
    cf_provider: pulumi_cloudflare.Provider,
) -> pulumi_cloudflare.Record:
    """Create Cloudflare CNAME record: service_name -> ALB DNS name (proxied)."""
    return pulumi_cloudflare.Record(
        f"{service_name}_dns",
        zone_id=zone_id,
        name=service_name,
        content=alb_dns_name,
        type="CNAME",
        ttl=1,
        proxied=True,
        opts=pulumi.ResourceOptions(provider=cf_provider),
    )
