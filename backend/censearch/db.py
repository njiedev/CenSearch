"""SQLAlchemy persistence. Only enrolled references have embedding columns."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from sqlalchemy import ForeignKey, JSON, LargeBinary, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = "people"
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    consent: Mapped[str]
    development_fixture: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(default=now)


class Reference(Base):
    __tablename__ = "references"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    filename: Mapped[str]
    path: Mapped[str]
    sha256: Mapped[str]
    quality: Mapped[dict] = mapped_column(JSON)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)


class Original(Base):
    __tablename__ = "originals"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    filename: Mapped[str]
    path: Mapped[str]
    sha256: Mapped[str]
    ownership_statement: Mapped[str]


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    config: Mapped[dict] = mapped_column(JSON)
    identity_version: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    started_at: Mapped[str] = mapped_column(default=now)
    finished_at: Mapped[str | None]
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    errors: Mapped[list] = mapped_column(JSON, default=list)


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("crawl_runs.id"))
    page_url: Mapped[str]
    image_url: Mapped[str]
    sha256: Mapped[str | None]
    identity_version: Mapped[str]
    scanned_at: Mapped[str] = mapped_column(default=now)
    status: Mapped[str]
    # No face boxes, pixels, perceptual hashes or embeddings for nonmatches.


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"))
    original_id: Mapped[int | None] = mapped_column(ForeignKey("originals.id", ondelete="CASCADE"))
    page_url: Mapped[str]
    image_url: Mapped[str]
    match_type: Mapped[str]
    band: Mapped[str]
    score: Mapped[float]
    face_band: Mapped[str]
    face_score: Mapped[float | None]
    copy_relation: Mapped[str]
    photo_relation: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(default="needs_review")
    created_at: Mapped[str] = mapped_column(default=now)
    answers: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    route: Mapped[str | None]
    drafted_request: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    recipients: Mapped[list] = mapped_column(JSON, default=list)
    deliveries: Mapped[list] = mapped_column(JSON, default=list)
    verification_checks: Mapped[list] = mapped_column(JSON, default=list)


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.engine = create_engine(
            f"sqlite:///{directory / 'likeness.sqlite'}",
            connect_args={"check_same_thread": False, "timeout": 10},
        )

        @event.listens_for(self.engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA secure_delete=ON")

        from censearch import case_records  # noqa: F401  (register workflow tables)

        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def version(self, session):
        ids = list(session.scalars(select(Person.id).order_by(Person.id)))
        return hashlib.sha256(json.dumps(ids).encode()).hexdigest()


def record(row):
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name != "embedding"
    }
