"""Start a local fixture demo and keep it available until Ctrl-C."""

import argparse
from contextlib import ExitStack
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import webbrowser

from e2e import ROOT, Recorder, await_crawl, wait_ready
from fixture_input import select_person
from mockweb.run import available, ignore_shutdown_signals, interrupted, running, stop
from mockweb.seed import photos, seed
from mockweb.seed_three import seed_three


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=8490)
    parser.add_argument("--base-port", type=int, default=9111)
    parser.add_argument("--model", action="store_true", help="use the model key from backend/.env")
    parser.add_argument("--no-browser", action="store_true", help="run without opening the console")
    parser.add_argument("--three", action="store_true", help="three staged photo pages and the dashboard")
    parser.add_argument("--resend-test", action="store_true",
                        help="send fictional notice text to Resend's test recipient; no site removal")
    args = parser.parse_args()
    if args.resend_test and not args.three:
        raise SystemExit("--resend-test requires --three")
    source = select_person(args.photos)
    ports = [args.api_port, *range(args.base_port, args.base_port + 8)]
    if len(set(ports)) != len(ports) or not all(1024 <= port <= 65535 for port in ports):
        raise SystemExit("Choose distinct API and mock ports between 1024 and 65535.")
    available(ports)
    output = ROOT / "data" / ("demo-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    fixture = output / "photos/demo-person"
    for category in ("reference", "originals", "wild"):
        folder = fixture / category
        folder.mkdir(parents=True)
        limit = 1 if category == "originals" else 3
        for index, path in enumerate(photos(source / category)[:limit]):
            shutil.copyfile(path, folder / f"{category}-{index + 1}{path.suffix}")
    (fixture.parent / "FIXTURE_ONLY").write_text("Local dataset fixtures; never upload.\n")
    seeds = seed_three(fixture, output / "mockweb", args.base_port, args.resend_test) if args.three else None
    if not args.three:
        seed(fixture.parent, output / "mockweb", args.base_port)
    environment = dict(
        os.environ,
        LIKENESS_DATA_DIR=str(output / "backend"),
        MOCK_BASE_PORT=str(args.base_port),
        ALLOW_PUBLIC_CRAWL="false",
        LIKENESS_ALLOW_EXTERNAL_DELIVERY="false",
        LIKENESS_DEMO_CLOCK="true",
        LIKENESS_SMTP_RELAY=f"smtp://127.0.0.1:{args.base_port + 7}",
        LIKENESS_RDAP_BOOTSTRAP=f"http://127.0.0.1:{args.base_port + 6}/bootstrap",
        LIKENESS_SEARCH_ENDPOINT=f"http://127.0.0.1:{args.base_port + 5}/report",
        CENSEARCH_EMAIL_ENABLED="false",
        CENSEARCH_DEMO_RESEND="true" if args.resend_test else "false",
        RESEND_API_KEY="",
        FACECHECK_API_TOKEN="",
        SERPAPI_API_KEY="",
        OBJ_ENDPOINT="",
        OBJ_BUCKET="",
        OBJ_ACCESS_KEY="",
        OBJ_SECRET_KEY="",
    )
    if not args.model:
        environment["OPENAI_API_KEY"] = ""
    mail_command = None
    mail_env = None
    if args.resend_test:
        from censearch.config import Settings

        key = Settings().resend_api_key.get_secret_value()
        if not key:
            raise SystemExit("Set RESEND_API_KEY privately in backend/.env before using --resend-test")
        mail_env = dict(os.environ, RESEND_API_KEY=key)
        mail_command = [sys.executable, "-m", "mockweb.resend_demo", "--port", str(args.base_port + 7),
                        "--site-port", str(args.base_port), "--run-id", output.name,
                        "--state-dir", str(output / "resend")]
    if args.three:
        frontend = ROOT.parent / "frontend/dist"
        if not (frontend / "app/index.html").is_file():
            raise SystemExit("Build the frontend first: npm --prefix ../frontend run build")
        local_frontend = output / "frontend"
        shutil.copytree(frontend, local_frontend)
        environment["LIKENESS_FRONTEND_DIR"] = str(local_frontend)
    base = f"http://127.0.0.1:{args.api_port}"
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with ExitStack() as stack:
            children = stack.enter_context(running(
                output / "mockweb", args.base_port, output / "logs",
                mail_command=mail_command, mail_env=mail_env,
            ))
            log = stack.enter_context((output / "api.log").open("w"))
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "censearch.api:app",
                 "--host", "127.0.0.1", "--port", str(args.api_port)],
                cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
            )
            stack.callback(stop, process)
            api = Recorder(base)
            stack.callback(api.client.close)
            # First callback on unwind: protect the entire ExitStack, even if
            # cleanup began because of a startup error instead of a signal.
            stack.callback(ignore_shutdown_signals)
            wait_ready(api, process)
            files = [
                (kind, (path.name, path.read_bytes(), "image/jpeg"))
                for kind, folder in (("references", "reference"), ("originals", "originals"))
                for path in photos(fixture / folder)
            ]
            response = api.request(
                "POST", "/api/people", files=files,
                data={
                    "name": "demo-person",
                    "consent": "Local development fixture; no real consent claim",
                    "ownership": "Local development fixture; no ownership claim",
                    "development_fixture": "true",
                },
            )
            response.raise_for_status()
            person = response.json()["person"]
            health = api.client.get("/api/health").json()
            response = api.request(
                "POST", "/api/crawls",
                json={"seeds": seeds or health["mock_seeds"], "rendered": True, "max_pages": 100},
            )
            response.raise_for_status()
            crawl = await_crawl(api, response.json()["id"])
            cases = api.client.get("/api/cases").json()
            if crawl["status"] != "completed" or not cases:
                raise RuntimeError(f"Find did not produce cases; inspect {output / 'api.log'}")
            destination = base + "/console/"
            if args.three:
                if len(cases) != 3 or {row["page_url"] for row in cases} != set(seeds):
                    raise RuntimeError(f"Expected exactly three matched pages, got {len(cases)} cases")
                session = json.dumps({"id": person["id"], "name": person["name"]}).replace("<", "\\u003c")
                (local_frontend / "demo.html").write_text(
                    '<!doctype html><title>Open local demo</title><script>'
                    f'localStorage.setItem("censearch.session",JSON.stringify({session}));'
                    'sessionStorage.removeItem("censearch.live");'
                    f'location.replace("/app/#scan/{crawl["id"]}");</script>'
                )
                destination = base + "/demo.html"
                manifest = {"dashboard": destination, "website": f"http://127.0.0.1:{args.base_port}/",
                            "pages": seeds, "person_id": person["id"], "run_id": crawl["id"],
                            "case_ids": [row["id"] for row in cases],
                            "transport": "Resend test recipient" if args.resend_test else "local SMTP",
                            "model_enabled": args.model}
                (output / "demo.json").write_text(json.dumps(manifest, indent=2))
                print(f"Website: {manifest['website']} | Transport: {manifest['transport']}", flush=True)
                if not args.model:
                    print("Model disabled: fallback cannot distinguish permission from page text. Use --model.", flush=True)
            print(f"READY: {destination} | {len(cases)} cases | Ctrl-C stops the demo.", flush=True)
            print(f"Local fixture data retained at {output}", flush=True)
            if not args.no_browser and not webbrowser.open(destination):
                print("Browser did not open automatically; open the console URL above.", flush=True)
            while True:
                if any(child.poll() is not None for child in [process, *children]):
                    raise RuntimeError(f"A demo process exited; inspect logs in {output}")
                time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nDemo stopped; child processes closed and local data retained.", flush=True)


if __name__ == "__main__":
    main()
