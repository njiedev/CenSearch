"""Separate scorer: outcomes, source observations and administrator receipts versus ground truth."""

import json


def score(manifest_path, results, receipts, delisted):
    manifest = json.loads(manifest_path.read_text())
    rows = []
    for expected in manifest:
        actual = next((row for row in results if row["page_url"] == expected["page_url"]), None)
        site_receipts = [row for row in receipts[expected["site"]] if row["page_url"] == expected["page_url"]]
        checks = {
            "found": actual is not None,
            "route": bool(actual and actual["route"] == expected["expected_route"]),
            "outcome": bool(actual and actual["check"]["outcome"] == expected["expected_outcome"]),
            "ladder": bool(
                actual and [row["rung"] for row in actual["deliveries"]] == expected["expected_rungs"]
            ),
            "delisted": (expected["page_url"] in delisted) == expected["expected_delisted"],
            "refusal": bool(
                actual and any(row["status"] == "reasoned_refusal" for row in actual["deliveries"])
            )
            == expected["expected_refusal"],
            "administrator": len(site_receipts) == (1 if expected["expected_rungs"] else 0),
        }
        rows.append({"page_url": expected["page_url"], "checks": checks, "passed": all(checks.values())})
    return {"total": len(rows), "passed": sum(row["passed"] for row in rows), "scenarios": rows}
