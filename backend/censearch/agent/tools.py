"""Plain Strands tools. No image inputs, submissions or case/ground-truth access."""

import ipaddress
import re
import socket
import subprocess
from urllib.parse import urldefrag, urljoin, urlsplit
from bs4 import BeautifulSoup
from strands import tool
from censearch.agent.web import loopback, relevant_headers, run_tool

POLICY = re.compile(r"copyright|dmca|abuse|privacy|legal|report|contact", re.I)
REPORT = re.compile(r"report|abuse|copyright|dmca|privacy", re.I)
EXCLUDED = re.compile(r"log[ -]?in|sign[ -]?in|newsletter|subscribe|search", re.I)
PLATFORMS = {
    "github.com": "https://support.github.com/contact/report-abuse",
    "facebook.com": "https://www.facebook.com/help/contact/295309487309948",
    "instagram.com": "https://help.instagram.com/contact/636276399721841",
}
REGISTRY_VERSION = "2026-10-10"
SEARCH = "https://support.google.com/legal/troubleshooter/1114905"


def report_form(form, soup):
    labels = form.get_text(" ", strip=True)
    associated = " ".join(
        node.get_text(" ", strip=True)
        for identifier in form.get("aria-labelledby", "").split()
        if (node := soup.find(id=identifier))
    )
    own = " ".join(
        [
            form.get("action", ""),
            labels,
            associated,
            form.get("aria-label", ""),
            *[node.get("value", "") for node in form.select('input[type="submit"]')],
        ]
    )
    if form.select_one('input[type="password"], input[type="search"]') or EXCLUDED.search(own):
        return False
    return form.get("method", "get").lower() == "post" and bool(REPORT.search(own))


def parse_page(response, session):
    soup = BeautifulSoup(response.text, "html.parser")
    url = str(response.url)
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    links = []
    for node in soup.select("a[href]")[:300]:
        target = urldefrag(urljoin(url, node["href"]))[0]
        if urlsplit(target).scheme in ("http", "https", "mailto"):
            links.append({"url": target, "text": node.get_text(" ", strip=True)[:300]})
    forms = []
    for form in soup.select("form")[:30]:
        endpoint = urljoin(url, form.get("action", url))
        if urlsplit(endpoint).scheme not in ("http", "https"):
            continue
        fields = [
            {
                "name": node.get("name", ""),
                "type": node.get("type", node.name),
                "label": " ".join(
                    label.get_text(" ", strip=True)
                    for label in form.select("label")
                    if label.get("for") == node.get("id") or node in label.descendants
                ),
            }
            for node in form.select("input, textarea, select, button")
        ][:40]
        headings = [node.get_text(" ", strip=True) for node in form.select("h1,h2,h3,legend")]
        nearby = form.find_previous(["h1", "h2", "h3"])
        is_report = report_form(form, soup)
        forms.append(
            {
                "action": endpoint,
                "method": form.get("method", "get").lower(),
                "fields": fields,
                "headings": headings,
                "nearby_heading": nearby.get_text(" ", strip=True)[:300] if nearby else None,
                "reporting": is_report,
            }
        )
        if is_report and urlsplit(endpoint).scheme in ("http", "https"):
            session.form(
                "site",
                endpoint,
                url,
                "reporting_form",
                fields=fields,
                form_text=form.get_text(" ", strip=True)[:1000],
            )
    for link in links:
        if link["url"].startswith("mailto:") and POLICY.search(link["text"] + " " + link["url"]):
            address = link["url"][7:].split("?")[0]
            if re.fullmatch(r"[^\s<>@]+@[^\s<>@]+", address):
                session.email("site", address, url, "published_email", link_text=link["text"])
    for node in soup.select("script,style,noscript,svg,template,[hidden],[aria-hidden=true]"):
        node.decompose()
    return {
        "status": response.status_code,
        "final_url": url,
        "title": title,
        "text": soup.get_text(" ", strip=True)[:12000],
        "links": links,
        "forms": forms,
        "headers": relevant_headers(response.headers),
        "contacts": list(session.candidates),
    }


@tool
def fetch_page(url: str) -> dict:
    """GET a page with a shared request budget and optional robots enforcement (off by default). Return text, links and forms.

    Args:
        url: Public or loopback HTTP(S) page URL. Never an upload or submission.
    """

    def fetch(session):
        response = session.web.get(url)
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            return {
                "status": response.status_code,
                "final_url": str(response.url),
                "text": "",
                "links": [],
                "forms": [],
                "headers": relevant_headers(response.headers),
            }
        return parse_page(response, session)

    return run_tool("fetch_page", {"url": url}, fetch)


@tool
def find_policy_pages(url: str) -> dict:
    """Find same-site policy/contact links with the link text supporting the choice.

    Args:
        url: The page to inspect for copyright, privacy, legal, abuse, report or contact links.
    """

    def find(session):
        page = fetch_page(url)
        final = page.get("final_url", url)
        links = [
            link
            for link in page.get("links", [])
            if urlsplit(link["url"]).netloc == urlsplit(final).netloc
            and link["url"] != urldefrag(final)[0]
            and POLICY.search(link["text"] + " " + urlsplit(link["url"]).path)
        ]
        return {"status": page.get("status"), "source": final, "links": links[:20]}

    return run_tool("find_policy_pages", {"url": url}, find)


