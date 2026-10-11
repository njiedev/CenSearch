"""Dashboard email contract checks with intercepted API responses; no real delivery."""

import asyncio
from playwright.async_api import async_playwright, expect
from app_browser import BASE, fill_authorization, responsive


async def email_contract(browser, ready):
    context = await browser.new_context(viewport={"width": 1440, "height": 1000})
    page = await context.new_page()
    row = {
        "id": 1, "page_url": "https://publisher.example/photo",
        "matched_image_url": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>",
        "band": "match", "state": "matched", "match_type": "face",
        "photo_relation": "different_photo", "copy_relation": "none",
        "batch_outcome": None, "drafted_request": None, "deliveries": [], "whitelisted": False,
        "possible_action": {"route": "privacy_request", "label": "Privacy request",
                            "reason": "Synthetic review", "source": "agent", "model_status": "completed"},
    }
    scan = {
        "run_id": 1, "kind": "public_search", "status": "completed",
        "label": "Synthetic email scan", "started_at": "2026-10-11T00:00:00Z",
        "finished_at": "2026-10-11T00:00:01Z", "match_count": 1, "possible_count": 0,
        "pages_fetched": 1, "images_checked": 1, "whitelisted_count": 0,
    }
    posts = []
    outcome = "sent" if ready else "drafted_not_sent"
    reason = "Email accepted by the sending service; awaiting the site's response." if ready else "Automatic email sending is not enabled. Request saved as a draft."
    batch = {
        "id": "email-contract", "mode": "send", "phase": "done", "status": "completed",
        "completed": 1, "total": 1,
        "items": [{"case_id": row["id"], "status": outcome, "reason": reason}],
    }

    async def api(route):
        path = route.request.url.split("/api", 1)[1].split("?", 1)[0]
        if route.request.method == "POST":
            assert path == "/batches", path
            body = route.request.post_data_json
            posts.append(body)
            assert body["mode"] == "send" and body["accepted_warning"] is True
            assert body["case_ids"] == [row["id"]]
            row["batch_outcome"] = {"status": outcome, "reason": reason}
            row["drafted_request"] = {
                "id": 1, "payload": {"body": "Synthetic notice text"},
                "recipient": {"address": "privacy@publisher.example", "channel": "email",
                              "endpoint": "mailto:privacy@publisher.example"},
            }
            return await route.fulfill(status=202, json=batch)
        responses = {
            "/people/email-test": {"id": "email-test", "name": "Email Test"},
            "/people/email-test/scans": [scan],
            "/people/email-test/whitelist": {"domains": []},
            "/cases": [row],
            "/public-searches/1": {
                "id": 1, "status": "completed", "results": [row], "metrics": {}, "errors": [],
                "started_at": scan["started_at"], "finished_at": scan["finished_at"],
            },
            "/batches/warning": {"warning": "Synthetic legal-responsibility warning.", "email_delivery": {"ready": ready}},
            "/batches/email-contract": batch,
        }
        assert path in responses, path
        await route.fulfill(json=responses[path])

    await page.route("**/api/**", api)
    await page.add_init_script("localStorage.setItem('censearch.session', JSON.stringify({id:'email-test',name:'Email Test'}))")
    await page.goto(BASE + "/app/#scan/1")
    await page.get_by_role("button", name="Select all visible").click()
    await page.get_by_role("button", name="Review with agent").click()
    note = page.get_by_text("The sending account is not connected yet. Email requests will be saved as drafts.")
    if ready:
        await expect(note).to_have_count(0)
    else:
        await expect(note).to_be_visible()
    await responsive(page, "email setup indicator")
    assert not posts
    await fill_authorization(page, review=False)
    await expect(page.get_by_role("heading", name="Batch complete")).to_be_visible()
    await expect(page.get_by_role("heading", name="Sent (1)" if ready else "Drafted for you to send yourself (1)", exact=True)).to_be_visible()
    await page.locator('.review-item [data-slot=accordion-trigger]').click()
    await expect(page.get_by_text("Delivery destination: website email contact")).to_be_visible()
    await expect(page.get_by_text(reason, exact=True)).to_be_visible()
    await expect(page.locator(".mx-notice")).to_have_text("Synthetic notice text")
    assert len(posts) == 1
    await context.close()
    print(f"PASS email API contract: ready={ready}, one authorized send-mode POST, correct outcome and notice, responsive setup indicator", flush=True)


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            await email_contract(browser, ready=False)
            await email_contract(browser, ready=True)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
