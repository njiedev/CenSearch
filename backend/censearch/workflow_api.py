"""Typed workflow request contracts; all mutating operations serialize with scheduler ticks."""

import asyncio
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Answers(Strict):
    identity_confirmed: bool | None = None
    owns_photo: bool | None = None
    authorized_use: bool | None = None
    impersonates_me: bool | None = None
    intimate: bool | None = None
    privacy_request: bool | None = None
    legitimate_use: bool | None = None
    identifiable: bool | None = None
    good_faith: bool | None = None
    accurate: bool | None = None
    authority_under_perjury: bool | None = None
    work_description: str | None = Field(default=None, max_length=2000)
    explanation: str | None = Field(default=None, max_length=2000)


class Contact(Strict):
    name: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=300, pattern=r"^[^\r\n]*$")
    address: str = Field(default="", max_length=1000)
    phone: str = Field(default="", max_length=100)
    signature: str = Field(default="", max_length=300)


class AnswerRequest(Strict):
    answered_by: str = Field(min_length=1, max_length=300, pattern=r".*\S.*")
    answers: Answers
    contact: Contact = Field(default_factory=Contact)


class PrepareRequest(Strict):
    approved_by: str = Field(min_length=1, max_length=300, pattern=r".*\S.*")
    revision: int
    rung: Literal["site", "host", "search"] = "site"


class DraftRequest(Strict):
    recipient_id: str
    rung: Literal["site", "host", "search"] = "site"


class ApprovalRequest(Strict):
    notice_id: int
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_by: str = Field(min_length=1, max_length=300, pattern=r".*\S.*")


class ReplyRequest(Strict):
    text: str = Field(min_length=1, max_length=8000)


class AdvanceRequest(Strict):
    seconds: int = Field(gt=0, le=31536000)


class BatchRequest(Strict):
    case_ids: list[int] = Field(min_length=1)
    contact: Contact
    accepted_by: str = Field(min_length=1, max_length=300, pattern=r".*\S.*")
    accepted_warning: bool = False


def install(app):
    router = APIRouter(prefix="/api")

    async def invoke(action, *args):
        workflow = app.state.workflow
        async with workflow.lock:
            if app.state.busy:
                raise HTTPException(409, "Enrollment, deletion or crawl is in progress")
            app.state.busy = True
            try:
                return await getattr(workflow, action)(*args)
            except LookupError as error:
                raise HTTPException(404, str(error)) from error
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            finally:
                app.state.busy = False

    @router.get("/batches/warning")
    async def batch_warning() -> dict:
        from censearch.batches import WARNING
        return {"warning": WARNING}

    @router.post("/batches", status_code=202)
    async def create_batch(request: BatchRequest) -> dict:
        if app.state.busy:
            raise HTTPException(409, "Another operation is in progress")
        async with app.state.workflow.lock:
            try:
                result = app.state.batches.create(request)
            except LookupError as error:
                raise HTTPException(404, str(error)) from error
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            app.state.busy = True

            async def worker():
                try:
                    async with app.state.workflow.lock:
                        await app.state.batches.run(result["id"])
                finally:
                    app.state.busy = False

            task = asyncio.create_task(worker())
            app.state.tasks.add(task)
            task.add_done_callback(app.state.tasks.discard)
            return result

    @router.get("/batches/{batch_id}")
    async def get_batch(batch_id: str) -> dict:
        try:
            return app.state.batches.view(batch_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @router.get("/cases/{case_id}/workflow")
    async def view(case_id: int) -> dict:
        async with app.state.workflow.lock:
            try:
                return app.state.workflow.view(case_id)
            except LookupError as error:
                raise HTTPException(404, str(error)) from error

    @router.post("/cases/{case_id}/answers")
    async def answer(case_id: int, request: AnswerRequest) -> dict:
        return await invoke("answer", case_id, request)

    @router.get("/cases/{case_id}/route")
    async def route(case_id: int) -> dict:
        return (await view(case_id))["decision"]

    @router.post("/cases/{case_id}/description")
    async def description(case_id: int) -> dict:
        return await invoke("description", case_id)

    @router.post("/cases/{case_id}/evidence")
    async def capture(case_id: int) -> dict:
        return await invoke("capture", case_id)

    @router.get("/cases/{case_id}/screenshot")
    async def screenshot(case_id: int):
        bundle = (await view(case_id))["bundle"]
        if not bundle:
            raise HTTPException(404, "Capture evidence first")
        return FileResponse(
            app.state.settings.data_dir / bundle["screenshot"]["path"],
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/cases/{case_id}/recipients")
    async def recipients(case_id: int) -> dict:
        return await invoke("recipients", case_id)

    @router.post("/cases/{case_id}/approve-draft")
    async def prepare(case_id: int, request: PrepareRequest) -> dict:
        return await invoke("approve_draft", case_id, request)

    @router.post("/cases/{case_id}/draft")
    async def draft(case_id: int, request: DraftRequest) -> dict:
        return await invoke("draft", case_id, request)

    @router.get("/cases/{case_id}/draft")
    async def get_draft(case_id: int) -> dict:
        notices = (await view(case_id))["notices"]
        if not notices:
            raise HTTPException(404, "No drafted request")
        return notices[-1]

    @router.post("/cases/{case_id}/approve")
    async def approve(case_id: int, request: ApprovalRequest) -> dict:
        return await invoke("approve_notice", case_id, request)

    @router.post("/cases/{case_id}/send")
    async def send(case_id: int) -> dict:
        return await invoke("send", case_id)

    @router.post("/cases/{case_id}/verify")
    async def verify(case_id: int) -> dict:
        return await invoke("verify", case_id)

    @router.post("/cases/{case_id}/reply-analysis")
    async def reply(case_id: int, request: ReplyRequest) -> dict:
        return await invoke("reply", case_id, request)

    @router.post("/scheduler/tick")
    async def tick() -> list[dict]:
        return await invoke("tick")

    @router.post("/clock/advance")
    async def advance(request: AdvanceRequest) -> dict:
        async with app.state.workflow.lock:
            try:
                value = app.state.workflow.clock.advance(request.seconds)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
        return {"now": value, "ticks": await invoke("tick")}

    app.include_router(router)
