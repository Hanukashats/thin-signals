"""SQLAlchemy 2 tables for PROCESSING_CONTRACT objects (schema v1) + seed candidates.

Graph (edges), snapshots (blob_ref on disk) and vectors (pgvector on fragments) live here —
replacement matrix PLAN_7.2 §6: no Neo4j / S3 / separate vector DB.
"""
from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1024  # TEI bge-m3


class Base(DeclarativeBase):
    pass


class Candidate(Base):
    """A technology candidate under evaluation. Seed rows come from the organizer XLSX as seed_unverified."""

    __tablename__ = "candidates"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    technology: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    companies: Mapped[str | None] = mapped_column(Text)
    source_urls: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default="seed_unverified", index=True)
    origin: Mapped[str] = mapped_column(String(32), default="seed")  # seed | live
    seed_meta: Mapped[dict | None] = mapped_column(JSONB)  # XLSX rationale/stage/trend/score: metadata, never features
    pattern_hints: Mapped[dict | None] = mapped_column(JSONB)  # primary/secondary patterns from dataset annotation: hints
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("origin", "technology", name="uq_candidate_origin_technology"),)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8))
    source_type: Mapped[str] = mapped_column(String(32))
    trust: Mapped[str] = mapped_column(String(16))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    blob_ref: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[date | None] = mapped_column(Date)
    published_at_unknown_reason: Mapped[str | None] = mapped_column(Text)
    translation_method: Mapped[str | None] = mapped_column(String(32))
    summary_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), index=True)


class Fragment(Base):
    __tablename__ = "fragments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    quote: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    start: Mapped[int | None] = mapped_column(Integer)
    end: Mapped[int | None] = mapped_column(Integer)
    fragment_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    canonical_name: Mapped[str] = mapped_column(Text, index=True)
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    identifiers: Mapped[dict] = mapped_column(JSONB, default=dict)
    resolution_status: Mapped[str] = mapped_column(String(16), default="unresolved")


class EvidenceEvent(Base):
    __tablename__ = "evidence_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    entity_ids: Mapped[list] = mapped_column(JSONB, default=list)
    event_at: Mapped[date | None] = mapped_column(Date)
    planned_for: Mapped[date | None] = mapped_column(Date)
    available_at: Mapped[date | None] = mapped_column(Date)
    date_unknown_reason: Mapped[str | None] = mapped_column(Text)
    origin_group_id: Mapped[str] = mapped_column(String(64), index=True)
    source_fragment_ids: Mapped[list] = mapped_column(JSONB)
    dedup_status: Mapped[str] = mapped_column(String(16), default="pending")
    duplicate_of: Mapped[str | None] = mapped_column(String(64))
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), index=True)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    predicate: Mapped[str] = mapped_column(Text)
    value: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(32))
    scope: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_for: Mapped[list] = mapped_column(JSONB)  # TS-INV-02: never empty (validated in pydantic)
    evidence_against: Mapped[list] = mapped_column(JSONB, default=list)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_events.id"))


class Edge(Base):
    __tablename__ = "edges"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    to_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    relation: Mapped[str] = mapped_column(String(32))
    claim_ids: Mapped[list] = mapped_column(JSONB)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    predictor_id: Mapped[str] = mapped_column(String(8))
    cohort_version: Mapped[str] = mapped_column(String(32))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    n: Mapped[int] = mapped_column(Integer)
    N: Mapped[int] = mapped_column("n_total", Integer)
    coverage: Mapped[str] = mapped_column(String(32))
    complete_period: Mapped[bool] = mapped_column(Boolean)
    protocol: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    code_version: Mapped[str] = mapped_column(String(64))


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    as_of: Mapped[date] = mapped_column(Date)
    rules_version: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))
    label: Mapped[str | None] = mapped_column(String(16), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    reason_codes: Mapped[list] = mapped_column(JSONB, default=list)
    predictors: Mapped[list] = mapped_column(JSONB, default=list)
    unresolved: Mapped[list] = mapped_column(JSONB, default=list)
    next_action: Mapped[str | None] = mapped_column(Text)
    review_at: Mapped[date | None] = mapped_column(Date)


class Run(Base):
    """TS-INV-01: idempotency_key = sha256(query|corpus_version|rules_version); repeats return the same run."""

    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    corpus_version: Mapped[str] = mapped_column(String(64))
    rules_version: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[str | None] = mapped_column(String(128))
    provider: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    """One shared view of immutable runs and a sealed archive; not another run ledger."""

    __tablename__ = "workspace"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    archive: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("id = 1", name="workspace_singleton"),)
