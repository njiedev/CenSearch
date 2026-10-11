"""GET verification and a clock shared by real-time and demonstration scheduling."""

from datetime import datetime, timedelta, timezone
import hashlib
import cv2
from censearch.agent.web import ReadOnlyWeb
from censearch.copy_detect import compare, features, verdict
from censearch.imaging import decode


class Clock:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.offset = 0

    def now(self):
        return datetime.now(timezone.utc) + timedelta(seconds=self.offset)

    def advance(self, seconds):
        if not self.enabled:
            raise ValueError("Demo clock requires LIKENESS_DEMO_CLOCK=1")
        if not 0 < seconds <= 31_536_000:
            raise ValueError("Advance must be positive and at most one year")
        self.offset += seconds
        return self.now().isoformat()


def classify(page_status, image_status, same_image=None, origin_status=None, is_image=True):
    statuses = (page_status, image_status)
    if any(code in (401, 403, 429, 451) for code in statuses):
        return "blocked"
    if any(code >= 500 for code in statuses):
        return "unreachable"
    if image_status == 200:
        if not is_image:
            return "blocked"
        if same_image is None:
            return "uncertain"
        return "still_present" if same_image else "replaced"
    if image_status in (404, 410) and page_status in (200, 404, 410) and origin_status == 200:
        return "removed"
    return "unreachable"


def check(case, original_bytes, calibration, web=None, *, settings=None):
    from urllib.parse import urlsplit

    web = web or ReadOnlyWeb(limit=16, timeout=3, settings=settings)
    result = {"outcome": "unreachable", "source_removed": False}
    try:
        page = web.get(case["page_url"], cache=False)
        image = web.get(case["image_url"], cache=False)
        relation = None
        origin_status = None
        if image.status_code == 200 and image.headers.get("content-type", "").startswith("image/"):
            if hashlib.sha256(image.content).digest() == hashlib.sha256(original_bytes).digest():
                relation = True
            else:
                source = decode(original_bytes)
                current = decode(image.content)
                value = verdict(
                    compare(features(source), features(current), features(cv2.flip(current, 1))),
                    calibration["copy"],
                )
                relation = True if value in ("exact", "derived") else None if value == "uncertain" else False
        if image.status_code in (404, 410):
            p = urlsplit(case["page_url"])
            origin_status = web.get(f"{p.scheme}://{p.netloc}/", cache=False).status_code
        classification = classify(
            page.status_code,
            image.status_code,
            relation,
            origin_status,
            image.headers.get("content-type", "").startswith("image/"),
        )
        result.update(
            outcome=classification,
            source_removed=classification == "removed",
            page_status=page.status_code,
            image_status=image.status_code,
            origin_status=origin_status,
            image_sha256=hashlib.sha256(image.content).hexdigest(),
        )
    except Exception as error:
        result.update(
            outcome="blocked" if isinstance(error, ValueError) and "robots" in str(error) else "unreachable",
            error=type(error).__name__,
        )
    finally:
        result["requests"] = web.trace
        web.close()
    return result
