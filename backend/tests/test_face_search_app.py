"""App scan integration with a synthetic image and intercepted provider/page requests."""

import json
import base64
import time
from io import BytesIO

import httpx
from PIL import Image
from pydantic import SecretStr
import pytest

from censearch.db import CrawlRun, Person, Reference
from censearch.facecheck import FaceCheckClient
from censearch.public_crawl import PublicCrawler


@pytest.fixture
def identity(client, settings):
    settings.facecheck_api_token = SecretStr("local-test-token")
    image = BytesIO()
    Image.new("RGB", (32, 32), "blue").save(image, format="JPEG")
    path = settings.data_dir / "synthetic.jpg"
    path.write_bytes(image.getvalue())
    with client.app.state.store.session.begin() as session:
        person = Person(
            id="synthetic", name="Synthetic test", consent="Test", development_fixture=False
        )
        session.add(person)
        session.flush()
        session.add(
            Reference(
                person_id=person.id,
                filename="synthetic.jpg",
                path="synthetic.jpg",
                sha256="test",
                quality={},
                embedding=b"\0" * 512,
            )
        )
    return person.id


def start(client, identity, **changes):
    return client.post(
        "/api/public-searches",
        json={
            "person_id": identity,
            "mode": "face_search",
            "facecheck_consent": True,
            "allow_public_fetch": True,
            **changes,
        },
    )


def wait(client, run_id):
    for _ in range(200):
        result = client.get(f"/api/public-searches/{run_id}").json()
        if result["status"] not in ("running", "queued"):
            return result
        time.sleep(0.01)
    pytest.fail("Face scan did not finish")


