"""Time a local demo batch using text-only API responses; never read fixture images."""

import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="all")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with httpx.Client(base_url="http://127.0.0.1:8490", timeout=15, trust_env=False) as client:
        response = client.get("/api/cases")
        response.raise_for_status()
        cases = response.json()
        ids = [case["id"] for case in cases] if args.cases == "all" else [
            int(value) for value in args.cases.split(",")
        ]
        started = time.monotonic()
        response = client.post("/api/batches", json={
            "case_ids": ids,
            "contact": {
                "name": "Demo Operator", "email": "operator@example.test",
                "address": "1 Example Street, Testville", "phone": "555-0100",
                "signature": "Demo Operator",
            },
            "accepted_by": "Demo Operator", "accepted_warning": True,
        })
        response.raise_for_status()
        batch_id = response.json()["id"]
        while True:
            response = client.get(f"/api/batches/{batch_id}")
            response.raise_for_status()
            batch = response.json()
            if batch["completed"] == batch["total"]:
                break
            if time.monotonic() - started > 600:
                raise TimeoutError(f"Batch {batch_id} exceeded 600 seconds")
            time.sleep(0.2)
        elapsed = time.monotonic() - started
        rows = []
        for item in batch["items"]:
            response = client.get(f"/api/cases/{item['case_id']}/workflow")
            response.raise_for_status()
            view = response.json()
            lookup = view.get("lookup") or {}
            decision = item["decision"]
            rows.append({
                "case_id": item["case_id"], "status": item["status"], "reason": item["reason"],
                "route": decision.get("route"), "route_source": decision.get("source"),
                "model_status": decision.get("model_status"),
                "route_metrics": decision.get("model_metrics", {}),
                "lookup_source": lookup.get("source"),
                "lookup_model_status": lookup.get("model_status"),
                "reused": lookup.get("reused"), "source_case_id": lookup.get("source_case_id"),
                "lookup_metrics": lookup.get("model_metrics", {}),
                "lookup_agent_attempt": lookup.get("agent_attempt", {}).get("model_metrics", {}),
                "lookup_tool_calls": [call["tool"] for call in lookup.get("tool_calls", [])],
            })
        report = {"seconds": round(elapsed, 3), "batch_id": batch_id, "status": batch["status"],
                  "lookups_run": sum(row["reused"] is False for row in rows),
                  "lookups_reused": sum(row["reused"] is True for row in rows), "cases": rows}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
