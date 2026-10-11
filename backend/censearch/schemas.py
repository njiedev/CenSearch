"""Public response contracts. Embeddings are intentionally absent."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class PhotoResult(BaseModel):
    kind: Literal["reference", "original"]
    index: int
    filename: str
    accepted: bool
    reason: str | None
    quality: dict[str, Any] | None = None


class ReferenceResponse(BaseModel):
    id: int
    person_id: str
    filename: str
    path: str
    sha256: str
    quality: dict[str, Any]


class OriginalResponse(BaseModel):
    id: int
    person_id: str
    filename: str
    path: str
    sha256: str
    ownership_statement: str


class PersonResponse(BaseModel):
    id: str
    name: str
    consent: str
    development_fixture: bool
    created_at: str
    references: list[ReferenceResponse]
    originals: list[OriginalResponse]
    active_reference_count: int


class EnrollmentResponse(BaseModel):
    person: PersonResponse
    photos: list[PhotoResult]


class DeletedResponse(BaseModel):
    deleted: str


class CrawlResponse(BaseModel):
    id: int
    config: dict[str, Any]
    identity_version: str
    status: Literal[
        "queued",
        "running",
        "completed",
        "completed_with_errors",
        "completed_with_limits",
        "failed",
        "interrupted",
        "cancelled",
    ]
    started_at: str
    finished_at: str | None
    metrics: dict[str, int]
    errors: list[dict[str, Any]]


class ScanResponse(BaseModel):
    id: int
    run_id: int
    page_url: str
    image_url: str
    sha256: str | None
    identity_version: str
    scanned_at: str
    status: Literal["discovered", "matched", "no_match", "cached_no_match", "blocked", "error"]


class BatchItemResponse(BaseModel):
    id: int
    batch_id: str
    case_id: int
    status: Literal[
        "queued", "reviewing", "capturing", "researching", "drafting", "ready_to_send",
        "sending", "sent", "drafted_not_sent", "left_alone", "held_for_review", "failed",
    ]
    reason: str
    decision: dict[str, Any]
    recipient: dict[str, Any]
    notice_id: int | None
    delivery_id: int | None


class CaseResponse(BaseModel):
    id: int
    person_id: str
    scan_id: int
    original_id: int | None
    page_url: str
    image_url: str
    match_type: Literal["face", "copy", "both", "facecheck"]
    band: Literal["match", "possible"]
    score: float = Field(description="Similarity, not a confidence percentage; see evidence.score_basis")
    face_band: Literal["match", "possible", "no_match", "not_checked"]
    face_score: float | None
    copy_relation: Literal["exact", "derived", "uncertain", "none"]
    photo_relation: Literal["same_photo", "different_photo", "uncertain"]
    evidence: dict[str, Any]
    state: str
    created_at: str
    answers: dict[str, Any] | None
    route: str | None
    drafted_request: dict[str, Any] | None
    recipients: list[dict[str, Any]]
    deliveries: list[dict[str, Any]]
    verification_checks: list[dict[str, Any]]
    matched_image_url: str
    provider_score: float | None = None
    thumbnail_available: bool = True
    possible_action: dict[str, Any]
    batch_outcome: BatchItemResponse | None
    whitelisted: bool


class ProbeResponse(BaseModel):
    status: Literal["completed", "model_not_configured", "model_error"]
    answer: str | None
    tool_calls: list[dict[str, Any]]
    message: str | None


class DatabaseHealth(BaseModel):
    status: Literal["ok", "unavailable"]


class FaceHealth(BaseModel):
    loaded: bool
    error: str | None
    calibration_sha256: str | None


class ModelHealth(BaseModel):
    configured: bool
    provider: str
    model: str
    live_call_verified: bool


class StorageHealth(BaseModel):
    configured: bool
    mode: Literal["s3_and_local", "local_disk"]
    remote_verified: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: DatabaseHealth
    face_models: FaceHealth
    model: ModelHealth
    object_storage: StorageHealth
    external_delivery_enabled: bool
    email_delivery: dict[str, Any]
    public_crawl_enabled: bool
    respect_robots: bool
    busy: bool
    mock_seeds: list[str]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None
    photos: list[PhotoResult] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class WhitelistResponse(BaseModel):
    domains: list[str]


class PersonScanResponse(BaseModel):
    run_id: int
    kind: Literal["public_search", "crawl"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    started_at: str | None
    finished_at: str | None
    label: str
    pages_fetched: int
    images_checked: int
    match_count: int
    possible_count: int
    whitelisted_count: int


class BatchResponse(BaseModel):
    id: str
    accepted_by: str
    accepted_at: str
    accepted_warning: bool
    warning: str
    contact: dict[str, Any]
    status: str
    finished_at: str | None
    mode: Literal["send", "prepare"]
    phase: Literal["preparing", "awaiting_review", "sending", "done"]
    total: int
    completed: int
    items: list[BatchItemResponse]
