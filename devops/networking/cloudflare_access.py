"""Cloudflare Zero Trust Access (IDP + Policy + Application) per service.

Follows the same patterns as platform/infra/product/cloudflare/ for
ZeroTrustAccessIdentityProvider, ZeroTrustAccessPolicy, and
ZeroTrustAccessApplication.
"""

import pulumi
import pulumi_cloudflare


def _sanitize_resource_name(service_name: str) -> str:
    """Sanitize service name for use in Pulumi resource logical names."""
    return service_name.replace(".", "_").replace("/", "_")


def create_access_application(
    service_name: str,
    zone_name: str,
    account_id: str,
    cf_provider: pulumi_cloudflare.Provider,
) -> pulumi_cloudflare.ZeroTrustAccessApplication:
    """Create Cloudflare Zero Trust IDP, policy, and access app for a platform service.

    Uses the same google_oauth config namespace and resource patterns as
    platform/infra/product/cloudflare/ (pgAdmin/Cronicle).
    """
    safe = _sanitize_resource_name(service_name)
    google_oauth_config = pulumi.Config("google_oauth")

    idp = pulumi_cloudflare.ZeroTrustAccessIdentityProvider(
        f"{safe}_platform_google_oauth_idp",
        account_id=account_id,
        config=pulumi_cloudflare.ZeroTrustAccessIdentityProviderConfigArgs(
            client_id=google_oauth_config.require_secret("client_id"),
            client_secret=google_oauth_config.require_secret("client_secret"),
            apps_domain="althq.com",
        ),
        name=f"Platform {service_name}",
        type="google-apps",
        opts=pulumi.ResourceOptions(provider=cf_provider),
    )

    policy = pulumi_cloudflare.ZeroTrustAccessPolicy(
        f"{safe}_platform_access_policy",
        name=f"Platform {service_name} Google Workspace",
        account_id=account_id,
        decision="allow",
        includes=[
            pulumi_cloudflare.ZeroTrustAccessPolicyIncludeArgs(
                login_method=(
                    pulumi_cloudflare.ZeroTrustAccessPolicyIncludeLoginMethodArgs(
                        id=idp.id,
                    )
                ),
            ),
        ],
        opts=pulumi.ResourceOptions(provider=cf_provider),
    )

    access_app = pulumi_cloudflare.ZeroTrustAccessApplication(
        f"{safe}_platform_access_app",
        destinations=[
            pulumi_cloudflare.ZeroTrustAccessApplicationDestinationArgs(
                uri=f"{service_name}.{zone_name}",
            )
        ],
        name=f"Platform {service_name}",
        session_duration="12h",
        type="self_hosted",
        enable_binding_cookie=False,
        http_only_cookie_attribute=True,
        same_site_cookie_attribute="lax",
        account_id=account_id,
        allowed_idps=[idp.id],
        app_launcher_visible=False,
        auto_redirect_to_identity=True,
        policies=[
            pulumi_cloudflare.ZeroTrustAccessApplicationPolicyArgs(
                id=policy.id,
            ),
        ],
        opts=pulumi.ResourceOptions(provider=cf_provider),
    )

    return access_app
