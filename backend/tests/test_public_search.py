"""Local HTTP E2E, run isolation, privacy and limit tests. No real identity searches."""

import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
import json
from threading import Thread
import time
import httpx
from PIL import Image
from pydantic import SecretStr
import pytest
from sqlalchemy import select
from censearch.crawl import extract
from censearch.db import Case, CrawlRun, Person
from censearch.discovery import Candidate, PublicSearchRequest
from censearch.public_crawl import PublicCrawler, public_view
from mockweb.server import Handler
from test_recipient_tools import completion, simulated_model
from test_round2 import workflow_case as workflow_case


@pytest.fixture
def mock_site(tmp_path, photo_folder):
    root = tmp_path / "mock"
    root.mkdir()
    (root / "original.jpg").write_bytes(
        sorted((photo_folder / "originals").glob("*.jpg"))[0].read_bytes()
    )
    (root / "reference.jpg").write_bytes(
        sorted((photo_folder / "reference").glob("*.jpg"))[0].read_bytes()
    )
    Image.new("RGB", (300, 300), "white").save(root / "negative.png")
    (root / "copy.html").write_text("""<title>Local original</title>
      <a href="/original.jpg"><img src="/missing-thumb.jpg" srcset="/small.jpg 100w, /original.jpg 1200w"></a>
      <a href="/not-followed.html">Do not follow depth-one pages</a>""")
    (root / "face.html").write_text('<title>Local portrait</title><img src="/reference.jpg">')
    (root / "negative.html").write_text('<title>No face</title><img src="/negative.png">')
    (root / "escape.html").write_text('<img src="https://example.test/fixture.jpg">')
    (root / "empty.html").write_text("<title>Empty</title>")
    requests = []

    class RecordingHandler(Handler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append((self.command, self.path, time.monotonic()))
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(RecordingHandler, directory=str(root)))
    server.site, server.token = "friendlink", "local-mock-admin"
    server.modes, server.originals = {}, {}
    server.removed, server.ignored = set(), set()
    server.receipts, server.delisted = [], []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def wait_run(client, run_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(f"/api/public-searches/{run_id}")
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(0.02)
    pytest.fail("Public run failed to finish within test deadline")


def test_supplied_urls_real_local_matcher_positive_negative_and_failed_page(
    client, enrolled, mock_site
):
    base, requests = mock_site
    response = client.post(
        "/api/public-searches",
        json={
            "person_id": enrolled["id"],
            "mode": "supplied_urls",
            "supplied_urls": [
                base + path
                for path in (
                    "/copy.html",
                    "/copy.html#repeat",
                    "/face.html",
                    "/negative.html",
                    "/missing.html",
                )
            ],
        },
    )
    assert response.status_code == 202, response.text
    run = wait_run(client, response.json()["id"])
    assert run["status"] == "completed_with_errors", run
    counts = run["local_counts"]
    assert counts["pages_attempted"] == 4 and counts["pages_failed"] == 1
    assert counts["images_fetched"] == 3 and counts["usable_faces"] >= 2
    assert counts["possible_matches"] == 2 and len(run["results"]) == 2
    assert all(value == 0 for value in run["counts"].values())
    copy = next(row for row in run["results"] if row["page_url"].endswith("/copy.html"))
    face = next(row for row in run["results"] if row["page_url"].endswith("/face.html"))
    assert copy["copy_relation"] == "exact" and copy["photo_relation"] == "same_photo"
    assert face["face_band"] == "match" and face["face_score"] > 0.99
    assert copy["evidence"]["image"]["storage"] == "local"
    discovery = copy["evidence"]["context"]["discovery"]
    assert discovery["label"] == "Check supplied public URLs"
    assert discovery["simulated"] is True and discovery["draft_only"] is False
    assert discovery["page_fetched_at"] and discovery["candidates"][0]["provider"] == "owner"
    assert copy["possible_action"]["route"] == "copyright_notice"
    assert client.get(f"/api/cases/{copy['id']}/workflow").status_code == 200
    scans = client.get(f"/api/scans?run_id={run['id']}").json()
    negative = next(scan for scan in scans if scan["page_url"].endswith("/negative.html"))
    assert negative["status"] == "no_match"
    with client.app.state.store.session() as session:
        assert session.scalar(select(Case).where(Case.scan_id == negative["id"])) is None
    assert all(request[0] == "GET" for request in requests)
    paths = [row[1] for row in requests]
    assert (
        "/small.jpg" not in paths
        and "/missing-thumb.jpg" not in paths
        and "/not-followed.html" not in paths
    )
    assert paths.count("/copy.html") == 1 and paths.count("/missing.html") == 1
    assert all(later[2] - earlier[2] >= 0.45 for earlier, later in zip(requests, requests[1:]))
    assert client.app.state.settings.allow_public_crawl is False
    assert client.get("/api/public-searches").json()[0]["id"] == run["id"]
    assert client.get("/api/public-searches/999999").status_code == 404


def test_fixture_rejects_search_public_pages_and_external_images(client, enrolled, mock_site):
    base, _ = mock_site
    for request in (
        {"mode": "name_search", "full_name": "Example Person", "allow_public_fetch": True},
        {
            "mode": "supplied_urls",
            "supplied_urls": ["https://example.test/"],
            "allow_public_fetch": True,
        },
    ):
        response = client.post(
            "/api/public-searches", json={"person_id": enrolled["id"], **request}
        )
        assert response.status_code == 422 and "fixtures" in response.text
    response = client.post(
        "/api/public-searches",
        json={"person_id": enrolled["id"], "supplied_urls": [base + "/escape.html"]},
    )
    run = wait_run(client, response.json()["id"])
    assert run["local_counts"]["images_fetched"] == 0
    assert run["results"] == [] and run["pages"][0]["image_errors"]


def test_explicit_public_opt_in_and_missing_key_api(client):
    # Fictional text-only enrollee: no face data, no comparisons or public requests.
    with client.app.state.store.session.begin() as session:
        session.add(
            Person(id="text-only", name="Example Person", consent="test", development_fixture=False)
        )
    request = {"person_id": "text-only", "full_name": "Example Person", "mode": "name_search"}
    assert client.post("/api/public-searches", json=request).status_code == 422
    response = client.post("/api/public-searches", json=request | {"allow_public_fetch": True})
    assert response.status_code == 202
    run = wait_run(client, response.json()["id"])
    assert run["provider_status"] == "not_configured"
    assert run["counts"]["queries_run"] == 0 and run["results"] == []
    assert run["agent"]["source"] == "rule_fallback"
    assert "supplied public URLs" in run["tool_calls"][0]["result"]["message"]


def crawler_for(client, enrolled, settings, urls):
    request = PublicSearchRequest(person_id=enrolled["id"], supplied_urls=urls)
    store = client.app.state.store
    with store.session.begin() as session:
        row = CrawlRun(config={"public_search": True}, identity_version="test-target-person")
        session.add(row)
        session.flush()
        run_id = row.id
    return PublicCrawler(settings, store, client.app.state.matcher, run_id, request, fixture=True)


def test_srcset_picture_and_linked_original_are_one_appearance():
    html = """<picture><source srcset="/s.jpg 200w, /l.jpg 1600w"><img src="/thumb.jpg"></picture>
      <meta property="og:image" content="/thumb.jpg"><a href="/original.jpg"><img src="/t.jpg"></a>"""
    images, _, _, _, _ = extract(html, "http://localhost/", prefer_original=True)
    assert set(images) == {"http://localhost/l.jpg", "http://localhost/original.jpg"}
    legacy, _, _, _, _ = extract(html, "http://localhost/")
    assert "http://localhost/thumb.jpg" in legacy


def test_page_and_image_caps(client, enrolled, settings, monkeypatch):
    crawler = crawler_for(client, enrolled, settings, ["http://localhost/start"])
    crawler.candidates = [
        Candidate(f"http://localhost/{n}", None, "", "owner", n, "now", "supplied_url")
        for n in range(30)
    ]
    seen = []

    async def fetch(url, **kwargs):
        seen.append(url)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<title>Empty</title>",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(crawler, "fetch", fetch)
    asyncio.run(crawler.run())
    assert len(seen) == 25 and crawler.metrics["page_budget_exhausted"] == 1
    assert public_view(crawler.store, crawler.run_id)["status"] == "completed_with_limits"
    crawler = crawler_for(client, enrolled, settings, ["http://localhost/many"])

    async def many(url, **kwargs):
        html = "".join(f'<img src="/{n}.jpg">' for n in range(120))
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text=html, request=httpx.Request("GET", url)
        )

    attempted = []

    async def analyse(page_url, image_url, *args):
        attempted.append(image_url)

    monkeypatch.setattr(crawler, "fetch", many)
    monkeypatch.setattr(crawler, "analyse_image", analyse)
    asyncio.run(crawler.run())
    assert len(attempted) == crawler.image_attempts == 100
    assert crawler.metrics["image_budget_exhausted"] == 1


