"""Small read-only real-domain run; save GET/tool traces, optional robots decisions and replayable pages."""

import hashlib
import json
import time
from censearch.agent.web import ReadOnlyWeb
from censearch.config import ROOT, Settings
from censearch.recipients import resolve

URLS = [
    "https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy",
    "https://www.wikimedia.org/",
]


def main():
    records = ROOT / "tests/recordings/real"
    records.mkdir(parents=True, exist_ok=True)
    manifest = {}

    def record(response):
        url = str(response.url)
        identifier = hashlib.sha256(url.encode()).hexdigest()[:20]
        name = identifier + ".txt"
        # Only page, optional robots and RDAP content is requested; no face downloads.
        (records / name).write_bytes(response.content)
        manifest[url] = {"file": name, "status": response.status_code, "headers": dict(response.headers)}

    results = []
    for url in URLS:
        start = time.monotonic()
        result = resolve(url, Settings(), ReadOnlyWeb(limit=18, recorder=record))
        result.update(url=url, wall_seconds=round(time.monotonic() - start, 3))
        results.append(result)
        print(
            json.dumps(
                {
                    "url": url,
                    "source": result["source"],
                    "seconds": result["wall_seconds"],
                    "requests": sum("method" in row for row in result["requests"]),
                    "contacts": [
                        {k: c[k] for k in ("rung", "channel", "address")} for c in result["recipients"]
                    ],
                    "tool_errors": [
                        row for row in result["tool_calls"] if row["result"].get("status") == "error"
                    ],
                }
            ),
            flush=True,
        )
    (records / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "reports/real_recipient_lookups.json").write_text(json.dumps(results, indent=2) + "\n")
    print("TOTAL_GETS", sum(sum("method" in row for row in r["requests"]) for r in results))


if __name__ == "__main__":
    main()
