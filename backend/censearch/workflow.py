"""Persistent Decide → approved request → delivery → verification workflow."""

import asyncio
from datetime import timedelta
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from censearch.agent.describe import describe
from censearch.agent.recipient import lookup
from censearch.agent.reply import read_reply
from censearch.agent.tools import fetch_page
from censearch.agent.web import lookup_session
from censearch.case_records import Attestation, CaseEvent, CaseWorkflow, Delivery, DraftApproval, Notice
from censearch.db import Case, Original, Person, record
from censearch.delivery import destination, send
from censearch.evidence import capture_page
from censearch.notices import digest, render
from censearch.routing import EXTRA_QUESTIONS, QUESTIONS, decide
from censearch.verify import Clock, check


class Workflow:
    def __init__(self, store, settings, storage):
        self.store = store
        self.settings = settings
        self.storage = storage
        self.clock = Clock(settings.demo_clock)
        self.lock = asyncio.Lock()
        self.live_call_verified = False
        self.calibration = json.loads(settings.calibration_path.read_text())

    def now(self):
        return self.clock.now().isoformat()

    def context(self, session, case_id):
        case = session.get(Case, case_id)
        if case is None:
            raise LookupError("Case not found")
        state = session.get(CaseWorkflow, case_id)
        if state is None:
            state = CaseWorkflow(case_id=case_id)
            session.add(state)
            session.flush()
        return case, state

    def event(self, session, case_id, kind, **details):
        session.add(CaseEvent(case_id=case_id, kind=kind, details=details, at=self.now()))

    def latest(self, session, model, case_id):
        return session.scalar(
            select(model).where(model.case_id == case_id).order_by(model.id.desc()).limit(1)
        )

    def view(self, case_id):
        with self.store.session.begin() as session:
            case, state = self.context(session, case_id)

            def rows(model):
                return [
                    record(row)
                    for row in session.scalars(
                        select(model).where(model.case_id == case_id).order_by(model.id)
                    )
                ]

            return {
                "case_id": case_id,
                "state": case.state,
                "revision": state.revision,
                "questions": QUESTIONS,
                "additional_questions": EXTRA_QUESTIONS,
                "answers": case.answers or {key: None for key in QUESTIONS | EXTRA_QUESTIONS},
                "contact": state.contact,
                "decision": state.decision,
                "description": state.description,
                "lookup": state.lookup,
                "bundle": state.bundle,
                "next_rung": state.next_rung,
                "attestations": rows(Attestation),
                "notices": rows(Notice),
                "deliveries": rows(Delivery),
                "draft_approvals": rows(DraftApproval),
                "timeline": rows(CaseEvent),
                "checks": case.verification_checks,
                "clock": self.now(),
                "demo_clock": self.clock.enabled,
            }

    async def answer(self, case_id, request):
        with self.store.session.begin() as session:
            case, state = self.context(session, case_id)
            if self.latest(session, Delivery, case_id):
                raise ValueError("Answers are frozen after delivery; do not silently change a sent notice")
            values = request.answers.model_dump()
            previous = case.answers or {}
            for key, value in values.items():
                if value is not None and value != previous.get(key):
                    session.add(
                        Attestation(
                            case_id=case_id,
                            question=key,
                            value={"answer": value},
                            answered_by=request.answered_by,
                            answered_at=self.now(),
                        )
                    )
                elif value is None and previous.get(key) is not None:
                    session.add(
                        Attestation(
                            case_id=case_id,
                            question=key,
                            value={"answer": None},
                            answered_by=request.answered_by,
                            answered_at=self.now(),
                        )
                    )
            state.revision += 1
            case.answers = values
            state.contact = request.contact.model_dump()
            self.event(
                session,
                case_id,
                "contact_saved",
                contact=state.contact,
                answered_by=request.answered_by,
                revision=state.revision,
            )
            evidence = {key: getattr(case, key) for key in ("copy_relation", "photo_relation", "original_id")}
            state.decision = decide(values, evidence)
            case.route = state.decision["route"]
            case.drafted_request = None
            case.state = "decided"
            self.event(session, case_id, "route_decided", **state.decision, revision=state.revision)
        return self.view(case_id)

    async def description(self, case_id):
        with self.store.session.begin() as session:
            case, _ = self.context(session, case_id)
            url = case.page_url
        if self.settings.model_configured:

            def fetch_text():
                with lookup_session(url, self.settings):
                    return fetch_page(url).get("text", "")

            text = await asyncio.to_thread(fetch_text)
        else:
            text = ""
        result = await describe(text, self.settings)
        self.live_call_verified |= result["status"] == "completed"
        with self.store.session.begin() as session:
            _, state = self.context(session, case_id)
            state.description = result
            self.event(session, case_id, "page_described", **result)
        return result

    async def capture(self, case_id):
        with self.store.session.begin() as session:
            case, state = self.context(session, case_id)
            person = session.get(Person, case.person_id)
            if person.development_fixture and self.storage.client:
                raise ValueError("Fixture evidence must not be uploaded to third-party storage")
            if self.latest(session, Notice, case_id):
                raise ValueError("Evidence is frozen once a notice exists")
            data = record(case)
        bundle = await capture_page(
            self.storage, data["person_id"], case_id, data["page_url"], data["evidence"]["image"], self.now()
        )
        with self.store.session.begin() as session:
            _, state = self.context(session, case_id)
            state.bundle = bundle
            self.event(session, case_id, "evidence_captured", bundle=bundle)
        return bundle

    async def recipients(self, case_id):
        with self.store.session.begin() as session:
            case, _ = self.context(session, case_id)
            url = case.page_url
        result = await lookup(url, self.settings)
        self.live_call_verified |= result["model_status"] == "completed"
        with self.store.session.begin() as session:
            case, state = self.context(session, case_id)
            state.lookup = result
            case.recipients = result["recipients"]
            self.event(session, case_id, "recipients_researched", **result)
        return result

    async def approve_draft(self, case_id, request):
        with self.store.session.begin() as session:
            case, state = self.context(session, case_id)
            if request.revision != state.revision or not state.decision:
                raise ValueError("Approval must cover the current answers and decision revision")
            if case.route in ("leave_alone", "hold_for_review"):
                raise ValueError("This route cannot be approved for drafting")
            if request.rung != state.next_rung:
                raise ValueError("That escalation rung is not available")
            session.add(
                DraftApproval(
                    case_id=case_id,
                    revision=state.revision,
                    rung=request.rung,
                    approved_by=request.approved_by,
                    at=self.now(),
                )
            )
            self.event(session, case_id, "draft_preparation_approved", **request.model_dump())
        return self.view(case_id)

    async def draft(self, case_id, request):
        with self.store.session.begin() as session:
            case, state = self.context(session, case_id)
            approval = session.scalar(
                select(DraftApproval)
                .where(
                    DraftApproval.case_id == case_id,
                    DraftApproval.revision == state.revision,
                    DraftApproval.rung == request.rung,
                )
                .order_by(DraftApproval.id.desc())
                .limit(1)
            )
            if not approval:
                raise ValueError(
                    "Explicit approval is required before drafting, including each escalation rung"
                )
            if state.next_rung != request.rung:
                raise ValueError("Rung unavailable; await the deadline and scheduler decision")
            previous = self.latest(session, Delivery, case_id)
            if previous and previous.rung == request.rung:
                raise ValueError("A delivery was already attempted on this rung")
            if not state.bundle:
                raise ValueError("Capture screenshot evidence and bundle before drafting")
            recipient = next(
                (
                    row
                    for row in case.recipients
                    if row["id"] == request.recipient_id and row["rung"] == request.rung
                ),
                None,
            )
            if recipient is None:
                raise ValueError("Choose a researched recipient on this rung")
            evidence = dict(state.decision["inputs"]["evidence"])
            work = session.get(Original, case.original_id) if case.original_id else None
            evidence["original_sha256"] = work.sha256 if work else None
            body = render(
                case.route,
                case.answers,
                state.contact,
                evidence,
                case.page_url,
                case.image_url,
                request.rung,
                self.now(),
            )
            payload = {
                "route": case.route,
                "rung": request.rung,
                "page_url": case.page_url,
                "image_url": case.image_url,
                "facts": case.answers,
                "contact": state.contact,
                "body": body,
                "template": case.route + "-v2",
                "bundle_sha256": state.bundle["bundle_file"]["sha256"],
                "recipient": recipient,
            }
            notice = Notice(
                case_id=case_id,
                revision=state.revision,
                rung=request.rung,
                recipient=recipient,
                payload=payload,
                sha256=digest(payload),
                created_at=self.now(),
            )
            session.add(notice)
            session.flush()
            case.drafted_request = record(notice)
            case.state = "drafted"
            self.event(
                session,
                case_id,
                "notice_drafted",
                notice_id=notice.id,
                sha256=notice.sha256,
                recipient=recipient,
                manual_submission=recipient["channel"].startswith("manual"),
            )
            return record(notice)

    async def approve_notice(self, case_id, request):
        with self.store.session.begin() as session:
            _, state = self.context(session, case_id)
            notice = session.get(Notice, request.notice_id)
            latest = self.latest(session, Notice, case_id)
            if (
                notice is None
                or notice.case_id != case_id
                or latest.id != notice.id
                or notice.revision != state.revision
                or notice.rung != state.next_rung
                or request.sha256 != notice.sha256
                or digest(notice.payload) != notice.sha256
            ):
                raise ValueError("Approval must cover the latest exact notice, recipient, rung and answers")
            if session.scalar(select(Delivery.id).where(Delivery.notice_id == notice.id)):
                raise ValueError("Notice already attempted")
            notice.approved_by = request.approved_by
            notice.approved_at = self.now()
            self.event(
                session,
                case_id,
                "exact_notice_approved",
                notice_id=notice.id,
                sha256=notice.sha256,
                approved_by=request.approved_by,
                rung=notice.rung,
            )
            return record(notice)

    async def send(self, case_id):
        try:
            with self.store.session.begin() as session:
                case, state = self.context(session, case_id)
                notice = self.latest(session, Notice, case_id)
                if (
                    notice is None
                    or not notice.approved_by
                    or notice.revision != state.revision
                    or notice.rung != state.next_rung
                ):
                    raise ValueError("Approve the current exact notice before sending")
                if digest(notice.payload) != notice.sha256 or notice.payload["recipient"] != notice.recipient:
                    raise ValueError("Approved notice or recipient changed")
                previous = self.latest(session, Delivery, case_id)
                if previous and (previous.notice_id == notice.id or previous.rung == notice.rung):
                    raise ValueError("Duplicate send refused")
                destination(notice.recipient["endpoint"], self.settings.allow_external_delivery)
                if notice.recipient["channel"] not in ("smtp", "http_form"):
                    raise ValueError("The person sends this real-site draft themselves")
                delivery = Delivery(
                    case_id=case_id,
                    notice_id=notice.id,
                    rung=notice.rung,
                    status="attempting",
                    response={},
                    sent_at=self.now(),
                    deadline=(
                        self.clock.now() + timedelta(seconds=self.settings.notice_interval)
                    ).isoformat(),
                )
                session.add(delivery)
                session.flush()
                identifier = delivery.id
                payload, recipient = notice.payload, notice.recipient
                self.event(session, case_id, "delivery_started", delivery_id=identifier, rung=notice.rung)
        except IntegrityError as error:
            raise ValueError("Duplicate send refused") from error
        # Claim persisted before I/O. An interrupted attempt cannot be blindly retried.
        result = await asyncio.to_thread(send, recipient, payload, self.settings.allow_external_delivery)
        with self.store.session.begin() as session:
            case, _ = self.context(session, case_id)
            delivery = session.get(Delivery, identifier)
            delivery.status = result["status"]
            delivery.response = result
            delivery.processed = result["status"] != "awaiting_response"
            case.state = "decision_required" if result["status"] == "reasoned_refusal" else result["status"]
            case.deliveries = [*case.deliveries, record(delivery)]
            self.event(session, case_id, "delivery_result", delivery=record(delivery))
            return record(delivery)

    async def verify(self, case_id):
        with self.store.session.begin() as session:
            case, _ = self.context(session, case_id)
            data = record(case)
        payload = (self.storage.root / data["evidence"]["image"]["path"]).read_bytes()
        result = await asyncio.to_thread(check, data, payload, self.calibration)
        result["checked_at"] = self.now()
        with self.store.session.begin() as session:
            case, _ = self.context(session, case_id)
            case.verification_checks = [*case.verification_checks, result]
            if result["outcome"] in ("removed", "replaced"):
                case.state = result["outcome"]
            self.event(session, case_id, "verification", **result)
        return result

    async def reply(self, case_id, request):
        with self.store.session.begin() as session:
            self.context(session, case_id)
        result = await read_reply(request.text, self.settings)
        self.live_call_verified |= result["status"] == "completed"
        with self.store.session.begin() as session:
            self.event(session, case_id, "reply_advisory", **result)
        return result

    async def tick(self):
        with self.store.session() as session:
            deliveries = [
                record(row)
                for row in session.scalars(
                    select(Delivery).where(
                        Delivery.processed.is_(False), Delivery.status == "awaiting_response"
                    )
                )
                if row.deadline <= self.now()
            ]
        results = []
        for delivery in deliveries:
            verification = await self.verify(delivery["case_id"])
            with self.store.session.begin() as session:
                case, state = self.context(session, delivery["case_id"])
                row = session.get(Delivery, delivery["id"])
                if verification["outcome"] in ("removed", "replaced"):
                    row.processed = True
                    results.append(
                        {"case_id": case.id, "verification": verification, "escalation": "resolved"}
                    )
                    continue
                if verification["outcome"] != "still_present":
                    results.append(
                        {
                            "case_id": case.id,
                            "verification": verification,
                            "escalation": "verification_uncertain",
                        }
                    )
                    continue
                next_rung = {"site": "host", "host": "search"}.get(row.rung)
                row.processed = True
                if next_rung:
                    state.next_rung = next_rung
                    case.state = "escalation_approval_required"
                    self.event(
                        session,
                        case.id,
                        "escalation_available",
                        from_rung=row.rung,
                        to_rung=next_rung,
                        reason="Silence past deadline; new draft and exact notice approvals required",
                    )
                else:
                    case.state = "ladder_exhausted"
                    self.event(session, case.id, "ladder_exhausted")
                results.append(
                    {
                        "case_id": case.id,
                        "verification": verification,
                        "next_rung": next_rung,
                        "escalation": "approval_required" if next_rung else "ladder_exhausted",
                    }
                )
        return results
