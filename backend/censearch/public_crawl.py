"""Depth-zero public runs, using the existing crawler GET path and local matcher."""

import asyncio
from collections import Counter
from copy import deepcopy
import time
from urllib.parse import urlsplit
import httpx
from sqlalchemy import select
from censearch.agent.discovery import discover
from censearch.agent.web import loopback, validate_read_url
from censearch.batches import case_summary
from censearch.crawl import BudgetExceeded, Crawler, USER_AGENT, extract, origin
from censearch.db import Case, CrawlRun, Scan, now, record
from censearch.discovery import (
    MATCH_LABEL,
    MOCK_LABEL,
    NAME_LABEL,
    REAL_LABEL,
    SUPPLIED_LABEL,
    SearchSession,
    build_queries,
    canonical_url,
    dedupe,
    supplied_urls,
)
from censearch.evidence import EvidenceStore
from censearch.matching import Matcher

COUNTS = (
    "queries_run",
    "pages_attempted",
    "pages_failed",
    "images_fetched",
    "usable_faces",
    "possible_matches",
)


def local_settings(settings):
    return settings.model_copy(update={"obj_endpoint": "", "obj_bucket": ""})


class PublicCrawler(Crawler):
    def __init__(self, settings, store, matcher, run_id, request, fixture=False):
        scoped = local_settings(settings).model_copy(
            update={
                "allow_public_crawl": request.allow_public_fetch and not fixture,
                "crawl_delay": max(0.5, settings.crawl_delay),
                "crawl_request_budget": min(150, settings.crawl_request_budget),
            }
        )
        # Evidence always stays local for this lane, independent of deployment storage settings.
        matcher = Matcher(
            store,
            matcher.face,
            EvidenceStore(scoped),
            matcher.calibration,
            matcher.calibration_sha256,
        )
        config = {
            "seeds": request.supplied_urls,
            "max_pages": 25,
            "max_images": 100,
            "depth": 0,
            "rendered": False,
            "delay": scoped.crawl_delay,
            "public_search": True,
            "request": request.model_dump(),
        }
        super().__init__(scoped, store, matcher, run_id, config)
        self.request = request
        self.fixture = fixture
        self.pages = []
        self.agent_state = {}
        self.search_session = None
        self.counts = Counter({key: 0 for key in COUNTS})
        self.local_counts = Counter({key: 0 for key in COUNTS})
        self.candidates = supplied_urls(request.supplied_urls)
        self.started = time.monotonic()
        self.deadline = self.started + scoped.discovery_timeout
        self.image_attempts = 0

    def progress(self, status=None):
        if self.search_session:
            self.counts["queries_run"] = self.search_session.queries_run
            self.candidates = dedupe(self.candidates + self.search_session.candidates)
            if self.agent_state.get("source") == "strands_agent" and self.search_session.calls:
                self.agent_state["queries"] = [call["input"] for call in self.search_session.calls]
        self.config["discovery"] = {
            "provider_status": self.search_session.status
            if self.search_session
            else "not_requested",
            "agent": deepcopy(self.agent_state),
            "tool_calls": deepcopy(self.search_session.calls) if self.search_session else [],
            "candidates": [row.record() for row in self.candidates],
            "pages": deepcopy(self.pages),
            "counts": dict(self.counts),
            "local_counts": dict(self.local_counts),
            "limits": {
                "queries": self.settings.discovery_max_queries,
                "pages": 25,
                "images": 100,
                "seconds": self.settings.discovery_timeout,
                "depth": 0,
                "per_origin_delay": self.config["delay"],
            },
        }
        with self.store.session.begin() as session:
            run = session.get(CrawlRun, self.run_id)
            run.config = deepcopy(self.config)
        super().progress(status)

    def check_deadline(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Public run time limit reached")

    async def raw(self, url):
        self.check_deadline()
        if self.fixture or not self.request.allow_public_fetch:
            from censearch.crawl import validate_url

            validate_url(url, allow_public=False)
        # Reject metadata/private network targets even when public fetching is enabled.
        await asyncio.to_thread(validate_read_url, url)
        try:
            return await super().raw(url)
        except BudgetExceeded:
            self.metrics["request_budget_exhausted"] = 1
            raise

    async def run(self):
        status = "completed"
        self.progress("running")
        try:
            async with asyncio.timeout(self.settings.discovery_timeout):
                if self.fixture and self.request.mode != "supplied_urls":
                    raise ValueError("Fixture runs must use supplied loopback URLs")
                async with httpx.AsyncClient(
                    headers={"User-Agent": USER_AGENT},
                    timeout=8,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    self.client = client
                    if self.request.mode != "supplied_urls":
                        self.search_session = SearchSession(self.settings, client, self.progress)
                        # Reserve time for fetching sources if the model/provider stalls.
                        try:
                            async with asyncio.timeout(
                                min(30, self.settings.discovery_timeout / 2)
                            ):
                                await discover(
                                    self.request,
                                    self.settings,
                                    self.search_session,
                                    self.agent_state,
                                )
                        except TimeoutError:
                            self.agent_state.update(
                                source="rule_fallback",
                                model_status="discovery_timeout",
                                queries=build_queries(
                                    self.request.full_name,
                                    self.request.handles,
                                    self.request.context,
                                    self.settings.discovery_max_queries,
                                ),
                            )
                            for query in build_queries(
                                self.request.full_name,
                                self.request.handles,
                                self.request.context,
                                self.settings.discovery_max_queries,
                            ):
                                result = await self.search_session.search(**query)
                                if result["status"] in (
                                    "not_configured",
                                    "provider_error",
                                    "query_limit",
                                ):
                                    break
                        self.candidates = dedupe(self.candidates + self.search_session.candidates)
                    else:
                        self.agent_state.update(
                            source="supplied_urls", model_status="not_requested", queries=[]
                        )
                    self.progress()
                    with self.store.session() as session:
                        version = session.get(CrawlRun, self.run_id).identity_version
                    gallery = self.matcher.gallery(self.request.person_id)
                    await self.traverse(version, gallery)
                    self.check_deadline()
            if self.errors or (
                self.search_session and self.search_session.status == "provider_error"
            ):
                status = "completed_with_errors"
            if any(
                self.metrics[key]
                for key in (
                    "page_budget_exhausted",
                    "image_budget_exhausted",
                    "request_budget_exhausted",
                )
            ):
                status = "completed_with_limits"
        except TimeoutError:
            self.metrics["time_budget_exhausted"] = 1
            status = "completed_with_limits"
        except asyncio.CancelledError:
            status = "interrupted"
            raise
        except Exception as error:
            self.errors.append({"error": type(error).__name__})
            status = "failed"
        finally:
            for page in self.pages:
                if page["status"] == "fetching":
                    page.update(status="error", error="Run time limit or interruption")
                    bucket = self.local_counts if page["simulated"] else self.counts
                    bucket["pages_failed"] += 1
            self.progress(status)

    async def traverse(self, version, gallery):
        grouped = {}
        for candidate in self.candidates:
            grouped.setdefault(canonical_url(candidate.page_url), []).append(candidate)
        self.origins = {origin(url) for url in grouped}
        for index, (url, candidates) in enumerate(grouped.items()):
            if self.metrics["request_budget_exhausted"]:
                break
            if index >= 25:
                self.metrics["page_budget_exhausted"] = 1
                break
            if self.image_attempts >= 100:
                self.metrics["image_budget_exhausted"] = 1
                break
            self.check_deadline()
            simulated = loopback(urlsplit(url).hostname)
            bucket = self.local_counts if simulated else self.counts
            page = {
                "page_url": url,
                "status": "fetching",
                "simulated": simulated,
                "attempted_at": now(),
                "fetched_at": None,
                "image_errors": [],
            }
            self.pages.append(page)
            bucket["pages_attempted"] += 1
            self.progress()
            try:
                response = await self.fetch(url, page=True)
                if response is None:
                    raise ValueError("Page blocked by crawl policy or redirect scope")
                page.update(fetched_at=now(), final_url=str(response.url))
                if "text/html" not in response.headers.get("content-type", ""):
                    raise ValueError("Supply an HTML source page, not a bare image or document")
                images, _, _, _, _ = extract(response.text, str(response.url), prefer_original=True)
                images = {canonical_url(image): context for image, context in images.items()}
                page["status"] = "fetched"
                methods = list(
                    dict.fromkeys(candidate.discovery_method for candidate in candidates)
                )
                discovery = {
                    "run_id": self.run_id,
                    "candidates": [row.record() for row in candidates],
                    "methods": methods,
                    "simulated": simulated,
                    "draft_only": not simulated,
                    "label": NAME_LABEL if "name_search" in methods else SUPPLIED_LABEL,
                    "source_label": MOCK_LABEL if simulated else REAL_LABEL,
                    "match_label": MATCH_LABEL,
                    "page_fetched_at": page["fetched_at"],
                }
                # Provider originals are useful leads, never proof of appearance. Only fetch images
                # observed on this page; rank observed provider originals first.
                preferred = {candidate.image_url for candidate in candidates if candidate.image_url}
                page["unverified_image_leads"] = sorted(preferred - images.keys())
                for image_url in sorted(images, key=lambda image: image not in preferred):
                    self.check_deadline()
                    if self.image_attempts >= 100:
                        self.metrics["image_budget_exhausted"] = 1
                        break
                    self.image_attempts += 1
                    before = self.metrics.copy()
                    before_errors = len(self.errors)
                    context = images[image_url] | {"discovery": discovery}
                    try:
                        await self.analyse_image(
                            str(response.url), image_url, context, version, gallery
                        )
                    except (asyncio.CancelledError, TimeoutError):
                        page["image_errors"].append(
                            {"url": image_url, "error": "Interrupted by run limit"}
                        )
                        raise
                    for key in ("images_fetched", "usable_faces"):
                        bucket[key] += self.metrics[key] - before[key]
                    bucket["possible_matches"] += self.metrics["matches"] - before["matches"]
                    page["image_errors"].extend(self.errors[before_errors:])
                    self.progress()
                    if self.metrics["request_budget_exhausted"]:
                        break
            except TimeoutError:
                raise
            except BudgetExceeded:
                self.metrics["request_budget_exhausted"] = 1
                page.update(status="error", error="Request budget exhausted")
                bucket["pages_failed"] += 1
                break
            except Exception as error:
                page.update(status="error", error=type(error).__name__ + ": " + str(error))
                bucket["pages_failed"] += 1
                self.errors.append({"url": url, "error": page["error"]})
            finally:
                self.progress()


def public_view(store, run_id):
    with store.session() as session:
        run = session.get(CrawlRun, run_id)
        if run is None or not run.config.get("public_search"):
            raise LookupError("Public search run not found")
        cases = session.scalars(
            select(Case).join(Scan).where(Scan.run_id == run_id).order_by(Case.id)
        )
        return (
            record(run)
            | run.config.get("discovery", {})
            | {
                "results": [case_summary(session, case) for case in cases],
            }
        )
