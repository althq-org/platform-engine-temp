"""Cloudflare Zero Trust Access (policy + application) per service.

Reuses the existing Google OAuth identity provider (same as althq-services):
looks up by name "{environment} althq-frontend Pages Previews", then creates
only the per-service Access policy and Access application. No client_id/secret needed.
"""

import pulumi
import pulumi_cloudflare


def _sanitize_resource_name(service_name: str) -> str:
    """Sanitize service name for use in Pulumi resource logical names."""
    return service_name.replace(".", "_").replace("/", "_")


def _get_environment() -> str:
    """Derive environment from Pulumi stack name (e.g. dev.service.us-west-2 -> dev)."""
    stack = pulumi.get_stack()
    return stack.split(".")[0] if "." in stack else "dev"


def create_access_application(
    service_name: str,
    zone_id: str,
    zone_name: str,
    account_id: str,
    cf_provider: pulumi_cloudflare.Provider,
) -> pulumi_cloudflare.ZeroTrustAccessApplication:
    """Create Cloudflare Zero Trust policy and access app for a platform service.

    Reuses the existing Google OAuth IDP (lookup by name, same as althq-services).
    No google_oauth client_id/secret config required.
    """
    safe = _sanitize_resource_name(service_name)
    environment = _get_environment()
    idp_name = f"{environment} althq-frontend Pages Previews"

    identity_providers = pulumi_cloudflare.get_zero_trust_access_identity_providers(
        account_id=account_id,
        zone_id=zone_id,
        opts=pulumi.InvokeOptions(provider=cf_provider),
    )
    matching = [idp for idp in identity_providers.results if idp.name == idp_name]
    if not matching:
        raise SystemExit(
            f"Cloudflare Zero Trust: no identity provider named '{idp_name}'. "
            "Create it in the Cloudflare dashboard or another stack (e.g. platform/infra/product)."
        )
    _raw_id = getattr(matching[0], "id", "")
    idp_id: str = str(_raw_id() if callable(_raw_id) else _raw_id)

    policy = pulumi_cloudflare.ZeroTrustAccessPolicy(
        f"{safe}_platform_access_policy",
        name=f"Platform {service_name} Google Workspace",
        account_id=account_id,
        decision="allow",
        includes=[
            pulumi_cloudflare.ZeroTrustAccessPolicyIncludeArgs(
                login_method=pulumi_cloudflare.ZeroTrustAccessPolicyIncludeLoginMethodArgs(
                    id=idp_id,
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
        allowed_idps=[idp_id],
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
