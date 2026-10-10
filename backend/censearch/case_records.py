"""Append-only facts and events; request-specific approvals and delivery claims."""

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from censearch.db import Base, now


class Attestation(Base):
    __tablename__ = "attestations"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    question: Mapped[str]
    value: Mapped[dict] = mapped_column(JSON)
    answered_by: Mapped[str]
    answered_at: Mapped[str] = mapped_column(default=now)


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    kind: Mapped[str]
    details: Mapped[dict] = mapped_column(JSON)
    at: Mapped[str]


class CaseWorkflow(Base):
    __tablename__ = "case_workflows"
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)
    contact: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[dict] = mapped_column(JSON, default=dict)
    lookup: Mapped[dict] = mapped_column(JSON, default=dict)
    bundle: Mapped[dict] = mapped_column(JSON, default=dict)
    next_rung: Mapped[str] = mapped_column(default="site")


class DraftApproval(Base):
    __tablename__ = "draft_approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    revision: Mapped[int]
    rung: Mapped[str]
    approved_by: Mapped[str]
    at: Mapped[str]


class Notice(Base):
    __tablename__ = "notices"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    revision: Mapped[int]
    rung: Mapped[str]
    recipient: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str]
    created_at: Mapped[str]
    approved_by: Mapped[str | None]
    approved_at: Mapped[str | None]


class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), unique=True)
    rung: Mapped[str]
    status: Mapped[str]
    response: Mapped[dict] = mapped_column(JSON)
    sent_at: Mapped[str]
    deadline: Mapped[str]
    processed: Mapped[bool] = mapped_column(default=False)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(primary_key=True)
    accepted_by: Mapped[str]
    accepted_at: Mapped[str]
    accepted_warning: Mapped[bool]
    warning: Mapped[str]
    contact: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="queued")
    finished_at: Mapped[str | None]


class BatchItem(Base):
    __tablename__ = "batch_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(default="queued")
    reason: Mapped[str] = mapped_column(default="Waiting for review")
    decision: Mapped[dict] = mapped_column(JSON, default=dict)
    recipient: Mapped[dict] = mapped_column(JSON, default=dict)
    notice_id: Mapped[int | None] = mapped_column(ForeignKey("notices.id", ondelete="SET NULL"))
    delivery_id: Mapped[int | None] = mapped_column(ForeignKey("deliveries.id", ondelete="SET NULL"))
