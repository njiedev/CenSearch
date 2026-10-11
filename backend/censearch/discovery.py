"""Text-only candidate discovery. No image payloads or provider response blobs are retained."""

import asyncio
from dataclasses import asdict, dataclass
import json
import logging
import re
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator
from censearch.crawl import validate_url
from censearch.db import now

NAME_LABEL = "Public web · name/handle search"
SUPPLIED_LABEL = "Check supplied public URLs"
MATCH_LABEL = "Possible match · review needed"
REAL_LABEL = "Real source"
MOCK_LABEL = "Simulated delivery · loopback mock administrator"
FACE_LABEL = "FaceCheck · scores 88+"
MISSING_KEY = "Search provider not configured. Set SERPAPI_API_KEY in backend/.env, or use Check supplied public URLs."
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


class RedactSearchKey(logging.Filter):
    """httpx INFO request logs otherwise include GET query credentials."""

    def filter(self, record):
        message = record.getMessage()
        if "api_key=" in message:
            record.msg = re.sub(r"(api_key=)[^&\s]+", r"\1[redacted]", message)
            record.args = ()
        return True


logging.getLogger("httpx").addFilter(RedactSearchKey())


def text_input(value):
    value = " ".join(value.split())
    if EMAIL.search(value) or any(word in value.lower() for word in ("data:", "base64", "://")):
        raise ValueError(
            "Use names, handles and public context only; no email addresses, URLs or image data"
        )
    return value


def canonical_url(url):
    validate_url(url, allow_public=True)
    parsed = urlsplit(url)
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    if port and (parsed.scheme.lower(), port) not in (("http", 80), ("https", 443)):
        host += f":{port}"
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in ("fbclid", "gclid")
    ]
    return urlunsplit(
        (parsed.scheme.lower(), host, parsed.path or "/", urlencode(sorted(query)), "")
    )


@dataclass(frozen=True)
class Candidate:
    page_url: str
    image_url: str | None
    query: str
    provider: str
    rank: int
    retrieved_at: str
    discovery_method: Literal["name_search", "supplied_url", "face_search"]
    provider_score: float | None = None

    def record(self):
        return asdict(self)


def dedupe(candidates):
    """Keep distinct image/page associations, fetching each canonical page only once."""
    result = {}
    for candidate in candidates:
        page = canonical_url(candidate.page_url)
        image = canonical_url(candidate.image_url) if candidate.image_url else None
        result.setdefault(
            (page, image),
            Candidate(
                page,
                image,
                candidate.query,
                candidate.provider,
                candidate.rank,
                candidate.retrieved_at,
                candidate.discovery_method,
                candidate.provider_score,
            ),
        )
    return list(result.values())


def supplied_urls(urls):
    return dedupe(
        [
            Candidate(url, None, "", "owner", rank, now(), "supplied_url")
            for rank, url in enumerate(urls, 1)
        ]
    )


class PublicSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: str = Field(min_length=1, max_length=100)
    full_name: str = Field(default="", max_length=200)
    handles: list[str] = Field(default_factory=list, max_length=10)
    context: str = Field(default="", max_length=300)
    supplied_urls: list[str] = Field(default_factory=list, max_length=25)
    mode: Literal["name_search", "supplied_urls", "combined", "face_search"] = "supplied_urls"
    allow_public_fetch: bool = False
    facecheck_consent: bool = False

    @model_validator(mode="after")
    def validate_inputs(self):
        self.full_name = text_input(self.full_name)
        self.context = text_input(self.context)
        self.handles = [text_input(handle) for handle in self.handles if handle.strip()]
        if any(len(handle) > 100 for handle in self.handles):
            raise ValueError("Handles must be at most 100 characters")
        if self.mode == "face_search":
            if not self.facecheck_consent:
                raise ValueError("Consent to sending your enrolled photo to FaceCheck is required")
            if self.full_name or self.handles or self.context or self.supplied_urls:
                raise ValueError("Face search cannot include name queries or supplied URLs")
        if self.mode in ("name_search", "combined") and not (self.full_name or self.handles):
            raise ValueError("Provide a full name or handle for name search")
        if self.mode == "supplied_urls" and not self.supplied_urls:
            raise ValueError("Provide at least one page URL")
        if self.mode == "name_search" and self.supplied_urls:
            raise ValueError("Choose combined mode to include supplied URLs")
        self.supplied_urls = [canonical_url(url.strip()) for url in self.supplied_urls]
        return self


