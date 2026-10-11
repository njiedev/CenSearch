"""Robots is opt-in; request safety controls apply in both modes."""

import asyncio
from urllib.robotparser import RobotFileParser

import httpx
import pytest

from censearch.agent.web import ReadOnlyWeb, lookup_session
from censearch.config import Settings
from censearch.crawl import BudgetExceeded, Crawler
from censearch.verify import check


def deny_all():
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Disallow: /", "Crawl-delay: 60"])
    return parser


def test_setting_environment(monkeypatch):
    monkeypatch.delenv("RESPECT_ROBOTS", raising=False)
    assert Settings(_env_file=None).respect_robots is False
    monkeypatch.setenv("RESPECT_ROBOTS", "true")
    assert Settings(_env_file=None).respect_robots is True


def test_crawler_default_preserves_guards(settings, monkeypatch):
    requested = []
    waits = []
    settings.crawl_request_budget = 2

    def respond(request):
        requested.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\nCrawl-delay: 60")
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "http://localhost:9999/outside"})
        return httpx.Response(200, text="ok")

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("censearch.crawl.asyncio.sleep", sleep)

    async def run():
        crawler = Crawler(settings, None, None, 0, {"seeds": ["http://localhost/"], "delay": 0.05})
        # Even a cached parser must have no effect while enforcement is off.
        crawler.robots["http://localhost"] = deny_all()
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            crawler.client = client
            assert (await crawler.fetch("http://localhost/private", page=True)).status_code == 200
            assert await crawler.fetch("http://localhost/redirect", page=True) is None
            assert crawler.metrics["out_of_scope_pages"] == 1
            with pytest.raises(BudgetExceeded):
                await crawler.fetch("http://localhost/another", page=True)
            with pytest.raises(ValueError, match="Public crawling"):
                await crawler.fetch("https://example.com/")
        assert crawler.metrics["robots_denied"] == 0
        assert crawler.metrics["network_requests"] == 2

    asyncio.run(run())
    assert [request.url.path for request in requested] == ["/private", "/redirect"]
    assert all(request.method == "GET" for request in requested)
    assert all(0 <= wait <= 0.05 for wait in waits)


def test_web_default_preserves_guards(settings, monkeypatch):
    requested = []
    waits = []

    def respond(request):
        requested.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\nCrawl-delay: 60")
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "http://192.168.1.1/private"})
        return httpx.Response(200, text="ok")

    monkeypatch.setattr("censearch.agent.web.time.sleep", waits.append)
    web = ReadOnlyWeb(settings=settings, limit=2, transport=httpx.MockTransport(respond))
    web.robots["http://localhost"] = deny_all()
    try:
        assert web.get("http://localhost/private").status_code == 200
        with pytest.raises(ValueError, match="Private-network"):
            web.get("http://localhost/redirect")
        with pytest.raises(ValueError, match="budget"):
            web.get("http://localhost/another")
        assert web.count == 2
        assert not any("robots_allowed" in entry for entry in web.trace)
    finally:
        web.close()
    assert [request.url.path for request in requested] == ["/private", "/redirect"]
    assert all(request.method == "GET" for request in requested)
    assert all(0 <= wait <= settings.crawl_delay for wait in waits)


def test_lookup_uses_active_settings(settings):
    settings.respect_robots = True
    with lookup_session("http://localhost/", settings) as session:
        assert session.web.respect_robots is True


def test_verify_robots_blocked(settings):
    settings.respect_robots = True
    requested = []

    def respond(request):
        requested.append(request.url.path)
        return httpx.Response(200, text="User-agent: *\nDisallow: /")

    web = ReadOnlyWeb(settings=settings, transport=httpx.MockTransport(respond), delay=0)
    result = check({"page_url": "http://localhost/private"}, b"", {}, web=web)
    assert result["outcome"] == "blocked"
    assert requested == ["/robots.txt"]


def test_health_reports_robots(client, settings):
    assert client.get("/api/health").json()["respect_robots"] is False
    settings.respect_robots = True
    assert client.get("/api/health").json()["respect_robots"] is True
