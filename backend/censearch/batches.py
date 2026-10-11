"""Persisted batch authorization and bounded site workers with independently failing cases."""

import asyncio
from uuid import uuid4
from sqlalchemy import select
from censearch.agent.route import pick_route, possible_action
from censearch.agent.tools import fetch_page
from censearch.agent.web import lookup_session
from censearch.case_records import Attestation, Batch, BatchItem, Delivery, Notice
from censearch.db import Case, Original, record
from censearch.email_delivery import EMAIL_CHANNELS
from censearch.whitelist import is_whitelisted
from censearch.workflow import site_origin
from censearch.workflow_api import ApprovalRequest, DraftRequest, PrepareRequest

WARNING = (
    "The agent will choose the legal basis and send requests on your behalf. "
    "Some notices contain statements made under penalty of perjury. "
    "Legal responsibility for what is sent lies with you. "
    "By accepting, you authorize this batch and accept the facts in the selected fixed templates: "
    "you are the depicted person, the information is accurate and the use is not authorized; "
    "for copyright, you own the identified enrolled original, believe in good faith the use lacks "
    "permission or legal authorization, and are authorized to act for the owner under penalty of perjury; "
    "for impersonation or intimate-image reports, you accept the corresponding description of the use."
)
TERMINAL = {"sent", "drafted_not_sent", "left_alone", "held_for_review", "failed"}


class BatchPhaseError(ValueError):
    pass