@tool
def dns_lookup(hostname: str) -> dict:
    """Resolve a hostname to IPs and, when dig is available, CNAMEs.

    Args:
        hostname: DNS hostname or IP literal without URL or port.
    """

    def lookup(session):
        if not hostname or len(hostname) > 253 or not re.fullmatch(r"[A-Za-z0-9.:-]+", hostname):
            return {"hostname": hostname, "status": "invalid_hostname", "addresses": [], "cnames": []}
        try:
            addresses = sorted({row[4][0] for row in socket.getaddrinfo(hostname, None)})
        except socket.gaierror:
            return {"hostname": hostname, "status": "not_resolved", "addresses": [], "cnames": []}
        cnames = []
        try:
            if not loopback(hostname):
                result = subprocess.run(
                    ["dig", "+short", "+time=2", "+tries=1", "CNAME", hostname],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                cnames = result.stdout.splitlines() if result.returncode == 0 else []
        except (OSError, subprocess.TimeoutExpired):
            pass
        return {
            "hostname": hostname,
            "status": "resolved",
            "addresses": addresses,
            "cnames": cnames,
            "caution": "DNS/CDN addresses do not prove the origin hosting provider.",
        }

    return run_tool("dns_lookup", {"hostname": hostname}, lookup)


@tool
def rdap_lookup(ip_or_domain: str) -> dict:
    """Use IANA bootstrap to select RDAP, then extract nested abuse entities and channels.

    Args:
        ip_or_domain: IP address or registered domain, without URL or port.
    """

    def lookup(session):
        try:
            address = ipaddress.ip_address(ip_or_domain)
            family = "ipv4" if address.version == 4 else "ipv6"
        except ValueError:
            address = None
            family = "dns"
            if not re.fullmatch(r"[A-Za-z0-9.-]+", ip_or_domain):
                raise ValueError("Invalid domain")
        override = getattr(session.settings, "rdap_bootstrap", "")
        local = loopback(urlsplit(session.url).hostname)
        bootstrap = override if local and override else f"https://data.iana.org/rdap/{family}.json"
        if address and not address.is_global and not (local and override):
            return {
                "status": "not_public",
                "contacts": [],
                "message": "No public RDAP for private allocations",
            }
        response = session.web.get(bootstrap)
        response.raise_for_status()
        choices = []
        for networks, urls in response.json()["services"]:
            for network in networks:
                if address:
                    subnet = ipaddress.ip_network(network)
                    match = address in subnet
                    specificity = subnet.prefixlen
                else:
                    match = ip_or_domain.rsplit(".", 1)[-1].lower() == network.lower()
                    specificity = len(network)
                if match:
                    choices.append((specificity, urls[0]))
        if not choices:
            return {"status": "no_registry", "bootstrap": bootstrap, "contacts": []}
        service = max(choices)[1]
        endpoint = service.rstrip("/") + ("/ip/" if address else "/domain/") + ip_or_domain
        if local and loopback(urlsplit(service).hostname):
            endpoint += f"?origin_port={urlsplit(session.url).port or 80}"
        response = session.web.get(endpoint)
        response.raise_for_status()
        data = response.json()
        contacts = []

        def entities(items):
            for entity in items:
                if "abuse" in entity.get("roles", []):
                    for field in entity.get("vcardArray", ["", []])[1]:
                        if field[0] == "email":
                            contacts.append(
                                session.email(
                                    "host",
                                    field[3],
                                    endpoint,
                                    "RDAP_abuse_vcard",
                                    network=data.get("name"),
                                    origin_unverified=True,
                                )
                            )
                entities(entity.get("entities", []))

        entities(data.get("entities", []))
        for link in data.get("links", []):
            if link.get("rel") == "abuse" and urlsplit(link.get("href", "")).scheme in ("http", "https"):
                contacts.append(session.form("host", link["href"], endpoint, "RDAP_abuse_link"))
        return {
            "status": "completed",
            "bootstrap": bootstrap,
            "registry_url": endpoint,
            "name": data.get("name"),
            "contacts": contacts,
        }

    return run_tool("rdap_lookup", {"ip_or_domain": ip_or_domain}, lookup)


@tool
def platform_registry(hostname: str) -> dict:
    """Consult a versioned registry of platform and search removal channels.

    Args:
        hostname: Website hostname whose reporting channel is needed.
    """

    def lookup(session):
        contacts = []
        for domain, endpoint in PLATFORMS.items():
            if hostname == domain or hostname.endswith("." + domain):
                contacts.append(
                    session.form(
                        "site",
                        endpoint,
                        "platform-registry-" + REGISTRY_VERSION,
                        "platform_registry",
                        domain=domain,
                    )
                )
        local = loopback(urlsplit(session.url).hostname)
        override = getattr(session.settings, "search_endpoint", "")
        search = override if local and override else SEARCH
        contacts.append(
            session.form(
                "search",
                search,
                "platform-registry-" + REGISTRY_VERSION,
                "search_registry",
                scope="Delisting only; source remains",
            )
        )
        return {"version": REGISTRY_VERSION, "contacts": contacts}

    return run_tool("platform_registry", {"hostname": hostname}, lookup)
