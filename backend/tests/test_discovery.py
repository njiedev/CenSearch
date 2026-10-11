"""Handwritten SerpApi fixtures and real pinned Strands tool execution; no external I/O."""

import asyncio
import json
import httpx
import pytest
from pydantic import SecretStr
from censearch.agent.discovery import discover
from censearch.discovery import (
    Candidate,
    PublicSearchRequest,
    SearchSession,
    build_queries,
    canonical_url,
    dedupe,
    supplied_urls,
)
from test_recipient_tools import completion, simulated_model

# Handwritten from https://serpapi.com/organic-results and /images-results.
WEB = {
    "search_metadata": {"status": "Success"},
    "organic_results": [
        {"position": 1, "title": "Example profile", "link": "https://example.test/profile#bio"},
        {"position": 2, "link": "https://example.test/profile?utm_source=test"},
        {"position": 3, "link": "https://example.test/event"},
    ],
}
IMAGES = {
    "images_results": [
        {
            "position": 1,
            "link": "https://example.test/team",
            "original": "https://cdn.example.test/original.jpg",
            "thumbnail": "https://serpapi.test/small.jpg",
            "title": "Never use this image description",
        },
        {"position": 2, "original": "https://cdn.example.test/orphan.jpg"},
    ]
}


def session_run(settings, responder, operation):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as client:
            session = SearchSession(settings, client)
            result = await operation(session)
            return result, session

    return asyncio.run(run())


@pytest.mark.parametrize(
    "kind,payload,expected", [("web", WEB, 2), ("images", IMAGES, 1), ("web", {}, 0)]
)
def test_documented_shapes_get_text_only(settings, kind, payload, expected):
    settings.serpapi_api_key = SecretStr("synthetic-key")
    seen = []

    def response(request):
        seen.append(request)
        assert request.method == "GET" and request.content == b""
        assert request.url.params["q"] == '"Example Person"'
        assert request.url.params["engine"] == ("google_images" if kind == "images" else "google")
        return httpx.Response(200, json=payload)

    result, session = session_run(settings, response, lambda s: s.search('"Example Person"', kind))
    assert result["status"] == "completed" and len(result["candidates"]) == expected
    assert session.queries_run == 1 and len(seen) == 1
    serialized = json.dumps(session.calls)
    assert "synthetic-key" not in serialized
    assert "thumbnail" not in serialized and "description" not in serialized
    if kind == "images":
        candidate = result["candidates"][0]
        assert candidate["image_url"].endswith("/original.jpg")
        assert candidate["page_url"] == "https://example.test/team"
        assert candidate["provider"] == "serpapi" and candidate["retrieved_at"]


@pytest.mark.parametrize(
    "status,payload",
    [(200, {"error": "secret synthetic-key"}), (429, {}), (200, {"organic_results": None})],
)
def test_provider_errors_are_explicit_and_sanitized(settings, status, payload):
    settings.serpapi_api_key = SecretStr("synthetic-key")
    result, session = session_run(
        settings, lambda r: httpx.Response(status, json=payload), lambda s: s.search("Example")
    )
    assert result["status"] == "provider_error"
    assert session.queries_run == 1
    assert "synthetic-key" not in json.dumps(session.calls)


def test_missing_key_never_uses_transport(settings):
    settings.serpapi_api_key = SecretStr("")

    def forbidden(request):
        pytest.fail("A missing key must not send any request")

    result, session = session_run(settings, forbidden, lambda s: s.search("Example"))
    assert result["status"] == "not_configured" and "supplied public URLs" in result["message"]
    assert session.queries_run == 0


def test_shared_query_cap_duplicate_and_result_cap(settings):
    settings.serpapi_api_key = SecretStr("synthetic-key")
    settings.discovery_max_queries = 2
    settings.discovery_results_per_query = 1
    seen = []

    def response(request):
        seen.append(request)
        return httpx.Response(200, json=WEB)

    async def run(session):
        first = await session.search("Example")
        duplicate = await session.search("Example")
        await session.search("Other", "images")
        capped = await session.search("Third")
        return first, duplicate, capped

    (first, duplicate, capped), session = session_run(settings, response, run)
    assert len(first["candidates"]) == 1
    assert duplicate["status"] == "duplicate_query" and capped["status"] == "query_limit"
    assert session.queries_run == len(seen) == 2


