"""Import the organizer's 100 rows (data/dataset_patterns_100.json) as `seed_unverified` candidates.

SC-02: XLSX rationale/stage/trend/score go to seed_meta (metadata), pattern annotations to pattern_hints —
neither is a scoring feature. Idempotent: (origin='seed', technology) is unique; re-running updates metadata.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ts.db.models import Candidate

SEED_FILE = Path("data/dataset_patterns_100.json")
META_KEYS = ("dataset_id", "excel_row", "dataset_rationale", "dataset_stage", "dataset_trend", "dataset_score",
             "annotation_status", "source_verification_status", "first_processing_stage",
             "next_verification", "counterevidence_or_ambiguity")
HINT_KEYS = ("primary_pattern", "secondary_patterns", "branches")


def candidate_id(technology: str) -> str:
    return "cand_" + hashlib.sha256(("seed|" + technology.strip().lower()).encode()).hexdigest()[:24]


def rows(path: Path = SEED_FILE) -> list[dict]:
    data = json.loads(path.read_text())
    if not isinstance(data, list) or len(data) != 100:
        raise ValueError(f"expected 100 seed rows, got {len(data) if isinstance(data, list) else type(data)}")
    return data


def to_candidate(row: dict) -> dict:
    return {
        "id": candidate_id(row["technology"]),
        "technology": row["technology"].strip(),
        "domain": row.get("domain"),
        "companies": row.get("companies"),
        "source_urls": row.get("source_urls") or [],
        "status": "seed_unverified",
        "origin": "seed",
        "seed_meta": {k: row.get(k) for k in META_KEYS if k in row},
        "pattern_hints": {k: row.get(k) for k in HINT_KEYS if k in row},
    }


def import_seed(session: Session, path: Path = SEED_FILE) -> dict:
    values = [to_candidate(r) for r in rows(path)]
    stmt = insert(Candidate).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_candidate_origin_technology",
        set_={"domain": stmt.excluded.domain, "companies": stmt.excluded.companies,
              "source_urls": stmt.excluded.source_urls, "seed_meta": stmt.excluded.seed_meta,
              "pattern_hints": stmt.excluded.pattern_hints},
    )
    session.execute(stmt)
    session.commit()
    total = session.query(Candidate).filter_by(origin="seed").count()
    unverified = session.query(Candidate).filter_by(origin="seed", status="seed_unverified").count()
    return {"imported": len(values), "seed_total": total, "seed_unverified": unverified}
