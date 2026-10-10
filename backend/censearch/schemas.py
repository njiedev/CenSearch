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


class CaseResponse(BaseModel):
    id: int
    person_id: str
    scan_id: int
    original_id: int | None
    page_url: str
    image_url: str
    match_type: Literal["face", "copy", "both"]
    band: Literal["match", "possible"]
    score: float = Field(description="Similarity, not a confidence percentage; see evidence.score_basis")
    face_band: Literal["match", "possible", "no_match"]
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
    possible_action: dict[str, Any]
    batch_outcome: dict[str, Any] | None


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
    public_crawl_enabled: bool
    busy: bool
    mock_seeds: list[str]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None
    photos: list[PhotoResult] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
