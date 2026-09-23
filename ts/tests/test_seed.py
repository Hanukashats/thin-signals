"""SC-02: seed rows -> candidates without label leakage as features."""
from __future__ import annotations

from pathlib import Path

from ts.seed import HINT_KEYS, META_KEYS, SEED_FILE, candidate_id, rows, to_candidate

ROOT = Path(__file__).resolve().parents[2]


def test_100_rows_unique_ids():
    cands = [to_candidate(r) for r in rows(ROOT / SEED_FILE)]
    assert len(cands) == 100
    assert len({c["id"] for c in cands}) == 100
    assert all(c["status"] == "seed_unverified" and c["origin"] == "seed" for c in cands)


def test_metadata_is_not_a_feature_column():
    c = to_candidate(rows(ROOT / SEED_FILE)[0])
    top = set(c) - {"seed_meta", "pattern_hints"}
    assert not (top & set(META_KEYS)) and not (top & set(HINT_KEYS))
    assert c["seed_meta"]["dataset_score"] == 7 and c["pattern_hints"]["primary_pattern"] == "P02"


def test_candidate_id_is_case_and_space_insensitive():
    assert candidate_id(" Foo Bar ") == candidate_id("foo bar")
