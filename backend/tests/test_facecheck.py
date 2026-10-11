"""Synthetic images and intercepted HTTP only; no faces leave the test process."""

from io import BytesIO
import json

import httpx
from PIL import Image
import pytest

from censearch.config import Settings
from censearch.facecheck import FaceCheckClient, FaceCheckError, prepare_photo


def client_for(handler):
    settings = Settings(_env_file=None, facecheck_api_token="test-secret")
    return FaceCheckClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))


def photo():
    stream = BytesIO()
    Image.new("RGB", (32, 32), "blue").save(stream, format="JPEG")
    return stream.getvalue()


def test_info_auth_and_secret_repr():
    def handler(request):
        assert str(request.url) == "https://facecheck.id/api/info"
        assert request.headers["authorization"] == "test-secret"
        return httpx.Response(200, json={"remaining_credits": 50, "is_online": True})

    assert client_for(handler).info()["remaining_credits"] == 50
    assert "test-secret" not in repr(Settings(_env_file=None, facecheck_api_token="test-secret"))


@pytest.mark.parametrize("confirmed,fixture", [(False, False), (True, True)])
def test_upload_gate_before_network(confirmed, fixture):
    def handler(request):
        pytest.fail("Forbidden photo reached HTTP transport")

    with pytest.raises(FaceCheckError, match="upload consent"):
        client_for(handler).upload(photo(), upload_consent=confirmed, development_fixture=fixture)


def test_upload_strips_metadata_and_filename():
    stream = BytesIO()
    exif = Image.Exif()
    exif[0x010E] = "private metadata"
    Image.new("RGB", (32, 32)).save(stream, format="JPEG", exif=exif)

    def handler(request):
        assert request.url.path == "/api/upload_pic"
        assert b'filename="photo.jpg"' in request.content
        assert b"private metadata" not in request.content
        return httpx.Response(200, json={"id_search": "search-123", "error": None})

    assert client_for(handler).upload(stream.getvalue(), upload_consent=True) == "search-123"


def test_invalid_image_and_size_rejected():
    with pytest.raises(ValueError):
        prepare_photo(b"not an image", 100)
    with pytest.raises(ValueError, match="limit"):
        prepare_photo(photo(), 10)


def test_submit_once_and_filter_thumbnails(monkeypatch):
    monkeypatch.setattr("censearch.facecheck.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            return httpx.Response(200, json={"progress": 20, "output": None})
        return httpx.Response(
            200,
            json={
                "output": {
                    "demo": True,
                    "items": [
                        {"url": "https://example.com/a", "score": 91, "base64": "PRIVATE-IMAGE"},
                        {"url": {"value": "https://example.com/b"}, "score": 92},
                        {"url": "https://example.com/cutoff", "score": 90},
                        {"url": "https://example.com/low", "score": 89},
                        {"url": "javascript:bad", "score": 90},
                        {"url": "https://example.com/c", "score": 150},
                    ],
                }
            },
        )

    result = client_for(handler).search("search-123")
    assert [row["status_only"] for row in calls] == [False, True]
    assert all(row["demo"] is True for row in calls)
    assert len(result["items"]) == 2
    assert [item["score"] for item in result["items"]] == [91, 92]
    assert "PRIVATE-IMAGE" not in json.dumps(result)


def test_live_resume_never_submits_and_empty_results_complete():
    def handler(request):
        assert json.loads(request.content) == {
            "id_search": "existing",
            "with_progress": True,
            "status_only": True,
            "demo": False,
        }
        return httpx.Response(200, json={"output": {"items": []}})

    result = client_for(handler).search("existing", live=True, resume=True)
    assert result["status"] == "completed"
    assert result["items"] == []
    assert result["testing_mode"] is False


@pytest.mark.parametrize(
    "status,body",
    [
        (401, {"error": "test-secret"}),
        (200, {"error": "test-secret"}),
        (200, ["test-secret"]),
        (302, {}),
    ],
)
def test_errors_redacted_and_redirects_not_followed(status, body):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json=body, headers={"location": "https://unrelated.invalid"})

    with pytest.raises(FaceCheckError) as caught:
        client_for(handler).info()
    assert "test-secret" not in str(caught.value)
    assert len(calls) == 1


def test_deadline_preserves_search_id(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("censearch.facecheck.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "censearch.facecheck.time.sleep", lambda amount: clock.__setitem__(0, clock[0] + amount)
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"progress": 0})

    result = client_for(handler).search("pending-id", wait_seconds=3)
    assert result["status"] == "pending"
    assert result["id_search"] == "pending-id"
    assert len(calls) == 2


def test_response_size_limit(monkeypatch):
    monkeypatch.setattr("censearch.facecheck.MAX_RESPONSE_BYTES", 10)
    with pytest.raises(FaceCheckError, match="size limit"):
        client_for(lambda request: httpx.Response(200, content=b"x" * 11)).info()