def test_canonical_dedupe_keeps_image_page_associations():
    assert (
        canonical_url("HTTPS://Example.test:443/p?b=2&a=1&utm_campaign=x#part")
        == "https://example.test/p?a=1&b=2"
    )
    rows = supplied_urls(["https://example.test", "https://EXAMPLE.test/#x"])
    assert len(rows) == 1 and rows[0].discovery_method == "supplied_url"
    rows = dedupe(
        [
            Candidate(
                "https://example.test/a",
                "https://cdn.test/x.jpg",
                "q",
                "serpapi",
                1,
                "now",
                "name_search",
            ),
            Candidate(
                "https://example.test/b",
                "https://cdn.test/x.jpg",
                "q",
                "serpapi",
                2,
                "now",
                "name_search",
            ),
        ]
    )
    assert len(rows) == 2  # same pixels on two pages must retain both source associations


def test_rule_queries_and_no_email():
    queries = build_queries("Example Person", ["@example", "@example"], "Example conference")
    assert [q["query"] for q in queries] == [
        '"Example Person"',
        '"@example"',
        '"Example Person" Example conference',
    ]
    assert all(q["reason"] for q in queries)
    assert len(build_queries("Example", [str(n) for n in range(20)])) == 8
    with pytest.raises(ValueError, match="email"):
        build_queries("Example", ["owner@example.test"])
    with pytest.raises(ValueError):
        PublicSearchRequest(person_id="a", full_name="owner@example.test", mode="name_search")


def test_fallback_no_model_and_failed_model(settings):
    async def run(session):
        request = PublicSearchRequest(person_id="a", full_name="Example Person", mode="name_search")
        state = {}
        await discover(request, settings, session, state)
        assert (
            state["source"] == "rule_fallback" and state["model_status"] == "model_not_configured"
        )

        class Broken:
            pass

        failed = {}
        await discover(request, settings, session, failed, model=Broken())
        assert failed["source"] == "rule_fallback" and failed["model_status"] == "model_error"
        assert failed["queries"] and session.calls

    session_run(settings, lambda r: pytest.fail("No key, no network"), run)


def test_pinned_strands_calls_search_and_records_full_trace(settings):
    settings.serpapi_api_key = SecretStr("synthetic-key")
    bodies = []

    def model_response(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return completion(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "discover-1",
                            "type": "function",
                            "function": {
                                "name": "public_search",
                                "arguments": json.dumps(
                                    {
                                        "query": '"Example Person"',
                                        "kind": "images",
                                        "reason": "Look for public pages associated with this exact name.",
                                    }
                                ),
                            },
                        }
                    ],
                },
                "tool_calls",
            )
        return completion(
            {"role": "assistant", "content": "One source page discovered; identity is unverified."}
        )

    async def run(session):
        state = {}
        request = PublicSearchRequest(person_id="a", full_name="Example Person", mode="name_search")
        await discover(request, settings, session, state, model=simulated_model(model_response))
        return state

    state, session = session_run(settings, lambda r: httpx.Response(200, json=IMAGES), run)
    assert state["source"] == "strands_agent" and state["model_status"] == "completed"
    assert state["sdk_tool_calls"][0]["tool_use"]["name"] == "public_search"
    assert session.calls[0]["input"]["reason"] and session.queries_run == 1
    assert len(bodies) == 2 and bodies[1]["messages"][-1]["role"] == "tool"
    assert state["messages"] and "synthetic-key" not in json.dumps(state)
    assert "Never use this image description" not in json.dumps(bodies)


def test_agent_can_propose_combinations_but_not_emails_or_image_descriptions():
    from censearch.agent.discovery import query_allowed

    request = PublicSearchRequest(
        person_id="a",
        full_name="Example Person",
        handles=["@alias"],
        context="Example conference",
        mode="name_search",
    )
    assert query_allowed('"Example Person" "@alias" conference', request)
    assert query_allowed('conference "@alias"', request)
    assert not query_allowed('"Example Person" red shirt portrait', request)
    assert not query_allowed("operator@example.test", request)
    assert not query_allowed("conference", request)


def test_key_is_redacted_from_httpx_info_logs(settings, caplog):
    settings.serpapi_api_key = SecretStr("synthetic-secret-key")
    caplog.set_level("INFO", logger="httpx")
    session_run(
        settings, lambda request: httpx.Response(200, json={}), lambda s: s.search("Example")
    )
    assert "synthetic-secret-key" not in caplog.text
    assert "[redacted]" in caplog.text


def test_environment_configuration(tmp_path, monkeypatch):
    from censearch.config import Settings

    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("SERPAPI_API_KEY=synthetic-only\nDISCOVERY_MAX_QUERIES=3\n")
    config = Settings(_env_file=env)
    assert config.serpapi_api_key.get_secret_value() == "synthetic-only"
    assert config.discovery_max_queries == 3
    assert "synthetic-only" not in repr(config)
    with pytest.raises(ValueError):
        Settings(_env_file=None, discovery_max_queries=9)
