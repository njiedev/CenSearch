"""Provider candidates are reviewable independently of local page verification."""

import base64
import binascii
import hashlib

from sqlalchemy import select

from censearch.db import Case, Scan
from censearch.evidence import EvidenceStore
from censearch.facecheck import MIN_SCORE, prepare_photo


def thumbnail_bytes(value):
    if not isinstance(value, str) or len(value) > 2_000_000:
        return None
    if value.startswith("data:image/"):
        header, separator, value = value.partition(",")
        if not separator or not header.endswith(";base64"):
            return None
    try:
        # FaceCheck's WebP data URLs include a space after the comma.
        return prepare_photo(base64.b64decode(value.strip(), validate=True), 1_500_000)
    except (ValueError, binascii.Error):
        return None


def materialize(session, run, items, settings):
    """Persist thumbnails locally; never infer an image URL or original ownership."""
    storage = EvidenceStore(settings.model_copy(update={"obj_endpoint": "", "obj_bucket": ""}))
    existing = {
        case.evidence.get("provider_item_key"): case
        for case in session.scalars(select(Case).join(Scan).where(Scan.run_id == run.id))
        if case.match_type == "facecheck"
    }
    saved = []
    for item in items:
        if not MIN_SCORE <= item["score"] <= 100:
            continue
        payload = thumbnail_bytes(item.get("base64"))
        fingerprint = hashlib.sha256(payload).hexdigest() if payload else "missing"
        key = hashlib.sha256((item["url"] + "\n" + fingerprint).encode()).hexdigest()
        case = next((row for row in existing.values() if row.id == item.get("case_id")), None)
        case = case or existing.get(key)
        if case is None:
            image = storage.put(
                run.config["request"]["person_id"], f"facecheck/{run.id}-{key}.jpg", payload
            ) if payload else {}
            scan = Scan(
                run_id=run.id, page_url=item["url"], image_url="",
                sha256=image.get("sha256"), identity_version=run.identity_version,
                status="provider_candidate",
            )
            session.add(scan)
            session.flush()
            case = Case(
                person_id=run.config["request"]["person_id"], scan_id=scan.id,
                page_url=item["url"], image_url="", match_type="facecheck",
                band="possible", score=item["score"], face_band="not_checked", face_score=None,
                copy_relation="uncertain", photo_relation="uncertain",
                evidence={
                    "score_basis": "facecheck_provider_score",
                    "provider_item_key": key,
                    "image": image | {"source": "facecheck_thumbnail"},
                    "context": {"discovery": {
                        "run_id": run.id, "draft_only": True, "simulated": False,
                        "methods": ["face_search"],
                        "match_label": "Found by FaceCheck",
                    }},
                },
            )
            session.add(case)
            session.flush()
            existing[key] = case
        elif payload and not case.evidence.get("image", {}).get("path"):
            image = storage.put(
                run.config["request"]["person_id"], f"facecheck/{run.id}-{key}.jpg", payload
            )
            case.evidence = case.evidence | {
                "provider_item_key": key,
                "image": image | {"source": "facecheck_thumbnail"},
            }
            scan = session.get(Scan, case.scan_id)
            scan.sha256 = image["sha256"]
            existing[key] = case
        row = {name: item[name] for name in ("url", "score", "label") if name in item}
        row["case_id"] = case.id
        if row not in saved:
            saved.append(row)
    return saved
