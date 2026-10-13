"""Live-path state machine: search → snapshot → dedup → countersearch → score → rank.

One Python process, no second scheduler. Repeating the same query, corpus version
and rules version returns the stored run and does not search again (TS-INV-01).
EPO/CORDIS are not called (fork stub_unavailable).
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Protocol
from urllib.parse import urlsplit

from ts.scoring.policy import route
from ts.scoring.relevance import chain_link
from ts.scoring.scorer import FeatureVector, load_rules, score
from ts.snapshots import save_snapshot
from ts.sources.connectors import Hit, normalise_work_id, script_of
from ts.sources.refetch import extract_text
from ts.sources.trust import classify, load_trust

STEPS = ("search", "snapshot", "dedup", "countersearch", "score", "rank")
TOP_N = 15
RUN_CONTRACT_VERSION = "run-status-0.2"
RETRIEVAL_CONTRACT_VERSION = "retrieval-0.8"
SNAPSHOT_EVIDENCE_VERSION = "snapshot-evidence-0.3"
CHAIN_CONNECTORS = frozenset({"searxng", "openalex", "crossref", "sec"})
_DEEP = frozenset({"arxiv", "openalex", "crossref", "europepmc", "doaj", "hal"})
# Phrase lists such as "market leader" are not in the brief and are not dataset
# patterns. They are not an admission cut. Maturity still comes from a filled
# checklist when texts are read, and from M04 when every source is a retelling.
MATURE_MARKERS: dict = {}
_ACTIVE_SEARCH_DEADLINE: ContextVar[float | None] = ContextVar(
    "thin_signals_search_deadline", default=None,
)


def transport_timeout(max_seconds: float = 40.0) -> float:
    """Cap one HTTP request by the inherited search deadline in this worker."""
    deadline_at = _ACTIVE_SEARCH_DEADLINE.get()
    if deadline_at is None:
        return max_seconds
    return max(0.001, min(max_seconds, deadline_at - monotonic()))


def retrieval_fingerprint(
    connector_names,
    *,
    limit: int,
    since: str | None,
    max_workers: int,
    deadline_seconds: float,
    source_timeout_seconds: float | None = None,
    wide_deadline_seconds: float | None = None,
    parent_fingerprint: str | None = None,
    snapshot_limit: int | None = None,
) -> str:
    """Stable identity for retrieval settings that can change a run result."""
    payload = {
        "version": RETRIEVAL_CONTRACT_VERSION,
        "connectors": list(connector_names),
        "limit": limit,
        "since": since,
        "max_workers": max_workers,
        "deadline_seconds": deadline_seconds,
        "source_timeout_seconds": source_timeout_seconds,
        "wide_deadline_seconds": wide_deadline_seconds,
        "parent_fingerprint": parent_fingerprint,
        "snapshot_limit": snapshot_limit,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


def connector_identity(connector) -> str:
    """Versioned connector settings that can alter retrieval belong in run identity."""
    return str(getattr(connector, "retrieval_identity", connector.name))


def _stage_connectors(connectors, step: str):
    """Some expensive discovery adapters intentionally do not run as falsifiers."""
    selected = []
    for connector in connectors:
        if step not in getattr(connector, "search_stages", {step}):
            continue
        enabled = getattr(connector, "stage_enabled", None)
        if callable(enabled) and not enabled(step):
            continue
        selected.append(connector)
    return selected


def _connector_metadata(connector) -> dict:
    """Allowlist bounded adapter telemetry; never expose reports, prompts or paths."""
    getter = getattr(connector, "public_metadata", None)
    if not callable(getter):
        return {}
    raw = getter()
    if not isinstance(raw, dict):
        return {}
    safe = {}
    research_id = raw.get("research_id")
    if isinstance(research_id, str) and 0 < len(research_id) <= 128:
        safe["research_id"] = research_id
    cost = raw.get("reported_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool) and 0 <= cost < 1000:
        safe["reported_cost_usd"] = float(cost)
    for key in ("advisory_count", "validated_count", "request_count", "request_limit"):
        value = raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10_000:
            safe[key] = value
    artifacts = raw.get("artifact_refs")
    if isinstance(artifacts, list):
        safe["artifact_refs"] = [
            value for value in artifacts[:8]
            if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{16}", value)
        ]
    return safe


def _advisory_provenance(raw: object) -> dict | None:
    if not isinstance(raw, dict) or raw.get("provider") != "gpt-researcher":
        return None
    safe = {"provider": "gpt-researcher"}
    research_id = raw.get("research_id")
    if isinstance(research_id, str) and 0 < len(research_id) <= 128:
        safe["research_id"] = research_id
    cost = raw.get("reported_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool) and 0 <= cost < 1000:
        safe["reported_cost_usd"] = float(cost)
    artifacts = raw.get("artifact_refs")
    if isinstance(artifacts, list):
        safe["artifact_refs"] = [
            value for value in artifacts[:8]
            if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{16}", value)
        ]
    return safe


def _scholarly_evidence(raw: object) -> dict | None:
    """Allowlist typed OpenAlex metadata; raw authorship text never leaves parsing."""
    if not isinstance(raw, dict):
        return None
    if raw.get("version") != "openalex-work-0.1" or raw.get("provider") != "openalex":
        return None
    safe = {"version": "openalex-work-0.1", "provider": "openalex"}
    allowed_roles = {
        "identity", "chronology", "affiliation", "access", "integrity",
        "reference_context",
    }
    roles = raw.get("roles")
    if isinstance(roles, (list, tuple)):
        safe["roles"] = list(dict.fromkeys(
            role for role in roles[:8] if isinstance(role, str) and role in allowed_roles
        ))
    work_id = normalise_work_id(raw.get("work_id"))
    if work_id:
        safe["work_id"] = work_id
    publication_date = raw.get("publication_date")
    if isinstance(publication_date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_date):
        safe["publication_date"] = publication_date
    work_type = raw.get("work_type")
    if isinstance(work_type, str) and re.fullmatch(r"[a-z][a-z-]{0,63}", work_type):
        safe["work_type"] = work_type
    ror_ids = raw.get("ror_ids")
    if isinstance(ror_ids, (list, tuple)):
        safe["ror_ids"] = sorted({
            value for value in ror_ids[:100]
            if isinstance(value, str) and re.fullmatch(r"ror:[0-9a-z]{9}", value)
        })
    access = raw.get("open_access")
    if isinstance(access, dict):
        public_access = {}
        if type(access.get("is_oa")) is bool:
            public_access["is_oa"] = access["is_oa"]
        status = access.get("status")
        if status in {"diamond", "gold", "green", "hybrid", "bronze", "closed"}:
            public_access["status"] = status
        url = access.get("url")
        if isinstance(url, str) and len(url) <= 2048:
            parsed = urlsplit(url)
            if parsed.scheme in {"http", "https"} and parsed.hostname:
                public_access["url"] = url
        if public_access:
            safe["open_access"] = public_access
    integrity = raw.get("integrity")
    if isinstance(integrity, dict):
        is_retracted = integrity.get("is_retracted")
        status = integrity.get("status")
        notice_type = integrity.get("notice_type")
        basis = integrity.get("basis")
        if (
            (type(is_retracted) is bool or is_retracted is None)
            and status in {"known_retracted", "not_flagged", "unknown"}
            and notice_type in {None, "erratum", "retraction"}
            and basis == "openalex_retraction_watch_flag"
        ):
            safe["integrity"] = {
                "is_retracted": is_retracted,
                "status": status,
                "notice_type": notice_type,
                "basis": basis,
            }
    referenced_count = raw.get("referenced_works_count")
    if type(referenced_count) is int and 0 <= referenced_count <= 10_000_000:
        safe["referenced_works_count"] = referenced_count
    return safe


class Searcher(Protocol):
    name: str

    def search(self, query: str, *, limit: int = 5) -> list[Hit]: ...


@dataclass
class RunReport:
    id: str
    query: str
    idempotency_key: str
    repeated: bool
    steps: list[dict]
    sources: list[dict]
    events: list[dict]
    card: dict
    top: list[dict]
    shortfall: int
    exclusion_registry: list[dict]
    status: str = "succeeded"
    run_contract_version: str = RUN_CONTRACT_VERSION
    retrieval_fingerprint: str | None = None
    model_id: str | None = None
    provider: str | None = None
    corpus_version: str = "live-w3"
    fanout: dict | None = None
    unread: list[dict] = field(default_factory=list)
    near_miss: list[dict] = field(default_factory=list)
    potential: list[dict] = field(default_factory=list)


@dataclass
class Harness:
    rules_version: str = "rules-0.1"
    corpus_version: str = "live-w3"
    snapshot_dir: Path = field(default_factory=lambda: Path("snapshots"))
    store: dict = field(default_factory=dict)
    trust_table: dict = field(default_factory=load_trust)
    # YYYY-MM-DD. Narrows candidate searches only; the countersearch for maturity keeps every year.
    since: str | None = None
    max_workers: int = 6
    deadline_seconds: float = 90.0
    snapshot_limit: int = 24

    def run(
        self,
        query: str,
        connectors: list[Searcher],
        *,
        limit: int = 5,
        extractor=None,
        budget_exhausted: bool = False,
        fetch_body=None,
        deadline_at: float | None = None,
    ) -> RunReport:
        connectors = list(connectors)
        rules = load_rules(self.rules_version)
        fingerprint = retrieval_fingerprint(
            [connector_identity(connector) for connector in connectors],
            limit=limit,
            since=self.since,
            max_workers=self.max_workers,
            deadline_seconds=self.deadline_seconds,
            snapshot_limit=self.snapshot_limit,
        )
        key = hashlib.sha256(
            f"{query}|{self.corpus_version}|{rules['version']}|{RUN_CONTRACT_VERSION}|{fingerprint}".encode()
        ).hexdigest()
        if key in self.store:
            return replace(self.store[key], repeated=True)
        steps: list[dict] = []
        deadline_at = (
            deadline_at
            if deadline_at is not None
            else monotonic() + max(0.0, self.deadline_seconds)
        )
        search_sources = _stage_connectors(connectors, "search")
        hits, failures = self._search(
            search_sources, query, limit, steps, deadline_at=deadline_at,
        )
        discovery_successes = len(search_sources) - len(failures)
        chain_sources = [
            item for item in _stage_connectors(connectors, "chain")
            if item.name in CHAIN_CONNECTORS
        ]
        if chain_sources:
            extra, extra_failures = self._search(
                chain_sources, _chain_query(query), limit, steps, step="chain",
                deadline_at=deadline_at,
            )
            discovery_successes += len(chain_sources) - len(extra_failures)
            hits.extend(hit for hit in extra if _on_topic(query, hit))
            failures.extend(extra_failures)
        self._snapshot(hits, fetch_body, steps, deadline_at=deadline_at)
        snapshot_step = steps[-1]
        snapshot_incomplete = (
            snapshot_step.get("name") == "snapshot"
            and (
                bool(snapshot_step.get("failed"))
                or snapshot_step.get("error") == "deadline_exceeded"
            )
        )
        sources = self._sources(hits)
        events = dedup(hits)
        steps.append({"name": "dedup", "status": "ok", "events": len(events),
                      "merged": sum(1 for e in events if e["dedup_status"] == "merged")})
        counter_sources = _stage_connectors(connectors, "countersearch")
        counter_hits, counter_failures = self._search(
            counter_sources, f"{query} mass adoption industry standard", limit, steps, step="countersearch",
            deadline_at=deadline_at,
        )
        countersearch_done = bool(counter_sources) and len(counter_failures) < len(counter_sources)
        run_failures = failures + counter_failures
        if discovery_successes == 0:
            run_status = "failed"
        elif run_failures or snapshot_incomplete:
            run_status = "degraded"
        else:
            run_status = "succeeded"
        counters, counter_evidence = markers(counter_hits)
        if sources and all(s["trust"] == "indicator" for s in sources):
            counters["M04"] = True
            counter_evidence["M04"] = "все найденные источники — индикаторы, первичных нет"
        observed = [e for e in events if e["type"] != "planned_for"]
        origins = len(_explicit_hit_origins(hits))
        if extractor is None and events:
            cards, model_id, provider = self._score_events(
                query, hits, events, counter_hits, rules, budget_exhausted,
                countersearch_done, steps,
            )
        else:
            fv, model_id, provider, scope = self._extract(
                query, hits, observed, origins, counters, counter_evidence, extractor, steps,
            )
            result = score(fv, rules)
            decision = route(_contract(
                fv, result, counters, budget_exhausted,
                countersearch_done=countersearch_done,
            ))
            steps.append({"name": "score", "status": "ok", "label": result.label, "gate": decision["action"]})
            cards = [_card(
                query, result, decision, sources, events, model_id, _blob("", hits),
                subject_hits=_subject_hits(query, query), scope=scope,
                counter_sources=self._sources(counter_hits, purpose="countersearch"),
            )]
        card = cards[0]
        top, excluded = rank(cards, require_subject=bool(_tokens(query)), query=query)
        steps.append({"name": "rank", "status": "ok", "admitted": len(top), "shortfall": TOP_N - len(top),
                      "connector_failures": run_failures, "run_status": run_status,
                      "countersearch_done": countersearch_done})
        report = RunReport(
            id=key[:16], query=query, idempotency_key=key, repeated=False, steps=steps, sources=sources, events=events,
            card=card, top=top, shortfall=TOP_N - len(top), exclusion_registry=excluded,
            status=run_status, model_id=model_id, provider=provider, corpus_version=self.corpus_version,
            retrieval_fingerprint=fingerprint,
        )
        self.store[key] = report
        return report

    def _score_events(
        self, query, hits, events, counter_hits, rules, budget_exhausted,
        countersearch_done, steps,
    ):
        """One card per distinct find. The same gates apply. Nothing is admitted early."""
        by_url: dict[str, list] = {}
        for hit in hits:
            by_url.setdefault(hit.url, []).append(hit)
        cards = []
        for event in events:
            group = [hit for url in event["urls"] for hit in by_url.get(url, [])]
            title = group[0].title if group else query
            event_sources = self._sources(group)
            related_counter_hits = _about_find(group, counter_hits)
            counters, evidence = markers(group + related_counter_hits)
            if event_sources and all(source["trust"] == "indicator" for source in event_sources):
                counters["M04"] = True
                evidence["M04"] = "у этой находки только пересказы, первоисточника нет"
            observed = [] if event["type"] == "planned_for" else [event]
            origins = len(_explicit_hit_origins(group))
            fv = FeatureVector(
                primary_pattern="P04", features={}, counters=counters,
                evidence_events=len(observed), independent_origins=origins,
                transition="unknown", evidence=evidence, mode="ledger", named_primary=False,
            )
            result = score(fv, rules)
            decision = route(_contract(
                fv, result, counters, budget_exhausted,
                countersearch_done=countersearch_done,
            ))
            blob = " ".join([title, *[hit.snippet or "" for hit in group]])
            cards.append(_card(
                title, result, decision, event_sources, [event], None, _blob(title, group),
                subject_hits=max(_subject_hits(query, title), _subject_hits(query, blob)),
                counter_sources=self._sources(related_counter_hits, purpose="countersearch"),
            ))
            steps.append({"name": "score", "status": "ok", "label": result.label, "gate": decision["action"], "find": title})
        return cards, None, None

    def _search(self, connectors, query, limit, steps, step="search", deadline_at=None):
        ordered_connectors = list(connectors)
        hits: list[Hit] = []
        failures: list[str] = []
        stage_started = monotonic()
        deadline_at = deadline_at if deadline_at is not None else monotonic() + max(0.0, self.deadline_seconds)
        remaining = deadline_at - monotonic()
        if remaining <= 0:
            for connector in ordered_connectors:
                failures.append(connector.name)
                steps.append({
                    "name": step, "connector": connector.name, "status": "failed",
                    "error": "deadline_exceeded", "elapsed_ms": 0, "queued_ms": 0,
                })
            return hits, failures

        def invoke(connector):
            started = monotonic()
            queued_ms = round((started - stage_started) * 1000)
            deadline_token = _ACTIVE_SEARCH_DEADLINE.set(deadline_at)
            try:
                if monotonic() >= deadline_at:
                    return [], "deadline_exceeded", round((monotonic() - started) * 1000), queued_ms, {}
                try:
                    depth = 8 if step == "search" and connector.name in _DEEP and limit < 8 else limit
                    dated = self.since and step in {"search", "chain"} and getattr(connector, "takes_since", False)
                    found = connector.search(query, limit=depth, **({"since": self.since} if dated else {}))
                    completed_at = monotonic()
                    if completed_at >= deadline_at:
                        return [], "deadline_exceeded", round((completed_at - started) * 1000), queued_ms, _connector_metadata(connector)
                    return found, None, round((completed_at - started) * 1000), queued_ms, _connector_metadata(connector)
                except Exception as e:  # noqa: BLE001 — one dead source must not stop the run
                    completed_at = monotonic()
                    error = "deadline_exceeded" if completed_at >= deadline_at else type(e).__name__
                    return [], error, round((completed_at - started) * 1000), queued_ms, _connector_metadata(connector)
            finally:
                _ACTIVE_SEARCH_DEADLINE.reset(deadline_token)

        if not ordered_connectors:
            return hits, failures
        executor = ThreadPoolExecutor(max_workers=max(1, min(self.max_workers, len(ordered_connectors))))
        futures = [executor.submit(invoke, connector) for connector in ordered_connectors]
        done, _pending = wait(futures, timeout=max(0.0, deadline_at - monotonic()))
        elapsed_at_deadline = round((monotonic() - stage_started) * 1000)
        for connector, future in zip(ordered_connectors, futures, strict=True):
            if future not in done:
                future.cancel()
                failures.append(connector.name)
                steps.append({
                    "name": step, "connector": connector.name, "status": "failed",
                    "error": "deadline_exceeded", "elapsed_ms": elapsed_at_deadline,
                    "queued_ms": 0,
                })
                continue
            found, error, elapsed_ms, queued_ms, metadata = future.result()
            if error:
                failures.append(connector.name)
                steps.append({
                    "name": step, "connector": connector.name, "status": "failed",
                    "error": error, "elapsed_ms": elapsed_ms, "queued_ms": queued_ms,
                    **metadata,
                })
                continue
            hits.extend(found)
            steps.append({
                "name": step, "connector": connector.name, "status": "ok",
                "n": len(found), "elapsed_ms": elapsed_ms, "queued_ms": queued_ms,
                **metadata,
            })
        executor.shutdown(wait=False, cancel_futures=True)
        return hits, failures

    def _sources(self, hits: list[Hit], purpose: str | None = None) -> list[dict]:
        cards = []
        for hit in hits:
            evidence = dict(hit.evidence or {"status": "snippet_only"})
            fetched_url = str(evidence.get("fetched_url") or "")
            claimed_trust = classify(hit.url, hit.source_type, self.trust_table)
            fetched_trust = (
                classify(
                    fetched_url,
                    str(evidence.get("fetched_source_type") or hit.source_type),
                    self.trust_table,
                )
                if fetched_url else claimed_trust
            )
            trust_rank = {"indicator": 0, "professional": 1, "primary": 2}
            effective_trust = min(
                (claimed_trust, fetched_trust),
                key=lambda value: trust_rank.get(value, 0),
            )
            card = {
                "name": hit.title,
                "url": hit.url,
                "date": hit.published,
                "date_unknown_reason": None if hit.published else "источник не указал дату",
                "type": hit.source_type,
                "language": hit.language,
                "trust": effective_trust,
                "connector": hit.connector,
                "snippet": (hit.snippet or "")[:500],
                **({"doi": hit.doi} if hit.doi else {}),
                **({"origin_ids": list(hit.origin_ids)} if hit.origin_ids else {}),
                **({"work_id": hit.work_id} if hit.work_id else {}),
            }
            card["evidence"] = evidence
            if purpose:
                card["purpose"] = purpose
            advisory = _advisory_provenance(hit.advisory_provenance)
            if advisory:
                card["advisory_provenance"] = advisory
            scholarly = _scholarly_evidence(hit.scholarly_evidence)
            if scholarly:
                card["scholarly_evidence"] = scholarly
            cards.append(card)
        return cards

    def _snapshot(self, hits, fetch_body, steps, *, deadline_at: float) -> None:
        """Preserve embedded bodies and a bounded primary-first set of source URLs."""
        saved = 0
        attempted = 0
        failed = 0
        deadline_exceeded = False
        by_url: dict[str, dict] = {}

        def preserve(hit: Hit, fetched) -> bool:
            nonlocal saved
            body = fetched.fetched_body if isinstance(fetched, Hit) else fetched
            content_type = fetched.fetched_content_type if isinstance(fetched, Hit) else None
            fetched_url = fetched.url if isinstance(fetched, Hit) else hit.url
            fetched_source_type = fetched.source_type if isinstance(fetched, Hit) else hit.source_type
            if isinstance(body, str):
                body = body.encode()
            if not isinstance(body, bytes):
                return False
            content_type = content_type or "application/octet-stream"
            try:
                text, _title = extract_text(body, content_type)
            except Exception:  # noqa: BLE001 - undecodable bodies are not evidence
                return False
            if not text:
                return False
            fragment = text[:1500]
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            snapshot = save_snapshot(
                self.snapshot_dir,
                fetched_url,
                body,
                content_type=content_type,
                text_hash=text_hash,
                source_type=fetched_source_type,
            )
            hit.evidence = {
                "version": SNAPSHOT_EVIDENCE_VERSION,
                "status": "preserved",
                "content_hash": snapshot["content_hash"],
                "snapshot_ref": f"sha256:{snapshot['content_hash']}",
                "attestation_ref": snapshot["attestation_ref"],
                "fetched_url": fetched_url,
                "content_type": content_type,
                "fetched_source_type": fetched_source_type,
                "fragment": fragment,
                "fragment_hash": hashlib.sha256(fragment.encode()).hexdigest(),
                "text_hash": text_hash,
            }
            by_url[hit.url] = dict(hit.evidence)
            saved += 1
            return True

        for hit in hits:
            if hit.evidence:
                by_url.setdefault(hit.url, dict(hit.evidence))
                continue
            if hit.url in by_url:
                hit.evidence = dict(by_url[hit.url])
                continue
            if hit.fetched_body is not None and preserve(hit, hit):
                continue

        candidates = []
        queued_urls = set(by_url)
        for index, hit in enumerate(hits):
            if hit.evidence or hit.url in queued_urls:
                continue
            queued_urls.add(hit.url)
            candidates.append((index, hit))
        trust_rank = {"primary": 0, "professional": 1, "indicator": 2}
        candidates.sort(key=lambda item: (
            trust_rank.get(classify(item[1].url, item[1].source_type, self.trust_table), 3),
            item[0],
        ))
        if fetch_body is not None:
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                for _index, hit in candidates[: max(0, self.snapshot_limit)]:
                    remaining = deadline_at - monotonic()
                    if remaining <= 0:
                        deadline_exceeded = True
                        break
                    attempted += 1

                    def invoke(url=hit.url):
                        token = _ACTIVE_SEARCH_DEADLINE.set(deadline_at)
                        try:
                            return fetch_body(url)
                        finally:
                            _ACTIVE_SEARCH_DEADLINE.reset(token)

                    future = executor.submit(invoke)
                    done, _pending = wait([future], timeout=max(0.0, remaining))
                    if future not in done:
                        future.cancel()
                        failed += 1
                        deadline_exceeded = True
                        break
                    try:
                        fetched = future.result()
                        if monotonic() >= deadline_at:
                            failed += 1
                            deadline_exceeded = True
                            break
                        if not preserve(hit, fetched):
                            failed += 1
                    except Exception:  # noqa: BLE001 - a source body must not abort retrieval
                        failed += 1
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        for hit in hits:
            if not hit.evidence:
                hit.evidence = dict(by_url.get(hit.url) or {"status": "snippet_only"})
        status = "ok" if saved else "skipped"
        steps.append({
            "name": "snapshot",
            "status": status,
            "saved": saved,
            "attempted": attempted,
            "failed": failed,
            "limit": self.snapshot_limit,
            **({"error": "deadline_exceeded"} if deadline_exceeded else {}),
            **({"reason": "no fetcher"} if fetch_body is None and not saved else {}),
        })

    def _extract(self, query, hits, observed, origins, counters, evidence, extractor, steps):
        events_n = len(observed)
        origins = min(origins, events_n)
        if extractor is None:
            fv = FeatureVector(
                primary_pattern="P04", features={}, counters=counters,
                evidence_events=events_n, independent_origins=origins,
                transition="unknown", evidence=evidence, mode="ledger", named_primary=False,
            )
            steps.append({"name": "extract", "status": "skipped", "reason": "no extractor"})
            return fv, None, None, None
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
        return fv, meta.get("model_id"), meta.get("provider"), _scope_or_none(out.get("scope"))


def _title_norm(title: str) -> list[str]:
    text = title.lower().replace("‐", "-").replace("–", "-").replace("—", "-")
    for mark in ("...", "…"):
        if mark in text:
            text = text.split(mark, 1)[0]
    for tail in (" - sciencedirect", " | wiley online library", " - wiley", " - mdpi"):
        if tail in text:
            text = text.split(tail, 1)[0]
    return re.findall(r"[a-z0-9а-яё]+", text)


def _same_title(left: list[str], right: list[str]) -> bool:
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    if len(short) < 6:
        return False
    if long[: len(short)] == short:
        return True
    # The same paper with two file tails still opens with the same long wording.
    shared = 0
    for a, b in zip(left, right):
        if a != b:
            break
        shared += 1
    if shared >= 8:
        return True
    # "Cu 3 P" and "Cu3P" are the same formula split by the page title.
    return "".join(long).startswith("".join(short))


def dedup(hits: list[Hit]) -> list[dict]:
    groups: OrderedDict[str, list[Hit]] = OrderedDict()
    for hit in hits:
        groups.setdefault(_event_key(hit), []).append(hit)
    parent = {key: key for key in groups}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    keys = list(groups)

    def component_aliases(root: str) -> set[str]:
        return {
            alias
            for key, group in groups.items()
            if find(key) == root
            for alias in _hit_identity_aliases(group)
        }

    def join(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            return

        def priority(key: str) -> tuple[int, str]:
            rank = 0 if key.startswith("doi:") else 1 if key.startswith("work:") else 2
            return rank, key

        keep, drop = sorted((root_left, root_right), key=priority)
        parent[drop] = keep

    # Stable DOI/OpenAlex Work aliases are stronger than title similarity.  A
    # DOI view and an OpenAlex-only view of the same Work must merge even when
    # the title is too short for the deliberately conservative title heuristic.
    for i, left in enumerate(keys):
        left_aliases = _hit_identity_aliases(groups[left])
        for right in keys[i + 1 :]:
            if left_aliases & _hit_identity_aliases(groups[right]):
                join(left, right)

    for i, left in enumerate(keys):
        left_titles = [_title_norm(hit.title) for hit in groups[left]]
        for right in keys[i + 1 :]:
            if not any(_same_title(a, b) for a in left_titles for b in (_title_norm(hit.title) for hit in groups[right])):
                continue
            root_left, root_right = find(left), find(right)
            if root_left == root_right:
                continue
            left_aliases = component_aliases(root_left)
            right_aliases = component_aliases(root_right)
            left_work_ids = {alias for alias in left_aliases if alias.startswith("work:")}
            right_work_ids = {alias for alias in right_aliases if alias.startswith("work:")}
            # OpenAlex already clustered locations into a Work. Do not undo two
            # conflicting Work identities merely because titles match. Distinct
            # DOI file records retain the established long-title merge contract.
            if left_work_ids and right_work_ids and left_work_ids.isdisjoint(right_work_ids):
                continue
            right_strong = root_right.startswith(("doi:", "work:"))
            left_strong = root_left.startswith(("doi:", "work:"))
            if right_strong and not left_strong:
                parent[root_left] = root_right
            else:
                parent[root_right] = root_left
    merged: OrderedDict[str, list[Hit]] = OrderedDict()
    for key, group in groups.items():
        merged.setdefault(find(key), []).extend(group)
    events = []
    for key, group in merged.items():
        group.sort(key=lambda hit: (0 if hit.doi else 1, hit.url))
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


def _chain_query(query: str) -> str:
    if re.search(r"[а-яё]", query.lower()):
        return f"{query} цепочка поставок производство новое поколение"
    return f"{query} supply chain production next generation"


def _tokens(text: str) -> list[str]:
    cleaned = text.lower().replace("‐", "-").replace("–", "-")
    return re.findall(r"[a-z0-9а-яё]{4,}", cleaned)


def _holds(word: str, token: str) -> bool:
    return token in word


def _substituted(tokens: list[str], words: list[str]) -> bool:
    """The frame is the same, but one word inside it was replaced by another."""
    if len(tokens) < 3:
        return False
    for index in range(1, len(tokens) - 1):
        left, mid, right = tokens[index - 1], tokens[index], tokens[index + 1]
        if any(_holds(word, mid) for word in words):
            continue
        for pos in range(len(words) - 2):
            gap = words[pos + 1]
            if (
                _holds(words[pos], left)
                and _holds(words[pos + 2], right)
                and not _holds(gap, mid)
                and not any(_holds(gap, token) for token in tokens)
            ):
                return True
    return False


def _subject_hits(query: str, title: str) -> int:
    """Share of the query's own wording, plus pairs that stayed side by side.

    More than half the words means this title is the subject. One different word
    between the same neighbors means a different subject. No stop list and no
    allowlist of special markers.
    """
    tokens = _tokens(query)
    if not tokens:
        return 0
    query_script, title_script = script_of(query), script_of(title)
    if query_script and title_script and query_script != title_script:
        return 1
    cleaned = title.lower().replace("‐", "-").replace("–", "-")
    words = _tokens(title)
    present = [token for token in tokens if token in cleaned]
    if len(present) * 2 <= len(tokens):
        return 0
    if _substituted(tokens, words):
        return 0
    pairs = sum(
        1
        for left, right in pairwise(tokens)
        if any(
            _holds(words[i], left) and _holds(words[i + 1], right)
            for i in range(len(words) - 1)
        )
    )
    return len(present) + pairs


def _on_topic(query: str, hit: Hit) -> bool:
    return _subject_hits(query, f"{hit.title} {hit.snippet}") > 0


def _about_find(group: list[Hit], counter_hits: list[Hit]) -> list[Hit]:
    """A maturity phrase counts only when it is about this find, not about another result."""
    related = []
    for counter in counter_hits:
        counter_doi = (counter.doi or "").lower().removeprefix("https://doi.org/")
        counter_tokens = set(re.findall(
            r"[a-z0-9а-яё]{3,}", f"{counter.title} {counter.snippet}".lower(),
        ))
        for source in group:
            source_doi = (source.doi or "").lower().removeprefix("https://doi.org/")
            if source_doi and source_doi == counter_doi:
                related.append(counter)
                break
            source_tokens = set(re.findall(r"[a-z0-9а-яё]{3,}", source.title.lower()))
            shared = source_tokens & counter_tokens
            if len(source_tokens) >= 2 and len(shared) >= 2 and len(shared) * 2 >= len(source_tokens):
                related.append(counter)
                break
    return related


def markers(hits: list[Hit]) -> tuple[dict, dict]:
    fired = {code: False for code in MATURE_MARKERS}
    evidence = {}
    for hit in hits:
        blob = f"{hit.title} {hit.snippet}"
        for code, pattern in MATURE_MARKERS.items():
            if fired[code]:
                continue
            found = pattern.search(blob)
            if found:
                fired[code] = True
                evidence[code] = f"{found.group(0)} ({hit.url})"
    return fired, evidence


_COUNTERS = frozenset({"M01", "M02", "M03", "M04", "M05", "M06"})


def rank(cards: list[dict], require_subject: bool = False, query: str = "") -> tuple[list[dict], list[dict]]:
    from ts.scoring.order import sort_admitted

    # Word overlap sorts. It does not exclude. require_subject and query stay for callers.
    _ = (require_subject, query)
    admitted, excluded = [], []
    for card in cards:
        codes = set(card.get("reason_codes") or [])
        # An empty pattern sum is not a verdict: the checklist was not filled.
        # Dataset weights stay. A counter from the brief still keeps the card out.
        passed = card["policy_action"] == "RANK_ELIGIBLE" and not (codes & _COUNTERS)
        if passed:
            admitted.append(card)
        else:
            excluded.append(card)
    ordered = sort_admitted(admitted)
    tail = [{**card, "policy_reason": "beyond_top_n"} for card in ordered[TOP_N:]]
    return ordered[:TOP_N], excluded + tail


def _event_key(hit: Hit) -> str:
    if hit.doi:
        return "doi:" + hit.doi.lower().removeprefix("https://doi.org/")
    if hit.work_id:
        return "work:" + hit.work_id.casefold()
    words = re.findall(r"[a-z0-9а-яё]+", hit.title.lower())
    return "title:" + " ".join(words[:8])


def _hit_identity_aliases(hits: list[Hit]) -> set[str]:
    aliases = set()
    for hit in hits:
        if hit.doi:
            aliases.add("doi:" + hit.doi.casefold().removeprefix("https://doi.org/"))
        if hit.work_id:
            aliases.add("work:" + hit.work_id.casefold())
    return aliases


def _host(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def _explicit_hit_origins(hits: list[Hit]) -> set[str]:
    """Explicit upstream institution/lab IDs only; domains never prove independence."""
    return {origin for hit in hits for origin in hit.origin_ids}


def _contract(fv: FeatureVector, result, counters: dict, budget_exhausted: bool, countersearch_done: bool) -> dict:
    mature = any(counters.get(code) for code in ("M01", "M02", "M03", "M06"))
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


def _scope_or_none(raw) -> int | None:
    if raw in (1, 2):
        return int(raw)
    return None


def _blob(title: str, hits: list) -> str:
    parts = [title]
    for hit in hits:
        parts.append(getattr(hit, "title", "") or "")
        parts.append(getattr(hit, "snippet", "") or "")
    return " ".join(parts)


def _card(query, result, decision, sources, events, model_id, text: str = "", subject_hits: int = 0,
          scope: int | None = None, counter_sources: list[dict] | None = None) -> dict:
    return {
        "technology": query,
        "subject_hits": subject_hits,
        "scope": scope if scope in (1, 2) else None,
        "chain_link": chain_link(text),
        "label": result.label,
        "confidence": result.confidence,
        "policy_action": decision["action"],
        "policy_reason": decision["reason"],
        "reason_codes": result.reason_codes,
        "predictors": result.predictors,
        "sources": sources,
        "counter_sources": list(counter_sources or []),
        "events": len(events),
        "planned_not_deployment": [e["key"] for e in events if e["type"] == "planned_for"],
        "model_id": model_id,
        "rules_version": result.rules_version,
    }