def test_timeout_returns_completed_page_and_interrupted_page(
    client, enrolled, settings, monkeypatch
):
    settings.discovery_timeout = 0.5
    crawler = crawler_for(
        client, enrolled, settings, ["http://localhost/first", "http://localhost/slow"]
    )

    async def fetch(url, **kwargs):
        if url.endswith("/slow"):
            await asyncio.sleep(2)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<title>Empty</title>",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(crawler, "fetch", fetch)
    monkeypatch.setattr(crawler.matcher, "gallery", lambda person_id: [])
    started = time.monotonic()
    asyncio.run(crawler.run())
    assert time.monotonic() - started < 1.5
    run = public_view(crawler.store, crawler.run_id)
    assert run["status"] == "completed_with_limits"
    assert [page["status"] for page in run["pages"]] == ["fetched", "error"]
    assert run["local_counts"]["pages_failed"] == 1


def test_fixture_redirect_guard_and_local_storage(client, enrolled, settings):
    settings.obj_bucket, settings.obj_endpoint = "do-not-upload", "https://example.test"
    crawler = crawler_for(client, enrolled, settings, ["http://localhost/redirect"])
    seen = []

    async def run():
        def respond(request):
            seen.append(str(request.url))
            return httpx.Response(302, headers={"location": "https://example.test/fixture.jpg"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            crawler.client = client
            with pytest.raises(ValueError, match="Public crawling"):
                await crawler.fetch("http://localhost/redirect")

    asyncio.run(run())
    assert seen == ["http://localhost/redirect"]
    assert crawler.matcher.evidence.client is None


def test_real_source_send_refused_even_with_loopback_recipient_and_external_flag(workflow_case, monkeypatch):
    from test_round3 import await_batch, isolated_workflow, payload

    client, case_id = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    client.app.state.settings.allow_external_delivery = True
    with client.app.state.store.session.begin() as session:
        case = session.get(Case, case_id)
        case.evidence = case.evidence | {"context": {"discovery": {"draft_only": True}}}
    response = client.post("/api/batches", json=payload([case_id]) | {"mode": "prepare"})
    batch = await_batch(client, response.json()["id"])
    assert batch["items"][0]["status"] == "drafted_not_sent"
    notice = client.get(f"/api/cases/{case_id}/workflow").json()["notices"][0]
    assert client.post(f"/api/cases/{case_id}/approve", json={
        "notice_id": notice["id"], "sha256": notice["sha256"], "approved_by": "Test operator",
    }).status_code == 200
    with pytest.raises(ValueError, match="Real source · draft only"):
        asyncio.run(client.app.state.workflow.send(case_id))
    assert not sent


def test_strands_trace_persisted_in_public_run(client, settings, monkeypatch):
    import censearch.agent.discovery as agent_module

    with client.app.state.store.session.begin() as session:
        session.add(
            Person(id="text-only", name="Example Person", consent="test", development_fixture=False)
        )
    calls = []

    def responder(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return completion(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "search-call",
                            "type": "function",
                            "function": {
                                "name": "public_search",
                                "arguments": json.dumps(
                                    {
                                        "query": '"Example Person"',
                                        "reason": "Find the exact supplied name.",
                                    }
                                ),
                            },
                        }
                    ],
                },
                "tool_calls",
            )
        return completion(
            {"role": "assistant", "content": "Search is unconfigured; use supplied URLs."}
        )

    monkeypatch.setattr(agent_module, "build_model", lambda settings: simulated_model(responder))
    settings.openai_api_key = SecretStr("simulated-only")
    response = client.post(
        "/api/public-searches",
        json={
            "person_id": "text-only",
            "full_name": "Example Person",
            "mode": "name_search",
            "allow_public_fetch": True,
        },
    )
    run = wait_run(client, response.json()["id"])
    assert run["agent"]["source"] == "strands_agent"
    assert run["agent"]["sdk_tool_calls"][0]["tool_use"]["name"] == "public_search"
    assert run["tool_calls"][0]["result"]["status"] == "not_configured"
    assert run["agent"]["messages"] and len(calls) == 2
    with client.app.state.store.session() as session:
        stored = session.get(CrawlRun, run["id"]).config["discovery"]
        assert stored["agent"]["sdk_tool_calls"] == run["agent"]["sdk_tool_calls"]


