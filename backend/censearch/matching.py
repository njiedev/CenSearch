"""Compare images in memory. Persist pixels only for a candidate case."""

import hashlib
import cv2
import numpy as np
from sqlalchemy import select
from censearch.copy_detect import compare, features, hash_text, verdict
from censearch.db import Case, Original, Person, Reference, now
from censearch.face import active_references, band_for
from censearch.imaging import decode


class Matcher:
    def __init__(self, store, face, evidence, calibration, calibration_sha256):
        self.store = store
        self.face = face
        self.evidence = evidence
        self.calibration = calibration
        self.calibration_sha256 = calibration_sha256

    def gallery(self):
        result = []
        with self.store.session() as session:
            for person in session.scalars(select(Person)):
                references = list(
                    session.scalars(
                        select(Reference).where(Reference.person_id == person.id).order_by(Reference.id)
                    )
                )
                works = list(session.scalars(select(Original).where(Original.person_id == person.id)))
                embeddings = np.array([np.frombuffer(row.embedding, np.float32) for row in references])
                originals = [
                    (row, features(decode((self.store.directory / row.path).read_bytes()))) for row in works
                ]
                result.append((person.id, embeddings, originals))
        return result

    def face_decisions(self, faces, gallery):
        if not faces or not gallery:
            return {}
        probes = np.array([face.embedding for face in faces])
        scores = np.column_stack(
            [(probes @ active_references(references).T).max(axis=1) for _, references, _ in gallery]
        )
        winners = scores.argmax(axis=1)
        decisions = {}
        for person_index in range(len(gallery)):
            eligible = np.flatnonzero(winners == person_index)
            if not len(eligible):
                continue
            index = int(eligible[np.argmax(scores[eligible, person_index])])
            score = float(scores[index, person_index])
            band = band_for(score, self.calibration)
            if band != "no_match":
                decisions[person_index] = (faces[index], score, band)
        return decisions

    def copy_decision(self, sha256, works, candidate, mirrored):
        best = (None, "none", None)
        rank = {"none": 0, "uncertain": 1, "derived": 2, "exact": 3}
        ordered = sorted(works, key=lambda pair: np.count_nonzero(pair[1].hash != candidate.hash))
        for work, original in ordered:
            if work.sha256 == sha256:
                return work, "exact", {"sha256_equal": True}
            evidence = compare(original, candidate, mirrored)
            relation = verdict(evidence, self.calibration["copy"])
            previous_score = best[2].get("dense_score", -1) if best[2] else -1
            if (rank[relation], evidence["dense_score"]) > (rank[best[1]], previous_score):
                best = (work, relation, evidence)
        return best

    def analyse(self, session, scan, payload, context, gallery, headers, final_url, pending):
        image = decode(payload)
        scan.sha256 = hashlib.sha256(payload).hexdigest()
        faces, skips = self.face.extract(image)
        candidate = features(image)
        mirrored = features(cv2.flip(image, 1))
        decisions = self.face_decisions(faces, gallery)
        matches = 0
        for index, (person_id, references, works) in enumerate(gallery):
            face, face_score, face_band = decisions.get(index, (None, None, "no_match"))
            work, relation, copy_evidence = self.copy_decision(scan.sha256, works, candidate, mirrored)
            if face_band == "no_match" and relation == "none":
                continue
            has_copy = relation != "none"
            definite_copy = relation in ("exact", "derived")
            if definite_copy:
                photo_relation = "same_photo"
            elif relation == "uncertain":
                photo_relation = "uncertain"
            else:
                photo_relation = "different_photo"
            match_type = "both" if face and has_copy else "face" if face else "copy"
            band = "match" if face_band == "match" or definite_copy else "possible"
            copy_score = 1.0 if relation == "exact" else (copy_evidence or {}).get("dense_score", -1.0)
            score = face_score if face_score is not None else copy_score
            retained = self.evidence.put(person_id, f"evidence/{scan.id}-{scan.sha256}.image", payload)
            pending.append(retained)
            face_evidence = None
            if face:
                face_evidence = {
                    "box": face.box,
                    "box_coordinates": "EXIF-oriented native pixels",
                    "detector_score": face.detector_score,
                    "blur": face.blur,
                    "reference_count": len(references),
                    "active_reference_count": len(active_references(references)),
                    "bands": self.calibration["deployment_bands"],
                }
            evidence = {
                "calibration_sha256": self.calibration_sha256,
                "fusion": "max",
                "phash": hash_text(candidate.hash),
                "face": face_evidence,
                "copy": copy_evidence,
                "context": context,
                "score_basis": "face_cosine_similarity" if face else "copy_dense_agreement",
                "photo_relation_basis": "protected_work_verified"
                if definite_copy
                else "copy_evidence_inconclusive"
                if has_copy
                else "no_protected_work_copy_detected",
                "image": retained
                | {
                    "response_headers": headers,
                    "fetched_at": now(),
                    "final_url": final_url,
                    "source": "http",
                },
            }
            session.add(
                Case(
                    person_id=person_id,
                    scan_id=scan.id,
                    original_id=work.id if work and has_copy else None,
                    page_url=scan.page_url,
                    image_url=scan.image_url,
                    match_type=match_type,
                    band=band,
                    score=score,
                    face_band=face_band,
                    face_score=face_score,
                    copy_relation=relation,
                    photo_relation=photo_relation,
                    evidence=evidence,
                )
            )
            matches += 1
        scan.status = "matched" if matches else "no_match"
        return {"matches": matches, "detected_faces": len(faces), "skip_reasons": skips}
