"""Clearly labelled deterministic baseline using exactly the agent's tools."""

from urllib.parse import urlsplit
from censearch.agent.tools import dns_lookup, fetch_page, find_policy_pages, platform_registry, rdap_lookup
from censearch.agent.web import lookup_session


def ranked(candidates):
    order = {"site": 0, "host": 1, "search": 2}
    rows = sorted(candidates, key=lambda row: (order[row["rung"]], row["channel"].startswith("manual")))
    return [dict(row, rank=index + 1) for index, row in enumerate(rows)]


def resolve(page_url, settings=None, web=None):
    with lookup_session(page_url, settings, web) as session:
        page = fetch_page(page_url)
        policies = find_policy_pages(page_url)
        parsed = urlsplit(page_url)
        if not policies.get("links"):
            root = f"{parsed.scheme}://{parsed.netloc}/"
            policies = find_policy_pages(root)
        for link in policies.get("links", [])[:3]:
            fetch_page(link["url"])
        dns = dns_lookup(parsed.hostname)
        if dns.get("addresses"):
            rdap_lookup(dns["addresses"][0])
        platform_registry(parsed.hostname)
        return {
            "source": "deterministic_baseline",
            "status": "completed",
            "model_status": "not_used",
            "recipients": ranked(session.candidates),
            "tool_calls": session.calls,
            "requests": session.web.trace,
            "page_status": page.get("status"),
            "limitations": [
                "Published contacts require human review.",
                "CDN/RDAP contacts may identify a serving network rather than the origin.",
            ],
        }
