"""
Shared utility functions used across modules.
"""
import os
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Get client IP address, handling proxy headers (A9 security fix).
    Trusts X-Forwarded-For header only if app is behind known proxy.
    Takes the RIGHTMOST IP from X-Forwarded-For (the one added by trusted proxy).
    Falls back to remote address for direct connections.

    ASSUMPTION: Single trusted proxy hop. If multiple hops exist,
    this logic needs adjustment to take the correct position.
    """
    # Check if app is behind proxy (via environment variable)
    behind_proxy = os.getenv("BEHIND_PROXY", "false").lower() == "true"

    if behind_proxy:
        # Trust X-Forwarded-For header from known proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For format: client, proxy1, proxy2
            # The RIGHTMOST IP is the one added by our trusted proxy
            # This prevents client spoofing
            # ASSUMPTION: Single trusted proxy hop. Rightmost = proxy's view of client
            ips = [ip.strip() for ip in forwarded_for.split(",")]
            return ips[-1] if ips else "unknown"

        # Fall back to X-Real-IP if X-Forwarded-For not present
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

    # Direct connection - use remote address
    return request.client.host if request.client else "unknown"
