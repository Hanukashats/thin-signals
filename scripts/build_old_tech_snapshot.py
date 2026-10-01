#!/usr/bin/env python3
"""Build the dated old-technology snapshot from the sealed research package.

Reads ranking.json, candidates.json and sources.json only after their SHA-256 matches MANIFEST.json.
Does not score, search, or edit the package.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs/lineage/novaya-zhizn-staryh-tehnologiy/thin-signals-repro-2026-09-29-v1.0"
OUT = ROOT / "data/old_tech/snapshot_2026-09-29.json"
SOURCES = ("research/ranking.json", "research/candidates.json", "research/sources.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def manifest_hashes() -> dict[str, str]:
    manifest = json.loads((PACKAGE / "MANIFEST.json").read_text(encoding="utf-8"))
    found = {
        row["path"]: row["sha256"]
        for row in manifest.get("files") or []
        if isinstance(row, dict) and row.get("path") in SOURCES
    }
    missing = [name for name in SOURCES if name not in found]
    if missing:
        raise SystemExit(f"manifest has no hash for {missing}")
    return found


def load_checked(name: str, expected: str):
    path = PACKAGE / name
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(f"{name} sha256 {actual} != manifest {expected}")
    return json.loads(path.read_text(encoding="utf-8")), actual


def main() -> None:
    expected = manifest_hashes()
    ranking, ranking_hash = load_checked("research/ranking.json", expected["research/ranking.json"])
    candidates, candidates_hash = load_checked("research/candidates.json", expected["research/candidates.json"])
    sources, sources_hash = load_checked("research/sources.json", expected["research/sources.json"])
    by_id = {row["id"]: row for row in candidates if isinstance(row, dict) and row.get("id")}
    sources_by_id = {row["id"]: row for row in sources if isinstance(row, dict) and row.get("id")}
    info = json.loads((PACKAGE / "PACKAGE_INFO.json").read_text(encoding="utf-8"))
    cards = []
    for row in ranking:
        source = by_id.get(row.get("id"))
        if source is None:
            raise SystemExit(f"candidate missing for {row.get('id')}")
        for field in ("barrier_then", "change_now", "historical_year", "history_class"):
            if source.get(field) in (None, ""):
                raise SystemExit(f"{row.get('id')} has empty {field}")
        cards.append({
            "id": row["id"],
            "name": row["name"],
            "rank": row["rank"],
            "score_lower": row["score_lower"],
            "score_upper": row["score_upper"],
            "decision": row["decision"],
            "fully_qualified": bool(row["fully_qualified"]),
            "holds": list(row.get("holds") or []),
            "missing_dimensions": list(row.get("missing_dimensions") or []),
            "historical_year": source["historical_year"],
            "family": source.get("family") or "",
            "history_class": source["history_class"],
            "history": source.get("history") or "",
            "barrier_then": source["barrier_then"],
            "change_now": source["change_now"],
            "evidence": source.get("evidence") or "",
            "first_product": source.get("first_product") or "",
            "buyers": source.get("buyers") or "",
            "risk": source.get("risk") or "",
            "market_findings": source.get("market_findings") or "",
            "test": source.get("test") or "",
            "source_ids": list(source.get("source_ids") or []),
            "sources": [
                {
                    "id": source_id,
                    "title": sources_by_id[source_id].get("title") or source_id,
                    "url": sources_by_id[source_id].get("url") or "",
                    "published": sources_by_id[source_id].get("published"),
                    "supports": sources_by_id[source_id].get("supports") or "",
                    "limitations": sources_by_id[source_id].get("limitations") or "",
                }
                for source_id in (source.get("source_ids") or [])
                if source_id in sources_by_id
            ],
        })
    qualified = sum(1 for card in cards if card["fully_qualified"])
    if qualified:
        raise SystemExit(f"refusing snapshot: {qualified} cards are fully qualified")
    cards.sort(key=lambda card: card["rank"])
    snapshot = {
        "as_of": info.get("research_cutoff") or "2026-09-29",
        "model_version": info.get("research_model_version") or "",
        "source_package": "docs/lineage/novaya-zhizn-staryh-tehnologiy/thin-signals-repro-2026-09-29-v1.0",
        "source_sha256": {
            "research/ranking.json": ranking_hash,
            "research/candidates.json": candidates_hash,
            "research/sources.json": sources_hash,
        },
        "fully_qualified_count": qualified,
        "cards": cards,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} cards={len(cards)} qualified={qualified}")


if __name__ == "__main__":
    sys.exit(main())