def test_request_budget_stops_without_retry_loop(client, enrolled, settings, mock_site):
    base, requests = mock_site
    settings.crawl_request_budget = 1
    crawler = crawler_for(client, enrolled, settings, [base + "/copy.html", base + "/face.html"])
    asyncio.run(crawler.run())
    run = public_view(crawler.store, crawler.run_id)
    assert run["status"] == "completed_with_limits"
    assert len(requests) == 1 and requests[0][1] == "/copy.html"
    assert crawler.image_attempts == 1 and run["pages"][0]["image_errors"]
    assert run["metrics"]["request_budget_exhausted"] == 1


def test_public_private_network_guard_before_http(client, enrolled, settings, monkeypatch):
    from censearch.agent import web

    crawler = crawler_for(client, enrolled, settings, ["http://localhost/test"])
    crawler.fixture = False
    crawler.request.allow_public_fetch = True
    crawler.settings.allow_public_crawl = True
    monkeypatch.setattr(
        web.socket, "getaddrinfo", lambda *args: [(2, 1, 6, "", ("169.254.169.254", 80))]
    )
    with pytest.raises(ValueError, match="Private-network"):
        asyncio.run(crawler.raw("http://example.test/meta"))
    assert crawler.metrics["network_requests"] == 0


def test_real_source_batch_stops_after_named_recipient_and_fixed_draft(workflow_case, monkeypatch):
    from test_round3 import await_batch, isolated_workflow, payload

    client, case_id = workflow_case
    with client.app.state.store.session.begin() as session:
        case = session.get(Case, case_id)
        case.evidence = case.evidence | {"context": {"discovery": {"draft_only": True}}}
    sent = isolated_workflow(client, monkeypatch)
    client.app.state.settings.allow_external_delivery = True
    response = client.post("/api/batches", json=payload([case_id]))
    result = await_batch(client, response.json()["id"])
    item = result["items"][0]
    assert item["status"] == "drafted_not_sent"
    assert item["recipient"]["id"] and item["notice_id"]
    assert "Real source · draft only" in item["reason"] and sent == []
    view = client.get(f"/api/cases/{case_id}/workflow").json()
    assert view["notices"][0]["payload"]["body"] and view["deliveries"] == []
