"""Atomic enrollment: reject the whole set if any supplied photo fails validation."""

from pathlib import Path
import uuid
import cv2
from sqlalchemy import select
from censearch.case_records import Batch, BatchItem
from censearch.db import Case, Person, Reference, Original, record
from censearch.face import active_references
from censearch.face_cache import delete_cache
from censearch.imaging import decode


class EnrollmentError(ValueError):
    def __init__(self, message, photos):
        super().__init__(message)
        self.photos = photos


class Enrollment:
    def __init__(self, store, face, evidence, calibration):
        self.store = store
        self.face = face
        self.evidence = evidence
        self.calibration = calibration

    def enroll(self, name, consent, references, originals, ownership, development_fixture=False):
        if not name.strip() or not consent.strip():
            raise ValueError("Name and consent statement are required")
        if not references:
            raise ValueError("At least one reference photo is required")
        if originals and not ownership.strip():
            raise ValueError("An ownership statement is required when adding original photos")
        if development_fixture and self.evidence.client is not None:
            raise ValueError("Development fixtures require local storage; disable Object Storage")
        results, accepted = self.validate_photos(references, originals)
        person_id = str(uuid.uuid4())
        try:
            with self.store.session.begin() as session:
                count = len(list(session.scalars(select(Person.id))))
                if count >= self.calibration["gallery_size"]:
                    raise ValueError("The calibrated gallery limit is 40 people")
                person = Person(
                    id=person_id,
                    name=name.strip(),
                    consent=consent.strip(),
                    development_fixture=development_fixture,
                )
                session.add(person)
                session.flush()
                for kind, index, filename, payload, image, face in accepted:
                    if kind == "reference":
                        ok, encoded = cv2.imencode(".jpg", image)
                        if not ok:
                            raise ValueError("Reference image encoding failed")
                        saved = self.evidence.put(person_id, f"references/{index}.jpg", encoded.tobytes())
                        session.add(
                            Reference(
                                person_id=person_id,
                                filename=filename,
                                path=saved["path"],
                                sha256=saved["sha256"],
                                embedding=face.embedding.tobytes(),
                                quality={
                                    "detector_score": face.detector_score,
                                    "blur": face.blur,
                                    "box": face.box,
                                },
                            )
                        )
                    else:
                        saved = self.evidence.put(person_id, f"originals/{index}.image", payload)
                        session.add(
                            Original(
                                person_id=person_id,
                                filename=filename,
                                path=saved["path"],
                                sha256=saved["sha256"],
                                ownership_statement=ownership.strip(),
                            )
                        )
        except Exception:
            self.evidence.delete_person(person_id)
            raise
        return {"person": self.get(person_id), "photos": results}

    def validate_photos(self, references, originals):
        results = []
        accepted = []
        for kind, uploads in (("reference", references), ("original", originals)):
            for index, (filename, payload) in enumerate(uploads):
                result = {
                    "kind": kind,
                    "index": index,
                    "filename": Path(filename).name,
                    "accepted": False,
                    "reason": None,
                }
                try:
                    image = decode(payload)
                    face = None
                    if kind == "reference":
                        faces, skips = self.face.extract(image)
                        if len(faces) != 1:
                            raise ValueError(
                                f"Exactly one quality-passing face required; found {len(faces)}; "
                                f"skipped: {', '.join(skips) or 'none'}"
                            )
                        face = faces[0]
                        result["quality"] = {
                            "detector_score": face.detector_score,
                            "blur": face.blur,
                            "box": face.box,
                        }
                    result["accepted"] = True
                    accepted.append((kind, index, result["filename"], payload, image, face))
                except ValueError as error:
                    result["reason"] = str(error)
                results.append(result)
        if any(not result["accepted"] for result in results):
            raise EnrollmentError("No photos saved. Remove or replace rejected photos and retry.", results)
        return results, accepted

    def add_photos(self, person_id, references, originals, ownership):
        person = self.get(person_id)
        if not references and not originals:
            raise ValueError("Choose at least one photo")
        if originals and not ownership.strip():
            raise ValueError("Confirm ownership before adding original photos")
        if person["development_fixture"] and self.evidence.client is not None:
            raise ValueError("Development fixtures require local storage; disable Object Storage")
        results, accepted = self.validate_photos(references, originals)
        pending = []
        try:
            with self.store.session.begin() as session:
                for kind, index, filename, payload, image, face in accepted:
                    token = uuid.uuid4().hex
                    if kind == "reference":
                        ok, encoded = cv2.imencode(".jpg", image)
                        if not ok:
                            raise ValueError("Face image encoding failed")
                        saved = self.evidence.put(person_id, f"references/{token}.jpg", encoded.tobytes())
                        pending.append(saved)
                        session.add(Reference(
                            person_id=person_id, filename=filename, path=saved["path"],
                            sha256=saved["sha256"], embedding=face.embedding.tobytes(),
                            quality={"detector_score": face.detector_score, "blur": face.blur, "box": face.box},
                        ))
                    else:
                        saved = self.evidence.put(person_id, f"originals/{token}.image", payload)
                        pending.append(saved)
                        session.add(Original(
                            person_id=person_id, filename=filename, path=saved["path"],
                            sha256=saved["sha256"], ownership_statement=ownership.strip(),
                        ))
        except Exception:
            self.evidence.remove_files(pending)
            raise
        return {"person": self.get(person_id), "photos": results}

    def photo(self, person_id, kind, photo_id):
        model = {"reference": Reference, "original": Original}.get(kind)
        if model is None:
            raise LookupError("Photo not found")
        with self.store.session() as session:
            row = session.get(model, photo_id)
            if row is None or row.person_id != person_id:
                raise LookupError("Photo not found")
            return record(row)

    def delete_photo(self, person_id, kind, photo_id):
        photo = self.photo(person_id, kind, photo_id)
        model = Reference if kind == "reference" else Original
        with self.store.session.begin() as session:
            if kind == "reference":
                ids = list(session.scalars(select(Reference.id).where(Reference.person_id == person_id)))
                if len(ids) <= 1:
                    raise ValueError("Keep at least one face photo. Add a replacement before removing this photo.")
            affected_batches = []
            if kind == "original":
                affected_batches = list(session.scalars(
                    select(BatchItem.batch_id).join(Case).where(Case.original_id == photo_id)
                ))
            self.evidence.remove_files([{"path": photo["path"], "object_key": photo["path"]}])
            session.delete(session.get(model, photo_id))
            session.flush()
            for batch in session.scalars(select(Batch).where(
                Batch.id.in_(affected_batches), ~Batch.id.in_(select(BatchItem.batch_id))
            )):
                session.delete(batch)
        return self.get(person_id)

    def get(self, person_id):
        with self.store.session() as session:
            person = session.get(Person, person_id)
            if person is None:
                raise LookupError("Person not found")
            references = list(
                session.scalars(
                    select(Reference).where(Reference.person_id == person_id).order_by(Reference.id)
                )
            )
            originals = list(session.scalars(select(Original).where(Original.person_id == person_id)))
            return record(person) | {
                "references": [record(row) for row in references],
                "originals": [record(row) for row in originals],
                "active_reference_count": len(active_references(references)),
            }

    def list(self):
        with self.store.session() as session:
            ids = list(session.scalars(select(Person.id).order_by(Person.created_at)))
        return [self.get(person_id) for person_id in ids]

    def delete(self, person_id):
        with self.store.session.begin() as session:
            person = session.get(Person, person_id)
            if person is None:
                raise LookupError("Person not found")
            # Remove files before reporting DB deletion; remote failures remain visible.
            self.evidence.delete_person(person_id)
            delete_cache(session, person_id)
            session.delete(person)
            session.flush()
            for batch in session.scalars(select(Batch).where(~Batch.id.in_(select(BatchItem.batch_id)))):
                session.delete(batch)
        with self.store.engine.connect() as connection:
            connection.exec_driver_sql("VACUUM")
        return {"deleted": person_id}
