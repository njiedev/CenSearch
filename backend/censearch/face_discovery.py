"""FaceCheck discovery for one explicitly consented enrolled identity."""

from copy import deepcopy

import httpx
from sqlalchemy import select

from censearch.db import CrawlRun, Person, Reference, now
from censearch.discovery import Candidate, canonical_url, dedupe
from censearch.facecheck import FaceCheckClient, FaceCheckError, MIN_SCORE, result_items
from censearch.face_review import materialize


def discover_faces(crawler):
    request = crawler.request
    with crawler.store.session() as session:
        person = session.get(Person, request.person_id)
        if person is None or person.development_fixture or not request.facecheck_consent:
            raise FaceCheckError("Face search requires a non-fixture identity and upload consent")
        photo = session.scalar(
            select(Reference).where(Reference.person_id == person.id).order_by(Reference.id)
        )
        if photo is None:
            raise FaceCheckError("Enroll a face photo before starting a face search")
        photo_path = (crawler.settings.data_dir / photo.path).resolve()
        if not photo_path.is_relative_to(crawler.settings.data_dir.resolve()):
            raise FaceCheckError("Enrolled photo is outside local storage")

    state = crawler.config.setdefault(
        "facecheck",
        {
            "status": "uploading",
            "items": [],
            "min_score": MIN_SCORE,
            "testing_mode": False,
            "consented_at": now(),
            "photo_id": photo.id,
            "photo_sha256": photo.sha256,
        },
    )
    crawler.progress()

    def progress(value):
        crawler.check_cancel()
        state.update(status="searching", progress=value)
        crawler.progress()

    with httpx.Client(trust_env=False, follow_redirects=False) as http:
        client = FaceCheckClient(crawler.settings, http)
        crawler.check_cancel()
        resume = bool(state.get("id_search"))
        if not resume:
            info = client.info()
            if not info.get("is_online") or info["remaining_credits"] < 3:
                raise FaceCheckError("FaceCheck must be online with at least 3 credits")
            with photo_path.open("rb") as stream:
                payload = stream.read(crawler.settings.upload_limit_bytes + 1)
            crawler.check_cancel()
            state["id_search"] = client.upload(payload, upload_consent=True)
            state["status"] = "submitting"
            # Persist the ID before submitting; resumes only poll this ID.
            crawler.progress()
        result = client.search(
            state["id_search"],
            live=True,
            resume=resume,
            wait_seconds=60,
            progress=progress,
            check_cancel=crawler.check_cancel,
            include_thumbnails=True,
        )
        if result["testing_mode"]:
            raise FaceCheckError("FaceCheck returned testing results for a live search")
        result["items"] = result_items(result["items"], include_thumbnails=True)
        if result["status"] == "completed":
            result["retrieved_at"] = now()
            with crawler.store.session.begin() as session:
                run = session.get(CrawlRun, crawler.run_id)
                result["items"] = materialize(session, run, result["items"], crawler.settings)
        state.update(deepcopy(result))

    candidates = []
    for rank, item in enumerate(state["items"], 1):
        # Defense in depth: this gate also covers alternate/injected client implementations.
        if not MIN_SCORE <= item["score"] <= 100:
            continue
        try:
            candidates.append(
                Candidate(
                    canonical_url(item["url"]),
                    None,
                    "",
                    "facecheck",
                    rank,
                    now(),
                    "face_search",
                    item["score"],
                )
            )
        except (ValueError, TypeError):
            continue
    crawler.candidates = dedupe(candidates)
    crawler.agent_state.update(source="facecheck", model_status="not_requested", queries=[])
    crawler.progress()
