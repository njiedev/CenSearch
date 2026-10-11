"""Real loopback HTTP enroll/crawl plus optional Playwright console acceptance."""

import argparse
from contextlib import ExitStack
from datetime import datetime
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import httpx
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from mockweb.run import available, running, stop
from fixture_input import select_person
from mockweb.seed import photos, seed
from score import score

ROOT = Path(__file__).resolve().parents[1]


class Recorder:
    def __init__(self, base):
        self.client = httpx.Client(base_url=base, timeout=60, trust_env=False)
        self.examples = []

    def request(self, method, path, *, example=True, **kwargs):
        response = self.client.request(method, path, **kwargs)
        content_type = response.headers.get("content-type", "")
        body = (
            response.json()
            if "application/json" in content_type
            else {
                "content_type": content_type,
                "byte_length": len(response.content),
                "sha256": hashlib.sha256(response.content).hexdigest(),
            }
        )
        if example:
            request = {key: value for key, value in kwargs.items() if key in ("json", "data")}
            if "files" in kwargs:
                request["files"] = [
                    {"field": name, "filename": parts[0], "bytes": len(parts[1]), "content_type": parts[2]}
                    for name, parts in kwargs["files"]
                ]
            self.examples.append(
                {
                    "method": method,
                    "path": path,
                    "request": request,
                    "status": response.status_code,
                    "response": body,
                }
            )
        return response


