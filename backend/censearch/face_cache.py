"""Reuse completed FaceCheck scans for the same identity and enrollment photo."""

from copy import deepcopy
from sqlalchemy import select

from censearch.db import Case, CrawlRun, Reference, Scan, now
from censearch.case_records import BatchItem, CaseEvent, Attestation, Notice
from censearch.facecheck import MIN_SCORE_EXCLUSIVE


def cached_run(session, person_id):
    photo = session.scalar(
        select(Reference).where(Reference.person_id == person_id).order_by(Reference.id)
    )
    if photo is None:
        return None
    for run in session.scalars(select(CrawlRun).order_by(CrawlRun.id.desc())):
        request = run.config.get("request", {})
        face = run.config.get("facecheck", {})
        if (
            run.config.get("public_search")
            and request.get("person_id") == person_id
            and request.get("mode") == "face_search"
            and run.status.startswith("completed")
            and face.get("status") == "completed"
            and face.get("testing_mode") is False
            and face.get("photo_sha256") == photo.sha256
            and face.get("score_above") == MIN_SCORE_EXCLUSIVE
        ):
            return run
    return None


def cache_summary(session, person_id):
    run = cached_run(session, person_id)
    if run is None:
        return {"available": False, "count": 0}
    face = run.config["facecheck"]
    return {
        "available": True,
        "run_id": run.id,
        "count": len(face["items"]),
        "saved_at": face.get("retrieved_at") or run.finished_at,
    }


def delete_cache(session, person_id, directory=None):
    """Drop unused provider candidates; retain cases already used in a review workflow."""
    deleted = 0
    for run in session.scalars(select(CrawlRun)):
        if run.config.get("request", {}).get("person_id") != person_id:
            continue
        if (
            not run.config.get("facecheck")
            or run.config["facecheck"].get("status") == "cache_deleted"
        ):
            continue
        config = deepcopy(run.config)
        config["facecheck"] = {
            "status": "cache_deleted",
            "items": [],
            "score_above": MIN_SCORE_EXCLUSIVE,
            "testing_mode": False,
            "deleted_at": now(),
        }
        discovery = config.get("discovery", {})
        discovery["candidates"] = [
            row
            for row in discovery.get("candidates", [])
            if row.get("discovery_method") != "face_search"
        ]
        run.config = config
        cases = session.scalars(
            select(Case).join(Scan).where(Scan.run_id == run.id, Case.match_type == "facecheck")
        )
        for case in cases:
            reviewed = case.state != "needs_review" or any(
                session.scalar(select(model).where(model.case_id == case.id).limit(1))
                for model in (BatchItem, CaseEvent, Attestation, Notice)
            )
            if reviewed:
                continue
            relative = case.evidence.get("image", {}).get("path")
            if directory and relative:
                path = (directory / relative).resolve()
                if path.is_relative_to(directory.resolve()):
                    path.unlink(missing_ok=True)
            scan = session.get(Scan, case.scan_id)
            session.delete(case)
            session.flush()
            session.delete(scan)
        deleted += 1
    return deleted
