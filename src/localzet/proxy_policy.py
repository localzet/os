"""Experimental policy for a dedicated application network namespace.

Not a host firewall or a launcher. The caller must establish namespace
isolation before starting any application, and provide a trusted proxy.
"""
import ipaddress


def render_policy(proxy_address: str, proxy_port: int) -> str:
    """Permit only TCP to one literal proxy endpoint; deny all other egress."""
    address = ipaddress.ip_address(proxy_address)
    if (address.is_unspecified or address.is_multicast or address.is_loopback
            or address.is_link_local or getattr(address, "ipv4_mapped", None)
            or getattr(address, "scope_id", None)):
        raise ValueError("proxy must be a dedicated reachable unicast endpoint")
    if type(proxy_port) is not int or not 1 <= proxy_port <= 65535:
        raise ValueError("invalid proxy port")
    family = "ip" if address.version == 4 else "ip6"
    return (
        "table inet localzet_proxy_only {\n"
        " chain output {\n"
        "  type filter hook output priority filter; policy drop;\n"
        f"  {family} daddr {address} tcp dport {proxy_port} counter accept\n"
        "  counter drop\n"
        " }\n"
        "}\n"
    )
