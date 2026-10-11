"""Exercise an isolated three-page demo through HTTP. Sends local SMTP only."""

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

import httpx


def verify(base, site, report_path, resend=False):
    for url in (base, site):
        if urlsplit(url).hostname != "127.0.0.1":
            raise ValueError("The demo verifier accepts literal loopback URLs only")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"passed": False, "transport": "Resend test recipient" if resend else "local SMTP",
              "photos_uploaded": False}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=60, trust_env=False) as client:
            health = client.get(base + "/api/health").json()
            assert health["email_delivery"]["enabled"] is False
            cases = client.get(base + "/api/cases").json()
            assert len(cases) == 3, len(cases)
            expected = {
                site + "/post/0001.html": ("copyright_notice", "sent"),
                site + "/post/0002.html": ("leave_alone", "left_alone"),
                site + "/post/0003.html": ("hold_for_review", "held_for_review"),
            }
            assert {row["page_url"] for row in cases} == set(expected)
            assert all(row["band"] == "match" for row in cases)
            report["matches"] = len(cases)
            for row in cases:
                assert client.get(row["image_url"]).status_code == 200
                assert not client.get(base + f"/api/cases/{row['id']}/workflow").json()["deliveries"]
            # A malformed email request must not cause removal.
            rejected = client.post(site + "/mail-inbox", json={"route": "copyright_notice"},
                                   headers={"X-Mock-Mail": "local-mock-admin"})
            assert rejected.status_code == 422
            assert client.get(site + "/receipts").json() == []
            response = client.post(base + "/api/batches", json={
                "mode": "send", "case_ids": [row["id"] for row in cases],
                "accepted_warning": True, "accepted_by": "Fictional demo operator",
                "contact": {"name": "Fictional demo operator", "email": "operator@example.test",
                            "address": "1 Demo Street (fictional)", "phone": "555-0100",
                            "signature": "Fictional demo operator"},
            })
            response.raise_for_status()
            batch_id = response.json()["id"]
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                batch = client.get(base + f"/api/batches/{batch_id}").json()
                if batch["status"] not in ("queued", "running"):
                    break
                time.sleep(0.5)
            else:
                raise TimeoutError("Agent batch exceeded 180 seconds")
            report["batch"] = batch
            by_id = {row["id"]: row for row in cases}
            for item in batch["items"]:
                case = by_id[item["case_id"]]
                actual = (item["decision"].get("route"), item["status"])
                print(json.dumps({"page": case["page_url"], "actual": actual,
                                  "reason": item["reason"]}), flush=True)
                assert actual == expected[case["page_url"]], (actual, expected[case["page_url"]])
                assert item["decision"]["source"] == "agent"
                assert item["decision"]["model_status"] == "completed"
            receipts = client.get(site + "/receipts").json()
            if resend:
                assert receipts == [], "Resend test submission must not remove the local photo"
                for row in cases:
                    assert client.get(row["image_url"]).status_code == 200
                sent = next(row for row in cases if row["page_url"].endswith("/0001.html"))
                workflow = client.get(base + f"/api/cases/{sent['id']}/workflow").json()
                delivery = workflow["deliveries"][-1]
                assert delivery["status"] == "awaiting_response"
                assert delivery["response"]["transport"] == "resend_demo"
                assert delivery["response"]["provider_id"]
                report["delivery"] = delivery
                report["passed"] = True
                return
            assert len(receipts) == 1, receipts
            assert receipts[0]["received_channel"] == "smtp"
            assert receipts[0]["route"] == "copyright_notice"
            assert receipts[0]["status"] == "acted"
            report["receipts"] = receipts
            for row in cases:
                removed = row["page_url"].endswith("/0001.html")
                assert client.get(row["image_url"]).status_code == (410 if removed else 200)
                if removed:
                    check = client.post(base + f"/api/cases/{row['id']}/verify")
                    check.raise_for_status()
                    report["verification"] = check.json()
                    assert check.json()["outcome"] == "removed", check.json()
            report["passed"] = True
    finally:
        report["seconds"] = round(time.monotonic() - started, 2)
        report_path.write_text(json.dumps(report, indent=2))
        print(f"Report: {report_path} | passed={report['passed']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--resend", action="store_true")
    args = parser.parse_args()
    verify(args.base.rstrip("/"), args.site.rstrip("/"), args.report, args.resend)
