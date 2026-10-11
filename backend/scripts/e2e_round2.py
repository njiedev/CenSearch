"""Real HTTP/SMTP workflow acceptance; fixture actions are independent of scorer ground truth."""

import argparse
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from e2e import Recorder, await_crawl, wait_ready
from mockweb.run import available, running, stop
from fixture_input import select_person
from mockweb.seed import photos
from mockweb.seed_round2 import seed_round2
from score_round2 import score

ROOT = Path(__file__).resolve().parents[1]
CONTACT = {
    "name": "Demo operator",
    "email": "operator@example.test",
    "signature": "Demo operator",
    "address": "Local fixture address",
    "phone": "555-0100",
}
FACTS = {
    "identity_confirmed": True,
    "authorized_use": False,
    "accurate": True,
    "good_faith": True,
    "authority_under_perjury": True,
    "work_description": "Hypothetical local fixture original; no actual ownership claim",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=8190)
    parser.add_argument("--base-port", type=int, default=8911)
    args = parser.parse_args()
    start = time.monotonic()
    output = ROOT / "data" / ("round2-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    output.mkdir(parents=True)
    source = select_person(args.photos)
    fixture = output / "photos/demo-person"
    for category in ("reference", "originals", "wild"):
        folder = fixture / category
        folder.mkdir(parents=True)
        for index, path in enumerate(photos(source / category)[: 3 if category == "reference" else 1]):
            shutil.copyfile(path, folder / f"{category}-{index + 1}{path.suffix}")
    (fixture / "FIXTURE_ONLY").write_text("Local development only; never upload")
    seed_round2(fixture, output / "mockweb", args.base_port)
    available([args.api_port])
    base = f"http://127.0.0.1:{args.api_port}"
    api = Recorder(base)
    env = dict(
        os.environ,
        LIKENESS_DATA_DIR=str(output / "backend"),
        MOCK_BASE_PORT=str(args.base_port),
        LIKENESS_DEMO_CLOCK="1",
        LIKENESS_SCHEDULER_POLL="3600",
        OPENAI_API_KEY="",
        OBJ_ENDPOINT="",
        OBJ_BUCKET="",
        OBJ_ACCESS_KEY="",
        OBJ_SECRET_KEY="",
        LIKENESS_SMTP_RELAY=f"smtp://127.0.0.1:{args.base_port + 7}",
        LIKENESS_RDAP_BOOTSTRAP=f"http://127.0.0.1:{args.base_port + 6}/bootstrap",
        LIKENESS_SEARCH_ENDPOINT=f"http://127.0.0.1:{args.base_port + 5}/report",
    )
    env.pop("LIKENESS_ALLOW_EXTERNAL_DELIVERY", None)
    summary = {
        "passed": False,
        "live_model_call_made": False,
        "disclaimer": "Hypothetical scripted assertions over local research fixtures, not real claims.",
    }
    try:
        with ExitStack() as stack:
            stack.enter_context(running(output / "mockweb", args.base_port, output / "logs", extended=True))
            log = stack.enter_context((output / "api.log").open("w"))
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "censearch.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.api_port),
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            stack.callback(stop, process)
            wait_ready(api, process)

            def call(method, path, expected=200, **kwargs):
                response = api.request(method, path, **kwargs)
                assert response.status_code == expected, (
                    f"{method} {path}: {response.status_code} {response.text}"
                )
                return response.json()

            def post(cid, action, payload=None, expected=200):
                return call(
                    "POST",
                    f"/api/cases/{cid}/{action}",
                    expected,
                    **({"json": payload} if payload is not None else {}),
                )

            def admin(port, action, target):
                response = api.client.post(
                    f"http://127.0.0.1:{port}/admin",
                    headers={"X-Mock-Admin": "local-mock-admin"},
                    json={"action": action, "path": target},
                )
                assert response.status_code == 200, response.text

            health = call("GET", "/api/health")
            assert not health["external_delivery_enabled"]
            files = [
                (kind, (p.name, p.read_bytes(), "image/jpeg"))
                for kind, folder in (("references", "reference"), ("originals", "originals"))
                for p in photos(fixture / folder)
            ]
            person = call(
                "POST",
                "/api/people",
                201,
                data={
                    "name": "demo-person",
                    "consent": "Local fixture only",
                    "ownership": "Hypothetical ownership only",
                    "development_fixture": "true",
                },
                files=files,
            )["person"]
            seeds = [f"http://127.0.0.1:{args.base_port + i}/" for i in (0, 1, 2, 3, 8)]
            run = call("POST", "/api/crawls", 202, json={"seeds": seeds, "rendered": True})
            completed = await_crawl(api, run["id"])
            assert completed["status"] == "completed", completed
            cases = call("GET", "/api/cases")
            assert len(cases) == 6, {"case_count": len(cases), "crawl": completed}
            by_path = {Path(item["page_url"]).name: item for item in cases}
            primary = by_path["0001.html"]["id"]
            post(primary, "send", expected=422)
            post(primary, "draft", {"recipient_id": "missing"}, expected=422)
            adverse = {}
            for mode, expected in (
                ("blocked", "blocked"),
                ("unreachable", "unreachable"),
                ("timeout", "unreachable"),
                ("replace", "replaced"),
            ):
                admin(args.base_port, mode, "/media/0001.jpg")
                result = post(primary, "verify")
                assert result["outcome"] == expected and result["source_removed"] is False, result
                adverse[mode] = result["outcome"]
                admin(args.base_port, "restore_bytes" if mode == "replace" else "restore", "/media/0001.jpg")
            summary["adverse_verification"] = adverse
            # Separate hosting administrator ignores one requested target, while acting on the other.
            admin(args.base_port + 4, "ignore", "/media/0005.jpg")

            def draft_send(cid, rung):
                view = call("GET", f"/api/cases/{cid}/workflow")
                recipients = view["lookup"]["recipients"]
                recipient = next(
                    row
                    for row in recipients
                    if row["rung"] == rung and row["channel"] in ("smtp", "http_form")
                )
                post(cid, "draft", {"recipient_id": recipient["id"], "rung": rung}, expected=422)
                post(
                    cid,
                    "approve-draft",
                    {"approved_by": "Demo operator", "revision": view["revision"], "rung": rung},
                )
                notice = post(cid, "draft", {"recipient_id": recipient["id"], "rung": rung})
                post(cid, "send", expected=422)
                post(
                    cid,
                    "approve",
                    {"notice_id": notice["id"], "sha256": notice["sha256"], "approved_by": "Demo operator"},
                )
                delivery = post(cid, "send")
                post(cid, "send", expected=422)
                return delivery

            actions = [
                ("0001.html", {"owns_photo": True}),
                ("0002.html", {"impersonates_me": True}),
                ("0003.html", {"legitimate_use": True}),
                ("0004.html", {"owns_photo": True}),
                ("0005.html", {"owns_photo": True}),
                ("0006.html", {"privacy_request": True}),
            ]
            for filename, values in actions:
                cid = by_path[filename]["id"]
                description = post(cid, "description")
                assert description["status"] == "model_not_configured"
                view = post(
                    cid,
                    "answers",
                    {"answered_by": "Demo operator", "answers": FACTS | values, "contact": CONTACT},
                )
                call("GET", f"/api/cases/{cid}/route")
                if values.get("legitimate_use"):
                    assert view["decision"]["route"] == "leave_alone"
                    post(
                        cid,
                        "approve-draft",
                        {"approved_by": "Demo operator", "revision": view["revision"]},
                        expected=422,
                    )
                    continue
                bundle = post(cid, "evidence")
                response = api.request("GET", bundle["screenshot_url"])
                assert response.status_code == 200
                assert hashlib.sha256(response.content).hexdigest() == bundle["screenshot"]["sha256"]
                lookup = post(cid, "recipients")
                assert lookup["source"] == "deterministic_baseline", lookup
                draft_send(cid, "site")
            tick = call("POST", "/api/clock/advance", json={"seconds": 172801})
            summary["site_deadline"] = tick
            for filename in ("0004.html", "0005.html"):
                cid = by_path[filename]["id"]
                assert call("GET", f"/api/cases/{cid}/workflow")["next_rung"] == "host"
                draft_send(cid, "host")
            summary["host_deadline"] = call("POST", "/api/clock/advance", json={"seconds": 172801})
            draft_send(by_path["0005.html"]["id"], "search")
            # Advancing yet again must never escalate the reasoned refusal.
            call("POST", "/api/clock/advance", json={"seconds": 172801})
            call("POST", "/api/scheduler/tick")
            results = []
            for item in cases:
                view = call("GET", f"/api/cases/{item['id']}/workflow")
                checked = post(item["id"], "verify")
                results.append(
                    {
                        "page_url": item["page_url"],
                        "route": view["decision"]["route"],
                        "deliveries": view["deliveries"],
                        "check": checked,
                        "state": view["state"],
                    }
                )
            receipts = {
                site: api.client.get(f"http://127.0.0.1:{args.base_port + index}/receipts").json()
                for site, index in (
                    ("pixboard", 0),
                    ("friendlink", 1),
                    ("localnews", 2),
                    ("shadygallery", 3),
                    ("host", 4),
                    ("search", 5),
                    ("editorial", 8),
                )
            }
            delisted = api.client.get(f"http://127.0.0.1:{args.base_port + 5}/search-results").json()[
                "delisted"
            ]
            scores = score(output / "mockweb/ground_truth.json", results, receipts, delisted)
            summary.update(
                scores=scores, results=results, receipts=receipts, passed=scores["passed"] == scores["total"]
            )
            print("SCORES", json.dumps(scores), flush=True)
            assert scores["passed"] == scores["total"], scores
            assert receipts["localnews"] == []
            assert len(receipts["editorial"]) == 1 and results[-1]["state"] == "decision_required"
            advisory = post(by_path["0006.html"]["id"], "reply-analysis", {"text": "Licensed editorial use"})
            assert advisory["status"] == "model_not_configured" and advisory["advisory"] is True
            call("GET", f"/api/cases/{primary}/draft")
            schema = api.client.get("/openapi.json").json()
            (output / "openapi.json").write_text(json.dumps(schema, indent=2) + "\n")
            (ROOT / "handoff/openapi.json").write_text(json.dumps(schema, indent=2) + "\n")
            # Preserve the run for review; deletion is covered separately by pytest and round 1 E2E.
            summary["person_id"] = person["id"]
    finally:
        api.client.close()
        (output / "api-examples.json").write_text(json.dumps(api.examples, indent=2) + "\n")
        summary["wall_seconds"] = round(time.monotonic() - start, 3)
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        (ROOT / "data/latest-round2.txt").write_text(str(output))
        ports = [args.api_port, *range(args.base_port, args.base_port + 9)]
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
        (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2) + "\n")
        print("CLEANUP", json.dumps(cleanup), flush=True)
        print("OUTPUT", output, "SECONDS", summary["wall_seconds"], flush=True)
        assert not result.stdout.strip(), "Acceptance listeners remain"


if __name__ == "__main__":

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    main()
