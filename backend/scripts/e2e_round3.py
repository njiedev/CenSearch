"""HTTP/SMTP + DOM-only batch acceptance with explicitly simulated failure/provider seams.

Mocks independently record actual recipients. This script never reads ground truth.
"""

import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
import socket
import subprocess
import threading
import time
from unittest.mock import patch
from urllib.parse import urlsplit
import httpx
import openai
import uvicorn
from playwright.sync_api import expect, sync_playwright
from strands.models.openai import OpenAIModel
from censearch.api import create_app
from censearch.agent.route import pick_route
from censearch.config import ROOT, Settings
from censearch.db import Case
from e2e import Recorder, await_crawl
from e2e_round2 import CONTACT
from fixture_input import select_person
from mockweb.run import available, running
from mockweb.seed import photos
from mockweb.seed_round2 import seed_round2


def browser_batch(base, cases, contact):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base, wait_until="networkidle")
            cards = page.get_by_test_id("match-card")
            expect(cards).to_have_count(len(cases))
            expect(page.get_by_test_id("match-total")).to_have_text(f"({len(cases)})")
            expect(cards.filter(has_text="Possible match")).to_have_count(1)
            page.get_by_role("button", name=f"Open match {cases[0]['id']}", exact=True).click()
            dialog = page.get_by_role("dialog")
            expect(
                dialog.get_by_role("heading", name=urlsplit(cases[0]["page_url"]).hostname)
            ).to_be_visible()
            expect(dialog).to_contain_text(cases[0]["possible_action"]["label"])
            expect(dialog).to_contain_text("Rule fallback")
            link = dialog.get_by_role("link", name="Open source page")
            expect(link).to_have_attribute("href", cases[0]["page_url"])
            expect(link).to_have_attribute("target", "_blank")
            expect(link).to_have_attribute("rel", "noreferrer")
            page.keyboard.press("Escape")
            page.get_by_role("button", name="Select all", exact=True).click()
            expect(page.get_by_test_id("selected-count")).to_have_text(f"{len(cases)} selected")
            for item in cases:
                expect(
                    page.get_by_role("checkbox", name=f"Select match {item['id']}", exact=True)
                ).to_be_checked()
            page.get_by_role("button", name="Clear selection").click()
            expect(page.get_by_test_id("selected-count")).to_have_text("0 selected")
            page.get_by_role("button", name="Select all", exact=True).click()
            page.get_by_role("button", name="Auto review / send", exact=True).click()
            expect(page.get_by_test_id("batch-selection").locator("li")).to_have_count(len(cases))
            for key, value in contact.items():
                page.get_by_label(f"Batch contact {key}", exact=True).fill(value)
            page.get_by_label("Who accepts responsibility").fill("Round 3 fixture operator")
            run = page.get_by_role("button", name="Run authorized batch")
            expect(run).to_be_disabled()
            expect(page.get_by_test_id("legal-warning")).to_contain_text("penalty of perjury")
            page.get_by_role(
                "checkbox",
                name="I accept the legal-responsibility warning and authorize this batch.",
            ).check()
            expect(run).to_be_enabled()
            with page.expect_response(
                lambda response: (
                    response.url.endswith("/api/batches") and response.request.method == "POST"
                )
            ) as pending:
                run.click()
            assert pending.value.status == 202, pending.value.text()
            batch_id = pending.value.json()["id"]
            expect(page.get_by_test_id("batch-progress")).to_contain_text(
                "Batch completed", timeout=60000
            )
            for card in cards.all():
                expect(card.get_by_test_id("match-outcome")).to_be_visible()
                assert card.get_by_test_id("match-status").inner_text() in (
                    "Sent",
                    "Failed",
                    "Drafted, not sent",
                    "Held for review",
                    "Left alone",
                )
            page.get_by_role("button", name=f"Open match {cases[0]['id']}", exact=True).click()
            expect(page.get_by_test_id("match-notice")).to_contain_text("Removal request:")
            saved = page.request.get(f"{base.rstrip('/')}/api/cases/{cases[0]['id']}").json()
            assert (
                page.get_by_test_id("match-notice").inner_text()
                == saved["drafted_request"]["payload"]["body"]
            )
            expect(page.get_by_role("dialog")).to_contain_text("Recipient:")
            page.keyboard.press("Escape")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.get_by_role("button", name=f"Open match {cases[0]['id']}", exact=True).click()
            assert page.get_by_role("dialog").evaluate("el => el.scrollWidth <= el.clientWidth")
            assert not errors, errors
            return batch_id, {
                "grid": len(cases),
                "select_all": "passed",
                "warning_gate": "passed",
                "detail": "passed",
                "outcomes": "passed",
                "narrow_overflow": "passed",
                "page_errors": errors,
            }
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=8490)
    parser.add_argument("--base-port", type=int, default=9111)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    start = time.monotonic()
    output = ROOT / "data" / ("round3-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    output.mkdir(parents=True)
    ports = [args.api_port, *range(args.base_port, args.base_port + 9)]
    available(ports)
    source = select_person(args.photos)
    seed_round2(source, output / "mockweb", args.base_port)
    settings = Settings(
        _env_file=None,
        LIKENESS_DATA_DIR=output / "backend",
        openai_api_key="",
        obj_endpoint="",
        obj_bucket="",
        obj_access_key="",
        obj_secret_key="",
        LIKENESS_ALLOW_EXTERNAL_DELIVERY=False,
        LIKENESS_SCHEDULER_POLL=3600,
        LIKENESS_SMTP_RELAY=f"smtp://127.0.0.1:{args.base_port + 7}",
        LIKENESS_RDAP_BOOTSTRAP=f"http://127.0.0.1:{args.base_port + 6}/bootstrap",
        LIKENESS_SEARCH_ENDPOINT=f"http://127.0.0.1:{args.base_port + 5}/report",
    )
    app = create_app(settings)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.api_port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    api = Recorder(f"http://127.0.0.1:{args.api_port}")
    summary = {
        "passed": False,
        "simulated": [
            "copyright model reply",
            "one lookup failure",
            "one external recipient",
            "one possible band",
        ],
    }

    def stop_api():
        server.should_exit = True
        thread.join(timeout=20)
        assert not thread.is_alive(), "API thread did not stop"

    def call(method, path, expected=200, **kwargs):
        response = api.request(method, path, **kwargs)
        assert response.status_code == expected, response.text
        return response.json()

    def receipts():
        return {
            str(index): api.client.get(f"http://127.0.0.1:{args.base_port + index}/receipts").json()
            for index in (0, 1, 2, 3, 4, 5, 8)
        }

    try:
        with ExitStack() as stack:
            stack.enter_context(
                running(output / "mockweb", args.base_port, output / "logs", extended=True)
            )
            thread.start()
            stack.callback(stop_api)
            deadline = time.monotonic() + 20
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert server.started
            files = [
                (kind, (p.name, p.read_bytes(), "image/jpeg"))
                for kind, folder in (("references", "reference"), ("originals", "originals"))
                for p in photos(source / folder)[:1]
            ]
            call(
                "POST",
                "/api/people",
                201,
                data={
                    "name": "Round 3 fixture",
                    "consent": "Local fixture only",
                    "ownership": "Hypothetical local fixture ownership",
                    "development_fixture": "true",
                },
                files=files,
            )
            run = call(
                "POST",
                "/api/crawls",
                202,
                json={
                    "seeds": [f"http://127.0.0.1:{args.base_port + i}/" for i in (0, 1, 2, 3, 8)],
                    "rendered": True,
                },
            )
            assert await_crawl(api, run["id"])["status"] == "completed"
            cases = call("GET", "/api/cases")
            assert len(cases) == 6
            by_path = {Path(item["page_url"]).name: item for item in cases}
            fail_id = by_path["0004.html"]["id"]
            external_id = by_path["0003.html"]["id"]
            different_id = by_path["0002.html"]["id"]
            with app.state.store.session.begin() as session:
                session.get(Case, by_path["0005.html"]["id"]).band = "possible"
            cases = call("GET", "/api/cases")
            body = {
                "case_ids": [item["id"] for item in cases],
                "contact": CONTACT,
                "accepted_by": "Fixture operator",
            }
            for extra in ({}, {"accepted_warning": False}):
                call("POST", "/api/batches", 422, json=body | extra)
                assert all(not rows for rows in receipts().values())
                assert all(item["drafted_request"] is None for item in call("GET", "/api/cases"))
            summary["warning_refusal"] = (
                "missing and false refused; zero independent receipts and drafts"
            )
            real_lookup = app.state.workflow.recipients

            async def controlled_lookup(cid):
                if cid == fail_id:
                    raise RuntimeError("Simulated recipient lookup failure")
                value = await real_lookup(cid)
                if cid == external_id:
                    row = {
                        "id": "simulated-external",
                        "rung": "site",
                        "rank": 1,
                        "channel": "http_form",
                        "address": "https://external.invalid/report",
                        "endpoint": "https://external.invalid/report",
                        "evidence": {"source": "simulated negative case"},
                    }
                    value["recipients"] = [row]
                    with app.state.store.session.begin() as session:
                        session.get(Case, cid).recipients = [row]
                return value

            simulated_calls = []

            def respond(request):
                simulated_calls.append(json.loads(request.content))
                return httpx.Response(
                    200,
                    json={
                        "id": "simulated",
                        "object": "chat.completion",
                        "created": 1,
                        "model": "simulated",
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "stop",
                                "message": {
                                    "role": "assistant",
                                    "content": '{"route":"copyright_notice","reason":"Deliberately incorrect simulated answer"}',
                                },
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    },
                )

            async def controlled_pick(case, text, config):
                if case["id"] != different_id:
                    return await pick_route(case, text, config)
                sdk = openai.AsyncOpenAI(
                    api_key="simulated-only",
                    base_url="http://localhost/v1",
                    http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
                )
                try:
                    model = OpenAIModel(client=sdk, model_id="simulated", stream=False)
                    return await pick_route(case, text, config, model)
                finally:
                    await sdk.close()

            outbound = []
            real_connect = socket.socket.connect

            def local_connect(sock, address):
                if isinstance(address, tuple) and address[0] not in (
                    "127.0.0.1",
                    "::1",
                    "localhost",
                ):
                    outbound.append(str(address))
                    raise AssertionError("Non-loopback connection attempted")
                return real_connect(sock, address)

            stack.enter_context(patch.object(app.state.workflow, "recipients", controlled_lookup))
            stack.enter_context(patch("censearch.batches.pick_route", controlled_pick))
            stack.enter_context(patch.object(socket.socket, "connect", local_connect))
            if args.browser:
                batch_id, browser = browser_batch(str(api.client.base_url), cases, CONTACT)
                summary["browser"] = browser
            else:
                batch_id = call(
                    "POST", "/api/batches", 202, json=body | {"accepted_warning": True}
                )["id"]
            deadline = time.monotonic() + 60
            batch = call("GET", f"/api/batches/{batch_id}")
            while batch["status"] in ("queued", "running") and time.monotonic() < deadline:
                time.sleep(0.1)
                batch = call("GET", f"/api/batches/{batch_id}")
            assert batch["status"] == "completed" and batch["completed"] == 6
            indexed = {item["case_id"]: item for item in batch["items"]}
            assert (
                indexed[fail_id]["status"] == "failed"
                and "lookup failure" in indexed[fail_id]["reason"]
            )
            assert indexed[external_id]["status"] == "drafted_not_sent"
            assert "External delivery disabled" in indexed[external_id]["reason"]
            assert indexed[different_id]["decision"]["route"] == "privacy_request"
            assert indexed[different_id]["decision"]["model_status"] == "guard_downgraded"
            assert len(simulated_calls) == 1 and not outbound, outbound
            received = receipts()
            actual = Counter(
                (row["received_recipient"], row["route"], row["page_url"])
                for rows in received.values()
                for row in rows
            )
            urls = {item["id"]: item["page_url"] for item in cases}
            expected = Counter(
                (item["recipient"]["address"], item["decision"]["route"], urls[item["case_id"]])
                for item in batch["items"]
                if item["status"] == "sent"
            )
            assert actual == expected and sum(actual.values()) == 4, {
                "actual": str(actual),
                "expected": str(expected),
            }
            verified = {}
            for name in ("0001.html", "0002.html"):
                cid = by_path[name]["id"]
                result = call("POST", f"/api/cases/{cid}/verify")
                assert result["outcome"] == "removed" and result["source_removed"]
                verified[name] = result["outcome"]
            for item in batch["items"]:
                view = call("GET", f"/api/cases/{item['case_id']}/workflow")
                assert all(row["value"]["batch_id"] == batch_id for row in view["attestations"])
            summary.update(
                passed=True,
                batch=batch,
                receipts=received,
                verified=verified,
                sent_count=4,
                no_outbound_connections=True,
                simulated_provider_calls=len(simulated_calls),
            )
            print(
                "ROUND3 6/6 checks passed; 4/4 independent recipient receipts; 2/2 removals verified",
                flush=True,
            )
            if args.browser:
                print("BROWSER", json.dumps(summary["browser"]), flush=True)
    finally:
        api.client.close()
        summary["seconds"] = round(time.monotonic() - start, 3)
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
        result = subprocess.run(
            ["lsof", "-nP", *[f"-iTCP:{port}" for port in ports], "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        )
        cleanup = {
            "ports": ports,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2))
        print("CLEANUP", json.dumps(cleanup), flush=True)
        print("OUTPUT", output, "SECONDS", summary["seconds"], flush=True)
        assert not result.stdout.strip(), "Acceptance listeners remain"


if __name__ == "__main__":
    main()