def intercept(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        "censearch.face_discovery.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    pages = []

    async def raw(self, url):
        pages.append(url)
        return httpx.Response(
            200,
            text="<title>Public page</title>",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(PublicCrawler, "raw", raw)
    return pages


def test_face_scan_filters_before_fetch_and_preserves_scores(
    client, settings, identity, monkeypatch
):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.headers["authorization"] == "local-test-token"
        if request.url.path == "/api/info":
            return httpx.Response(200, json={"remaining_credits": 47, "is_online": True})
        if request.url.path == "/api/upload_pic":
            assert b'filename="photo.jpg"' in request.content
            return httpx.Response(200, json={"id_search": "app-search"})
        assert json.loads(request.content)["demo"] is False
        return httpx.Response(
            200,
            json={
                "output": {
                    "demo": False,
                    "items": [
                        {
                            "url": f"https://example.com/{score}",
                            "score": score,
                            "base64": "never-save-this",
                        }
                        for score in (89, 90, 91, 99)
                    ],
                }
            },
        )

    pages = intercept(monkeypatch, handler)
    response = start(client, identity)
    assert response.status_code == 202, response.text
    run = wait(client, response.json()["id"])
    assert run["status"] == "completed", run
    assert [item["score"] for item in run["facecheck"]["items"]] == [91, 99]
    assert set(pages) == {"https://example.com/91", "https://example.com/99"}
    assert [row["provider_score"] for row in run["candidates"]] == [91, 99]
    assert all(row["discovery_method"] == "face_search" for row in run["candidates"])
    assert len(run["results"]) == 2
    for row in run["results"]:
        assert row["match_type"] == "facecheck" and row["band"] == "possible"
        assert row["face_score"] is None and row["face_band"] == "not_checked"
        assert row["possible_action"]["route"] == "hold_for_review"
        assert row["thumbnail_available"] is False
        assert client.get(row["matched_image_url"]).status_code == 404
    assert run["agent"]["source"] == "facecheck"
    assert calls == ["/api/info", "/api/upload_pic", "/api/search"]
    assert "never-save-this" not in json.dumps(run) and "local-test-token" not in json.dumps(run)
    history = client.get(f"/api/people/{identity}/scans").json()
    assert history[0]["label"] == "FaceCheck · score above 90"
    assert client.post(f"/api/public-searches/{run['id']}/resume").status_code == 409
    summary = client.get(f"/api/people/{identity}/face-search-cache").json()
    assert summary["available"] and summary["count"] == 2
    assert summary["run_id"] == run["id"] and summary["saved_at"]
    # A cached scan is readable offline, with no provider key or loaded face models.
    settings.facecheck_api_token = SecretStr("")
    client.app.state.face = None
    saved = start(
        client,
        identity,
        facecheck_source="cache",
        facecheck_consent=False,
        allow_public_fetch=False,
    )
    assert saved.status_code == 202, saved.text
    assert saved.json()["id"] == run["id"] and saved.json()["cache_hit"] is True
    assert calls == ["/api/info", "/api/upload_pic", "/api/search"]
    assert len(pages) == 2
    assert [row["id"] for row in saved.json()["results"]] == [row["id"] for row in run["results"]]


def test_provider_thumbnails_reviewable_when_page_blocked(client, settings, identity, monkeypatch):
    from test_round3 import await_batch, payload
    from censearch.agent.route import match_evidence

    images = []
    for color in ("red", "blue"):
        stream = BytesIO()
        Image.new("RGB", (32, 32), color).save(stream, format="JPEG")
        images.append(base64.b64encode(stream.getvalue()).decode())

    def handler(request):
        if request.url.path == "/api/info":
            return httpx.Response(200, json={"remaining_credits": 47, "is_online": True})
        if request.url.path == "/api/upload_pic":
            return httpx.Response(200, json={"id_search": "thumbnails"})
        return httpx.Response(200, json={"output": {"demo": False, "items": [
            {"url": "https://example.com/gallery", "score": score, "base64": image}
            for score, image in [(99, images[0]), (95, "data:image/jpeg;base64," + images[1]),
                                 (99, images[0]), (90, images[0])]
        ]}})

    intercept(monkeypatch, handler)

    async def blocked(self, url):
        return httpx.Response(403, request=httpx.Request("GET", url))

    monkeypatch.setattr(PublicCrawler, "raw", blocked)
    run = wait(client, start(client, identity).json()["id"])
    assert len(run["results"]) == 2  # Distinct images survive page-level crawl deduplication.
    assert len(run["candidates"]) == 1
    assert run["errors"]
    paths = []
    for case in run["results"]:
        response = client.get(case["matched_image_url"])
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "image/jpeg"
        assert Image.open(BytesIO(response.content)).size == (32, 32)
        assert case["evidence"]["image"]["source"] == "facecheck_thumbnail"
        assert case["evidence"]["context"]["discovery"]["draft_only"] is True
        assert case["original_id"] is None and case["copy_relation"] == "uncertain"
        assert "image" not in json.dumps(match_evidence(case))
        paths.append(settings.data_dir / case["evidence"]["image"]["path"])
    assert "base64" not in json.dumps(run)
    assert all(image not in json.dumps(run) for image in images)
    cases = client.get(f"/api/cases?person_id={identity}&run_id={run['id']}")
    assert cases.status_code == 200 and len(cases.json()) == 2

    # Review uses real persisted IDs and the existing fallback, without provider calls.
    batch = client.post("/api/batches", json=payload([run["results"][0]["id"]]))
    assert batch.status_code == 202, batch.text
    finished = await_batch(client, batch.json()["id"])
    assert finished["items"][0]["status"] == "held_for_review"
    # Merely opening the details panel must not prevent cache deletion.
    assert client.get(f"/api/cases/{run['results'][1]['id']}/workflow").status_code == 200
    assert client.delete(f"/api/people/{identity}/face-search-cache").status_code == 200
    remaining = client.get(f"/api/cases?person_id={identity}").json()
    assert len(remaining) == 1 and remaining[0]["id"] == run["results"][0]["id"]
    assert paths[0].is_file() and not paths[1].exists()
    assert client.get(f"/api/batches/{batch.json()['id']}").json()["items"] == finished["items"]


def test_old_cache_materializes_missing_thumbnail_once(client, identity):
    run_id = saved_run(client, identity)
    for _ in range(2):
        result = start(client, identity, facecheck_source="cache", facecheck_consent=False,
                       allow_public_fetch=False)
        assert result.status_code == 202
        assert len(result.json()["results"]) == 1
        assert result.json()["results"][0]["thumbnail_available"] is False
    assert len(client.get(f"/api/cases?run_id={run_id}").json()) == 1


def saved_run(client, identity, *, photo_sha256="test", status="completed", demo=False):
    with client.app.state.store.session.begin() as session:
        row = CrawlRun(
            config={
                "public_search": True,
                "request": {
                    "person_id": identity,
                    "mode": "face_search",
                    "facecheck_consent": True,
                },
                "facecheck": {
                    "status": status,
                    "testing_mode": demo,
                    "photo_sha256": photo_sha256,
                    "score_above": 90,
                    "items": [{"url": "https://example.com/face", "score": 99}],
                    "id_search": "old-search",
                    "retrieved_at": "2026-10-11T00:00:00Z",
                },
                "discovery": {
                    "candidates": [
                        {"page_url": "https://example.com/face", "discovery_method": "face_search"}
                    ]
                },
            },
            identity_version="test",
            status="completed",
            finished_at="2026-10-11T00:00:01Z",
        )
        session.add(row)
        session.flush()
        return row.id


def test_delete_clears_all_provider_copies_and_prevents_fallback(client, identity):
    ids = [saved_run(client, identity), saved_run(client, identity)]
    path = f"/api/people/{identity}/face-search-cache"
    assert client.get(path).json()["run_id"] == ids[-1]
    client.app.state.busy = True
    assert client.delete(path).status_code == 409
    client.app.state.busy = False
    assert client.delete(path).json() == {"deleted": 2}
    assert client.get(path).json() == {"available": False, "count": 0}
    for run_id in ids:
        run = client.get(f"/api/public-searches/{run_id}").json()
        assert run["facecheck"]["status"] == "cache_deleted"
        assert run["facecheck"]["items"] == [] and run["candidates"] == []
        assert "old-search" not in json.dumps(run)
        assert client.post(f"/api/public-searches/{run_id}/resume").status_code == 422
    assert (
        start(
            client,
            identity,
            facecheck_source="cache",
            facecheck_consent=False,
            allow_public_fetch=False,
        ).status_code
        == 404
    )
    assert client.delete(path).json() == {"deleted": 0}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"photo_sha256": "different-photo"},
        {"status": "pending"},
        {"demo": True},
    ],
)
def test_ineligible_results_are_not_cached(client, identity, kwargs):
    saved_run(client, identity, **kwargs)
    assert client.get(f"/api/people/{identity}/face-search-cache").json()["available"] is False


