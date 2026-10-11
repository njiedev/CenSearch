"""Person-owned hostname exclusions, evaluated against current settings at read time."""

import ipaddress
import re
from urllib.parse import urlsplit
from sqlalchemy import select
from censearch.db import WhitelistDomain


def normalize_domain(entry):
    value = entry.strip().lower()
    try:
        if any(character in value for character in "\r\n\t"):
            raise ValueError()
        # Bare IPv6 addresses need no URL parsing (which requires brackets).
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            pass
        parsed = urlsplit(value if "://" in value else "//" + value)
        if parsed.username or parsed.password or not parsed.hostname:
            raise ValueError()
        parsed.port  # Validate a supplied port before discarding it.
        host = parsed.hostname.removeprefix("www.").removesuffix(".")
        try:
            return str(ipaddress.ip_address(host))
        except ValueError:
            pass
        host = host.encode("idna").decode("ascii")
        labels = host.split(".")
        if host == "localhost":
            return host
        if len(host) > 253 or len(labels) < 2 or labels[-1].isdigit():
            raise ValueError()
        if any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
        ):
            raise ValueError()
        return host
    except (ValueError, UnicodeError):
        raise ValueError(f"Invalid whitelist entry: {entry!r}") from None


def domains_for(session, person_id):
    return list(
        session.scalars(
            select(WhitelistDomain.domain)
            .where(WhitelistDomain.person_id == person_id)
            .order_by(WhitelistDomain.domain)
        )
    )


def matches(page_url, domains):
    try:
        host = (urlsplit(page_url).hostname or "").lower().removeprefix("www.").removesuffix(".")
        try:
            host = str(ipaddress.ip_address(host))
        except ValueError:
            host = host.encode("idna").decode("ascii")
    except (ValueError, UnicodeError):
        return False
    for domain in domains:
        if host == domain:
            return True
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            if domain != "localhost" and host.endswith("." + domain):
                return True
    return False


def is_whitelisted(session, case):
    return matches(case.page_url, domains_for(session, case.person_id))
