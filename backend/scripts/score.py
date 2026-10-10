"""Independent scoring. Only this script reads the mock ground-truth manifest."""

import argparse
from collections import defaultdict
import json
from pathlib import Path


def score(manifest_path, cases, scans, identity_map):
    truth = json.loads(manifest_path.read_text())
    by_key = defaultdict(list)
    for case in cases:
        by_key[(case["page_url"], case["image_url"])].append(case)
    discovered = {(scan["page_url"], scan["image_url"]) for scan in scans}
    target = [row for row in truth if row["accessible"] and row["identity"] in identity_map]
    distractors = [row for row in truth if row["accessible"] and row["identity"] is None]
    rows = []
    for row in target:
        matches = [
            case
            for case in by_key[(row["page_url"], row["image_url"])]
            if case["person_id"] == identity_map[row["identity"]]
        ]
        expected_relation = "same_photo" if row["same_photo"] else "different_photo"
        rows.append(
            {
                "site": row["site"],
                "transform": row["transform"],
                "page_url": row["page_url"],
                "expected_relation": expected_relation,
                "discovered": (row["page_url"], row["image_url"]) in discovered,
                "matched": bool(matches),
                "face_found": any(case["face_band"] in ("match", "possible") for case in matches),
                "copy_verified": any(case["copy_relation"] in ("exact", "derived") for case in matches),
                "relation_correct": any(case["photo_relation"] == expected_relation for case in matches),
                "case_ids": [case["id"] for case in matches],
            }
        )
    false_positives = sum(bool(by_key[(row["page_url"], row["image_url"])]) for row in distractors)
    robots_violations = sum(
        (row["page_url"], row["image_url"]) in discovered for row in truth if not row["accessible"]
    )
    per_transform = {}
    for transform in sorted({row["transform"] for row in rows}):
        subset = [row for row in rows if row["transform"] == transform]
        per_transform[transform] = {
            "expected": len(subset),
            "matched": sum(row["matched"] for row in subset),
            "face": sum(row["face_found"] for row in subset),
            "copy": sum(row["copy_verified"] for row in subset),
        }
    return {
        "expected_accessible": len(target),
        "discovered": sum(row["discovered"] for row in rows),
        "matched": sum(row["matched"] for row in rows),
        "relations_correct": sum(row["relation_correct"] for row in rows),
        "distractors": len(distractors),
        "false_positives": false_positives,
        "robots_violations": robots_violations,
        "per_transform": per_transform,
        "appearances": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    print(
        json.dumps(
            score(args.manifest, snapshot["cases"], snapshot["scans"], snapshot["identity_map"]), indent=2
        )
    )
