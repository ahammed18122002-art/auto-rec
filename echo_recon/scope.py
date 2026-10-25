"""Strict target parsing and scope checks. No shell interpolation is used anywhere."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, parse_qsl

_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)


@dataclass(frozen=True)
class Target:
    raw: str
    host: str
    scheme: str
    port: int | None
    path: str
    query: str

    @property
    def origin(self) -> str:
        display_host = f"[{self.host}]" if ":" in self.host else self.host
        netloc = display_host if self.port is None else f"{display_host}:{self.port}"
        return urlunsplit((self.scheme, netloc, "", "", ""))

    @property
    def url(self) -> str:
        display_host = f"[{self.host}]" if ":" in self.host else self.host
        netloc = display_host if self.port is None else f"{display_host}:{self.port}"
        return urlunsplit((self.scheme, netloc, self.path or "/", self.query, ""))

    @property
    def has_query_parameters(self) -> bool:
        return bool(parse_qsl(self.query, keep_blank_values=True))


def parse_target(value: str) -> Target:
    """Accept a domain, IP, or URL; validate the authority and normalize scheme."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("একটি domain বা URL দিন।")
    if any(ord(ch) < 32 for ch in raw) or any(ch.isspace() for ch in raw):
        raise ValueError("Target-এ whitespace/control character থাকা যাবে না।")
    candidate = raw if "://" in raw else "https://" + raw
    try:
        parts = urlsplit(candidate)
        host = (parts.hostname or "").rstrip(".").lower()
        port = parts.port
    except ValueError as exc:
        raise ValueError("Target URL বা port সঠিক নয়।") from exc
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("শুধু http:// অথবা https:// URL ব্যবহার করুন।")
    if not host or host.startswith(".") or ".." in host:
        raise ValueError("সঠিক domain বা IP address দিন।")
    # IP literals are accepted; DNS names must consist of valid labels.
    import ipaddress
    try:
        ipaddress.ip_address(host.strip("[]"))
        normalized_host = host
    except ValueError:
        if len(host) > 253 or not all(_HOST_LABEL.fullmatch(label) for label in host.split(".")):
            raise ValueError("Domain-এর format সঠিক নয়।")
        normalized_host = host
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL-এর মধ্যে username/password দেওয়া যাবে না।")
    path = parts.path or "/"
    # Keep query only for parameter testing; report functions redact its values.
    return Target(raw=raw, host=normalized_host, scheme=parts.scheme.lower(), port=port,
                  path=path, query=parts.query)


def is_in_scope(host: str, root_host: str) -> bool:
    """Permit only the exact target host or a DNS descendant of the supplied root."""
    host = (host or "").strip().lower().rstrip(".").strip("[]")
    root_host = (root_host or "").strip().lower().rstrip(".").strip("[]")
    if not host or not root_host:
        return False
    if host == root_host:
        return True
    # IP targets do not have in-scope DNS descendants.
    import ipaddress
    try:
        ipaddress.ip_address(root_host)
        return False
    except ValueError:
        return host.endswith("." + root_host)


def filter_in_scope_hosts(lines: list[str], root_host: str) -> list[str]:
    """Extract hostname-like lines and drop anything outside the supplied scope."""
    found: set[str] = set()
    for line in lines:
        host = line.strip().lower().rstrip(".")
        if host.startswith("*."):
            host = host[2:]
        if len(host) <= 253 and is_in_scope(host, root_host):
            found.add(host)
    return sorted(found)


def redact_url(url: str) -> str:
    """Redact query parameter values before displaying URLs in generated reports."""
    try:
        p = urlsplit(url)
        if not p.query:
            return url
        keys = parse_qsl(p.query, keep_blank_values=True)
        query = "&".join(f"{k}=REDACTED" for k, _ in keys)
        return urlunsplit((p.scheme, p.netloc, p.path, query, ""))
    except Exception:
        return "[target redacted]"


def bound_active_hosts(root_host: str, in_scope_hosts: list[str], max_hosts: int = 100) -> list[str]:
    """Keep passive discovery evidence, but bound live probing to a predictable host count."""
    if max_hosts < 1:
        raise ValueError("max_hosts must be at least 1")
    normalized = filter_in_scope_hosts([root_host, *in_scope_hosts], root_host)
    # Always include the supplied root first; cap additional discovered hosts afterwards.
    children = [host for host in normalized if host != root_host]
    return [root_host] + children[: max_hosts - 1]