def test_cache_isolation_and_identity_deletion(client, identity):
    run_id = saved_run(client, identity)
    with client.app.state.store.session.begin() as session:
        session.add(Person(id="other", name="Other", consent="Synthetic"))
    assert client.get("/api/people/other/face-search-cache").json()["available"] is False
    assert client.delete("/api/people/other/face-search-cache").json() == {"deleted": 0}
    assert client.get(f"/api/people/{identity}/face-search-cache").json()["available"] is True
    assert client.delete(f"/api/people/{identity}").status_code == 200
    assert (
        client.get(f"/api/public-searches/{run_id}").json()["facecheck"]["status"]
        == "cache_deleted"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"facecheck_consent": False},
        {"allow_public_fetch": False},
        {"full_name": "A name"},
        {"supplied_urls": ["https://example.com/"]},
    ],
)
def test_face_scan_requires_separate_consent_and_no_text_bypass(client, identity, changes):
    assert start(client, identity, **changes).status_code == 422


def test_fixture_and_missing_config_rejected_before_network(client, identity, settings):
    with client.app.state.store.session.begin() as session:
        session.get(Person, identity).development_fixture = True
    assert start(client, identity).status_code == 422
    with client.app.state.store.session.begin() as session:
        session.get(Person, identity).development_fixture = False
    settings.facecheck_api_token = SecretStr("")
    assert start(client, identity).status_code == 503


def test_pending_resume_polls_same_id_without_new_upload(client, identity, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/info":
            return httpx.Response(200, json={"is_online": True, "remaining_credits": 47})
        if request.url.path == "/api/upload_pic":
            return httpx.Response(200, json={"id_search": "pending-search"})
        body = json.loads(request.content)
        assert body["id_search"] == "pending-search"
        if not body["status_only"]:
            return httpx.Response(200, json={"progress": 0})
        return httpx.Response(200, json={"output": {"demo": False, "items": []}})

    intercept(monkeypatch, handler)
    original_search = FaceCheckClient.search

    def quick_search(self, *args, **kwargs):
        kwargs["wait_seconds"] = 0.001 if not kwargs["resume"] else 1
        return original_search(self, *args, **kwargs)

    monkeypatch.setattr(FaceCheckClient, "search", quick_search)
    run = wait(client, start(client, identity).json()["id"])
    assert run["facecheck"]["status"] == "pending"
    assert client.post(f"/api/public-searches/{run['id']}/resume").status_code == 202
    resumed = wait(client, run["id"])
    assert resumed["status"] == "completed" and resumed["facecheck"]["items"] == []
    assert calls == ["/api/info", "/api/upload_pic", "/api/search", "/api/search"]


def test_provider_failure_is_visible(client, identity, monkeypatch):
    intercept(monkeypatch, lambda request: httpx.Response(401, text="secret body"))
    run = wait(client, start(client, identity).json()["id"])
    assert run["status"] == "failed"
    assert "HTTP 401" in run["errors"][0]["message"]
    assert "secret body" not in json.dumps(run)
