"""Browser regression following app_browser.py's local Playwright workflow.

All API responses are intercepted; only synthetic images are shown and no credits are spent.
Run: CENSEARCH_TEST_URL=http://127.0.0.1:5177 backend/.venv/bin/python frontend/tests/face_search_browser.py
"""

import asyncio
import json
import os
import re
from io import BytesIO
from PIL import Image
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("CENSEARCH_TEST_URL", "http://127.0.0.1:5177")


def candidate(case_id, thumbnail=True):
    return {
        "id": case_id, "page_url": "https://example.com/qualified", "match_type": "facecheck",
        "provider_score": 99, "band": "possible", "state": "needs_review",
        "matched_image_url": f"/api/cases/{case_id}/image", "thumbnail_available": thumbnail,
        "created_at": "2026-10-11T00:00:20Z", "batch_outcome": None, "drafted_request": None,
        "deliveries": [], "possible_action": {
            "route": "hold_for_review", "label": "Hold for review", "reason": "Evidence is uncertain.",
            "source": "rule_fallback", "possible": True, "model_status": "not_requested",
        },
    }


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        await context.add_init_script("localStorage.setItem('censearch.session', JSON.stringify({id:'synthetic',name:'Synthetic test'})); sessionStorage.setItem('censearch.live','1')")
        state = {"scan": None, "run": None, "requests": [], "polls": 0, "fail": False,
                 "cache": {"available": False, "count": 0}, "cache_reads": 0, "deletes": 0, "cases": []}
        image = BytesIO()
        Image.new("RGB", (32, 32), "blue").save(image, format="PNG")

        async def intercept(route):
            request = route.request
            path = request.url.split("/api", 1)[-1]
            status = 200
            if path == "/people/synthetic":
                body = {"id": "synthetic", "name": "Synthetic test"}
            elif path == "/people/synthetic/face-search-cache":
                if request.method == "DELETE":
                    state["deletes"] += 1
                    state["cache"] = {"available": False, "count": 0}
                    state["run"]["facecheck"].update(status="cache_deleted", items=[], id_search=None)
                    state["cases"] = []
                    body = {"deleted": 1}
                else:
                    body = state["cache"]
            elif path == "/people/synthetic/whitelist":
                body = {"domains": []}
            elif path == "/people/synthetic/scans":
                body = [state["scan"]] if state["scan"] else []
            elif path.startswith("/cases?"):
                body = state["cases"]
            elif path.endswith("/image"):
                await route.fulfill(content_type="image/png", body=image.getvalue())
                return
            elif path.endswith("/workflow"):
                body = {"state": "needs_review", "checks": [], "notices": [], "deliveries": []}
            elif path == "/batches/warning":
                body = {"warning": "Accept legal responsibility for this review."}
            elif path == "/public-searches" and request.method == "POST":
                body_in = request.post_data_json
                if body_in.get("facecheck_source") == "cache":
                    assert body_in["facecheck_consent"] is False and body_in["allow_public_fetch"] is False
                    state["cache_reads"] += 1
                    await route.fulfill(status=202, content_type="application/json", body=json.dumps(state["run"]))
                    return
                state["requests"].append(body_in)
                if state["fail"]:
                    status, body = 503, {"detail": "FaceCheck is not configured on this server"}
                else:
                    assert body_in == {
                        "person_id": "synthetic", "full_name": "", "handles": [], "context": "",
                        "supplied_urls": [], "mode": "face_search", "allow_public_fetch": True,
                        "facecheck_consent": True,
                        "facecheck_source": "live",
                    }, body_in
                    state["scan"] = {
                        "run_id": 10, "kind": "public_search", "status": "running", "label": "FaceCheck · score above 90",
                        "started_at": "2026-10-11T00:00:00Z", "finished_at": None,
                        "pages_fetched": 0, "images_checked": 0, "match_count": 0, "possible_count": 0, "whitelisted_count": 0,
                    }
                    state["run"] = {
                        "id": 10, "person_id": "synthetic", "status": "running", "started_at": "2026-10-11T00:00:00Z", "finished_at": None,
                        "metrics": {}, "results": [], "errors": [],
                        "facecheck": {"status": "searching", "id_search": "existing-id", "progress": 25,
                                      "score_above": 90, "testing_mode": False, "items": []},
                    }
                    body = state["run"]
            elif path == "/public-searches/10/resume":
                state["polls"] = 0
                state["run"]["status"] = "running"
                state["run"]["facecheck"]["status"] = "searching"
                state["scan"]["status"] = "running"
                body = state["run"]
            elif path == "/public-searches/10":
                state["polls"] += 1
                if state["run"]["status"] == "running" and state["polls"] >= 3:
                    state["run"].update(status="completed_with_errors", finished_at="2026-10-11T00:00:30Z")
                    state["scan"].update(status="completed", finished_at="2026-10-11T00:00:30Z")
                    state["run"]["facecheck"].update(status="completed", items=[
                        {"url": "https://example.com/qualified", "score": 99, "label": "Possible match"},
                        {"url": "https://example.com/" + "long" * 120, "score": 91, "label": "Possible match"},
                        # Deliberately malformed API response tests the display's extra cutoff guard.
                        {"url": "https://example.com/excluded", "score": 90, "label": "Possible match"},
                    ])
                    state["run"]["errors"] = [{"message": "Source page could not be fetched."}]
                    state["run"]["facecheck"]["retrieved_at"] = "2026-10-11T00:00:20Z"
                    state["cache"] = {"available": True, "count": 2, "run_id": 10, "saved_at": "2026-10-11T00:00:20Z"}
                    state["cases"] = [candidate(41), candidate(42, False)]
                body = state["run"]
            else:
                raise AssertionError(f"Unexpected API request: {request.method} {path}")
            await route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

        await context.route("**/api/**", intercept)
        await context.route("**/photos/**", lambda route: route.fulfill(content_type="image/png", body=image.getvalue()))
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            await page.goto(BASE + "/app/#new")
            await expect(page.get_by_role("radio", name="Face search · FaceCheck")).to_be_checked()
            await page.get_by_role("button", name="Start scan", exact=True).click()
            await expect(page.get_by_text("Allow the photo upload and 3-credit search to continue.")).to_be_visible()
            assert not state["requests"]
            consent = page.get_by_role("checkbox", name="I authorize sending this enrolled photo", exact=False)
            await consent.focus()
            await page.keyboard.press("Space")
            await expect(consent).to_be_checked()
            await page.get_by_role("checkbox", name="I allow this scan", exact=False).check()
            for width in (360, 600, 840, 1440):
                await page.set_viewport_size({"width": width, "height": 1000})
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            await page.get_by_role("button", name="Start scan", exact=True).click()
            await expect(page.get_by_role("heading", name="Searching FaceCheck")).to_be_visible()
            await expect(page.get_by_text("FaceCheck 25%", exact=False)).to_be_visible()
            await expect(page.get_by_role("button", name="Review with agent")).to_be_visible(timeout=15000)
            await expect(page.get_by_text("Score 90", exact=True)).to_have_count(0)
            await expect(page.get_by_role("article")).to_have_count(2)
            await expect(page.get_by_text("FaceCheck · Score 99 · Not locally verified")).to_have_count(2)
            await expect(page.get_by_text("Thumbnail unavailable", exact=True)).to_be_visible()
            assert await page.get_by_alt_text("Candidate image", exact=True).evaluate("img => img.complete && img.naturalWidth === 32")
            await page.get_by_role("button", name="Open match 41:", exact=False).click()
            await expect(page.get_by_text("This provider thumbnail has not been", exact=False)).to_be_visible()
            await page.keyboard.press("Escape")
            await page.get_by_role("checkbox", name="Select match 41", exact=True).check()
            await page.get_by_role("button", name="Review with agent").click()
            await expect(page.get_by_role("heading", name=re.compile("Authorize (agent review|automatic requests)"))).to_be_visible()
            await expect(page.get_by_role("heading", name="1 match selected")).to_be_visible()
            for width in (360, 600, 840, 1440):
                await page.set_viewport_size({"width": width, "height": 1000})
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            await page.get_by_role("button", name="Back to matches").click()
            await expect(page.get_by_role("article")).to_have_count(2)
            for width in (360, 600, 840, 1440):
                await page.set_viewport_size({"width": width, "height": 1000})
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width

            await page.goto(BASE + "/app/#new")
            await expect(page.get_by_role("radio", name="Use saved scan · no credits")).to_be_checked()
            await expect(page.get_by_role("checkbox", name="I authorize sending", exact=False)).to_have_count(0)
            await page.get_by_role("button", name="Open saved scan").click()
            await expect(page.get_by_role("article")).to_have_count(2)
            assert state["cache_reads"] == 1 and len(state["requests"]) == 1

            state["run"]["facecheck"].update(status="pending", items=[])
            state["run"]["status"] = "failed"
            await page.goto(BASE + "/app/#scan/10/running")
            await page.get_by_role("button", name="Check existing FaceCheck search").click()
            await expect(page.get_by_role("heading", name="Searching FaceCheck")).to_be_visible()
            await expect(page.get_by_role("button", name="Review with agent")).to_be_visible(timeout=15000)
            assert len(state["requests"]) == 1, "Resume started a new paid scan"

            state["run"]["facecheck"]["items"] = []
            state["cases"] = []
            await page.reload()
            await expect(page.get_by_role("heading", name="No matches found")).to_be_visible()

            state["fail"] = True
            state["cache"] = {"available": False, "count": 0}
            await page.goto(BASE + "/app/#new")
            await page.get_by_role("checkbox", name="I authorize sending this enrolled photo", exact=False).check()
            await page.get_by_role("checkbox", name="I allow this scan", exact=False).check()
            await page.get_by_role("button", name="Start scan", exact=True).click()
            await expect(page.get_by_text("FaceCheck is not configured on this server")).to_be_visible()
            await page.get_by_role("radio", name="Name / links · text search").check()
            await expect(page.get_by_role("textbox", name="Full name", exact=True)).to_be_visible()
            state["cache"] = {"available": True, "count": 2, "run_id": 10, "saved_at": "2026-10-11T00:00:20Z"}
            await page.reload()
            await page.get_by_role("button", name="Delete FaceCheck cache").click()
            await expect(page.get_by_role("region", name="Confirm cache deletion")).to_be_visible()
            await page.get_by_role("button", name="Keep cache").click()
            assert state["deletes"] == 0
            await page.get_by_role("button", name="Delete FaceCheck cache").click()
            await page.get_by_role("button", name="Confirm delete cache").click()
            await expect(page.get_by_role("button", name="Open saved scan")).to_have_count(0)
            await expect(page.get_by_role("checkbox", name="I authorize sending", exact=False)).not_to_be_checked()
            assert state["deletes"] == 1
            await page.goto(BASE + "/app/#scan/10")
            await expect(page.get_by_role("heading", name="No matches found")).to_be_visible()
            await expect(page.get_by_role("button", name="Check existing FaceCheck search")).to_have_count(0)
            assert not errors, errors
            print("PASS: consent, keyboard, >90 results, provider thumbnail rendering and selection, review authorization, missing thumbnails, blocked sources, no-charge resume, cache reuse/deletion, empty/error states, text mode, and 360/600/840/1440px overflow; mocked API and synthetic images only.")
        except Exception:
            print('BROWSER FAILURE:', page.url, await page.locator('body').inner_text(), errors, 'polls:', state['polls'])
            raise
        finally:
            await context.close()
            await browser.close()


asyncio.run(main())
