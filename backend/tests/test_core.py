import hashlib
import importlib
import inspect
from io import BytesIO
import json
import pkgutil
import cv2
import numpy as np
from PIL import Image
import pytest
from sqlalchemy import select
from censearch.agent.model import build_model
from censearch.agent.tools import dns_lookup
from censearch.config import ROOT, Settings
from censearch.copy_detect import compare, features, verdict
from censearch.crawl import Crawler, extract, validate_url
from censearch.db import Case, CrawlRun, Original, Person, Reference, Scan
from censearch.face import active_references, band_for
from censearch.imaging import decode
from mockweb.seed import transforms


def test_imports_and_boundary():
    import censearch
    import mockweb

    for package in (censearch, mockweb):
        for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            loaded = importlib.import_module(module.name)
            source = inspect.getsource(loaded)
            if module.name.startswith("censearch."):
                assert "ground_truth" not in source
                assert "from mockweb" not in source
            else:
                assert "from censearch" not in source


def test_config_environment_and_relative_paths(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("LIKENESS_DATA_DIR=example-data\nCHAT_MODEL=from-file\nMODEL_MAX_TOKENS=2048\n")
    monkeypatch.setenv("CHAT_MODEL", "from-environment")
    settings = Settings(_env_file=env)
    assert settings.chat_model == "from-environment"
    assert settings.data_dir == ROOT / "example-data"
    assert settings.model_max_tokens == 2048
    with pytest.raises(ValueError):
        Settings(_env_file=None, model_max_tokens=4097)


def test_health_and_unconfigured_probe(client):
    health = client.get("/api/health").json()
    assert health["database"]["status"] == "ok"
    assert health["face_models"]["loaded"] is True
    assert health["model"]["configured"] is False
    assert health["object_storage"]["mode"] == "local_disk"
    response = client.post("/api/agent/probe", json={"hostname": "localhost"})
    assert response.status_code == 200
    assert response.json()["status"] == "model_not_configured"
    assert response.json()["answer"] is None
    assert response.json()["tool_calls"] == []


def test_degraded_health(settings, tmp_path):
    from fastapi.testclient import TestClient
    from censearch.api import create_app

    settings.models_dir = tmp_path / "missing-models"
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health").json()
        assert health["status"] == "degraded"
        assert health["face_models"]["loaded"] is False
        assert health["face_models"]["error"]


def test_dns_tool_and_provider(settings):
    result = dns_lookup(hostname="localhost")
    assert result["status"] == "resolved"
    assert "127.0.0.1" in result["addresses"]
    assert dns_lookup(hostname="https://invalid/path")["status"] == "invalid_hostname"
    assert build_model(settings) is None
    settings.model_provider = "unsupported"
    with pytest.raises(ValueError):
        build_model(settings)


def test_reference_prefix_and_bands(calibration):
    refs = np.arange(8)
    for count, expected in ((1, 1), (2, 1), (3, 3), (4, 3), (5, 5), (8, 5)):
        assert active_references(refs[:count]).tolist() == list(range(expected))
    high = calibration["deployment_bands"]["match"]["threshold"]
    low = calibration["deployment_bands"]["possible"]["threshold"]
    assert band_for(high, calibration) == "match"
    assert band_for(low, calibration) == "possible"
    assert band_for(low - 0.000001, calibration) == "no_match"
    with pytest.raises(ValueError):
        active_references([])


def test_enrollment_quality_atomic_and_no_embeddings(client, enrolled):
    assert len(enrolled["references"]) == 1
    assert "embedding" not in json.dumps(enrolled)
    bad = BytesIO()
    Image.new("RGB", (300, 300), "white").save(bad, "PNG")
    response = client.post(
        "/api/people",
        data={"name": "Rejected", "consent": "test"},
        files={"references": ("blank.png", bad.getvalue(), "image/png")},
    )
    assert response.status_code == 422
    detail = response.json()["error"]
    assert detail["code"] == "photo_rejected"
    assert detail["photos"][0]["accepted"] is False
    assert "found 0" in detail["photos"][0]["reason"]
    assert len(client.get("/api/people").json()) == 1
    response = client.post(
        "/api/people",
        data={"name": "Rejected", "consent": "test"},
        files={"references": ("bad.jpg", b"not a photo", "image/jpeg")},
    )
    assert response.status_code == 422
    assert client.get("/api/people/missing").status_code == 404


def test_fixture_cloud_guard(client):
    enrollment = client.app.state.enrollment
    enrollment.evidence.client = object()
    with pytest.raises(ValueError, match="Development fixtures require local storage"):
        enrollment.enroll("fixture", "test", [("a", b"x")], [], "", True)
    enrollment.evidence.client = None


def test_quality_size_and_blur(client, monkeypatch):
    face = client.app.state.face
    image = np.full((100, 100, 3), 255, np.uint8)
    row = np.zeros(15, np.float32)
    row[:4] = [10, 10, 20, 20]
    row[14] = 0.99
    monkeypatch.setattr(face, "detect_rows", lambda image: [row])
    assert face.upright(image)[1] == ["face_too_small"]
    row[2:4] = 50
    assert face.upright(image)[1] == ["blur"]


@pytest.mark.parametrize("transform", ["resize", "crop", "mirror", "border", "caption_overlay"])
def test_copy_transform_verdicts(photo_folder, calibration, transform):
    payload = sorted((photo_folder / "originals").glob("*.jpg"))[0].read_bytes()
    original = features(decode(payload))
    image = decode(transforms(payload)[transform])
    result = compare(original, features(image), features(cv2.flip(image, 1)))
    assert verdict(result, calibration["copy"]) == "derived", result


def test_copy_negative_and_uncertain(calibration):
    random = np.random.default_rng(123)
    first = random.integers(0, 255, (250, 250, 3), dtype=np.uint8)
    second = random.integers(0, 255, (250, 250, 3), dtype=np.uint8)
    result = compare(features(first), features(second), features(cv2.flip(second, 1)))
    assert verdict(result, calibration["copy"]) == "none"
    threshold = calibration["copy"]
    evidence = {
        "inliers": threshold["minimum_inliers"],
        "central_overlap": 0.8,
        "dense_score": (threshold["dense_threshold"] + threshold["uncertain_threshold"]) / 2,
    }
    assert verdict(evidence, threshold) == "uncertain"


def analyse(client, payload):
    store = client.app.state.store
    matcher = client.app.state.matcher
    gallery = matcher.gallery()
    with store.session.begin() as session:
        run = CrawlRun(config={}, identity_version=store.version(session))
        session.add(run)
        session.flush()
        scan = Scan(
            run_id=run.id,
            page_url="http://127.0.0.1/photo",
            image_url="http://127.0.0.1/image",
            identity_version=run.identity_version,
            status="discovered",
        )
        session.add(scan)
        session.flush()
        result = matcher.analyse(session, scan, payload, {}, gallery, {}, scan.image_url, [])
        return result, scan.id


def test_nonmatch_privacy_and_delete(client, enrolled, photo_folder, settings):
    before = {
        str(path): path.read_bytes()
        for path in settings.data_dir.rglob("*")
        if path.is_file() and path.suffix != ".sqlite"
    }
    blank = BytesIO()
    Image.new("RGB", (300, 300), "white").save(blank, "PNG")
    result, scan_id = analyse(client, blank.getvalue())
    assert result["matches"] == 0
    after = {
        str(path): path.read_bytes()
        for path in settings.data_dir.rglob("*")
        if path.is_file() and path.suffix != ".sqlite"
    }
    assert before == after
    with client.app.state.store.session() as session:
        scan = session.get(Scan, scan_id)
        assert scan.status == "no_match"
        assert scan.sha256 == hashlib.sha256(blank.getvalue()).hexdigest()
        assert set(Scan.__table__.columns.keys()) == {
            "id",
            "run_id",
            "page_url",
            "image_url",
            "sha256",
            "identity_version",
            "scanned_at",
            "status",
        }
        assert list(session.scalars(select(Case))) == []
    original = sorted((photo_folder / "originals").glob("*.jpg"))[0].read_bytes()
    matched, _ = analyse(client, original)
    assert matched["matches"] == 1
    case = client.get("/api/cases").json()[0]
    assert case["copy_relation"] == "exact"
    assert case["answers"] is None and case["route"] is None
    response = client.get(case["matched_image_url"])
    assert response.content == original
    assert response.headers["cache-control"] == "no-store"
    assert client.delete(f"/api/people/{enrolled['id']}").status_code == 200
    assert not (settings.data_dir / "people" / enrolled["id"]).exists()
    with client.app.state.store.session() as session:
        for model in (Person, Reference, Original, Case):
            assert list(session.scalars(select(model))) == []
    assert client.get(case["matched_image_url"]).status_code == 404


def test_extraction_scope_and_busy(client):
    images, links, _, _, scripts = extract(
        '<title>x</title><script src="a.js"></script><img src="a.jpg"><a href="/next">next</a>',
        "http://127.0.0.1:8811/",
    )
    assert "http://127.0.0.1:8811/a.jpg" in images
    assert links == ["http://127.0.0.1:8811/next"]
    assert scripts
    with pytest.raises(ValueError):
        validate_url("https://example.com/photo")
    assert client.post("/api/crawls", json={"seeds": ["https://example.com/"]}).status_code == 422
    client.app.state.busy = True
    assert client.post("/api/crawls", json={"seeds": ["http://127.0.0.1:8811/"]}).status_code == 409
    client.app.state.busy = False


def test_robots_redirect_and_budget(client, settings):
    settings.respect_robots = True
    import asyncio
    import httpx
    from censearch.crawl import BudgetExceeded

    requests = []

    def respond(request):
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "https://example.com/"})
        return httpx.Response(200, text="ok")

    async def check():
        crawler = Crawler(
            settings,
            client.app.state.store,
            client.app.state.matcher,
            0,
            {"seeds": ["http://127.0.0.1:8811/"], "delay": 0.01},
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
            crawler.client = transport
            assert await crawler.fetch("http://127.0.0.1:8811/private/photo") is None
            assert crawler.metrics["robots_denied"] == 1
            with pytest.raises(ValueError, match="Public crawling"):
                await crawler.fetch("http://127.0.0.1:8811/redirect")
            settings.crawl_request_budget = len(requests)
            with pytest.raises(BudgetExceeded):
                await crawler.fetch("http://127.0.0.1:8811/allowed")
        assert all("127.0.0.1" in url for url in requests)
        assert not any("/private/" in url for url in requests)

    asyncio.run(check())