def wait_ready(api, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("API exited; see api.log")
        try:
            response = api.client.get("/api/health")
            if response.status_code == 200:
                if not response.json()["face_models"]["loaded"]:
                    raise RuntimeError(response.text)
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise TimeoutError("API did not become ready")


def await_crawl(api, identifier):
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        response = api.request("GET", f"/api/crawls/{identifier}", example=False)
        response.raise_for_status()
        value = response.json()
        if value["status"] not in ("queued", "running"):
            api.request("GET", f"/api/crawls/{identifier}")
            return value
        time.sleep(0.15)
    raise TimeoutError("Crawl exceeded 100 seconds")


def browser_flow(base, person, output):
    """Uses the brief's explicitly requested local Playwright workflow."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
        )
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900}, permissions=["camera"])
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base, wait_until="networkidle")
            expect(page.get_by_test_id("health-summary")).to_contain_text("Face models: loaded")
            page.get_by_role("button", name="Enroll", exact=True).click()
            page.get_by_label("Name", exact=True).fill("Browser fixture")
            page.get_by_label("Consent statement").fill(
                "Local fixture for browser acceptance; no real consent claim"
            )
            page.get_by_label("Reference photos", exact=True).set_input_files(
                str(photos(person / "reference")[0])
            )
            page.get_by_label("Owned original photos (optional)").set_input_files(
                str(photos(person / "originals")[0])
            )
            page.get_by_label("Ownership statement (required with originals)").fill(
                "Hypothetical fixture only"
            )
            page.get_by_label("Local development fixture, not a real consent or ownership claim").check()
            page.get_by_role("button", name="Enroll person", exact=True).click()
            expect(page.get_by_text("Enrollment saved", exact=True)).to_be_visible(timeout=15000)
            page.screenshot(path=str(output / "console-enroll.png"), full_page=True)
            # Exercise actual capture plumbing with Chromium's synthetic camera.
            # It is not presented as verification on a person's live camera.
            page.get_by_role("button", name="Start webcam", exact=True).click()
            expect(page.get_by_label("Webcam preview")).to_be_visible()
            page.wait_for_function("document.querySelector('video').videoWidth > 0")
            page.get_by_role("button", name="Capture reference", exact=True).click()
            expect(page.get_by_role("button", name="Remove capture 1")).to_be_visible()
            page.get_by_role("button", name="Remove capture 1").click()
            page.get_by_role("button", name="Stop webcam", exact=True).click()
            page.get_by_role("button", name="Find", exact=True).click()
            page.get_by_role("button", name="Start crawl", exact=True).click()
            expect(page.get_by_test_id("crawl-status")).to_have_text("Crawl 2: completed", timeout=100000)
            expect(page.get_by_test_id("case-card").first).to_be_visible()
            expect(page.get_by_test_id("case-card").first.locator("img")).to_be_visible()
            page.wait_for_function(
                "[...document.querySelectorAll('[data-testid=case-card] img')]"
                ".every(i => i.complete && i.naturalWidth > 0)"
            )
            page.screenshot(path=str(output / "console-find.png"), full_page=True)
            page.get_by_role("button", name="Open case", exact=False).first.click()
            expect(page.get_by_text("Case record", exact=True)).to_be_visible()
            page.screenshot(path=str(output / "console-case.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "console-mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                "Narrow screen overflows"
            )
            page.get_by_role("button", name="Enroll", exact=True).click()
            page.get_by_role("button", name="Delete Browser fixture", exact=True).click()
            expect(page.get_by_text("No people enrolled yet.", exact=True)).to_be_visible()
            # Invalid upload must show the actual quality rejection in the screen.
            page.get_by_label("Name", exact=True).fill("Rejected browser fixture")
            page.get_by_label("Consent statement").fill("Local test")
            blank = BytesIO()
            Image.new("RGB", (250, 250), "white").save(blank, "PNG")
            page.get_by_label("Reference photos", exact=True).set_input_files(
                {"name": "blank.png", "mimeType": "image/png", "buffer": blank.getvalue()}
            )
            page.get_by_role("button", name="Enroll person", exact=True).click()
            expect(page.get_by_role("alert")).to_contain_text("photo_rejected")
            page.screenshot(path=str(output / "console-rejected.png"), full_page=True)
            assert not errors, errors
            return {
                "enroll": "passed",
                "find": "passed",
                "case": "passed",
                "delete": "passed",
                "rejection": "passed",
                "webcam": "synthetic Chromium capture passed; physical camera untested",
                "page_errors": errors,
                "narrow_overflow": False,
            }
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--person", help="Folder name; defaults to first person, without name-specific rules")
    parser.add_argument("--base-port", type=int, default=8811)
    parser.add_argument("--api-port", type=int, default=8190)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    output = ROOT / "data" / ("e2e-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    output.mkdir(parents=True)
    photo_root = args.photos.resolve()
    person = select_person(args.photos, args.person)
    # A small input set copied only inside ignored data. Originals stay read-only.
    import shutil

    fixture_folder = output / "photos"
    for category in ("reference", "originals", "wild"):
        target = fixture_folder / "demo-person" / category
        target.mkdir(parents=True)
        limit = 3 if category in ("reference", "wild") else 1
        for index, source in enumerate(photos(person / category)[:limit]):
            shutil.copyfile(source, target / f"{category}-{index + 1}{source.suffix}")
    (fixture_folder / "distractors").mkdir()
    if (photo_root / "distractors").exists():
        for index, source in enumerate(photos(photo_root / "distractors")[:4]):
            shutil.copyfile(source, fixture_folder / "distractors" / f"distractor-{index + 1}{source.suffix}")
    (fixture_folder / "FIXTURE_ONLY").write_text("Local development fixtures. Never upload.\n")
    seed_result = seed(fixture_folder, output / "mockweb", args.base_port)
    print("SEED", json.dumps(seed_result), flush=True)
    available([args.api_port])
    base = f"http://127.0.0.1:{args.api_port}"
    api = Recorder(base)
    environment = dict(
        os.environ,
        LIKENESS_DATA_DIR=str(output / "backend"),
        MOCK_BASE_PORT=str(args.base_port),
        ALLOW_PUBLIC_CRAWL="false",
        OBJ_ENDPOINT="",
        OBJ_BUCKET="",
        OBJ_ACCESS_KEY="",
        OBJ_SECRET_KEY="",
    )
    summary = {"output": str(output), "browser": "not requested"}
    try:
        with ExitStack() as stack:
            stack.enter_context(running(output / "mockweb", args.base_port, output / "logs"))
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
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            stack.callback(stop, process)
            wait_ready(api, process)
            health = api.request("GET", "/api/health").json()
            assert health["object_storage"]["mode"] == "local_disk"
            openapi = api.client.get("/openapi.json")
            openapi.raise_for_status()
            (ROOT / "handoff/openapi.json").write_text(json.dumps(openapi.json(), indent=2) + "\n")
            api.request("GET", "/api/people")
            api.request("GET", "/api/cases")
            data = {
                "name": "demo-person",
                "consent": "Local development fixture; no claim of real consent",
                "ownership": "Hypothetical local fixture, not a copyright assertion",
                "development_fixture": "true",
            }
            files = [
                ("references", (path.name, path.read_bytes(), "image/jpeg"))
                for path in photos(fixture_folder / "demo-person" / "reference")
            ]
            files.extend(
                ("originals", (path.name, path.read_bytes(), "image/jpeg"))
                for path in photos(fixture_folder / "demo-person" / "originals")
            )
            response = api.request("POST", "/api/people", data=data, files=files)
            assert response.status_code == 201, response.text
            enrolled = response.json()["person"]
            api.request("GET", f"/api/people/{enrolled['id']}")
            response = api.request(
                "POST",
                "/api/crawls",
                json={"seeds": health["mock_seeds"], "rendered": True, "max_pages": 100},
            )
            assert response.status_code == 202, response.text
            run_id = response.json()["id"]
            run = await_crawl(api, run_id)
            print("CRAWL", json.dumps(run), flush=True)
            assert run["status"] == "completed", run
            api.request("GET", "/api/crawls")
            cases = api.request("GET", f"/api/cases?run_id={run_id}").json()
            scans = api.request("GET", f"/api/scans?run_id={run_id}").json()
            snapshot = {"cases": cases, "scans": scans, "identity_map": {"demo-person": enrolled["id"]}}
            (output / "snapshot.json").write_text(json.dumps(snapshot, indent=2))
            scores = score(output / "mockweb/ground_truth.json", cases, scans, snapshot["identity_map"])
            (output / "scores.json").write_text(json.dumps(scores, indent=2))
            print(
                "CASES",
                json.dumps(
                    [
                        {
                            key: item[key]
                            for key in ("id", "page_url", "match_type", "band", "score", "photo_relation")
                        }
                        for item in cases
                    ]
                ),
                flush=True,
            )
            print("SCORES", json.dumps(scores), flush=True)
            assert cases, "No cases found"
            # The legacy scorer counts discoveries behind robots exclusions.
            # These are expected with enforcement disabled; retain the raw score.
            summary["robots_policy"] = {
                "respect_robots": api.request("GET", "/api/health").json()["respect_robots"],
                "legacy_robots_violations": scores["robots_violations"],
            }
            if summary["robots_policy"]["respect_robots"]:
                assert scores["robots_violations"] == 0
            retained_paths = {item["evidence"]["image"]["path"] for item in cases}
            retained_paths.update(item["path"] for item in enrolled["references"])
            retained_paths.update(item["path"] for item in enrolled["originals"])
            actual_paths = {
                str(path.relative_to(output / "backend"))
                for path in (output / "backend/people").rglob("*")
                if path.is_file()
            }
            assert actual_paths == retained_paths, "Unexpected persisted pixels, crops or sidecars"
            summary["privacy_file_audit"] = {
                "expected": len(retained_paths),
                "actual": len(actual_paths),
                "passed": True,
            }
            for log_path in (output / "logs").glob("mock-*.log"):
                for line in log_path.read_text().splitlines():
                    if not line.startswith('{"path"'):
                        continue
                    entry = json.loads(line)
                    if summary["robots_policy"]["respect_robots"]:
                        assert not entry["path"].startswith("/private/"), entry
                    assert entry["user_agent"].startswith("LikenessGuard/"), entry
            # Print actual recall, including misses; do not tune or demand perfect scores.
            for item in cases:
                response = api.request("GET", item["matched_image_url"], example=item == cases[0])
                assert response.status_code == 200
                assert hashlib.sha256(response.content).hexdigest() == item["evidence"]["image"]["sha256"]
            api.request("GET", f"/api/cases/{cases[0]['id']}")
            api.request("GET", "/api/cases/999999")
            api.request("POST", "/api/crawls", json={"seeds": []})
            api.request(
                "POST",
                "/api/people",
                data={"name": "Bad fixture", "consent": "Local testing"},
                files=[("references", ("bad.jpg", b"not an image", "image/jpeg"))],
            )
            probe = api.request("POST", "/api/agent/probe", json={"hostname": "localhost"}).json()
            print("PROBE", json.dumps(probe), flush=True)
            summary.update(
                scores=scores, model_probe=probe, live_model_call_run=health["model"]["configured"]
            )
            response = api.request("DELETE", f"/api/people/{enrolled['id']}")
            assert response.status_code == 200
            assert api.client.get("/api/cases").json() == []
            assert not (output / "backend/people" / enrolled["id"]).exists()
            if args.browser:
                summary["browser"] = browser_flow(base, fixture_folder / "demo-person", output)
                print("BROWSER", json.dumps(summary["browser"]), flush=True)
    finally:
        api.client.close()
        (output / "api-examples.json").write_text(json.dumps(api.examples, indent=2))
        summary["wall_seconds"] = round(time.monotonic() - started, 3)
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
        (ROOT / "data/latest-e2e.txt").write_text(str(output))
        ports = [args.api_port, *range(args.base_port, args.base_port + 8)]
        check = subprocess.run(
            ["lsof", "-nP", *[f"-iTCP:{port}" for port in ports], "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        )
        cleanup = {
            "ports": ports,
            "exit_code": check.returncode,
            "stdout": check.stdout,
            "stderr": check.stderr,
        }
        (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2))
        print("CLEANUP", json.dumps(cleanup), flush=True)
        print("OUTPUT", output, flush=True)
        if check.stdout.strip():
            raise RuntimeError("Listeners remain on acceptance ports; see cleanup.json")


if __name__ == "__main__":

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    main()
