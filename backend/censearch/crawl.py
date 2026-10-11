"""Bounded GET-only crawler. Nonmatching bytes never leave memory."""

import asyncio
from collections import Counter, deque
import hashlib
import ipaddress
import re
import time
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy import select
from censearch.db import CrawlRun, Scan, now

USER_AGENT = "LikenessGuard/0.1 (operator-scoped, read-only photo discovery)"


def origin(url):
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def absolute(base, value):
    target = urldefrag(urljoin(base, value))[0]
    return target if urlsplit(target).scheme in ("http", "https") else None


def validate_url(url, allow_public=False):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTP(S) URL without credentials")
    if not allow_public:
        if parsed.hostname == "localhost":
            return
        try:
            if ipaddress.ip_address(parsed.hostname).is_loopback:
                return
        except ValueError:
            pass
        raise ValueError("Public crawling is disabled; use a loopback mock URL")


def extract(html, page_url, computed=(), *, prefer_original=False):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    author = soup.select_one('meta[name="author"]')
    common = {"title": title, "author": author.get("content", "") if author else ""}
    images = {}

    def add(value, node=None, method="img"):
        url = absolute(page_url, value)
        if not url:
            return
        context = common | {"extraction": method}
        if node is not None:
            parent = node.find_parent(["figure", "article", "section", "li"]) or node.parent
            caption = parent.find("figcaption") if parent else None
            context.update(
                alt=node.get("alt", ""),
                caption=caption.get_text(" ", strip=True) if caption else "",
                nearby_text=parent.get_text(" ", strip=True)[:1500] if parent else "",
            )
        images.setdefault(url, context)

    suppressed = set()
    if prefer_original:
        for node in soup.select("img, source"):
            if node.name == "source" and node.find_parent("picture"):
                continue
            variants = []
            picture = node.find_parent("picture")
            nodes = [node, *(picture.select("source") if picture else [])]
            for source in nodes:
                for attr in ("srcset", "data-srcset"):
                    for option in source.get(attr, "").split(","):
                        parts = option.strip().split()
                        if parts:
                            size = re.search(r"([0-9.]+)[wx]$", parts[-1])
                            variants.append((float(size[1]) if size else 1, parts[0]))
            aliases = {
                absolute(page_url, node[attr])
                for attr in ("src", "data-src", "data-original")
                if node.get(attr)
            }
            aliases.update(absolute(page_url, url) for _, url in variants)
            anchor = node.find_parent("a", href=True)
            linked = None
            if anchor and re.search(
                r"\.(jpe?g|png|webp|gif|avif|bmp)$", urlsplit(anchor["href"]).path, re.I
            ):
                linked = anchor["href"]
            largest = max(variants, key=lambda item: item[0])[1] if variants else None
            chosen = (
                linked or node.get("data-original") or largest
                or node.get("data-src") or node.get("src")
            )
            if chosen:
                add(chosen, node, "preferred_original")
                suppressed.update(aliases - {absolute(page_url, chosen)})
    else:
        for node in soup.select("img, source"):
            for attr in ("src", "data-src", "data-original"):
                if node.get(attr):
                    add(node[attr], node, attr)
            for attr in ("srcset", "data-srcset"):
                for option in node.get(attr, "").split(","):
                    if option.strip():
                        add(option.strip().split()[0], node, attr)
    for node in soup.select('meta[property="og:image"], meta[name="og:image"]'):
        if node.get("content"):
            add(node["content"], method="og:image")
    for node in soup.select("[style], style"):
        for value in re.findall(r"url\(\s*['\"]?([^)'\"]+)", node.get("style", node.get_text())):
            add(value.strip(), node, "css_background")
    for value in computed:
        add(value, method="computed_css")
    links = []
    for node in soup.select("a[href]"):
        target = absolute(page_url, node["href"])
        if not target:
            continue
        if re.search(r"\.(jpe?g|png|webp|gif|avif|bmp)$", urlsplit(target).path, re.I):
            add(target, node, "linked_image")
        else:
            links.append(target)
    styles = [absolute(page_url, node["href"]) for node in soup.select('link[rel="stylesheet"][href]')]
    for variant in suppressed:
        images.pop(variant, None)
    return images, links, common, [url for url in styles if url], bool(soup.find("script"))


class BudgetExceeded(ValueError):
    pass


