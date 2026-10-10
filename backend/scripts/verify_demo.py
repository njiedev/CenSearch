"""Text-only lifecycle verification for the stay-open demo."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    log_path = ROOT / "data/fix-demo.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        process = subprocess.Popen(
            ["make", "demo"],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 120
            while "READY:" not in log_path.read_text():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"Demo failed to reach READY; see {log_path}")
                time.sleep(0.25)
            with httpx.Client(base_url="http://127.0.0.1:8490", trust_env=False) as client:
                people = client.get("/api/people").json()
                cases = client.get("/api/cases").json()
                print(json.dumps({"people": len(people), "cases": len(cases),
                                  "still_running": process.poll() is None}), flush=True)
                assert people and cases
                time.sleep(2)
                assert process.poll() is None
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
            process.wait(timeout=30)
        free = []
        for port in [8490, *range(9111, 9119)]:
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(("127.0.0.1", port))
                free.append(port)
        print(json.dumps({"free_ports_after_sigint": free}), flush=True)
        listeners = subprocess.run(
            ["lsof", "-nP", "-iTCP:" + ",".join(map(str, free)), "-sTCP:LISTEN"],
            capture_output=True, text=True,
        )
        print(json.dumps({"lsof_exit": listeners.returncode, "listeners": listeners.stdout,
                          "lsof_warnings": listeners.stderr}), flush=True)
        assert listeners.returncode == 1 and not listeners.stdout
        output_line = next(line for line in log_path.read_text().splitlines()
                           if line.startswith("Local fixture data retained at "))
        output = Path(output_line.removeprefix("Local fixture data retained at "))
        import sqlite3

        with sqlite3.connect(output / "backend/likeness.sqlite") as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                      for table in ("people", "cases") if table in tables}
        print(json.dumps({"persisted_after_exit": counts}), flush=True)


if __name__ == "__main__":
    main()
