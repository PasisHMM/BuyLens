"""Product-link normalization and allow-list matching."""

import ipaddress
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "gclid", "gbraid", "wbraid", "fbclid", "msclkid", "yclid", "dclid", "twclid", "ttclid",
    "mc_cid", "mc_eid", "_ga", "_gl", "srsltid", "irclickid", "clickid", "cjevent",
    "ref", "ref_", "referrer", "source", "cmp", "cid", "icid", "spm",
}  # fmt: skip
TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "_branch", "oly_")


class InvalidProductUrl(ValueError):
    pass


def normalize_url(raw: str) -> str:
    """Return an https URL without tracking parameters or fragment. Rejects anything unsafe."""
    raw = raw.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https"):
        raise InvalidProductUrl("Only web links (https://…) can be checked.")
    if parts.username or parts.password:
        raise InvalidProductUrl("Links with credentials are not supported.")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or "." not in host:
        raise InvalidProductUrl("That doesn't look like a product link.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise InvalidProductUrl("Links to IP addresses are not supported.")
    if parts.port not in (None, 80, 443):
        raise InvalidProductUrl("Links with custom ports are not supported.")

    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def domain_matches(host: str, domain: str) -> bool:
    """`www.levi.com` and `levi.com` match `levi.com`; `evil-levi.com` does not."""
    host, domain = host.lower().rstrip("."), domain.lower().rstrip(".")
    return host == domain or host.endswith(f".{domain}")


def seller_domain_for(url: str, domains: list[str]) -> str | None:
    host = host_of(url)
    # Longest match first, so a dedicated subdomain seller would win over its parent.
    for domain in sorted(domains, key=len, reverse=True):
        if domain_matches(host, domain):
            return domain
    return None
