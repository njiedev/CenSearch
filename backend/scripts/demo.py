"""Start a local fixture demo and keep it available until Ctrl-C."""

import argparse
from contextlib import ExitStack
from datetime import datetime
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
from mockweb.run import available, running, stop
from mockweb.seed import photos, seed


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=8490)
    parser.add_argument("--base-port", type=int, default=9111)
    parser.add_argument("--model", action="store_true", help="use the model key from backend/.env")
    args = parser.parse_args()
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
        OBJ_ENDPOINT="",
        OBJ_BUCKET="",
        OBJ_ACCESS_KEY="",
        OBJ_SECRET_KEY="",
    )
    if not args.model:
        environment["OPENAI_API_KEY"] = ""
    base = f"http://127.0.0.1:{args.api_port}"
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with ExitStack() as stack:
            children = stack.enter_context(running(output / "mockweb", args.base_port, output / "logs"))
            log = stack.enter_context((output / "api.log").open("w"))
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "censearch.api:app",
                 "--host", "127.0.0.1", "--port", str(args.api_port)],
                cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
            )
            stack.callback(stop, process)
            api = Recorder(base)
            stack.callback(api.client.close)
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
            health = api.client.get("/api/health").json()
            response = api.request(
                "POST", "/api/crawls",
                json={"seeds": health["mock_seeds"], "rendered": True, "max_pages": 100},
            )
            response.raise_for_status()
            crawl = await_crawl(api, response.json()["id"])
            cases = api.client.get("/api/cases").json()
            if crawl["status"] != "completed" or not cases:
                raise RuntimeError(f"Find did not produce cases; inspect {output / 'api.log'}")
            print(f"READY: {base} | {len(cases)} cases | Ctrl-C stops the demo.", flush=True)
            print(f"Local fixture data retained at {output}", flush=True)
            if not webbrowser.open(base):
                print("Browser did not open automatically; open the console URL above.", flush=True)
            while True:
                if any(child.poll() is not None for child in [process, *children]):
                    raise RuntimeError(f"A demo process exited; inspect logs in {output}")
                time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nDemo stopped; child processes closed and local data retained.", flush=True)


if __name__ == "__main__":
    main()
