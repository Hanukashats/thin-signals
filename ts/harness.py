"""Live-path state machine: search → snapshot → dedup → countersearch → score → rank.

One Python process, no second scheduler. Repeating the same query, corpus version
and rules version returns the stored run and does not search again (TS-INV-01).
EPO/CORDIS are not called (fork stub_unavailable).
"""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ts.scoring.policy import route
from ts.scoring.scorer import FeatureVector, load_rules, score
from ts.snapshots import save_snapshot
from ts.sources.connectors import Hit
from ts.sources.trust import classify, load_trust

STEPS = ("search", "snapshot", "dedup", "countersearch", "score", "rank")
TOP_N = 15
MATURE_MARKERS = {
    "M01": re.compile(r"market leader|лидер рынка|dominant vendor", re.IGNORECASE),
    "M02": re.compile(r"industry standard|отраслевой стандарт|ISO/IEC", re.IGNORECASE),
    "M03": re.compile(r"widely deployed|массовое внедрение|production deployment", re.IGNORECASE),
}


class Searcher(Protocol):
    name: str

    def search(self, query: str, *, limit: int = 5) -> list[Hit]: ...


@dataclass
class RunReport:
    id: str
    query: str
    repeated: bool
    steps: list[dict]
    sources: list[dict]
    events: list[dict]
    card: dict
    top: list[dict]
    shortfall: int
    exclusion_registry: list[dict]
    model_id: str | None = None
    provider: str | None = None


@dataclass
class Harness:
    rules_version: str = "rules-0.1"
    corpus_version: str = "live-w3"
    snapshot_dir: Path = field(default_factory=lambda: Path("snapshots"))
    store: dict = field(default_factory=dict)
    trust_table: dict = field(default_factory=load_trust)

    def run(
        self,
        query: str,
        connectors: list[Searcher],
        *,
        limit: int = 5,
        extractor=None,
        budget_exhausted: bool = False,
        fetch_body=None,
    ) -> RunReport:
        rules = load_rules(self.rules_version)
        key = hashlib.sha256(f"{query}|{self.corpus_version}|{rules['version']}".encode()).hexdigest()
        if key in self.store:
            return replace(self.store[key], repeated=True)
        steps: list[dict] = []
        hits, failures = self._search(connectors, query, limit, steps)
        sources = self._sources(hits)
        self._snapshot(hits, fetch_body, steps)
        events = dedup(hits)
        steps.append({"name": "dedup", "status": "ok", "events": len(events),
                      "merged": sum(1 for e in events if e["dedup_status"] == "merged")})
        counter_hits, _ = self._search(connectors, f"{query} mass adoption industry standard", limit, steps, step="countersearch")
        counters, counter_evidence = markers(counter_hits)
        if sources and all(s["trust"] == "indicator" for s in sources):
            counters["M04"] = True
            counter_evidence["M04"] = "все найденные источники — индикаторы, первичных нет"
        observed = [e for e in events if e["type"] != "planned_for"]
        origins = len({_host(h.url) for h in hits})
        fv, model_id, provider = self._extract(
            query, hits, observed, origins, counters, counter_evidence, extractor, steps,
        )
        result = score(fv, rules)
        decision = route(_contract(fv, result, counters, budget_exhausted, countersearch_done=True))
        steps.append({"name": "score", "status": "ok", "label": result.label, "gate": decision["action"]})
        card = _card(query, result, decision, sources, events, model_id)
        top, excluded = rank([card])
        steps.append({"name": "rank", "status": "ok", "admitted": len(top), "shortfall": TOP_N - len(top),
                      "connector_failures": failures})
        report = RunReport(
            id=key[:16], query=query, repeated=False, steps=steps, sources=sources, events=events,
            card=card, top=top, shortfall=TOP_N - len(top), exclusion_registry=excluded,
            model_id=model_id, provider=provider,
        )
        self.store[key] = report
        return report

    def _search(self, connectors, query, limit, steps, step="search"):
        hits: list[Hit] = []
        failures = []
        for connector in connectors:
            try:
                found = connector.search(query, limit=limit)
                hits.extend(found)
                steps.append({"name": step, "connector": connector.name, "status": "ok", "n": len(found)})
            except Exception as e:  # noqa: BLE001 — one dead source must not stop the run
                failures.append(connector.name)
                steps.append({"name": step, "connector": connector.name, "status": "failed", "error": type(e).__name__})
        return hits, failures

    def _sources(self, hits: list[Hit]) -> list[dict]:
        cards = []
        for hit in hits:
            cards.append({
                "name": hit.title,
                "url": hit.url,
                "date": hit.published,
                "date_unknown_reason": None if hit.published else "источник не указал дату",
                "type": hit.source_type,
                "language": hit.language,
                "trust": classify(hit.url, hit.source_type, self.trust_table),
                "connector": hit.connector,
            })
        return cards

    def _snapshot(self, hits, fetch_body, steps) -> None:
        saved = 0
        if fetch_body is None:
            steps.append({"name": "snapshot", "status": "skipped", "reason": "no fetcher"})
            return
        for hit in hits:
            try:
                body = fetch_body(hit.url)
            except Exception as e:  # noqa: BLE001
                steps.append({"name": "snapshot", "status": "failed", "url": hit.url, "error": type(e).__name__})
                continue
            if isinstance(body, str):
                body = body.encode()
            save_snapshot(self.snapshot_dir, hit.url, body)
            saved += 1
        steps.append({"name": "snapshot", "status": "ok", "saved": saved})

    def _extract(self, query, hits, observed, origins, counters, evidence, extractor, steps):
        events_n = len(observed)
        origins = min(origins, events_n)
        if extractor is None:
            fv = FeatureVector(
                primary_pattern="P04", features={}, counters=counters,
                evidence_events=events_n, independent_origins=origins,
                transition="unknown", evidence=evidence, mode="ledger",
            )
            steps.append({"name": "extract", "status": "skipped", "reason": "no extractor"})
            return fv, None, None
        fragments = [f"{h.title}. {h.snippet}" for h in hits[:12]]
        out, meta = extractor.extract({"technology": query, "fragments": fragments})
        from ts.extract import to_feature_vector
        fv = to_feature_vector(out, "ledger")
        fv.evidence_events = events_n
        fv.independent_origins = origins
        fv.mode = "ledger"
        for code, fired in counters.items():
            if fired:
                fv.counters[code] = True
                fv.evidence[code] = evidence.get(code, fv.evidence.get(code, ""))
        steps.append({"name": "extract", "status": "ok", "model_id": meta.get("model_id")})
        return fv, meta.get("model_id"), meta.get("provider")


