"""Typed objects from docs/PROCESSING_CONTRACT.md (schema v1, LivingSet 7.2).

Only contracts; persistence lives in ts/db (W1/W3). Field semantics: see the contract.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


class SourceTrust(str, Enum):
    primary = "primary"            # regulators, registries, patents, papers, vendor official sites
    professional = "professional"  # industry media, analyst reports
    indicator = "indicator"        # social, blogs, aggregators, press releases, ads


class SourceType(str, Enum):
    paper = "paper"
    patent = "patent"
    registry = "registry"
    official_site = "official_site"
    industry_media = "industry_media"
    analyst_report = "analyst_report"
    press_release = "press_release"
    social = "social"
    blog = "blog"
    aggregator = "aggregator"
    repository = "repository"
    other = "other"


class Document(BaseModel):
    id: str
    url: HttpUrl
    title: str
    language: str = Field(min_length=2, max_length=8)
    source_type: SourceType
    trust: SourceTrust
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    blob_ref: str
    fetched_at: datetime
    published_at: Optional[date] = None
    published_at_unknown_reason: Optional[str] = None
    translation_method: Optional[str] = None
    summary_generated: bool = False

    @model_validator(mode="after")
    def _date_or_reason(self) -> "Document":
        if self.published_at is None and not self.published_at_unknown_reason:
            raise ValueError("published_at unknown requires published_at_unknown_reason")
        return self


class Fragment(BaseModel):
    id: str
    document_id: str
    quote: str = Field(min_length=1)
    page: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None
    fragment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class Entity(BaseModel):
    id: str
    type: Literal["technology", "application", "organization", "person", "standard", "program"]
    canonical_name: str
    aliases: list[str] = []
    identifiers: dict[str, str] = {}
    resolution_status: Literal["resolved", "ambiguous", "unresolved"] = "unresolved"


EventType = Literal[
    "research_result", "replication", "patent_publication", "grant_awarded",
    "funding_closed", "funding_discussed", "product_announced", "product_released",
    "pilot_started", "deployment_confirmed", "contract_signed", "roadmap_announced",
    "standard_draft", "standard_adopted", "regulation_published", "regulation_effective",
    "repository_release", "job_opened", "job_closed", "negative_result",
]


class EvidenceEvent(BaseModel):
    id: str
    type: EventType
    entity_ids: list[str]
    event_at: Optional[date] = None
    planned_for: Optional[date] = None
    available_at: Optional[date] = None
    date_unknown_reason: Optional[str] = None
    origin_group_id: str
    source_fragment_ids: list[str] = Field(min_length=1)
    dedup_status: Literal["canonical", "duplicate_of", "pending"] = "pending"
    duplicate_of: Optional[str] = None

    @model_validator(mode="after")
    def _dates(self) -> "EvidenceEvent":
        if self.event_at is None and self.planned_for is None and not self.date_unknown_reason:
            raise ValueError("event without event_at/planned_for requires date_unknown_reason")
        if self.type == "deployment_confirmed" and self.planned_for and self.event_at is None:
            raise ValueError("planned deployment is roadmap_announced, not deployment_confirmed")
        return self


ClaimStatus = Literal["verified", "supported", "unknown", "disputed", "refuted"]


class Claim(BaseModel):
    id: str
    subject_id: str
    predicate: str
    value: Optional[str] = None
    unit: Optional[str] = None
    scope: Optional[str] = None
    kind: Literal["source_fact", "vendor_statement", "analyst_inference", "hypothesis", "forecast"]
    status: ClaimStatus
    critical: bool = False
    evidence_for: list[str] = Field(min_length=1, description="fragment ids — TS-INV-02")
    evidence_against: list[str] = []
    event_id: Optional[str] = None


class Edge(BaseModel):
    id: str
    from_entity_id: str
    to_entity_id: str
    relation: Literal[
        "supports", "contradicts", "subtopic_of", "implements", "funded_by",
        "announces", "pilots", "depends_on", "supplier_of", "potential_supplier_of",
    ]
    claim_ids: list[str] = Field(min_length=1)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None


class Observation(BaseModel):
    predictor_id: Literal["D01", "D02", "D03", "D04", "D05", "D06"]
    cohort_version: str
    period_start: date
    period_end: date
    n: int = Field(ge=0)
    N: int = Field(ge=0)
    coverage: Literal["complete_for_query", "partial", "unknown"]
    complete_period: bool
    protocol: str
    computed_at: datetime
    code_version: str


SignalLabel = Literal["weak_signal", "watchlist", "mature", "noise"]


class Decision(BaseModel):
    id: str
    candidate_id: str
    as_of: date
    rules_version: str
    action: str
    label: Optional[SignalLabel] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reason_codes: list[str]
    predictors: list[dict] = Field(default_factory=list, description="visible components, each with fragment refs")
    unresolved: list[str] = []
    next_action: Optional[str] = None
    review_at: Optional[date] = None


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    retryable = "retryable"
    failed = "failed"
    cancelled = "cancelled"
    succeeded = "succeeded"


class Run(BaseModel):
    """TS-INV-01: idempotency_key = sha256(query|corpus_version|rules_version)."""
    id: str
    query: str
    corpus_version: str
    rules_version: str
    model_id: Optional[str] = None
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: RunStatus = RunStatus.queued
    created_at: datetime
    finished_at: Optional[datetime] = None