def build_queries(full_name, handles=(), context="", limit=8):
    name, context = text_input(full_name), text_input(context)
    proposals = []
    if name:
        proposals.append(
            (f'"{name}"', "Search the exact supplied name to reduce unrelated results.")
        )
    for handle in handles:
        handle = text_input(handle)
        if handle:
            proposals.append((f'"{handle}"', "Search this supplied handle for public profiles."))
    if name and context:
        proposals.append(
            (f'"{name}" {context}', "Use the supplied context to distinguish namesakes.")
        )
    unique = dict(proposals)
    return [
        {"query": query, "reason": reason, "kind": "web"}
        for query, reason in list(unique.items())[:limit]
    ]


class SearchSession:
    """One shared, sequential allowance for the agent and fallback; no pagination or retries."""

    def __init__(self, settings, client, progress=None, check_cancel=None):
        self.check_cancel = check_cancel or (lambda: None)
        self.settings = settings
        self.client = client
        self.progress = progress or (lambda: None)
        self.queries_run = 0
        self.calls = []
        self.candidates = []
        self.seen = set()
        self.status = "ready" if settings.serpapi_api_key.get_secret_value() else "not_configured"

    async def search(self, query, kind="web", reason=""):
        self.check_cancel()
        query = text_input(query)
        if not query or len(query) > 600 or kind not in ("web", "images"):
            raise ValueError("A bounded text query and web/images kind are required")
        call = {"tool": "public_search", "input": {"query": query, "kind": kind, "reason": reason}}
        self.calls.append(call)
        result = {"status": "completed", "candidates": []}
        call["result"] = result
        try:
            if not self.settings.serpapi_api_key.get_secret_value():
                result.update(status="not_configured", message=MISSING_KEY)
            elif (query, kind) in self.seen:
                result.update(
                    status="duplicate_query", message="This query already ran in this run."
                )
            elif self.queries_run >= self.settings.discovery_max_queries:
                result.update(status="query_limit", message="Run query cap reached.")
            else:
                self.seen.add((query, kind))
                self.queries_run += 1
                params = {
                    "engine": "google_images" if kind == "images" else "google",
                    "q": query,
                    "api_key": self.settings.serpapi_api_key.get_secret_value(),
                }
                # Do not log request URLs or exceptions: GET URLs contain the secret key.
                async with self.client.stream(
                    "GET", "https://serpapi.com/search.json", params=params, timeout=8
                ) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > 2_000_000:
                            raise ValueError("Provider response too large")
                data = json.loads(payload)
                if not isinstance(data, dict) or data.get("error"):
                    result.update(
                        status="provider_error",
                        message="Search provider returned an error; check quota or configuration.",
                    )
                else:
                    records = data.get(
                        "images_results" if kind == "images" else "organic_results", []
                    )
                    candidates = []
                    for index, row in enumerate(
                        records[: self.settings.discovery_results_per_query], 1
                    ):
                        if not isinstance(row, dict) or not row.get("link"):
                            continue
                        try:
                            candidates.append(
                                Candidate(
                                    canonical_url(row["link"]),
                                    canonical_url(row["original"])
                                    if kind == "images" and row.get("original")
                                    else None,
                                    query,
                                    "serpapi",
                                    row["position"]
                                    if isinstance(row.get("position"), int)
                                    else index,
                                    now(),
                                    "name_search",
                                )
                            )
                        except (ValueError, TypeError):
                            continue
                    candidates = dedupe(candidates)
                    self.candidates = dedupe(self.candidates + candidates)
                    result["candidates"] = [row.record() for row in candidates]
            if result["status"] in ("not_configured", "provider_error", "query_limit"):
                self.status = result["status"]
            elif self.status == "ready":
                self.status = "completed"
            return result
        except asyncio.CancelledError:
            result.update(status="interrupted", message="Search interrupted by the run time limit.")
            raise
        except Exception as error:
            self.status = "provider_error"
            result.update(
                status="provider_error",
                error=type(error).__name__,
                message="Search request failed; no retry was attempted.",
            )
            return result
        finally:
            self.progress()


def provenance(case):
    return case.evidence.get("context", {}).get("discovery", {})


def draft_only(case):
    return bool(provenance(case).get("draft_only"))
