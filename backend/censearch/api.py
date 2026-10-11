"""HTTP API and same-origin console for the full approved-removal workflow."""

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import logging
from urllib.parse import urlsplit
import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from censearch.agent.probe import Probe
from censearch.agent.web import loopback
from censearch.batches import Batches, case_summary
from censearch.config import ROOT, Settings
from censearch.copy_detect import VERSION
from censearch.crawl import Crawler, validate_url
from censearch.db import Case, CrawlRun, Person, Scan, Store, now, record
from censearch.discovery import PublicSearchRequest
from censearch.public_crawl import PublicCrawler, public_view
from censearch.enroll import Enrollment, EnrollmentError
from censearch.evidence import EvidenceStore
from censearch.face import FaceConfig, OpenCVFaceEngine
from censearch.matching import Matcher
from censearch.workflow import Workflow
from censearch.workflow_api import install
from censearch.schemas import (
    CaseResponse,
    CrawlResponse,
    DeletedResponse,
    EnrollmentResponse,
    ErrorResponse,
    HealthResponse,
    PersonResponse,
    ProbeResponse,
    ScanResponse,
)

logger = logging.getLogger(__name__)


class CrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seeds: list[str] = Field(min_length=1, max_length=20)
    rendered: bool = True
    delay: float = Field(default=0.05, ge=0.01, le=60)
    max_pages: int = Field(default=100, ge=1, le=1000)


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hostname: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.:-]+$")


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        store = Store(settings.data_dir)
        app.state.store = store
        app.state.settings = settings
        app.state.busy = False
        app.state.tasks = set()
        app.state.face = None
        app.state.face_error = None
        app.state.calibration_sha256 = None
        app.state.evidence = EvidenceStore(settings)
        app.state.probe = Probe(settings)
        app.state.workflow = Workflow(store, settings, app.state.evidence)
        app.state.batches = Batches(app.state.workflow)
        app.state.batches.recover()
        # Interrupted jobs cannot keep claiming to run after a process restart.
        with store.session.begin() as session:
            for run in session.scalars(select(CrawlRun).where(CrawlRun.status.in_(("queued", "running")))):
                run.status = "interrupted"
                run.finished_at = now()
        try:
            calibration_bytes = settings.calibration_path.read_bytes()
            calibration = json.loads(calibration_bytes)
            face = OpenCVFaceEngine(settings.models_dir, FaceConfig(**calibration["pipeline"]["quality"]))
            if face.signature() != calibration["pipeline"] or calibration["copy"]["version"] != VERSION:
                raise ValueError("Installed model pipeline does not match the supplied calibration")
            if calibration["fusion"] != "max":
                raise ValueError("Unsupported calibration fusion rule")
            app.state.calibration_sha256 = hashlib.sha256(calibration_bytes).hexdigest()
            app.state.face = face
            app.state.enrollment = Enrollment(store, face, app.state.evidence, calibration)
            app.state.matcher = Matcher(
                store, face, app.state.evidence, calibration, app.state.calibration_sha256
            )
        except (OSError, ValueError, KeyError, cv2.error) as error:
            app.state.face_error = str(error)

        async def schedule():
            while True:
                await asyncio.sleep(settings.scheduler_poll)
                if app.state.busy:
                    continue
                async with app.state.workflow.lock:
                    if app.state.busy:
                        continue
                    app.state.busy = True
                    try:
                        await app.state.workflow.tick()
                    except Exception:
                        logger.exception("Scheduler tick failed")
                    finally:
                        app.state.busy = False

        scheduler = asyncio.create_task(schedule())
        try:
            yield
        finally:
            scheduler.cancel()
            await asyncio.gather(scheduler, return_exceptions=True)
            if app.state.tasks:
                await asyncio.gather(*app.state.tasks, return_exceptions=True)
            store.engine.dispose()

    app = FastAPI(
        title="Likeness Guard",
        version="0.1.0",
        lifespan=lifespan,
        responses={code: {"model": ErrorResponse} for code in (404, 409, 413, 422, 503)},
    )

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": {
                        404: "not_found",
                        409: "busy",
                        413: "upload_too_large",
                        422: "validation_error",
                        503: "not_ready",
                    }.get(error.status_code, "request_failed"),
                    "message": error.detail,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = [
            {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request",
                    "details": details,
                }
            },
        )

    def ready():
        if app.state.face is None:
            raise HTTPException(503, "Face models unavailable. Run make setup and inspect /api/health.")

    def idle():
        if app.state.busy:
            raise HTTPException(
                409, "An enrollment, deletion or crawl is in progress; retry after it finishes"
            )

    def get_case(case_id):
        with app.state.store.session() as session:
            row = session.get(Case, case_id)
            if row is None:
                raise HTTPException(404, "Case not found")
            return case_summary(session, row)

    @app.get("/api/health", response_model=HealthResponse)
    def health():
        database = "ok"
        try:
            with app.state.store.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            database = "unavailable"
        return {
            "status": "ok" if database == "ok" and app.state.face else "degraded",
            "database": {"status": database},
            "face_models": {
                "loaded": app.state.face is not None,
                "error": app.state.face_error,
                "calibration_sha256": app.state.calibration_sha256,
            },
            "model": {
                "configured": settings.model_configured,
                "provider": settings.model_provider,
                "model": settings.chat_model,
                "live_call_verified": (
                    app.state.probe.live_call_verified or app.state.workflow.live_call_verified
                ),
            },
            "object_storage": {
                "configured": settings.object_storage_configured,
                "mode": "s3_and_local" if settings.object_storage_configured else "local_disk",
                "remote_verified": app.state.evidence.remote_verified,
            },
            "external_delivery_enabled": settings.allow_external_delivery,
            "public_crawl_enabled": settings.allow_public_crawl,
            "respect_robots": settings.respect_robots,
            "busy": app.state.busy,
            "mock_seeds": [f"http://127.0.0.1:{settings.mock_base_port + index}/" for index in range(4)],
        }

    async def uploads(files):
        result = []
        if len(files) > 20:
            raise HTTPException(422, "At most 20 photos per upload category")
        for upload in files:
            payload = await upload.read(settings.upload_limit_bytes + 1)
            await upload.close()
            if len(payload) > settings.upload_limit_bytes:
                raise HTTPException(413, "A photo exceeds the upload size limit")
            result.append((upload.filename or "upload", payload))
        return result

    @app.post(
        "/api/people", status_code=201, response_model=EnrollmentResponse, response_model_exclude_unset=True
    )
    async def enroll(
        name: str = Form(...),
        consent: str = Form(...),
        ownership: str = Form(""),
        development_fixture: bool = Form(False),
        references: list[UploadFile] = File(...),
        originals: list[UploadFile] = File(default=[]),
    ):
        ready()
        idle()
        app.state.busy = True
        try:
            reference_data = await uploads(references)
            original_data = await uploads(originals)
            result = await asyncio.to_thread(
                app.state.enrollment.enroll,
                name,
                consent,
                reference_data,
                original_data,
                ownership,
                development_fixture,
            )
            return result
        except EnrollmentError as error:
            return JSONResponse(
                status_code=422,
                content={"error": {"code": "photo_rejected", "message": str(error), "photos": error.photos}},
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            app.state.busy = False

    @app.get("/api/people", response_model=list[PersonResponse])
    def people():
        ready()
        return app.state.enrollment.list()

    @app.get("/api/people/{person_id}", response_model=PersonResponse)
    def person(person_id: str):
        ready()
        try:
            return app.state.enrollment.get(person_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @app.delete("/api/people/{person_id}", response_model=DeletedResponse)
    async def delete_person(person_id: str):
        ready()
        idle()
        app.state.busy = True
        try:
            return await asyncio.to_thread(app.state.enrollment.delete, person_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error
        finally:
            app.state.busy = False

    @app.post("/api/crawls", status_code=202, response_model=CrawlResponse)
    async def start_crawl(request: CrawlRequest):
        ready()
        idle()
        try:
            for url in request.seeds:
                validate_url(url, settings.allow_public_crawl)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        config = request.model_dump()
        # Configuration establishes a minimum; clients may ask for a slower crawl.
        config["delay"] = max(config["delay"], settings.crawl_delay)
        with app.state.store.session.begin() as session:
            row = CrawlRun(config=config, identity_version=app.state.store.version(session))
            session.add(row)
            session.flush()
            result = record(row)
        app.state.busy = True

        async def worker():
            try:
                crawler = Crawler(settings, app.state.store, app.state.matcher, row.id, config)
                # CPU-bound OpenCV work and the crawler event loop live off the API loop.
                await asyncio.to_thread(lambda: asyncio.run(crawler.run()))
            finally:
                app.state.busy = False

        task = asyncio.create_task(worker())
        app.state.tasks.add(task)
        task.add_done_callback(app.state.tasks.discard)
        return result

    @app.post("/api/public-searches", status_code=202)
    async def start_public_search(request: PublicSearchRequest) -> dict:
        ready()
        idle()
        with app.state.store.session.begin() as session:
            person = session.get(Person, request.person_id)
            if person is None:
                raise HTTPException(404, "Enrolled person not found")
            real_urls = any(not loopback(urlsplit(url).hostname) for url in request.supplied_urls)
            if person.development_fixture and (request.mode != "supplied_urls" or real_urls):
                raise HTTPException(422, "Local fixtures can only check supplied loopback URLs")
            if (real_urls or request.mode != "supplied_urls") and not request.allow_public_fetch:
                raise HTTPException(422, "Enable public fetching explicitly for this run")
            row = CrawlRun(
                config={"public_search": True, "request": request.model_dump()},
                identity_version=app.state.store.version(session) + ":person:" + person.id,
            )
            session.add(row)
            session.flush()
            run_id, fixture = row.id, person.development_fixture
        app.state.busy = True

        async def worker():
            try:
                crawler = PublicCrawler(
                    settings, app.state.store, app.state.matcher, run_id, request, fixture
                )
                await asyncio.to_thread(lambda: asyncio.run(crawler.run()))
            finally:
                app.state.busy = False

        task = asyncio.create_task(worker())
        app.state.tasks.add(task)
        task.add_done_callback(app.state.tasks.discard)
        return public_view(app.state.store, run_id)

    @app.get("/api/public-searches")
    def public_searches() -> list[dict]:
        with app.state.store.session() as session:
            ids = [
                row.id
                for row in session.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()))
                if row.config.get("public_search")
            ]
        return [public_view(app.state.store, run_id) for run_id in ids]

    @app.get("/api/public-searches/{run_id}")
    def public_search(run_id: int) -> dict:
        try:
            return public_view(app.state.store, run_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/crawls", response_model=list[CrawlResponse])
    def crawls():
        with app.state.store.session() as session:
            return [record(row) for row in session.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()))]

    @app.get("/api/crawls/{run_id}", response_model=CrawlResponse)
    def crawl(run_id: int):
        with app.state.store.session() as session:
            row = session.get(CrawlRun, run_id)
            if row is None:
                raise HTTPException(404, "Crawl not found")
            return record(row)

    @app.get("/api/scans", response_model=list[ScanResponse])
    def scans(run_id: int | None = None):
        statement = select(Scan)
        if run_id is not None:
            statement = statement.where(Scan.run_id == run_id)
        with app.state.store.session() as session:
            return [record(row) for row in session.scalars(statement)]

    @app.get("/api/cases", response_model=list[CaseResponse])
    def cases(person_id: str | None = None, run_id: int | None = None):
        statement = select(Case)
        if person_id:
            statement = statement.where(Case.person_id == person_id)
        if run_id is not None:
            statement = statement.join(Scan).where(Scan.run_id == run_id)
        with app.state.store.session() as session:
            return [
                case_summary(session, row)
                for row in session.scalars(statement.order_by(Case.id))
            ]

    @app.get("/api/cases/{case_id}", response_model=CaseResponse)
    def case(case_id: int):
        return get_case(case_id)

    @app.get(
        "/api/cases/{case_id}/image",
        response_class=FileResponse,
        responses={
            200: {
                "content": {
                    "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                    "image/png": {"schema": {"type": "string", "format": "binary"}},
                }
            }
        },
    )
    def case_image(case_id: int):
        item = get_case(case_id)
        path = settings.data_dir / item["evidence"]["image"]["path"]
        if not path.is_file():
            raise HTTPException(404, "Evidence file is missing")
        with Image.open(path) as image:
            media_type = Image.MIME.get(image.format, "application/octet-stream")
        return FileResponse(
            path,
            media_type=media_type,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.post("/api/agent/probe", response_model=ProbeResponse)
    async def agent_probe(request: ProbeRequest):
        return await app.state.probe.run(request.hostname)

    install(app)

    console = ROOT / "demo-ui/dist"
    if console.exists():
        app.mount("/assets", StaticFiles(directory=console / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        path = console / "index.html"
        if not path.exists():
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "console_not_built",
                        "message": "Build the console with: cd demo-ui && npm ci && npm run build",
                    }
                },
            )
        return FileResponse(path, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
