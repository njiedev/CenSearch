"""Delete stored FaceCheck results; cases already used in a review are retained."""

from copy import deepcopy
from sqlalchemy import select

from censearch.db import Case, CrawlRun, Scan, now
from censearch.case_records import BatchItem, CaseEvent, Attestation, Notice
from censearch.facecheck import MIN_SCORE


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
            "min_score": MIN_SCORE,
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