class Crawler:
    def __init__(self, settings, store, matcher, run_id, config):
        self.settings = settings
        self.store = store
        self.matcher = matcher
        self.run_id = run_id
        self.config = config
        self.origins = {origin(url) for url in config["seeds"]}
        self.robots = {}
        self.locks = {}
        self.next_request = {}
        self.metrics = Counter()
        self.errors = []
        self.client = None
        self.browser_context = None

    async def raw(self, url):
        validate_url(url, self.settings.allow_public_crawl)
        host = origin(url)
        async with self.locks.setdefault(host, asyncio.Lock()):
            if self.metrics["network_requests"] >= self.settings.crawl_request_budget:
                raise BudgetExceeded("Crawl request budget exhausted")
            await asyncio.sleep(max(0, self.next_request.get(host, 0) - time.monotonic()))
            delay = self.config["delay"]
            if self.settings.respect_robots and host in self.robots:
                delay = max(delay, self.robots[host].crawl_delay(USER_AGENT) or 0)
            self.next_request[host] = time.monotonic() + delay
            self.metrics["network_requests"] += 1
            async with self.client.stream("GET", url) as response:
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.settings.upload_limit_bytes:
                        raise ValueError("Resource exceeds upload_limit_bytes")
                headers = dict(response.headers)
                # httpx has decoded content; prevent a second decompression in the browser.
                for key in ("content-encoding", "transfer-encoding", "content-length"):
                    headers.pop(key, None)
                return httpx.Response(
                    response.status_code, headers=headers, content=bytes(content), request=response.request
                )

    async def allowed(self, url, page=False):
        validate_url(url, self.settings.allow_public_crawl)
        host = origin(url)
        if page and host not in self.origins:
            self.metrics["out_of_scope_pages"] += 1
            return False
        if not self.settings.respect_robots:
            return True
        async with self.locks.setdefault("robots:" + host, asyncio.Lock()):
            if host not in self.robots:
                response = await self.raw(host + "/robots.txt")
                parser = RobotFileParser(host + "/robots.txt")
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                elif response.status_code == 404:
                    parser.parse(["User-agent: *", "Allow: /"])
                else:
                    parser.parse(["User-agent: *", "Disallow: /"])
                self.robots[host] = parser
        permitted = self.robots[host].can_fetch(USER_AGENT, url)
        if not permitted:
            self.metrics["robots_denied"] += 1
        return permitted

    async def fetch(self, url, page=False, follow_redirects=True):
        for _ in range(6):
            if not await self.allowed(url, page):
                return None
            response = await self.raw(url)
            if response.is_redirect and follow_redirects:
                url = urljoin(url, response.headers["location"])
                continue
            if not response.is_redirect:
                response.raise_for_status()
            return response
        raise ValueError("Too many redirects")

    async def intercept(self, route):
        request = route.request
        if request.method != "GET":
            self.metrics["blocked_methods"] += 1
            await route.abort()
            return
        navigation = request.is_navigation_request()
        try:
            # Fulfill ourselves: every redirected hop/resource gets the same controls.
            response = await self.fetch(request.url, page=navigation, follow_redirects=False)
            if response is None:
                await route.abort()
            else:
                await route.fulfill(
                    status=response.status_code, headers=dict(response.headers), body=response.content
                )
        except (httpx.HTTPError, ValueError):
            await route.abort()

    async def render(self, url):
        tab = await self.browser_context.new_page()
        try:
            await tab.goto(url, wait_until="networkidle", timeout=15000)
            await tab.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await tab.wait_for_timeout(150)
            html = await tab.content()
            backgrounds = await tab.evaluate(r"""() => [...document.querySelectorAll('*')].flatMap(
                el => [...getComputedStyle(el).backgroundImage.matchAll(/url\(["']?([^"')]+)["']?\)/g)]
                .map(match => match[1]))""")
            self.metrics["rendered_pages"] += 1
            return html, backgrounds
        finally:
            await tab.close()

    def progress(self, status=None):
        with self.store.session.begin() as session:
            row = session.get(CrawlRun, self.run_id)
            row.metrics = dict(self.metrics)
            row.errors = list(self.errors)
            if status:
                row.status = status
            if status and status not in ("queued", "running"):
                row.finished_at = now()

    async def analyse_image(self, page_url, image_url, context, version, gallery, response=None):
        pending = []
        try:
            with self.store.session.begin() as session:
                scan = Scan(
                    run_id=self.run_id,
                    page_url=page_url,
                    image_url=image_url,
                    identity_version=version,
                    status="discovered",
                )
                session.add(scan)
                session.flush()
                self.metrics["discovered"] += 1
                try:
                    if response is None:
                        response = await self.fetch(image_url)
                    if response is None:
                        scan.status = "blocked"
                        return
                    self.metrics["images_fetched"] += 1
                    payload = response.content
                    scan.sha256 = hashlib.sha256(payload).hexdigest()
                    previous = session.scalar(
                        select(Scan.id)
                        .where(
                            Scan.id != scan.id,
                            Scan.sha256 == scan.sha256,
                            Scan.identity_version == version,
                            Scan.status.in_(("no_match", "cached_no_match")),
                        )
                        .limit(1)
                    )
                    if previous and not self.config.get("public_search"):
                        scan.status = "cached_no_match"
                        self.metrics["cached_no_match"] += 1
                    else:
                        result = self.matcher.analyse(
                            session,
                            scan,
                            payload,
                            context,
                            gallery,
                            dict(response.headers),
                            str(response.url),
                            pending,
                        )
                        self.metrics["analysed"] += 1
                        self.metrics["matches"] += result["matches"]
                        self.metrics["usable_faces"] += result["detected_faces"]
                        for reason in result["skip_reasons"]:
                            self.metrics["skip_" + reason] += 1
                except (httpx.HTTPError, ValueError) as error:
                    # Analysis failures must roll back partial cases and retained files.
                    if pending:
                        raise
                    scan.status = "error"
                    self.errors.append({"url": image_url, "error": str(error)})
                    self.metrics["image_errors"] += 1
        except BaseException:
            self.matcher.evidence.remove_files(pending)
            raise

    async def run(self):
        with self.store.session() as session:
            version = session.get(CrawlRun, self.run_id).identity_version
        browser = None
        try:
            gallery = self.matcher.gallery()
            self.progress("running")
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT}, timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                self.client = client
                async with async_playwright() as playwright:
                    if self.config["rendered"]:
                        browser = await playwright.chromium.launch()
                        self.browser_context = await browser.new_context(
                            user_agent=USER_AGENT, service_workers="block", accept_downloads=False
                        )
                        await self.browser_context.route("**/*", self.intercept)
                    try:
                        await self.traverse(version, gallery)
                    finally:
                        if browser:
                            await browser.close()
            status = "completed_with_errors" if self.errors else "completed"
            if self.metrics["page_budget_exhausted"] or self.metrics["request_budget_exhausted"]:
                status = "completed_with_limits"
            self.progress(status)
        except BaseException as error:
            self.errors.append({"error": type(error).__name__ + ": " + str(error)})
            self.progress("failed")
            if isinstance(error, asyncio.CancelledError):
                raise

    async def traverse(self, version, gallery):
        queue = deque((url, url, {}) for url in self.config["seeds"])
        visited = set()
        while queue and len(visited) < self.config["max_pages"]:
            url, parent, parent_context = queue.popleft()
            if url in visited or origin(url) not in self.origins:
                continue
            visited.add(url)
            try:
                response = await self.fetch(url, page=True)
                if response is None:
                    continue
                if response.headers.get("content-type", "").startswith("image/"):
                    await self.analyse_image(parent, url, parent_context, version, gallery, response)
                    continue
                if "text/html" not in response.headers.get("content-type", ""):
                    continue
                final_url = str(response.url)
                images, links, context, styles, has_scripts = extract(response.text, final_url)
                if has_scripts and self.browser_context:
                    html, computed = await self.render(final_url)
                    images, links, context, styles, _ = extract(html, final_url, computed)
                for stylesheet in styles:
                    sheet = await self.fetch(stylesheet)
                    if sheet is not None:
                        for value in re.findall(r"url\(\s*['\"]?([^)'\"]+)", sheet.text):
                            target = absolute(str(sheet.url), value.strip())
                            if target:
                                images.setdefault(target, context | {"extraction": "stylesheet_css"})
                self.metrics["pages"] += 1
                queue.extend((link, final_url, context) for link in links if link not in visited)
                for image_url, image_context in images.items():
                    await self.analyse_image(final_url, image_url, image_context, version, gallery)
            except BudgetExceeded as error:
                self.metrics["request_budget_exhausted"] += 1
                self.errors.append({"url": url, "error": str(error)})
                break
            except Exception as error:
                self.metrics["page_errors"] += 1
                self.errors.append({"url": url, "error": str(error)})
            finally:
                self.progress()
        if queue:
            self.metrics["page_budget_exhausted"] += 1