def dedup(hits: list[Hit]) -> list[dict]:
    groups: OrderedDict[str, list[Hit]] = OrderedDict()
    for hit in hits:
        groups.setdefault(_event_key(hit), []).append(hit)
    events = []
    for key, group in groups.items():
        planned = next((h.planned_for for h in group if h.planned_for), None)
        deployed = any(h.deployment and not h.planned_for for h in group)
        events.append({
            "key": key,
            "type": "observed" if deployed or not planned else "planned_for",
            "planned_for": None if deployed else planned,
            "deployment_confirmed": deployed,
            "dedup_status": "merged" if len(group) > 1 else "unique",
            "urls": [h.url for h in group],
            "connectors": sorted({h.connector for h in group}),
        })
    return events


def markers(hits: list[Hit]) -> tuple[dict, dict]:
    blob = "\n".join(f"{h.title} {h.snippet}" for h in hits)
    fired, evidence = {}, {}
    for code, pattern in MATURE_MARKERS.items():
        found = pattern.search(blob)
        fired[code] = bool(found)
        if found:
            evidence[code] = found.group(0)
    return fired, evidence


def rank(cards: list[dict]) -> tuple[list[dict], list[dict]]:
    admitted, excluded = [], []
    for card in cards:
        if card["policy_action"] == "RANK_ELIGIBLE" and card["label"] == "weak_signal":
            admitted.append(card)
        else:
            excluded.append(card)
    return admitted[:TOP_N], excluded


def _event_key(hit: Hit) -> str:
    if hit.doi:
        return "doi:" + hit.doi.lower().removeprefix("https://doi.org/")
    words = re.findall(r"[a-z0-9а-яё]+", hit.title.lower())
    return "title:" + " ".join(words[:8])


def _host(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def _contract(fv: FeatureVector, result, counters: dict, budget_exhausted: bool, countersearch_done: bool) -> dict:
    mature = bool(counters.get("M01") or counters.get("M02") or counters.get("M03") or result.gate == "maturity")
    if fv.evidence_events == 0:
        novelty, maturity, claims = "unclear", "unclear", ["unknown"]
    elif mature:
        novelty, maturity, claims = "known", "established", ["supported"]
    else:
        novelty, maturity = "new", "emerging"
        claims = ["verified"] if fv.transition == "verified" else ["supported"]
    origins = min(fv.independent_origins, fv.evidence_events)
    return {
        "as_of": datetime.now(tz=UTC).date().isoformat(),
        "novelty": novelty,
        "maturity": maturity,
        "critical_claims": claims,
        "fatal_finding": "none",
        "evidence_events": fv.evidence_events,
        "independent_origins": origins,
        "countersearch_done": countersearch_done,
        "source_availability_valid": fv.evidence_events > 0,
        "budget_exhausted": budget_exhausted,
        "branches_complete": countersearch_done,
        "transition_verified": fv.transition == "verified",
    }


def _card(query, result, decision, sources, events, model_id) -> dict:
    return {
        "technology": query,
        "label": result.label,
        "confidence": result.confidence,
        "policy_action": decision["action"],
        "policy_reason": decision["reason"],
        "reason_codes": result.reason_codes,
        "predictors": result.predictors,
        "sources": sources,
        "events": len(events),
        "planned_not_deployment": [e["key"] for e in events if e["type"] == "planned_for"],
        "model_id": model_id,
        "rules_version": result.rules_version,
    }
