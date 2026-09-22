"""PROCESSING_CONTRACT invariants encoded in pydantic (TS-INV-02, SC-07, TZ-07)."""
from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from ts.schemas import Claim, Document, EvidenceEvent, SourceTrust, SourceType

H = "a" * 64


def doc(**kw):
    d = dict(id="d1", url="https://example.org/x", title="t", language="en",
             source_type=SourceType.paper, trust=SourceTrust.primary, content_hash=H,
             blob_ref="snapshots/" + H, fetched_at=datetime(2026, 9, 22), published_at=date(2026, 9, 1))
    d.update(kw)
    return Document(**d)


def test_document_unknown_date_needs_reason():
    with pytest.raises(ValidationError):
        doc(published_at=None)
    assert doc(published_at=None, published_at_unknown_reason="page has no date").published_at is None


def test_claim_requires_fragment_evidence():
    with pytest.raises(ValidationError):
        Claim(id="c1", subject_id="e1", predicate="raised", kind="source_fact", status="verified", evidence_for=[])
    c = Claim(id="c1", subject_id="e1", predicate="raised", kind="source_fact", status="verified", evidence_for=["f1"])
    assert c.evidence_for == ["f1"]


def test_planned_deployment_is_not_confirmed():
    with pytest.raises(ValidationError):
        EvidenceEvent(id="e1", type="deployment_confirmed", entity_ids=["x"], planned_for=date(2027, 1, 1),
                      origin_group_id="g1", source_fragment_ids=["f1"])
    ok = EvidenceEvent(id="e1", type="roadmap_announced", entity_ids=["x"], planned_for=date(2027, 1, 1),
                       origin_group_id="g1", source_fragment_ids=["f1"])
    assert ok.type == "roadmap_announced"


def test_event_without_any_date_needs_reason():
    with pytest.raises(ValidationError):
        EvidenceEvent(id="e1", type="research_result", entity_ids=["x"], origin_group_id="g1", source_fragment_ids=["f1"])