class Batches:
    def __init__(self, workflow):
        self.workflow = workflow
        self.store = workflow.store

    def create(self, request):
        if request.accepted_warning is not True:
            raise ValueError("Accept the legal-responsibility warning before starting a batch")
        if len(set(request.case_ids)) != len(request.case_ids):
            raise ValueError("Duplicate case IDs are not allowed")
        if any(not value.strip() for value in request.contact.model_dump().values()):
            raise ValueError("All contact fields are required for autonomous route selection")
        with self.store.session.begin() as session:
            blocked = []
            for case_id in request.case_ids:
                case = session.get(Case, case_id)
                if case is None:
                    raise LookupError(f"Case {case_id} not found")
                if is_whitelisted(session, case):
                    blocked.append(case_id)
            if blocked:
                raise ValueError(f"Cases {blocked} are on the whitelist")
            batch = Batch(
                id=uuid4().hex,
                mode=request.mode,
                accepted_by=request.accepted_by,
                accepted_at=self.workflow.now(),
                accepted_warning=True,
                warning=WARNING,
                contact=request.contact.model_dump(),
            )
            session.add(batch)
            session.flush()
            for case_id in request.case_ids:
                session.add(BatchItem(batch_id=batch.id, case_id=case_id))
        return self.view(batch.id)

    def view(self, batch_id):
        with self.store.session() as session:
            batch = session.get(Batch, batch_id)
            if batch is None:
                raise LookupError("Batch not found")
            items = [
                record(row)
                for row in session.scalars(
                    select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.id)
                )
            ]
            return record(batch) | {
                "items": items,
                "total": len(items),
                "completed": sum(
                    item["status"] in TERMINAL
                    or (
                        batch.phase in ("preparing", "awaiting_review")
                        and item["status"] == "ready_to_send"
                    )
                    for item in items
                ),
            }

    def update(self, item_id, status, reason, **values):
        with self.store.session.begin() as session:
            row = session.get(BatchItem, item_id)
            row.status = status
            row.reason = reason
            for key, value in values.items():
                setattr(row, key, value)

    def recover(self):
        """Never retry an interrupted delivery, whose receipt may be unknown."""
        with self.store.session.begin() as session:
            for batch in session.scalars(
                select(Batch).where(Batch.status.in_(("queued", "running")))
            ):
                if batch.phase == "awaiting_review":
                    continue
                batch.phase = "done"
                batch.status = "interrupted"
                batch.finished_at = self.workflow.now()
                for item in session.scalars(
                    select(BatchItem).where(BatchItem.batch_id == batch.id)
                ):
                    if item.status not in TERMINAL:
                        item.status = "failed"
                        item.reason = "Interrupted; inspect delivery records before retrying"

    async def run(self, batch_id):
        with self.store.session.begin() as session:
            session.get(Batch, batch_id).status = "running"
        batch = self.view(batch_id)
        sites = {}
        with self.store.session() as session:
            for item in batch["items"]:
                case = session.get(Case, item["case_id"])
                sites.setdefault(site_origin(case.page_url), []).append(item)
        limit = asyncio.Semaphore(4)

        async def run_site(items):
            # Only successful research is cached. A failed/empty/model-error
            # lookup is retried afresh by the next actionable case on this site.
            # Cache lifetime is this batch; same-site cases preserve input order.
            cache = {}
            async with limit:
                for item in items:
                    try:
                        await self.run_case(batch, item, cache)
                    except Exception as error:
                        self.update(item["id"], "failed", f"{type(error).__name__}: {error}")

        # The outer workflow lock still excludes manual mutations and scheduler
        # ticks. Workers own separate cases, sessions and browser instances.
        async with asyncio.TaskGroup() as group:
            for items in sites.values():
                group.create_task(run_site(items))
        with self.store.session.begin() as session:
            batch_row = session.get(Batch, batch_id)
            ready = session.scalar(select(BatchItem.id).where(
                BatchItem.batch_id == batch_id, BatchItem.status == "ready_to_send"
            ))
            batch_row.phase = "awaiting_review" if ready is not None else "done"
            batch_row.status = "completed"
            batch_row.finished_at = self.workflow.now() if ready is None else None

    async def run_case(self, batch, item, site_cache=None):
        if self.leave_whitelisted(item):
            return
        workflow = self.workflow
        case_id, item_id = item["case_id"], item["id"]
        self.update(item_id, "reviewing", "Choosing a legal route")
        with self.store.session.begin() as session:
            case, _ = workflow.context(session, case_id)
            if workflow.latest(session, Notice, case_id) or workflow.latest(
                session, Delivery, case_id
            ):
                raise ValueError(
                    "An existing notice or delivery requires review; batch will not resend it"
                )
            data = record(case)
            original = session.get(Original, case.original_id) if case.original_id else None
            if original and original.person_id != case.person_id:
                raise ValueError("Original does not belong to this enrolled person")
            original_name = original.filename if original else None
        text = ""
        fetch_error = None
        if workflow.settings.model_configured:

            def fetch_text():
                with lookup_session(data["page_url"], workflow.settings):
                    return fetch_page(data["page_url"]).get("text", "")

            try:
                text = await asyncio.to_thread(fetch_text)
            except Exception as error:
                fetch_error = type(error).__name__
        decision = await pick_route(data, text, workflow.settings)
        if fetch_error:
            decision["page_fetch_error"] = fetch_error
        self.update(item_id, "reviewing", decision["reason"], decision=decision)
        route = decision["route"]
        facts = {"identity_confirmed": True, "accurate": True, "authorized_use": False}
        if route == "copyright_notice":
            facts.update(
                owns_photo=True,
                good_faith=True,
                authority_under_perjury=True,
                work_description=f"Enrolled original photograph: {original_name}",
            )
        elif route == "privacy_request":
            facts["privacy_request"] = True
        elif route == "impersonation_report":
            facts["impersonates_me"] = True
        elif route == "intimate_image_report":
            facts.update(intimate=True, identifiable=True, good_faith=True)
        if route in ("leave_alone", "hold_for_review"):
            facts = {}
        authorization = {
            "batch_id": batch["id"],
            "accepted_by": batch["accepted_by"],
            "accepted_at": batch["accepted_at"],
            "route_source": decision["source"],
            "statement": (
                f"Route picked by {decision['source'].replace('_', ' ')}; facts accepted by "
                f"{batch['accepted_by']} in batch {batch['id']} at {batch['accepted_at']}"
            ),
        }
        with self.store.session.begin() as session:
            case, state = workflow.context(session, case_id)
            state.revision += 1
            state.contact = batch["contact"]
            state.decision = decision | {"inputs": decision["inputs"] | {"answers": facts}}
            case.answers = facts
            case.route = route
            case.state = "decided"
            session.add(
                Attestation(
                    case_id=case_id,
                    question="batch_legal_responsibility",
                    value=authorization | {"accepted_warning": True, "warning": batch["warning"]},
                    answered_by=batch["accepted_by"],
                    answered_at=batch["accepted_at"],
                )
            )
            for key, value in facts.items():
                session.add(
                    Attestation(
                        case_id=case_id,
                        question=key,
                        value=authorization | {"answer": value},
                        answered_by=batch["accepted_by"],
                        answered_at=batch["accepted_at"],
                    )
                )
            workflow.event(
                session, case_id, "batch_route_decided", decision=decision, **authorization
            )
            revision = state.revision
        if route in ("leave_alone", "hold_for_review"):
            status = "left_alone" if route == "leave_alone" else "held_for_review"
            with self.store.session.begin() as session:
                session.get(Case, case_id).state = status
            self.update(item_id, status, decision["reason"])
            return
        self.update(item_id, "capturing", "Capturing evidence before drafting")
        await workflow.capture(case_id)
        self.update(item_id, "researching", "Looking up the site recipient")
        if site_cache is not None and "lookup" in site_cache:
            lookup = workflow.reuse_recipients(case_id, site_cache["lookup"])
        else:
            lookup = await workflow.recipients(case_id)
            if (
                site_cache is not None
                and lookup.get("status") == "completed"
                and lookup.get("model_status") != "model_error"
                and any(row["rung"] == "site" for row in lookup["recipients"])
            ):
                site_cache["lookup"] = lookup
        candidates = [row for row in lookup["recipients"] if row["rung"] == "site"]
        if not candidates:
            raise ValueError("Recipient lookup found no site recipient")
        email_candidates = [row for row in candidates if row["channel"] in EMAIL_CHANNELS]
        recipient = min(
            email_candidates if workflow.settings.email_enabled and email_candidates else candidates,
            key=lambda row: row.get("rank", 9999),
        )
        if (
            recipient["channel"] in EMAIL_CHANNELS
            and workflow.settings.email_enabled
            and batch["mode"] == "send"
            and (
                decision["source"] != "agent"
                or decision.get("model_status") != "completed"
                or fetch_error
            )
        ):
            with self.store.session.begin() as session:
                session.get(Case, case_id).state = "held_for_review"
            self.update(
                item_id, "held_for_review",
                "Automatic email needs a completed agent review and page context.",
            )
            return
        if self.leave_whitelisted(item):
            return
        self.update(item_id, "drafting", "Preparing the fixed notice", recipient=recipient)
        await workflow.approve_draft(
            case_id,
            PrepareRequest(
                approved_by=batch["accepted_by"],
                revision=revision,
            ),
            authorization=authorization,
        )
        notice = await workflow.draft(case_id, DraftRequest(recipient_id=recipient["id"]))
        self.update(item_id, "drafting", "Checking delivery eligibility", notice_id=notice["id"])
        try:
            with self.store.session() as session:
                case = session.get(Case, case_id)
                workflow.delivery_eligible(session, case, recipient, batch["contact"])
        except ValueError as error:
            self.update(item_id, "drafted_not_sent", str(error))
            return
        if batch["mode"] == "prepare":
            self.update(item_id, "ready_to_send", "Drafted. Waiting for your review.")
            return
        await self.deliver(batch, item, notice, authorization)

    def leave_whitelisted(self, item):
        with self.store.session.begin() as session:
            case = session.get(Case, item["case_id"])
            if not is_whitelisted(session, case):
                return False
            case.state = "left_alone"
        self.update(item["id"], "left_alone", "Site is on your whitelist.")
        return True

    def start_send(self, batch_id, case_ids=None):
        """Validate the entire selection before making the send phase visible."""
        with self.store.session.begin() as session:
            batch = session.get(Batch, batch_id)
            if batch is None:
                raise LookupError("Batch not found")
            if batch.phase != "awaiting_review":
                raise BatchPhaseError("Batch is not awaiting review")
            items = list(session.scalars(select(BatchItem).where(BatchItem.batch_id == batch_id)))
            ready = {item.case_id for item in items if item.status == "ready_to_send"}
            selected = ready if case_ids is None else set(case_ids)
            if selected - ready:
                raise ValueError(f"Cases {sorted(selected - ready)} are not ready_to_send in this batch")
            if case_ids is not None and len(case_ids) != len(selected):
                raise ValueError("Duplicate case IDs are not allowed")
            for item in items:
                if item.status == "ready_to_send" and item.case_id not in selected:
                    item.status = "drafted_not_sent"
                    item.reason = "Not sent. You left this one out."
            batch.phase = "sending"
            batch.status = "running"
            batch.finished_at = None
        return self.view(batch_id)

    async def send(self, batch_id):
        batch = self.view(batch_id)
        for item in batch["items"]:
            if item["status"] != "ready_to_send":
                continue
            try:
                if self.leave_whitelisted(item):
                    continue
                with self.store.session() as session:
                    notice = session.get(Notice, item["notice_id"])
                    if notice is None or notice.case_id != item["case_id"]:
                        raise ValueError("Prepared notice is missing or belongs to another case")
                    notice = record(notice)
                    attestation = session.scalar(select(Attestation).where(
                        Attestation.case_id == item["case_id"],
                        Attestation.question == "batch_legal_responsibility",
                    ).order_by(Attestation.id.desc()))
                    if attestation is None or attestation.value.get("batch_id") != batch_id:
                        raise ValueError("Batch attestation is missing or superseded")
                    authorization = attestation.value
                await self.deliver(batch, item, notice, authorization)
            except Exception as error:
                self.update(item["id"], "failed", f"{type(error).__name__}: {error}")
        with self.store.session.begin() as session:
            row = session.get(Batch, batch_id)
            row.phase = "done"
            row.status = "completed"
            row.finished_at = self.workflow.now()

    async def deliver(self, batch, item, notice, authorization):
        if self.leave_whitelisted(item):
            return
        workflow = self.workflow
        case_id, item_id = item["case_id"], item["id"]
        with self.store.session() as session:
            case = session.get(Case, case_id)
            workflow.delivery_eligible(session, case, notice["recipient"], notice["payload"]["contact"])
        await workflow.approve_notice(
            case_id,
            ApprovalRequest(
                notice_id=notice["id"],
                sha256=notice["sha256"],
                approved_by=batch["accepted_by"],
            ),
            authorization=authorization,
        )
        self.update(item_id, "sending", "Sending the authorized request")
        delivery = await workflow.send(case_id)
        if delivery["status"] == "uncertain":
            self.update(
                item_id,
                "failed",
                "Delivery uncertain; may have been received. Inspect before retrying.",
                delivery_id=delivery["id"],
            )
        elif delivery["status"] == "failed":
            self.update(
                item_id, "failed",
                "Email provider rejected the request. Check the sending account.",
                delivery_id=delivery["id"],
            )
        else:
            self.update(
                item_id,
                "sent",
                "Email accepted by the sending service; awaiting the site's response."
                if delivery["response"].get("transport") == "resend"
                else "Demo email accepted by Resend. Test delivery is simulated; the website is unchanged."
                if delivery["response"].get("transport") == "resend_demo"
                else f"Sent; recipient response: {delivery['status'].replace('_', ' ')}",
                delivery_id=delivery["id"],
            )


def case_summary(session, case):
    latest = session.scalar(
        select(BatchItem).where(BatchItem.case_id == case.id).order_by(BatchItem.id.desc())
    )
    return record(case) | {
        "whitelisted": is_whitelisted(session, case),
        "matched_image_url": f"/api/cases/{case.id}/image",
        "provider_score": case.score if case.match_type == "facecheck" else None,
        "thumbnail_available": bool(case.evidence.get("image", {}).get("path")),
        "possible_action": possible_action(record(case)),
        "batch_outcome": record(latest) if latest else None,
    }
