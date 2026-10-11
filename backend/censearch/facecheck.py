"""Explicit FaceCheck uploads, bounded polling, and optional local-review thumbnails."""

from io import BytesIO
import json
import time
from urllib.parse import urlsplit

import cv2
import httpx

from censearch.imaging import decode

BASE_URL = "https://facecheck.id"
MAX_RESPONSE_BYTES = 20_000_000
MIN_SCORE = 88


class FaceCheckError(RuntimeError):
    pass


def prepare_photo(payload: bytes, limit: int) -> bytes:
    """Validate locally and remove EXIF and the original filename before upload."""
    if not payload or len(payload) > limit:
        raise ValueError("Photo is empty or exceeds the upload limit")
    image = decode(payload)
    height, width = image.shape[:2]
    if max(height, width) > 1600:
        scale = 1600 / max(height, width)
        image = cv2.resize(image, (round(width * scale), round(height * scale)))
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise ValueError("Could not encode the photo")
    return encoded.tobytes()


def result_items(items, *, include_thumbnails=False):
    """Filter scores before optionally retaining bounded thumbnails for local review."""
    if not isinstance(items, list):
        raise FaceCheckError("FaceCheck returned invalid search results")
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        # The examples use strings; Swagger also permits a MaskedUrl object.
        if isinstance(url, dict):
            url = url.get("value")
        score = item.get("score")
        if not isinstance(url, str) or not isinstance(score, (int, float)):
            continue
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                continue
            if parsed.username or parsed.password or not MIN_SCORE <= score <= 100:
                continue
        except ValueError:
            continue
        row = {"url": url, "score": score, "label": "Possible match · review needed"}
        thumbnail = item.get("base64")
        if include_thumbnails and isinstance(thumbnail, str) and len(thumbnail) <= 2_000_000:
            row["base64"] = thumbnail
        result.append(row)
    return result


class FaceCheckClient:
    def __init__(self, settings, client):
        self.token = settings.facecheck_api_token.get_secret_value()
        self.client = client
        self.upload_limit = settings.upload_limit_bytes

    def post(self, endpoint, **kwargs):
        if not self.token:
            raise FaceCheckError("Set FACECHECK_API_TOKEN in backend/.env")
        try:
            with self.client.stream(
                "POST",
                BASE_URL + endpoint,
                headers={"accept": "application/json", "Authorization": self.token},
                follow_redirects=False,
                **kwargs,
            ) as response:
                if response.status_code != 200:
                    raise FaceCheckError(f"FaceCheck returned HTTP {response.status_code}")
                body = BytesIO()
                for chunk in response.iter_bytes():
                    body.write(chunk)
                    if body.tell() > MAX_RESPONSE_BYTES:
                        raise FaceCheckError("FaceCheck response exceeded the size limit")
                data = json.loads(body.getvalue())
        except (httpx.HTTPError, ValueError) as error:
            # Provider bodies and exceptions can contain credentials or image payloads.
            raise FaceCheckError(f"FaceCheck request failed ({type(error).__name__})") from None
        if not isinstance(data, dict):
            raise FaceCheckError("FaceCheck returned an invalid response")
        if data.get("error"):
            raise FaceCheckError(
                "FaceCheck rejected the request; check credits and photo suitability"
            )
        return data

    def info(self):
        data = self.post("/api/info", timeout=20)
        fields = ("is_online", "remaining_credits", "has_credits_to_search", "faces")
        if not isinstance(data.get("remaining_credits"), int):
            raise FaceCheckError("FaceCheck did not return account information")
        return {key: data.get(key) for key in fields}

    def upload(self, payload, *, upload_consent=False, development_fixture=False):
        if development_fixture or not upload_consent:
            raise FaceCheckError(
                "Explicit upload consent is required; development fixtures are forbidden"
            )
        photo = prepare_photo(payload, self.upload_limit)
        data = self.post(
            "/api/upload_pic", files={"images": ("photo.jpg", photo, "image/jpeg")}, timeout=30
        )
        search_id = data.get("id_search")
        if not isinstance(search_id, str) or not search_id.strip():
            raise FaceCheckError("FaceCheck did not return a search ID")
        return search_id

    def search(
        self,
        search_id,
        *,
        live=False,
        resume=False,
        wait_seconds=120,
        progress=None,
        check_cancel=None,
        include_thumbnails=False,
    ):
        if not search_id or not 0 < wait_seconds <= 600:
            raise ValueError("A search ID and wait limit of 1–600 seconds are required")
        deadline = time.monotonic() + wait_seconds
        status_only = resume
        while time.monotonic() < deadline:
            if check_cancel:
                check_cancel()
            data = self.post(
                "/api/search",
                json={
                    "id_search": search_id,
                    "with_progress": True,
                    "status_only": status_only,
                    "demo": not live,
                },
                timeout=min(20, max(0.1, deadline - time.monotonic())),
            )
            # Submit once. Subsequent requests and explicit resumes only check status.
            status_only = True
            output = data.get("output")
            if isinstance(output, dict):
                return {
                    "id_search": search_id,
                    "testing_mode": output.get("demo")
                    if isinstance(output.get("demo"), bool)
                    else not live,
                    "status": "completed",
                    "items": result_items(output.get("items") or [], include_thumbnails=include_thumbnails),
                }
            if progress:
                value = data.get("progress")
                progress(value if isinstance(value, (int, float)) else None)
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        return {
            "id_search": search_id,
            "testing_mode": not live,
            "status": "pending",
            "items": [],
        }
