"""Bounded GET transport with optional robots enforcement for research, evidence and checks."""

from contextlib import contextmanager
from contextvars import ContextVar
import ipaddress
import socket
import threading
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import httpx
from censearch.config import Settings

UA = "LikenessGuard/0.2 (read-only recipient research)"
ACTIVE = ContextVar("recipient_lookup", default=None)


def loopback(hostname):
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def validate_read_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only HTTP(S) URLs without credentials are supported")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    if not addresses:
        raise ValueError("Hostname has no addresses")
    for row in addresses:
        address = ipaddress.ip_address(row[4][0])
        if not address.is_global and not (loopback(parsed.hostname) and address.is_loopback):
            raise ValueError("Private-network targets other than literal loopback are not allowed")
    return parsed


class ReadOnlyWeb:
    def __init__(
        self,
        limit=20,
        timeout=8,
        delay=None,
        transport=None,
        recorder=None,
        *,
        settings=None,
        respect_robots=None,
    ):
        settings = settings or Settings()
        self.respect_robots = settings.respect_robots if respect_robots is None else respect_robots
        self.client = httpx.Client(
            timeout=timeout,
            trust_env=False,
            follow_redirects=False,
            headers={"User-Agent": UA},
            transport=transport,
        )
        self.limit = limit
        self.delay = settings.crawl_delay if delay is None else delay
        self.count = 0
        self.trace = []
        self.robots = {}
        self.cache = {}
        self.last = {}
        self.lock = threading.RLock()
        self.recorder = recorder

    def close(self):
        self.client.close()

    def raw(self, url):
        validate_read_url(url)
        if self.count >= self.limit:
            raise ValueError("Read-only request budget exhausted")
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        parser = self.robots.get(origin) if self.respect_robots else None
        delay = max(self.delay, (parser.crawl_delay(UA) or 0) if parser else 0)
        time.sleep(max(0, self.last.get(origin, 0) + delay - time.monotonic()))
        self.count += 1
        self.last[origin] = time.monotonic()
        try:
            with self.client.stream("GET", url) as response:
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 20_000_000:
                        raise ValueError("GET response exceeds 20 MB")
                headers = dict(response.headers)
                for key in ("content-encoding", "content-length", "transfer-encoding"):
                    headers.pop(key, None)
                result = httpx.Response(
                    response.status_code, headers=headers, content=bytes(content), request=response.request
                )
            self.trace.append(
                {
                    "url": url,
                    "method": "GET",
                    "status": result.status_code,
                    "headers": relevant_headers(result.headers),
                }
            )
            if self.recorder:
                self.recorder(result)
            return result
        except Exception as error:
            self.trace.append({"url": url, "method": "GET", "error": type(error).__name__})
            raise

    def get(self, url, *, cache=True):
        with self.lock:
            original = url
            if cache and url in self.cache:
                return self.cache[url]
            for _ in range(6):
                parsed = validate_read_url(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                if self.respect_robots:
                    if origin not in self.robots:
                        robot_url = origin + "/robots.txt"
                        response = self.raw(robot_url)
                        # Redirecting robots files are fetched without granting access to the page.
                        for _ in range(4):
                            if not response.is_redirect:
                                break
                            robot_url = urljoin(robot_url, response.headers["location"])
                            response = self.raw(robot_url)
                        parser = RobotFileParser()
                        lines = (
                            response.text.splitlines()
                            if response.status_code == 200
                            else [
                                "User-agent: *",
                                "Allow: /" if response.status_code == 404 else "Disallow: /",
                            ]
                        )
                        parser.parse(lines)
                        self.robots[origin] = parser
                    allowed = self.robots[origin].can_fetch(UA, url)
                    self.trace.append({"url": url, "robots_allowed": allowed})
                    if not allowed:
                        raise ValueError("robots.txt disallows " + url)
                response = self.raw(url)
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                if cache:
                    self.cache[original] = response
                return response
            raise ValueError("GET redirect limit exceeded")


def relevant_headers(headers):
    names = ("content-type", "etag", "last-modified", "server", "via", "location", "cf-ray", "x-served-by")
    return {key: headers[key] for key in names if key in headers}


class LookupSession:
    def __init__(self, url, settings=None, web=None):
        self.url = url
        self.settings = settings
        self.web = web or ReadOnlyWeb(settings=settings)
        self.calls = []
        self.candidates = []
        self.lock = threading.RLock()

    def add(self, rung, channel, address, endpoint, source, method, **evidence):
        candidate = {
            "rung": rung,
            "channel": channel,
            "address": address,
            "endpoint": endpoint,
            "evidence": {"source": source, "method": method, **evidence},
        }
        with self.lock:
            previous = next(
                (
                    c
                    for c in self.candidates
                    if all(c[k] == candidate[k] for k in ("rung", "channel", "address", "endpoint"))
                ),
                None,
            )
            if previous:
                return previous
            candidate["id"] = f"contact-{len(self.candidates) + 1}"
            self.candidates.append(candidate)
            return candidate

    def email(self, rung, address, source, method, **evidence):
        relay = getattr(self.settings, "smtp_relay", "")
        # A mock relay is never used for contacts discovered on real domains.
        local = loopback(urlsplit(self.url).hostname)
        endpoint = relay if relay and local and address.endswith(".test") else "mailto:" + address
        return self.add(
            rung,
            "smtp" if endpoint.startswith("smtp:") else "email",
            address,
            endpoint,
            source,
            method,
            **evidence,
        )

    def form(self, rung, endpoint, source, method, **evidence):
        channel = "http_form" if loopback(urlsplit(endpoint).hostname) else "manual_web"
        return self.add(rung, channel, endpoint, endpoint, source, method, **evidence)


@contextmanager
def lookup_session(url, settings=None, web=None):
    session = LookupSession(url, settings, web)
    token = ACTIVE.set(session)
    try:
        yield session
    finally:
        ACTIVE.reset(token)
        session.web.close()


def run_tool(name, args, operation):
    session = ACTIVE.get()
    if session is None:
        with lookup_session(args.get("url", "http://localhost")):
            return run_tool(name, args, operation)
    with session.lock:
        try:
            result = operation(session)
        except Exception as error:
            result = {
                "status": "error",
                "error": type(error).__name__,
                "message": str(error)[:500] if isinstance(error, ValueError) else "Read-only lookup failed",
            }
        session.calls.append({"tool": name, "input": args, "result": result})
        return result
