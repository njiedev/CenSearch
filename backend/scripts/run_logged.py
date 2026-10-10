"""Record a command's exact output, exit code and elapsed wall time."""

import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
logs = root / "data/checks"
logs.mkdir(parents=True, exist_ok=True)
command = sys.argv[1:]
started = time.monotonic()
result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
elapsed = time.monotonic() - started
entry = {
    "at": datetime.datetime.now().isoformat(),
    "command": command,
    "exit_code": result.returncode,
    "wall_seconds": round(elapsed, 3),
    "output": result.stdout,
}
with (logs / "commands.jsonl").open("a") as stream:
    stream.write(json.dumps(entry) + "\n")
print(result.stdout, end="")
print(f"EXIT={result.returncode} WALL={elapsed:.3f}s")
sys.exit(result.returncode)
